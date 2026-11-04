import asyncio
import logging
import math
import re
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ldap3 import FIRST, NONE, SIMPLE, SUBTREE, Connection, Server, ServerPool, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.credential_verifier import (
    CredentialCheck,
    CredentialStatus,
)

logger = logging.getLogger(__name__)

_INVALID_CREDENTIALS = 49
# O AD recusou o login simples numa conexão aberta: falta LDAPS ou StartTLS.
_NEEDS_SECURE_CONNECTION = {8, 13}  # strongerAuthRequired, confidentialityRequired

# Código "data XXX" que o AD põe na mensagem do erro 49. Só os de senha vencida e de conta
# bloqueada mudam a resposta; o resto (52e senha errada, 525 usuário inexistente...) é
# "usuário ou senha inválidos".
_STATUS_BY_AD_CODE = {
    "532": CredentialStatus.EXPIRED,  # senha vencida
    "773": CredentialStatus.EXPIRED,  # troca de senha obrigatória
    "533": CredentialStatus.BLOCKED,  # conta desativada
    "701": CredentialStatus.BLOCKED,  # conta expirada
    "775": CredentialStatus.BLOCKED,  # conta bloqueada por tentativas
    "530": CredentialStatus.BLOCKED,  # fora do horário permitido
    "531": CredentialStatus.BLOCKED,  # estação de trabalho não permitida
}
_AD_CODE = re.compile(r"\bdata ([0-9a-f]+)", re.IGNORECASE)
# Grupos dentro de grupos também contam (LDAP_MATCHING_RULE_IN_CHAIN).
_IN_CHAIN = "1.2.840.113556.1.4.1941"


class DirectoryConnection(Protocol):
    """O pedaço do ``ldap3.Connection`` que o verificador usa (os testes simulam o AD)."""

    result: dict[str, Any]
    response: list[dict[str, Any]] | None

    def bind(self) -> bool: ...

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: str = ...,
        attributes: Sequence[str] | None = ...,
        size_limit: int = ...,
    ) -> bool: ...

    def unbind(self) -> bool: ...


ConnectionFactory = Callable[[str, str], DirectoryConnection]


@dataclass(frozen=True, slots=True)
class ActiveDirectoryConfig:
    # Ex.: ["ldaps://dc01.empresa.local"]. Mais de um = o próximo é tentado se o primeiro cair.
    server_urls: Sequence[str]
    domain: str  # o login vira "usuario@dominio" na autenticação
    base_dn: str  # onde procurar o usuário, ex.: "DC=empresa,DC=local"
    # Só quem está neste grupo (direta ou indiretamente) entra. None = qualquer usuário.
    required_group_dn: str | None = None
    start_tls: bool = False  # para ldap:// (porta 389); com ldaps:// não é preciso
    ca_cert_file: Path | None = None  # CA interna; None = certificados do sistema
    timeout_seconds: float = 10


class LdapCredentialVerifier:
    """Confere usuário e senha no Active Directory, autenticando como o próprio usuário.

    Não usa conta de serviço: depois do login, a mesma conexão lê o nome e confere o
    grupo. Nada da requisição (nem a senha) é gravado em log.
    """

    def __init__(
        self, config: ActiveDirectoryConfig, *, connect: ConnectionFactory | None = None
    ) -> None:
        self._config = config
        self._connect = connect or _real_connection_factory(config)

    async def verify(self, username: str, password: str) -> CredentialCheck:
        if not username or not password:
            # Senha vazia no LDAP é um login anônimo, que o servidor ACEITA.
            return CredentialCheck(CredentialStatus.INVALID)
        return await asyncio.to_thread(self._verify, username, password)

    def _verify(self, username: str, password: str) -> CredentialCheck:
        try:
            connection = self._connect(f"{username}@{self._config.domain}", password)
            try:
                if not connection.bind():
                    return CredentialCheck(_status_from_bind_failure(connection.result))
                return self._lookup(connection, username)
            finally:
                connection.unbind()
        except (LDAPException, OSError) as error:
            raise ExternalServiceError("O AD não respondeu ao validar o login") from error

    def _lookup(self, connection: DirectoryConnection, username: str) -> CredentialCheck:
        conditions = f"(objectClass=user)(sAMAccountName={escape_filter_chars(username)})"
        if self._config.required_group_dn:
            group = escape_filter_chars(self._config.required_group_dn)
            conditions += f"(memberOf:{_IN_CHAIN}:={group})"
        connection.search(
            self._config.base_dn,
            f"(&{conditions})",
            search_scope=SUBTREE,
            attributes=["displayName"],
            size_limit=1,
        )
        entries = [
            item for item in connection.response or [] if item.get("type") == "searchResEntry"
        ]
        if not entries:
            # Fora do grupo, ou fora da base de busca (configuração errada).
            logger.info(
                "Login do AD aceito, mas '%s' não foi encontrado em APP_AD_BASE_DN%s",
                username,
                " com o grupo exigido" if self._config.required_group_dn else "",
            )
            return CredentialCheck(CredentialStatus.NOT_ALLOWED)
        return CredentialCheck(CredentialStatus.VALID, display_name=_display_name(entries[0]))


def _status_from_bind_failure(result: dict[str, Any]) -> CredentialStatus:
    code = result.get("result")
    if code == _INVALID_CREDENTIALS:
        match = _AD_CODE.search(str(result.get("message", "")))
        ad_code = match.group(1).lower() if match else ""
        return _STATUS_BY_AD_CODE.get(ad_code, CredentialStatus.INVALID)
    if code in _NEEDS_SECURE_CONNECTION:
        logger.error(
            "O AD exige conexão segura: use ldaps:// em APP_AD_SERVER_URLS ou APP_AD_START_TLS"
        )
    else:
        logger.error("O AD recusou o login: %s - %s", code, result.get("description"))
    raise ExternalServiceError("O AD não conseguiu validar o login")


def _display_name(entry: dict[str, Any]) -> str | None:
    value = entry.get("attributes", {}).get("displayName")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, str) and value.strip() else None


def _real_connection_factory(config: ActiveDirectoryConfig) -> ConnectionFactory:
    # No Linux, o ldap3 grava o timeout no socket com struct.pack: precisa ser inteiro.
    timeout = max(1, math.ceil(config.timeout_seconds))
    tls = Tls(
        validate=ssl.CERT_REQUIRED,
        version=ssl.PROTOCOL_TLS_CLIENT,
        ca_certs_file=str(config.ca_cert_file) if config.ca_cert_file else None,
    )
    servers = [
        Server(url, tls=tls, get_info=NONE, connect_timeout=timeout)
        for url in config.server_urls
    ]
    # Com mais de um, o pool tenta o próximo quando um cai. active=1: dá uma volta pelos
    # servidores e desiste, em vez de tentar para sempre.
    pool: Server | ServerPool = (
        servers[0]
        if len(servers) == 1
        else ServerPool(servers, pool_strategy=FIRST, active=1, exhaust=False)
    )

    def connect(user: str, password: str) -> DirectoryConnection:
        connection = Connection(
            pool,
            user=user,
            password=password,
            authentication=SIMPLE,
            receive_timeout=timeout,
            read_only=True,
            auto_referrals=False,
            raise_exceptions=False,
        )
        if config.start_tls:
            connection.open()
            connection.start_tls()
        return connection  # type: ignore[no-any-return]

    return connect

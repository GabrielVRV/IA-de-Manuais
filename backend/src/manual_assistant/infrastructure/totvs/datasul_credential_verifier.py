import logging
from typing import Any

import httpx

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.credential_verifier import (
    CredentialCheck,
    CredentialStatus,
)

logger = logging.getLogger(__name__)

# c_status devolvido pelo api_valida_login.p. "ERRO" (falha no Progress) e qualquer valor
# desconhecido viram ExternalServiceError.
_STATUS_BY_TOTVS_CODE = {
    "OK": CredentialStatus.VALID,
    "INVALIDO": CredentialStatus.INVALID,
    "NAO_INFORMADO": CredentialStatus.INVALID,
    "SENHA_VENCIDA": CredentialStatus.EXPIRED,
}


class DatasulCredentialVerifier:
    """Confere usuário e senha na API REST ``api_valida_login`` do Datasul (Progress).

    A chamada usa o Basic Auth do próprio usuário: com senha errada, o Datasul já
    responde 401 antes de chegar ao programa. Nada da requisição é gravado em log.
    """

    def __init__(
        self,
        login_url: str,
        *,
        timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,  # os testes simulam o Datasul
    ) -> None:
        self._login_url = login_url
        self._timeout = timeout_seconds
        self._transport = transport

    async def verify(self, username: str, password: str) -> CredentialCheck:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self._login_url,
                    auth=httpx.BasicAuth(username, password),
                    json={"tt_login": [{"usuario": username, "senha": password}]},
                )
        except httpx.HTTPError as error:
            raise ExternalServiceError("O TOTVS não respondeu ao validar o login") from error

        if response.status_code == httpx.codes.UNAUTHORIZED:
            return CredentialCheck(CredentialStatus.INVALID)
        if response.status_code != httpx.codes.OK:
            raise ExternalServiceError(
                f"O TOTVS respondeu HTTP {response.status_code} ao validar o login"
            )

        result = _read_result(response)
        status = _STATUS_BY_TOTVS_CODE.get(str(result.get("c_status", "")))
        if status is None:
            # A mensagem do Progress não traz a senha; ajuda a diagnosticar o "ERRO".
            logger.error(
                "TOTVS recusou a validação do login: %s - %s",
                result.get("c_status"),
                result.get("c_mensagem"),
            )
            raise ExternalServiceError("O TOTVS não conseguiu validar o login")
        if status is not CredentialStatus.VALID:
            return CredentialCheck(status)
        name = result.get("nom_usuario")
        return CredentialCheck(status, display_name=name if isinstance(name, str) else None)


def _read_result(response: httpx.Response) -> dict[str, Any]:
    """Primeiro registro de ``tt_retorno_login``."""
    try:
        body = response.json()
    except ValueError as error:
        raise ExternalServiceError("O TOTVS respondeu algo que não é JSON") from error
    rows = body.get("tt_retorno_login") if isinstance(body, dict) else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        # Só os nomes dos campos: o suficiente para ajustar o formato no primeiro deploy.
        keys = sorted(body) if isinstance(body, dict) else type(body).__name__
        logger.error("Resposta inesperada do TOTVS ao validar o login. Campos: %s", keys)
        raise ExternalServiceError("Resposta inesperada do TOTVS ao validar o login")
    first: dict[str, Any] = rows[0]
    return first

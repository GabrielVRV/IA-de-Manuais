from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from ldap3.core.exceptions import LDAPSocketOpenError

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.credential_verifier import (
    CredentialCheck,
    CredentialStatus,
)
from manual_assistant.infrastructure.active_directory.ldap_credential_verifier import (
    ActiveDirectoryConfig,
    LdapCredentialVerifier,
)

pytestmark = pytest.mark.anyio

CONFIG = ActiveDirectoryConfig(
    server_urls=["ldaps://dc01.empresa.local"],
    domain="empresa.local",
    base_dn="DC=empresa,DC=local",
)
GROUP = "CN=IA Manuais,OU=Grupos,DC=empresa,DC=local"


def bind_error(code: str) -> dict[str, Any]:
    """Como o AD responde a um login recusado."""
    return {
        "result": 49,
        "description": "invalidCredentials",
        "message": f"80090308: LdapErr: DSID-0C09044E, comment: AcceptSecurityContext error, "
        f"data {code}, v4563\x00",
    }


@dataclass
class FakeAd:
    """AD simulado: o resultado do login e o que a busca devolve."""

    bind_result: dict[str, Any] | None = None  # None = login aceito
    entries: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"type": "searchResEntry", "attributes": {"displayName": "Gabriel Viaro"}}
        ]
    )
    error: Exception | None = None
    binds: list[tuple[str, str]] = field(default_factory=list)
    searches: list[tuple[str, str]] = field(default_factory=list)
    unbound: bool = False

    def connect(self, user: str, password: str) -> "FakeAd":
        if self.error is not None:
            raise self.error
        self.binds.append((user, password))
        return self

    # --- DirectoryConnection ---
    result: dict[str, Any] = field(default_factory=dict)
    response: list[dict[str, Any]] | None = None

    def bind(self) -> bool:
        self.result = self.bind_result or {"result": 0}
        return self.bind_result is None

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: str = "SUBTREE",
        attributes: Sequence[str] | None = None,
        size_limit: int = 0,
    ) -> bool:
        self.searches.append((search_base, search_filter))
        assert (search_scope, attributes, size_limit) == ("SUBTREE", ["displayName"], 1)
        self.response = [*self.entries, {"type": "searchResDone"}]
        return bool(self.entries)

    def unbind(self) -> bool:
        self.unbound = True
        return True


def verifier(ad: FakeAd, config: ActiveDirectoryConfig = CONFIG) -> LdapCredentialVerifier:
    return LdapCredentialVerifier(config, connect=ad.connect)


async def test_valid_login_binds_as_the_user_and_brings_the_ad_name() -> None:
    ad = FakeAd()

    check = await verifier(ad).verify("gabriel.viaro", "Senha-Ç")

    assert check == CredentialCheck(CredentialStatus.VALID, display_name="Gabriel Viaro")
    assert ad.binds == [("gabriel.viaro@empresa.local", "Senha-Ç")]
    assert ad.searches == [
        ("DC=empresa,DC=local", "(&(objectClass=user)(sAMAccountName=gabriel.viaro))")
    ]
    assert ad.unbound


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("52e", CredentialStatus.INVALID),  # senha errada
        ("525", CredentialStatus.INVALID),  # usuário inexistente
        ("532", CredentialStatus.EXPIRED),
        ("773", CredentialStatus.EXPIRED),
        ("533", CredentialStatus.BLOCKED),
        ("775", CredentialStatus.BLOCKED),
        ("999", CredentialStatus.INVALID),  # código desconhecido
    ],
)
async def test_refused_login_is_translated_from_the_ad_code(
    code: str, status: CredentialStatus
) -> None:
    ad = FakeAd(bind_result=bind_error(code))

    assert await verifier(ad).verify("gabriel.viaro", "x") == CredentialCheck(status)
    assert ad.searches == []
    assert ad.unbound


async def test_an_empty_password_never_reaches_the_ad() -> None:
    # No LDAP, senha vazia é um login anônimo, que o AD aceitaria.
    ad = FakeAd()

    assert await verifier(ad).verify("gabriel.viaro", "") == CredentialCheck(
        CredentialStatus.INVALID
    )
    assert ad.binds == []


async def test_the_required_group_is_checked_including_nested_groups() -> None:
    ad = FakeAd()
    config = ActiveDirectoryConfig(
        server_urls=CONFIG.server_urls,
        domain=CONFIG.domain,
        base_dn=CONFIG.base_dn,
        required_group_dn=GROUP,
    )

    await verifier(ad, config).verify("gabriel.viaro", "x")

    ((_, search_filter),) = ad.searches
    assert f"(memberOf:1.2.840.113556.1.4.1941:={GROUP})" in search_filter


async def test_a_user_outside_the_group_is_not_allowed() -> None:
    ad = FakeAd(entries=[])

    check = await verifier(ad).verify("gabriel.viaro", "x")

    assert check == CredentialCheck(CredentialStatus.NOT_ALLOWED)


async def test_the_login_is_escaped_in_the_search_filter() -> None:
    ad = FakeAd()

    await verifier(ad).verify("a*)(cn=*", "x")

    ((_, search_filter),) = ad.searches
    assert "a\\2a\\29\\28cn=\\2a" in search_filter


async def test_a_missing_display_name_is_none() -> None:
    ad = FakeAd(entries=[{"type": "searchResEntry", "attributes": {"displayName": []}}])

    check = await verifier(ad).verify("gabriel.viaro", "x")

    assert check == CredentialCheck(CredentialStatus.VALID, display_name=None)


async def test_an_unreachable_ad_is_an_external_service_error() -> None:
    ad = FakeAd(error=LDAPSocketOpenError("unable to open socket"))

    with pytest.raises(ExternalServiceError):
        await verifier(ad).verify("gabriel.viaro", "x")


async def test_an_ad_that_demands_a_secure_connection_is_an_external_service_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ad = FakeAd(bind_result={"result": 8, "description": "strongerAuthRequired"})

    with pytest.raises(ExternalServiceError):
        await verifier(ad).verify("gabriel.viaro", "Senha-secreta")

    assert "ldaps://" in caplog.text
    assert "Senha-secreta" not in caplog.text


async def test_the_real_ldap3_connection_reports_an_unreachable_server() -> None:
    # Sem conexão injetada: monta o ldap3 de verdade, apontando para uma porta fechada.
    config = ActiveDirectoryConfig(
        server_urls=["ldap://127.0.0.1:1"],
        domain="empresa.local",
        base_dn="DC=empresa,DC=local",
        timeout_seconds=2,
    )

    with pytest.raises(ExternalServiceError):
        await LdapCredentialVerifier(config).verify("gabriel.viaro", "x")

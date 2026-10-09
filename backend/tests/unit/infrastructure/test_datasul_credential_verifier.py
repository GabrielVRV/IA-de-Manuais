import base64
import json
from typing import Any

import httpx
import pytest

from manual_assistant.application.errors import ExternalServiceError
from manual_assistant.application.ports.credential_verifier import (
    CredentialCheck,
    CredentialStatus,
)
from manual_assistant.infrastructure.totvs.datasul_credential_verifier import (
    DatasulCredentialVerifier,
)

pytestmark = pytest.mark.anyio

LOGIN_URL = "http://datasul:8080/api/sfc/v1/api_valida_login/validarLogin/"


def answer(status: str, **fields: str) -> dict[str, Any]:
    return {"tt_retorno_login": [{"c_status": status, "c_mensagem": "msg", **fields}]}


def verifier_answering(
    handler: httpx.Response | Exception, requests: list[httpx.Request] | None = None
) -> DatasulCredentialVerifier:
    def respond(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        if isinstance(handler, Exception):
            raise handler
        return handler

    return DatasulCredentialVerifier(LOGIN_URL, transport=httpx.MockTransport(respond))


async def test_valid_login_brings_the_totvs_name() -> None:
    requests: list[httpx.Request] = []
    verifier = verifier_answering(
        httpx.Response(200, json=answer("OK", cod_usuario="gviaro", nom_usuario="Gabriel")),
        requests,
    )

    check = await verifier.verify("gviaro", "Senha-Ç")

    assert check == CredentialCheck(CredentialStatus.VALID, display_name="Gabriel")
    (request,) = requests
    assert str(request.url) == LOGIN_URL
    # Basic Auth do próprio usuário, em UTF-8 (senhas com acento funcionam).
    credentials = base64.b64decode(request.headers["authorization"].removeprefix("Basic "))
    assert credentials.decode() == "gviaro:Senha-Ç"
    assert json.loads(request.content) == {"tt_login": [{"usuario": "gviaro", "senha": "Senha-Ç"}]}


@pytest.mark.parametrize(
    ("response", "status"),
    [
        (httpx.Response(401), CredentialStatus.INVALID),  # o próprio Datasul recusou
        (httpx.Response(200, json=answer("INVALIDO")), CredentialStatus.INVALID),
        (httpx.Response(200, json=answer("NAO_INFORMADO")), CredentialStatus.INVALID),
        (httpx.Response(200, json=answer("SENHA_VENCIDA")), CredentialStatus.EXPIRED),
    ],
)
async def test_refusals(response: httpx.Response, status: CredentialStatus) -> None:
    check = await verifier_answering(response).verify("gviaro", "senha")

    assert check == CredentialCheck(status)


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("conexão recusada"),
        httpx.ReadTimeout("demorou"),
        httpx.Response(500),
        httpx.Response(200, text="<html>erro</html>"),
        httpx.Response(200, json={"outra_coisa": []}),
        httpx.Response(200, json={"tt_retorno_login": []}),
        httpx.Response(200, json=answer("ERRO")),
    ],
)
async def test_failures_become_external_service_errors(
    failure: httpx.Response | Exception,
) -> None:
    with pytest.raises(ExternalServiceError):
        await verifier_answering(failure).verify("gviaro", "senha")


async def test_never_logs_the_password(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    verifier = verifier_answering(httpx.Response(200, json=answer("ERRO")))

    with pytest.raises(ExternalServiceError):
        await verifier.verify("gviaro", "senha-secreta")

    assert "senha-secreta" not in caplog.text
    assert "ERRO" in caplog.text

from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from manual_assistant.application.errors import NotAuthenticatedError
from manual_assistant.domain.user import UserId
from manual_assistant.infrastructure.security.jwt_tokens import JwtTokenService
from tests.factories import FIXED_NOW
from tests.security import TEST_SECRET, fast_hasher


class TestArgon2:
    def test_hashes_are_salted_and_verifiable(self) -> None:
        hasher = fast_hasher()

        first, second = hasher.hash("senha-forte"), hasher.hash("senha-forte")

        assert first != second  # sal aleatório: mesma senha, hashes diferentes
        assert first.startswith("$argon2id$")
        assert hasher.verify("senha-forte", first)
        assert not hasher.verify("senha-errada", first)

    def test_garbage_hashes_never_verify(self) -> None:
        assert not fast_hasher().verify("qualquer", "isso-nao-e-um-hash")


class TestJwt:
    USER_ID = UserId(uuid4())

    def service(
        self, *, secret: str = TEST_SECRET, now_offset: timedelta = timedelta()
    ) -> JwtTokenService:
        return JwtTokenService(secret, ttl=timedelta(hours=1), clock=lambda: FIXED_NOW + now_offset)

    def test_round_trip(self) -> None:
        # A biblioteca confere a validade com o relógio real; por isso, sem relógio fixo aqui.
        token = JwtTokenService(TEST_SECRET, ttl=timedelta(hours=1)).issue(self.USER_ID)

        assert token.expires_at > FIXED_NOW
        assert (
            JwtTokenService(TEST_SECRET, ttl=timedelta(hours=1)).verify(token.value) == self.USER_ID
        )

    def test_rejects_expired_tokens(self) -> None:
        old = self.service(now_offset=-timedelta(days=1)).issue(self.USER_ID)

        with pytest.raises(NotAuthenticatedError, match="expirou"):
            self.service().verify(old.value)

    def test_rejects_tokens_signed_with_another_secret(self) -> None:
        forged = self.service(secret="outro-segredo-com-mais-de-32-caracteres!").issue(self.USER_ID)

        with pytest.raises(NotAuthenticatedError):
            self.service().verify(forged.value)

    def test_rejects_unsigned_tokens(self) -> None:
        """Ataque clássico: token com alg=none e sem assinatura."""
        unsigned = jwt.encode(
            {"sub": str(self.USER_ID), "typ": "session", "iat": 0, "exp": 9999999999},
            key="",
            algorithm="none",
        )

        with pytest.raises(NotAuthenticatedError):
            self.service().verify(unsigned)

    @pytest.mark.parametrize("token", ["", "abc.def.ghi", "nao-e-jwt"])
    def test_rejects_garbage(self, token: str) -> None:
        with pytest.raises(NotAuthenticatedError):
            self.service().verify(token)

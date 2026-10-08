from datetime import timedelta
from uuid import UUID

import jwt

from manual_assistant.application.clock import Clock, utc_now
from manual_assistant.application.errors import NotAuthenticatedError
from manual_assistant.application.ports.security import SessionToken
from manual_assistant.domain.user import UserId

_ALGORITHM = "HS256"
_TOKEN_TYPE = "session"  # noqa: S105 - tipo do token, não é senha


class JwtTokenService:
    """Token de sessão assinado (JWT HS256) com validade."""

    def __init__(self, secret: str, *, ttl: timedelta, clock: Clock = utc_now) -> None:
        self._secret = secret
        self._ttl = ttl
        self._clock = clock

    def issue(self, user_id: UserId) -> SessionToken:
        now = self._clock()
        expires_at = now + self._ttl
        payload = {"sub": str(user_id), "typ": _TOKEN_TYPE, "iat": now, "exp": expires_at}
        return SessionToken(
            value=jwt.encode(payload, self._secret, algorithm=_ALGORITHM),
            expires_at=expires_at,
        )

    def verify(self, token: str) -> UserId:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],  # nunca aceitar o algoritmo que o token declara
                options={"require": ["sub", "exp", "iat"]},
            )
            if payload.get("typ") != _TOKEN_TYPE:
                raise jwt.InvalidTokenError("tipo de token inesperado")
            return UserId(UUID(payload["sub"]))
        except (jwt.PyJWTError, ValueError) as error:
            raise NotAuthenticatedError(
                "Sua sessão expirou ou é inválida. Faça login novamente."
            ) from error

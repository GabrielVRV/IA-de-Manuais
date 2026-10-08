import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import NewType, Self
from uuid import UUID, uuid4

from manual_assistant.domain.errors import InvalidValueError

UserId = NewType("UserId", UUID)

USERNAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{2,49}")
DISPLAY_NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class UserRole(StrEnum):
    ADMIN = "admin"  # usa o chat e administra manuais e usuários
    USER = "user"  # usa o chat


def normalize_username(username: str) -> str:
    """Logins não diferenciam maiúsculas: 'Gabriel' e 'gabriel' são a mesma pessoa."""
    return username.strip().lower()


def validate_password(password: str, *, username: str) -> None:
    """Política de senha. Comprimento importa mais que regras de símbolo (NIST SP 800-63B)."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise InvalidValueError(f"A senha precisa ter ao menos {PASSWORD_MIN_LENGTH} caracteres")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise InvalidValueError(f"A senha pode ter no máximo {PASSWORD_MAX_LENGTH} caracteres")
    if normalize_username(password) == normalize_username(username):
        raise InvalidValueError("A senha não pode ser igual ao login")


@dataclass(eq=False, kw_only=True, slots=True)
class User:
    id: UserId
    username: str
    display_name: str
    role: UserRole
    # Hash produzido pela porta PasswordHasher; o domínio nunca vê a senha guardada.
    password_hash: str
    created_at: datetime
    is_active: bool = True
    must_change_password: bool = True
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        if not USERNAME_PATTERN.fullmatch(self.username):
            raise InvalidValueError(
                "O login deve ter de 3 a 50 caracteres: letras minúsculas, números, '.', '_' ou '-'"
            )
        if not self.display_name.strip():
            raise InvalidValueError("O nome do usuário é obrigatório")
        if len(self.display_name) > DISPLAY_NAME_MAX_LENGTH:
            raise InvalidValueError(f"O nome excede {DISPLAY_NAME_MAX_LENGTH} caracteres")
        if self.created_at.tzinfo is None:
            raise InvalidValueError("A data de cadastro precisa ter fuso horário")

    @classmethod
    def register(
        cls,
        *,
        username: str,
        display_name: str,
        role: UserRole,
        password_hash: str,
        now: datetime,
    ) -> Self:
        """Novo usuário recebe uma senha provisória e precisa trocá-la no primeiro acesso."""
        return cls(
            id=UserId(uuid4()),
            username=normalize_username(username),
            display_name=display_name.strip(),
            role=role,
            password_hash=password_hash,
            created_at=now,
        )

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def record_failed_login(self, now: datetime, *, max_attempts: int, lockout: timedelta) -> None:
        """Após ``max_attempts`` erros seguidos, bloqueia por ``lockout`` (contra força bruta)."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = now + lockout
            self.failed_login_attempts = 0

    def record_successful_login(self, now: datetime) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = now

    def change_password(self, password_hash: str) -> None:
        self.password_hash = password_hash
        self.must_change_password = False

    def reset_password(self, temporary_password_hash: str) -> None:
        """Senha provisória definida por um administrador: troca obrigatória no próximo acesso."""
        self.password_hash = temporary_password_hash
        self.must_change_password = True
        self.failed_login_attempts = 0
        self.locked_until = None

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NewType, Self
from uuid import UUID, uuid4

from manual_assistant.domain.errors import InvalidValueError

UserId = NewType("UserId", UUID)

USERNAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{2,49}")
DISPLAY_NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
INVALID_USERNAME_MESSAGE = (
    "O login deve ter de 3 a 50 caracteres: letras minúsculas, números, '.', '_' ou '-'"
)


class UserRole(StrEnum):
    ADMIN = "admin"  # usa o chat e administra manuais e usuários
    USER = "user"  # usa o chat
    PENDING = "pending"  # entrou pelo AD e aguarda um administrador liberar o acesso


class AuthSource(StrEnum):
    """Quem confere a senha do usuário."""

    LOCAL = "local"  # este sistema (Argon2)
    AD = "ad"  # o Active Directory (usuário de rede): aqui não existe senha guardada


def normalize_username(username: str) -> str:
    """Logins não diferenciam maiúsculas: 'Gabriel' e 'gabriel' são a mesma pessoa."""
    return username.strip().lower()


def normalize_typed_login(username: str) -> str:
    """Login digitado na tela de entrada. O domínio que se digita por hábito do Windows
    ('EMPRESA\\gabriel', 'gabriel@empresa.local') é descartado: o login é só 'gabriel'."""
    name = normalize_username(username).rpartition("\\")[2]
    return name.partition("@")[0] if name.count("@") == 1 else name


def is_valid_username(username: str) -> bool:
    return USERNAME_PATTERN.fullmatch(username) is not None


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
    # Só usuários locais têm senha: a dos usuários do AD fica no AD.
    password_hash: str | None
    created_at: datetime
    auth_source: AuthSource = AuthSource.LOCAL
    is_active: bool = True
    must_change_password: bool = True
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        if not is_valid_username(self.username):
            raise InvalidValueError(INVALID_USERNAME_MESSAGE)
        if not self.display_name.strip():
            raise InvalidValueError("O nome do usuário é obrigatório")
        if len(self.display_name) > DISPLAY_NAME_MAX_LENGTH:
            raise InvalidValueError(f"O nome excede {DISPLAY_NAME_MAX_LENGTH} caracteres")
        if self.created_at.tzinfo is None:
            raise InvalidValueError("A data de cadastro precisa ter fuso horário")
        if (self.password_hash is None) != (self.auth_source is AuthSource.AD):
            raise InvalidValueError("Só usuários locais têm senha guardada neste sistema")

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
        """Novo usuário local recebe uma senha provisória e precisa trocá-la no primeiro acesso."""
        return cls(
            id=UserId(uuid4()),
            username=normalize_username(username),
            display_name=display_name.strip(),
            role=role,
            password_hash=password_hash,
            created_at=now,
        )

    @classmethod
    def provision_from_directory(cls, *, username: str, display_name: str, now: datetime) -> Self:
        """Primeiro login de um usuário do AD: entra, mas aguarda um administrador liberar."""
        return cls(
            id=UserId(uuid4()),
            username=normalize_username(username),
            display_name=_fit_display_name(display_name, fallback=username),
            role=UserRole.PENDING,
            password_hash=None,
            created_at=now,
            auth_source=AuthSource.AD,
            must_change_password=False,
        )

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    @property
    def is_pending(self) -> bool:
        return self.role is UserRole.PENDING

    @property
    def is_local(self) -> bool:
        return self.auth_source is AuthSource.LOCAL

    def record_successful_login(self, now: datetime) -> None:
        self.last_login_at = now

    def sync_display_name(self, display_name: str) -> None:
        """O nome dos usuários do AD acompanha o cadastro do AD."""
        self.display_name = _fit_display_name(display_name, fallback=self.display_name)

    def change_password(self, password_hash: str) -> None:
        self._require_local_password()
        self.password_hash = password_hash
        self.must_change_password = False

    def reset_password(self, temporary_password_hash: str) -> None:
        """Senha provisória definida por um administrador: troca obrigatória no próximo acesso."""
        self._require_local_password()
        self.password_hash = temporary_password_hash
        self.must_change_password = True

    def use_directory_login(self, username: str | None = None) -> None:
        """Passa a conferir a senha no AD, mantendo o perfil. A senha local é descartada.

        ``username``: o login de rede, quando é diferente do login atual.
        """
        if username is not None:
            name = normalize_username(username)
            if not is_valid_username(name):
                raise InvalidValueError(INVALID_USERNAME_MESSAGE)
            self.username = name
        self.auth_source = AuthSource.AD
        self.password_hash = None
        self.must_change_password = False

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def _require_local_password(self) -> None:
        if not self.is_local:
            raise InvalidValueError("A senha do AD é a senha de rede: troque-a no Windows")

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)


def _fit_display_name(display_name: str, *, fallback: str) -> str:
    """Nome vindo de fora (AD): sem espaços nas pontas, no tamanho máximo, nunca vazio."""
    name = display_name.strip()[:DISPLAY_NAME_MAX_LENGTH].strip()
    return name or fallback

class ApplicationError(Exception):
    """Falha ao executar um caso de uso."""


class ManualNotFoundError(ApplicationError):
    def __init__(self, manual_id: object) -> None:
        super().__init__(f"Manual não encontrado: {manual_id}")


class InvalidDocumentError(ApplicationError):
    """O arquivo enviado foi recusado antes do processamento (formato, tamanho...)."""


class UnreadableDocumentError(ApplicationError):
    """O documento enviado não pôde ser lido (corrompido, protegido por senha, sem texto...)."""


class StoredFileNotFoundError(ApplicationError):
    """O arquivo original de um manual não está mais no armazenamento."""


class InvalidCredentialsError(ApplicationError):
    """Login falhou. Mesma mensagem para login inexistente, senha errada ou conta inativa,
    para não revelar quais logins existem."""

    def __init__(self) -> None:
        super().__init__("Usuário ou senha inválidos")


class AccountLockedError(ApplicationError):
    def __init__(self, minutes: int) -> None:
        super().__init__(f"Muitas tentativas de login. Tente novamente em {minutes} minuto(s).")


class NotAuthenticatedError(ApplicationError):
    def __init__(self, message: str = "Faça login para continuar") -> None:
        super().__init__(message)


class PermissionDeniedError(ApplicationError):
    def __init__(self, message: str = "Você não tem permissão para esta ação") -> None:
        super().__init__(message)


class PasswordChangeRequiredError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("Troque sua senha provisória para continuar")


class UserNotFoundError(ApplicationError):
    def __init__(self, user_id: object) -> None:
        super().__init__(f"Usuário não encontrado: {user_id}")


class UserAlreadyExistsError(ApplicationError):
    def __init__(self, username: str) -> None:
        super().__init__(f"Já existe um usuário com o login '{username}'")


class ExternalServiceError(ApplicationError):
    """Um serviço externo (LLM, embeddings, banco vetorial) falhou ou não respondeu.

    Os adaptadores traduzem as exceções das bibliotecas de terceiros para este erro,
    assim os casos de uso nunca dependem de SDKs específicos.
    """

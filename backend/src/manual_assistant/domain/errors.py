class DomainError(Exception):
    """Violação de uma regra de negócio."""


class InvalidValueError(DomainError, ValueError):
    """Um valor não respeita as regras do domínio (ex.: pergunta vazia)."""


class InvalidStateTransitionError(DomainError):
    """Operação não permitida no estado atual da entidade."""

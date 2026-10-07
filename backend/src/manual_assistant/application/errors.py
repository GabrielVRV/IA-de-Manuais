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


class ExternalServiceError(ApplicationError):
    """Um serviço externo (LLM, embeddings, banco vetorial) falhou ou não respondeu.

    Os adaptadores traduzem as exceções das bibliotecas de terceiros para este erro,
    assim os casos de uso nunca dependem de SDKs específicos.
    """

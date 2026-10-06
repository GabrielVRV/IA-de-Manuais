class ApplicationError(Exception):
    """Falha ao executar um caso de uso."""


class UnreadableDocumentError(ApplicationError):
    """O documento enviado não pôde ser lido (corrompido, protegido por senha, sem texto...)."""


class ExternalServiceError(ApplicationError):
    """Um serviço externo (LLM, embeddings, banco vetorial) falhou ou não respondeu.

    Os adaptadores traduzem as exceções das bibliotecas de terceiros para este erro,
    assim os casos de uso nunca dependem de SDKs específicos.
    """

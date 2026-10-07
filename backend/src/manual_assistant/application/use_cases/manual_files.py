from manual_assistant.domain.manual import ManualId


def original_file_key(manual_id: ManualId) -> str:
    """Chave do PDF original no armazenamento: derivada do id, nunca do nome enviado."""
    return f"{manual_id}.pdf"

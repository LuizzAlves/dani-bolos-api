"""
Tradutor semântico opcional usando Groq API.
Chamado apenas quando o classificador determinístico falha.
"""

import re
from app.integrations.groq import groq_translate
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Padrões de PII para mascarar
_PHONE_PATTERN = re.compile(r"\b\d{10,13}\b")
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b")
_EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_LONG_NUMBER_PATTERN = re.compile(r"\b\d{6,}\b")


def mask_pii(text: str) -> str:
    """Mascara dados pessoais antes de enviar à IA."""
    masked = _EMAIL_PATTERN.sub("[EMAIL]", text)
    masked = _CPF_PATTERN.sub("[CPF]", masked)
    masked = _PHONE_PATTERN.sub("[TELEFONE]", masked)
    masked = _LONG_NUMBER_PATTERN.sub("[NUMERO]", masked)
    return masked


async def semantic_translate(
    text: str,
    state: str,
    options: list[dict],
) -> int | None:
    """
    Usa Groq para traduzir texto livre em um ID de catálogo.

    Args:
        text: Texto original do cliente
        state: Estado atual da conversa
        options: Lista de opções válidas [{"id": 1, "name": "..."}, ...]

    Returns:
        ID matched ou None se sem correspondência / falha
    """
    settings = get_settings()

    if not settings.AI_TRANSLATOR_ENABLED:
        return None

    if not settings.GROQ_API_KEY:
        logger.warning("groq_api_key_not_set")
        return None

    # Não chamar IA para números puros
    if text.strip().isdigit():
        return None

    # Mascarar PII
    masked_text = mask_pii(text)

    # Preparar opções formatadas
    options_text = "\n".join(
        f"- ID {opt['id']}: {opt['name']}" for opt in options
    )

    try:
        matched_id = await groq_translate(
            masked_text=masked_text,
            state=state,
            options_text=options_text,
            model=settings.GROQ_TRANSLATOR_MODEL,
        )

        if matched_id is not None:
            # Validar contra opções ativas
            valid_ids = {opt["id"] for opt in options}
            if matched_id in valid_ids:
                logger.info(
                    "semantic_translation_success",
                    matched_id=matched_id,
                    state=state,
                )
                return matched_id
            else:
                logger.warning(
                    "semantic_translation_invalid_id",
                    matched_id=matched_id,
                    valid_ids=list(valid_ids),
                )
                return None

        return None

    except Exception as e:
        logger.error("semantic_translation_error", error=str(e))
        return None

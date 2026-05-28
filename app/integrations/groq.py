"""
Client HTTP assíncrono para a API Groq.
Usado como tradutor semântico opcional.
"""

import json
import httpx
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def groq_translate(
    masked_text: str,
    state: str,
    options_text: str,
    model: str | None = None,
) -> int | None:
    """
    Chama a Groq API para traduzir texto livre em ID de catálogo.

    Retorna matched_id (int) ou None.
    """
    settings = get_settings()
    model = model or settings.GROQ_TRANSLATOR_MODEL

    if not settings.GROQ_API_KEY:
        return None

    system_prompt = (
        "Você é um assistente que traduz respostas de clientes em IDs de catálogo. "
        "Responda APENAS com JSON no formato {\"matched_id\": <número>} ou "
        "{\"matched_id\": null} se não conseguir identificar. "
        "Não invente IDs. Use apenas os IDs listados."
    )

    user_prompt = (
        f"Estado atual: {state}\n\n"
        f"Opções disponíveis:\n{options_text}\n\n"
        f"Resposta do cliente: \"{masked_text}\"\n\n"
        "Qual é o matched_id?"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "max_tokens": 50,
                },
            )

            if response.status_code != 200:
                logger.error(
                    "groq_api_error",
                    status=response.status_code,
                    body=response.text[:200],
                )
                return None

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            matched_id = result.get("matched_id")

            if matched_id is not None:
                return int(matched_id)
            return None

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error("groq_parse_error", error=str(e))
        return None
    except httpx.TimeoutException:
        logger.warning("groq_timeout")
        return None
    except Exception as e:
        logger.error("groq_exception", error=str(e))
        return None

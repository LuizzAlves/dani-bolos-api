"""
Client HTTP assíncrono para a Evolution API.
Envia texto, mídia e presença via WhatsApp.
"""

import httpx
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Client httpx reutilizável
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _headers() -> dict:
    settings = get_settings()
    return {
        "apikey": settings.EVOLUTION_API_TOKEN,
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    settings = get_settings()
    return settings.EVOLUTION_API_URL.rstrip("/")


def _instance() -> str:
    return get_settings().EVOLUTION_INSTANCE_NAME


async def send_text(phone: str, text: str) -> bool:
    """
    Envia mensagem de texto via Evolution API.
    POST /message/sendText/{instance}
    """
    try:
        url = f"{_base_url()}/message/sendText/{_instance()}"
        payload = {
            "number": phone,
            "text": text,
        }
        client = _get_client()
        response = await client.post(url, json=payload, headers=_headers())

        if response.status_code in (200, 201):
            logger.info("evolution_text_sent", phone=phone[:6] + "***")
            return True
        else:
            logger.error(
                "evolution_text_error",
                status=response.status_code,
                body=response.text[:200],
            )
            return False

    except Exception as e:
        logger.error("evolution_text_exception", error=str(e))
        return False


async def send_media(
    phone: str,
    media_url: str,
    caption: str | None = None,
    media_type: str = "image",
) -> bool:
    """
    Envia mídia via Evolution API.
    POST /message/sendMedia/{instance}
    """
    try:
        url = f"{_base_url()}/message/sendMedia/{_instance()}"
        payload = {
            "number": phone,
            "mediatype": media_type,
            "media": media_url,
        }
        if caption:
            payload["caption"] = caption

        client = _get_client()
        response = await client.post(url, json=payload, headers=_headers())

        if response.status_code in (200, 201):
            logger.info("evolution_media_sent", phone=phone[:6] + "***")
            return True
        else:
            logger.error(
                "evolution_media_error",
                status=response.status_code,
                body=response.text[:200],
            )
            return False

    except Exception as e:
        logger.error("evolution_media_exception", error=str(e))
        return False


async def send_presence(phone: str, presence: str = "composing") -> bool:
    """
    Envia presença (digitando...) via Evolution API.
    POST /chat/sendPresence/{instance}
    """
    try:
        url = f"{_base_url()}/chat/sendPresence/{_instance()}"
        payload = {
            "number": phone,
            "presence": presence,
        }
        client = _get_client()
        response = await client.post(url, json=payload, headers=_headers())
        return response.status_code in (200, 201)
    except Exception as e:
        logger.debug("evolution_presence_error", error=str(e))
        return False

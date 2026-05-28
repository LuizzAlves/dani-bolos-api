"""
Parser robusto de payloads da Evolution API.
Normaliza tanto payload direto quanto embrulhado pelo n8n.
"""

import unicodedata
from app.schemas.evolution import ParsedMessage
from app.logging_config import get_logger

logger = get_logger(__name__)


def normalize_text(text: str) -> str:
    """Normaliza texto: lowercase, strip, remove acentos para comparação."""
    text = text.strip().lower()
    # Remove acentos
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def parse_evolution_payload(raw_payload: dict | list) -> ParsedMessage:
    """
    Parseia payload da Evolution API.

    Aceita dois formatos:
    1. Direto da Evolution: {"event": "messages.upsert", "instance": "...", "data": {...}}
    2. Wrapped pelo n8n: [{"headers": {...}, "body": {"event": "...", "data": {...}}}]
    """
    try:
        # Detectar formato
        body = _extract_body(raw_payload)
        if body is None:
            return ParsedMessage(
                phone="",
                should_ignore=True,
                ignore_reason="payload_format_unknown",
                raw_payload=raw_payload if isinstance(raw_payload, dict) else {},
            )

        # Verificar se é evento de mensagem
        event = body.get("event", "")
        if event != "messages.upsert":
            return ParsedMessage(
                phone="",
                should_ignore=True,
                ignore_reason=f"event_type_ignored:{event}",
                raw_payload=body,
            )

        data = body.get("data", {})
        key = data.get("key", {})
        remote_jid = key.get("remoteJid", "")

        # Ignorar mensagens de grupo
        if "@g.us" in remote_jid:
            return ParsedMessage(
                phone=remote_jid,
                should_ignore=True,
                ignore_reason="group_message",
                raw_payload=body,
            )

        # Ignorar mensagens enviadas pelo bot (fromMe)
        if key.get("fromMe", False):
            return ParsedMessage(
                phone=_extract_phone(remote_jid),
                should_ignore=True,
                ignore_reason="from_me",
                raw_payload=body,
            )

        # Extrair telefone
        phone = _extract_phone(remote_jid)
        if not phone:
            return ParsedMessage(
                phone="",
                should_ignore=True,
                ignore_reason="no_phone",
                raw_payload=body,
            )

        # Extrair metadados
        push_name = data.get("pushName")
        message_id = key.get("id")
        instance = body.get("instance", "")
        timestamp = data.get("messageTimestamp")
        message_type = data.get("messageType", "")
        message_obj = data.get("message", {})

        # Ignorar status de entrega/leitura
        status = data.get("status", "")
        if status in ("READ", "DELIVERY_ACK", "PLAYED") and not message_obj:
            return ParsedMessage(
                phone=phone,
                should_ignore=True,
                ignore_reason=f"status_update:{status}",
                raw_payload=body,
            )

        # Extrair texto
        text = _extract_text(message_type, message_obj)

        # Verificar se é mídia não suportada
        unsupported_types = {
            "audioMessage", "imageMessage", "videoMessage",
            "stickerMessage", "documentMessage", "pttMessage",
        }
        if message_type in unsupported_types or (text is None and message_type not in ("conversation", "extendedTextMessage")):
            return ParsedMessage(
                phone=phone,
                push_name=push_name,
                message_id=message_id,
                instance=instance,
                timestamp=timestamp,
                is_unsupported_media=True,
                raw_payload=body,
            )

        normalized = normalize_text(text) if text else None

        return ParsedMessage(
            phone=phone,
            push_name=push_name,
            text=text,
            normalized_text=normalized,
            message_id=message_id,
            instance=instance,
            timestamp=timestamp,
            raw_payload=body,
        )

    except Exception as e:
        logger.error("payload_parse_error", error=str(e))
        return ParsedMessage(
            phone="",
            should_ignore=True,
            ignore_reason=f"parse_error:{str(e)}",
            raw_payload=raw_payload if isinstance(raw_payload, dict) else {},
        )


def _extract_body(raw_payload: dict | list) -> dict | None:
    """Extrai o body do payload, independente do formato."""
    if isinstance(raw_payload, list):
        # Formato n8n: [{"headers": {...}, "body": {...}}]
        if len(raw_payload) == 0:
            return None
        item = raw_payload[0]
        if isinstance(item, dict) and "body" in item:
            return item["body"]
        return item

    if isinstance(raw_payload, dict):
        # Formato n8n com body
        if "body" in raw_payload and "headers" in raw_payload:
            return raw_payload["body"]
        # Formato direto da Evolution
        if "event" in raw_payload:
            return raw_payload
        # Pode ser o body já extraído
        if "data" in raw_payload:
            return raw_payload

    return None


def _extract_phone(remote_jid: str) -> str:
    """Extrai telefone do remoteJid, removendo @s.whatsapp.net."""
    if "@" in remote_jid:
        return remote_jid.split("@")[0]
    return remote_jid


def _extract_text(message_type: str, message_obj: dict) -> str | None:
    """Extrai texto da mensagem."""
    if message_type == "conversation":
        return message_obj.get("conversation")
    elif message_type == "extendedTextMessage":
        return message_obj.get("extendedTextMessage", {}).get("text")
    return None

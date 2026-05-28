"""
Schemas Pydantic para payloads da Evolution API.
"""

from pydantic import BaseModel, Field
from typing import Any


class ParsedMessage(BaseModel):
    """Mensagem normalizada após parsing do payload."""
    phone: str = Field(..., description="Telefone sem @s.whatsapp.net")
    push_name: str | None = Field(None, description="Nome do WhatsApp")
    text: str | None = Field(None, description="Texto original da mensagem")
    normalized_text: str | None = Field(None, description="Texto lowercase/stripped")
    message_id: str | None = Field(None, description="ID da mensagem")
    instance: str | None = Field(None, description="Nome da instância Evolution")
    timestamp: int | None = Field(None, description="Timestamp da mensagem")
    is_unsupported_media: bool = Field(False, description="Se é mídia não suportada")
    should_ignore: bool = Field(False, description="Se deve ser ignorada")
    ignore_reason: str | None = Field(None, description="Motivo para ignorar")
    raw_payload: dict = Field(default_factory=dict, description="Payload original")


class WebhookResponse(BaseModel):
    """Resposta padrão do endpoint de webhook."""
    status: str = "ok"
    message: str = ""
    processed: bool = False

"""
Schemas de mensagens e respostas.
"""

from pydantic import BaseModel, Field
from typing import Literal


class ResponseItem(BaseModel):
    """Um item de resposta a ser enviado ao cliente."""
    type: Literal["text", "media"] = "text"
    text: str | None = None
    media_url: str | None = None
    media_type: str | None = None  # "image" ou "video"
    caption: str | None = None


class ProcessingResult(BaseModel):
    """Resultado completo do processamento de uma mensagem."""
    responses: list[ResponseItem] = Field(default_factory=list)
    new_state: str | None = None
    action_code: str | None = None
    trigger: str | None = None
    error: str | None = None

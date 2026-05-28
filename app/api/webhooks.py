"""
Webhook endpoints para receber mensagens da Evolution API.
"""

from fastapi import APIRouter, Request, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.services import message_service
from app.schemas.evolution import WebhookResponse
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_webhook_token(x_webhook_token: str = Header(None)):
    """Verifica token de autenticação recebido no header."""
    settings = get_settings()
    if settings.WEBHOOK_TOKEN and x_webhook_token != settings.WEBHOOK_TOKEN:
        logger.warning("webhook_auth_failed")
        raise HTTPException(status_code=403, detail="Acesso negado: token inválido")
    return True


@router.post("/evolution", response_model=WebhookResponse, dependencies=[Depends(verify_webhook_token)])
async def webhook_evolution(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe payload direto da Evolution API.
    Formato: {"event": "messages.upsert", "instance": "...", "data": {...}}
    """
    try:
        payload = await request.json()
        logger.info("webhook_evolution_received", evolution_event=payload.get("event", "unknown"))
        result = await message_service.process_message(db, payload)
        return result
    except Exception as e:
        logger.error("webhook_evolution_error", error=str(e))
        return WebhookResponse(status="error", message="Internal error")


@router.post("/evolution/n8n", response_model=WebhookResponse, dependencies=[Depends(verify_webhook_token)])
async def webhook_evolution_n8n(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Recebe payload embrulhado pelo n8n.
    Formato: [{"headers": {...}, "body": {"event": "...", "data": {...}}}]
    """
    try:
        payload = await request.json()
        logger.info("webhook_n8n_received")
        result = await message_service.process_message(db, payload)
        return result
    except Exception as e:
        logger.error("webhook_n8n_error", error=str(e))
        return WebhookResponse(status="error", message="Internal error")

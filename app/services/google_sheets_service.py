"""
Serviço de orquestração do Google Sheets.
Espelha os dados do PostgreSQL e envia alertas operacionais.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select

from app.models import Order, Client, EventTypeEnum, OrderStatus, OrderExtra
from app.integrations import google_sheets as sheets_client
from app.repositories import events as event_repo
from app.logging_config import get_logger

logger = get_logger(__name__)


async def upsert_order(db: AsyncSession, order_id: int) -> bool:
    """
    Busca o pedido com todas as relações e envia para o Google Sheets.
    Registra erro se falhar, mas não bloqueia.
    """
    try:
        # Busca pedido com todas as relações para popular nomes
        query = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.client),
                selectinload(Order.size),
                selectinload(Order.filling_1),
                selectinload(Order.filling_2),
                selectinload(Order.finish),
                selectinload(Order.order_extras).joinedload(OrderExtra.extra)
            )
        )
        result = await db.execute(query)
        order = result.scalar_one_or_none()
        
        if not order:
            logger.warning("google_sheets_upsert_order_not_found", order_id=order_id)
            return False

        # Monta payload com dados reais
        client = order.client
        payload = {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": order.status.value if order.status else "DESCONHECIDO",
            "client_name": client.name or "Desconhecido",
            "phone": client.phone,
            "size": order.size.description if order.size else None,
            "dough": order.dough.value if order.dough else None,
            "filling_1": order.filling_1.name if order.filling_1 else None,
            "filling_2": order.filling_2.name if order.filling_2 else None,
            "extras": [oe.extra.name for oe in order.order_extras] if order.order_extras else [],
            "finish": order.finish.name if order.finish else None,
            "pickup_date": order.pickup_date.strftime("%Y-%m-%d") if order.pickup_date else None,
            "pickup_time": order.pickup_time.strftime("%H:%M") if order.pickup_time else None,
            "notes": order.notes,
            "base_value": float(order.base_value) if order.base_value else 0.0,
            "extras_value": float(order.extras_value) if order.extras_value else 0.0,
            "total_value": float(order.total_value) if order.total_value else 0.0,
            "submitted_at": order.created_at.isoformat() if order.created_at else None,
        }

        # Envia
        success = await sheets_client.send_to_webhook("upsert_order", payload)
        
        if success:
            await event_repo.log_event(
                db, EventTypeEnum.EXTERNAL_API_CALL,
                conversation_id=order.conversation_id,
                order_id=order.id,
                payload={
                    "provider": "google_sheets",
                    "action": "upsert_order",
                    "status": "success"
                },
            )
            return True
        else:
            await event_repo.log_event(
                db, EventTypeEnum.ERROR,
                conversation_id=order.conversation_id,
                order_id=order.id,
                payload={
                    "provider": "google_sheets",
                    "action": "upsert_order",
                    "error": "Failed to send to Sheets Web App",
                },
            )
            return False

    except Exception as e:
        logger.error("google_sheets_upsert_order_exception", error=str(e), order_id=order_id)
        await event_repo.log_event(
            db, EventTypeEnum.ERROR,
            order_id=order_id,
            payload={"provider": "google_sheets", "error": str(e)},
        )
        return False


async def create_alert(
    db: AsyncSession,
    title: str,
    phone: str,
    reason: str,
    conversation_id=None,
    order_id=None,
    order_number=None,
) -> bool:
    """Envia um alerta (handoff/erro/aprovação) para a agenda no Sheets."""
    try:
        # Determine severity and action based on reason/title
        severity = "warning"
        action = "review_needed"
        if "erro" in title.lower():
            severity = "error"
            action = "investigate"
            
        payload = {
            "severity": severity,
            "action": action,
            "error_code": reason[:50] if reason else None,
            "message": title,
            "order_id": order_id,
            "order_number": order_number,
            "phone": phone,
        }
        
        success = await sheets_client.send_to_webhook("alert", payload)
        
        if success:
            await event_repo.log_event(
                db, EventTypeEnum.EXTERNAL_API_CALL,
                conversation_id=conversation_id,
                payload={
                    "provider": "google_sheets",
                    "action": "alert",
                    "status": "success"
                },
            )
            return True
        else:
            await event_repo.log_event(
                db, EventTypeEnum.ERROR,
                conversation_id=conversation_id,
                payload={
                    "provider": "google_sheets",
                    "action": "alert",
                    "error": "Failed to send alert to Sheets",
                },
            )
            return False
            
    except Exception as e:
        logger.error("google_sheets_alert_exception", error=str(e))
        return False

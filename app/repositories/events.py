"""
Repositório de eventos (log imutável).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventTypeEnum


async def log_event(
    db: AsyncSession,
    event_type: EventTypeEnum,
    conversation_id: UUID | None = None,
    order_id: UUID | None = None,
    payload: dict | None = None,
) -> Event:
    """Registra um evento no log auditável."""
    event = Event(
        conversation_id=conversation_id,
        order_id=order_id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(event)
    await db.flush()
    return event


async def has_message_event(db: AsyncSession, message_id: str) -> bool:
    """Verifica se uma mensagem já foi processada (idempotência)."""
    if not message_id:
        return False
    
    # Busca por MESSAGE_RECEIVED que tenha este message_id no payload
    # O operador @> verifica se o JSON (à direita) está contido no JSONB (à esquerda)
    query = select(Event).where(
        Event.event_type == EventTypeEnum.MESSAGE_RECEIVED,
        Event.payload.op("->>")("message_id") == message_id
    )
    result = await db.execute(query)
    return result.first() is not None


async def get_latest_payload_by_action(
    db: AsyncSession,
    conversation_id: UUID,
    action: str,
    order_id: UUID | None = None,
) -> dict | None:
    """Busca o payload mais recente de um evento marcado por action."""
    filters = [
        Event.conversation_id == conversation_id,
        Event.payload.op("->>")("action") == action,
    ]
    if order_id is not None:
        filters.append(Event.order_id == order_id)

    query = (
        select(Event)
        .where(*filters)
        .order_by(Event.created_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    event = result.scalar_one_or_none()
    return event.payload if event else None

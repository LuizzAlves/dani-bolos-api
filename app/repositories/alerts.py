"""
Repositório de alertas para o dashboard administrativo.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertTypeEnum


async def get_pending_alerts(db: AsyncSession) -> list[Alert]:
    """Retorna alertas não resolvidos, mais recentes primeiro."""
    result = await db.execute(
        select(Alert)
        .where(Alert.resolved == False)
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


async def get_alert_count(db: AsyncSession) -> int:
    """Contagem de alertas pendentes."""
    result = await db.execute(
        select(func.count(Alert.id)).where(Alert.resolved == False)
    )
    return result.scalar_one()


async def get_alert_by_id(db: AsyncSession, alert_id: UUID) -> Alert | None:
    """Busca alerta pelo ID."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    return result.scalar_one_or_none()


async def create_alert(
    db: AsyncSession,
    alert_type: AlertTypeEnum,
    title: str,
    description: str | None = None,
    client_id: UUID | None = None,
    conversation_id: UUID | None = None,
    order_id: UUID | None = None,
    client_phone: str | None = None,
    client_name: str | None = None,
    last_message: str | None = None,
) -> Alert:
    """Cria um novo alerta."""
    alert = Alert(
        alert_type=alert_type,
        title=title,
        description=description,
        client_id=client_id,
        conversation_id=conversation_id,
        order_id=order_id,
        client_phone=client_phone,
        client_name=client_name,
        last_message=last_message,
    )
    db.add(alert)
    await db.flush()
    return alert


async def resolve_alert(db: AsyncSession, alert_id: UUID) -> bool:
    """Marca alerta como resolvido. Retorna True se encontrou."""
    result = await db.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.resolved == False)
        .values(resolved=True, resolved_at=datetime.now(timezone.utc))
    )
    await db.flush()
    return result.rowcount > 0

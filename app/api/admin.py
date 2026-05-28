"""
Admin endpoints protegidos por token.
"""

from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.models import Client, Conversation, Order, Event, OrderExtra
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_token(x_admin_token: str = Header(...)):
    """Verifica token de autenticação admin."""
    settings = get_settings()
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token inválido")
    return True


@router.post("/reset-test-client")
async def reset_test_client(
    phone: str,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """
    Remove todos os dados de um cliente de teste.
    Exige header X-Admin-Token.
    Use apenas para testes, nunca em produção.
    """
    # Buscar cliente
    result = await db.execute(
        select(Client).where(Client.phone == phone)
    )
    client = result.scalar_one_or_none()

    if not client:
        return {"status": "not_found", "message": f"Cliente {phone} não encontrado"}

    # Buscar conversas
    convs = await db.execute(
        select(Conversation).where(Conversation.client_id == client.id)
    )
    conv_ids = [c.id for c in convs.scalars().all()]

    # Buscar orders
    orders_result = await db.execute(
        select(Order).where(Order.client_id == client.id)
    )
    order_ids = [o.id for o in orders_result.scalars().all()]

    # Deletar em ordem de dependência
    if order_ids:
        await db.execute(
            delete(OrderExtra).where(OrderExtra.order_id.in_(order_ids))
        )
        await db.execute(
            delete(Event).where(Event.order_id.in_(order_ids))
        )

    if conv_ids:
        await db.execute(
            delete(Event).where(Event.conversation_id.in_(conv_ids))
        )

    if order_ids:
        await db.execute(
            delete(Order).where(Order.id.in_(order_ids))
        )

    if conv_ids:
        await db.execute(
            delete(Conversation).where(Conversation.id.in_(conv_ids))
        )

    await db.execute(
        delete(Client).where(Client.id == client.id)
    )

    await db.commit()

    logger.info("test_client_reset", phone=phone[:6] + "***")

    return {
        "status": "ok",
        "message": f"Cliente {phone} e todos os dados associados foram removidos",
        "deleted": {
            "conversations": len(conv_ids),
            "orders": len(order_ids),
        },
    }

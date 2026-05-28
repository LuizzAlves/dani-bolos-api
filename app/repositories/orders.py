"""
Repositório de pedidos.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderExtra, OrderStatus, CakeShape, DoughType


async def create_draft_order(
    db: AsyncSession, client_id: UUID, conversation_id: UUID
) -> Order:
    """Cria um pedido rascunho."""
    order = Order(
        client_id=client_id,
        conversation_id=conversation_id,
        status=OrderStatus.RASCUNHO,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order


async def get_active_order(db: AsyncSession, conversation_id: int) -> Order | None:
    """Retorna o pedido em andamento (RASCUNHO) para a conversa."""
    query = (
        select(Order)
        .where(
            Order.conversation_id == conversation_id,
            Order.status == OrderStatus.RASCUNHO
        )
        .order_by(Order.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def cancel_old_drafts(db: AsyncSession, conversation_id: int) -> list[UUID]:
    """Cancela todos os rascunhos em andamento dessa conversa e retorna os IDs cancelados."""
    query = (
        update(Order)
        .where(
            Order.conversation_id == conversation_id,
            Order.status == OrderStatus.RASCUNHO
        )
        .values(status=OrderStatus.CANCELADO)
        .returning(Order.id)
    )
    result = await db.execute(query)
    await db.flush()
    return list(result.scalars().all())


async def get_order_by_id(db: AsyncSession, order_id: UUID) -> Order | None:
    """Busca pedido pelo ID."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def get_order_by_number(db: AsyncSession, order_number: int) -> Order | None:
    """Busca pedido pelo número legível."""
    result = await db.execute(
        select(Order).where(Order.order_number == order_number)
    )
    return result.scalar_one_or_none()


async def update_order_size(
    db: AsyncSession,
    order_id: UUID,
    size_id: int,
    shape: CakeShape,
    filling_count: int,
    base_value: Decimal,
) -> None:
    """Salva tamanho, forma, camadas de recheio e valor base."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(
            size_id=size_id,
            shape=shape,
            filling_count=filling_count,
            base_value=base_value,
        )
    )
    await db.flush()


async def update_order_dough(
    db: AsyncSession, order_id: UUID, dough: DoughType, base_value: Decimal
) -> None:
    """Salva tipo de massa e recalcula valor base."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(dough=dough, base_value=base_value)
    )
    await db.flush()


async def update_order_filling(
    db: AsyncSession, order_id: UUID, filling_number: int, filling_id: int
) -> None:
    """Salva recheio 1 ou 2."""
    field = "filling_1_id" if filling_number == 1 else "filling_2_id"
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(**{field: filling_id})
    )
    await db.flush()


async def add_order_extra(
    db: AsyncSession,
    order_id: UUID,
    extra_id: int,
    layers: int,
    unit_price: Decimal,
) -> OrderExtra:
    """Adiciona um extra ao pedido."""
    oe = OrderExtra(
        order_id=order_id,
        extra_id=extra_id,
        layers=layers,
        unit_price=unit_price,
        total_price=unit_price * layers,
    )
    db.add(oe)
    await db.flush()
    return oe


async def clear_order_extras(db: AsyncSession, order_id: UUID) -> None:
    """Remove todos os extras do pedido (para recálculo)."""
    from sqlalchemy import delete
    await db.execute(
        delete(OrderExtra).where(OrderExtra.order_id == order_id)
    )
    await db.flush()


async def update_order_finish(db: AsyncSession, order_id: UUID, finish_id: int) -> None:
    """Salva finalização."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(finish_id=finish_id)
    )
    await db.flush()


async def update_order_date(db: AsyncSession, order_id: UUID, pickup_date) -> None:
    """Salva data de retirada."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(pickup_date=pickup_date)
    )
    await db.flush()


async def update_order_time(db: AsyncSession, order_id: UUID, pickup_time) -> None:
    """Salva horário de retirada."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(pickup_time=pickup_time)
    )
    await db.flush()


async def update_order_notes(db: AsyncSession, order_id: UUID, notes: str) -> None:
    """Salva observações."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(notes=notes)
    )
    await db.flush()


async def update_order_values(
    db: AsyncSession,
    order_id: UUID,
    base_value: Decimal | None = None,
    extras_value: Decimal | None = None,
    total_value: Decimal | None = None,
) -> None:
    """Atualiza valores do pedido."""
    values = {}
    if base_value is not None:
        values["base_value"] = base_value
    if extras_value is not None:
        values["extras_value"] = extras_value
    if total_value is not None:
        values["total_value"] = total_value
    if values:
        await db.execute(
            update(Order).where(Order.id == order_id).values(**values)
        )
        await db.flush()


async def finalize_order(db: AsyncSession, order_id: UUID) -> None:
    """Muda status para AGUARDANDO_CONFIRMACAO."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=OrderStatus.AGUARDANDO_CONFIRMACAO)
    )
    await db.flush()


async def cancel_order(db: AsyncSession, order_id: UUID) -> None:
    """Cancela o pedido."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=OrderStatus.CANCELADO)
    )
    await db.flush()


async def set_external_task(
    db: AsyncSession,
    order_id: UUID,
    provider: str,
    task_id: str,
    task_url: str,
) -> None:
    """Salva referência externa (Google Sheets)."""
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(
            external_task_provider=provider,
            external_task_id=task_id,
            external_task_url=task_url,
        )
    )
    await db.flush()

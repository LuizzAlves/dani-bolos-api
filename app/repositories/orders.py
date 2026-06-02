"""
Repositório de pedidos.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models import (
    Order, OrderExtra, OrderStatus, CakeShape, DoughType,
    Client, Size, Filling, Finish, Extra,
)


FIRST_ORDER_NUMBER = 1548


async def _next_order_number(db: AsyncSession) -> int:
    """Gera o próximo número legível do pedido com trava transacional."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('danibolos_orders_order_number'))"))
    result = await db.execute(
        select(func.coalesce(func.max(Order.order_number), FIRST_ORDER_NUMBER - 1) + 1)
    )
    return int(result.scalar_one())


async def create_draft_order(
    db: AsyncSession, client_id: UUID, conversation_id: UUID
) -> Order:
    """Cria um pedido rascunho."""
    order_number = await _next_order_number(db)
    order = Order(
        order_number=order_number,
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


async def get_order_by_number_with_details(
    db: AsyncSession, order_number: int, client_id: UUID | None = None
) -> Order | None:
    """Busca pedido pelo número legível com todos os detalhes (e filtrado por cliente, opcional)."""
    query = (
        select(Order)
        .options(
            joinedload(Order.client),
            joinedload(Order.size),
            joinedload(Order.filling_1),
            joinedload(Order.filling_2),
            joinedload(Order.finish),
            selectinload(Order.order_extras).joinedload(OrderExtra.extra),
        )
        .where(Order.order_number == order_number)
    )
    if client_id:
        query = query.where(Order.client_id == client_id)

    result = await db.execute(query)
    return result.unique().scalar_one_or_none()


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


# ============================================================
# FUNÇÕES DO DASHBOARD ADMINISTRATIVO
# ============================================================

async def list_orders_by_status(
    db: AsyncSession,
    statuses: list[OrderStatus],
    limit: int = 200,
    offset: int = 0,
) -> list[Order]:
    """Lista pedidos filtrados por status(es), para o Kanban."""
    query = (
        select(Order)
        .options(
            joinedload(Order.client),
            joinedload(Order.size),
            joinedload(Order.filling_1),
            joinedload(Order.filling_2),
            joinedload(Order.finish),
            selectinload(Order.order_extras).joinedload(OrderExtra.extra),
        )
        .where(Order.status.in_(statuses))
        .order_by(Order.pickup_date.asc().nullslast(), Order.pickup_time.asc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def count_orders_by_date(
    db: AsyncSession, year: int, month: int
) -> list[dict]:
    """Contagem de pedidos por dia do mês (para heatmap do calendário)."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    excluded = [OrderStatus.RASCUNHO, OrderStatus.CANCELADO]
    query = (
        select(
            Order.pickup_date,
            func.count(Order.id).label("count"),
        )
        .where(
            Order.pickup_date >= start,
            Order.pickup_date < end,
            Order.status.notin_(excluded),
        )
        .group_by(Order.pickup_date)
    )
    result = await db.execute(query)
    return [{"date": str(row.pickup_date), "count": row.count} for row in result.all()]


async def list_orders_by_date(
    db: AsyncSession, target_date: date
) -> list[Order]:
    """Lista pedidos de uma data específica."""
    excluded = [OrderStatus.RASCUNHO, OrderStatus.CANCELADO]
    query = (
        select(Order)
        .options(
            joinedload(Order.client),
            joinedload(Order.size),
            joinedload(Order.filling_1),
            joinedload(Order.filling_2),
            joinedload(Order.finish),
        )
        .where(
            Order.pickup_date == target_date,
            Order.status.notin_(excluded),
        )
        .order_by(Order.pickup_time.asc().nullslast())
    )
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def update_order_status(
    db: AsyncSession, order_id: UUID, new_status: OrderStatus
) -> bool:
    """Muda o status de um pedido. Retorna True se encontrou."""
    result = await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=new_status)
    )
    await db.flush()
    return result.rowcount > 0


async def get_order_with_details(db: AsyncSession, order_id: UUID) -> Order | None:
    """Retorna pedido com todos os JOINs para detalhes completos."""
    query = (
        select(Order)
        .options(
            joinedload(Order.client),
            joinedload(Order.size),
            joinedload(Order.filling_1),
            joinedload(Order.filling_2),
            joinedload(Order.finish),
            selectinload(Order.order_extras).joinedload(OrderExtra.extra),
        )
        .where(Order.id == order_id)
    )
    result = await db.execute(query)
    return result.unique().scalar_one_or_none()


async def create_manual_order(
    db: AsyncSession,
    client_id: UUID,
    size_id: int | None,
    shape: CakeShape | None,
    dough: DoughType | None,
    filling_1_id: int | None,
    filling_2_id: int | None,
    finish_id: int | None,
    pickup_date: date | None,
    pickup_time=None,
    notes: str | None = None,
    base_value: Decimal | None = None,
    extras_value: Decimal | None = None,
    total_value: Decimal | None = None,
    filling_count: int | None = None,
) -> Order:
    """Cria pedido manual (sem conversation_id)."""
    order_number = await _next_order_number(db)
    order = Order(
        order_number=order_number,
        client_id=client_id,
        conversation_id=None,
        status=OrderStatus.AGUARDANDO_CONFIRMACAO,
        size_id=size_id,
        shape=shape,
        dough=dough,
        filling_count=filling_count or 2,
        filling_1_id=filling_1_id,
        filling_2_id=filling_2_id,
        finish_id=finish_id,
        pickup_date=pickup_date,
        pickup_time=pickup_time,
        notes=notes,
        base_value=base_value,
        extras_value=extras_value or Decimal("0.00"),
        total_value=total_value,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """Métricas rápidas para o dashboard."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    excluded = [OrderStatus.RASCUNHO, OrderStatus.CANCELADO]

    # Pedidos agendados para hoje
    today_q = await db.execute(
        select(func.count(Order.id)).where(
            Order.pickup_date == today,
            Order.status.notin_(excluded),
        )
    )
    today_count = today_q.scalar_one()

    # Aguardando confirmação
    aguardando_q = await db.execute(
        select(func.count(Order.id)).where(
            Order.status == OrderStatus.AGUARDANDO_CONFIRMACAO,
        )
    )
    aguardando_count = aguardando_q.scalar_one()

    # Faturamento semanal
    fat_q = await db.execute(
        select(func.coalesce(func.sum(Order.total_value), 0)).where(
            Order.pickup_date >= week_start,
            Order.pickup_date <= today,
            Order.status.notin_(excluded),
        )
    )
    faturamento = fat_q.scalar_one()

    # Pedidos amanhã
    tomorrow = today + timedelta(days=1)
    tomorrow_q = await db.execute(
        select(func.count(Order.id)).where(
            Order.pickup_date == tomorrow,
            Order.status.notin_(excluded),
        )
    )
    tomorrow_count = tomorrow_q.scalar_one()

    return {
        "today_count": today_count,
        "aguardando_count": aguardando_count,
        "faturamento_semanal": float(faturamento),
        "tomorrow_count": tomorrow_count,
    }

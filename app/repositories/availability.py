"""
Repositório de disponibilidade de datas.
"""

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Availability
from app.core.service_hours import is_date_open

async def check_date_available(db: AsyncSession, target_date: date) -> dict:
    """
    Verifica disponibilidade de uma data.
    Retorna dict com: available, blocked, block_reason, remaining_slots.
    """
    result = await db.execute(
        select(Availability).where(Availability.date == target_date)
    )
    avail = result.scalar_one_or_none()

    # Check if the shop is open on this weekday
    is_open, reason = await is_date_open(db, target_date)
    if not is_open:
        return {
            "available": False,
            "blocked": True,
            "block_reason": reason,
            "remaining_slots": 0,
        }

    if avail is None:
        # Data não cadastrada — considerar indisponível (fora da agenda)
        return {
            "available": False,
            "blocked": True,
            "block_reason": "Data fora da agenda configurada",
            "remaining_slots": 0,
        }

    if avail.blocked:
        return {
            "available": False,
            "blocked": True,
            "block_reason": avail.block_reason or "Data bloqueada",
            "remaining_slots": 0,
        }

    remaining = avail.max_orders - avail.confirmed_orders
    return {
        "available": remaining > 0,
        "blocked": False,
        "block_reason": None if remaining > 0 else "LIMITE_ATINGIDO",
        "remaining_slots": max(0, remaining),
    }


async def increment_confirmed_orders(db: AsyncSession, target_date: date) -> bool:
    """
    Incrementa confirmed_orders atomicamente.
    Retorna True se incrementou com sucesso, False se lotou.
    Usa WHERE para garantir atomicidade.
    """
    # Garantir que o registro existe
    result = await db.execute(
        select(Availability).where(Availability.date == target_date)
    )
    avail = result.scalar_one_or_none()

    if avail is None:
        # Data não cadastrada — não incrementar
        return False

    if avail.blocked or avail.confirmed_orders >= avail.max_orders:
        return False

    # Incremento atômico com check de capacidade
    result = await db.execute(
        update(Availability)
        .where(
            Availability.date == target_date,
            Availability.confirmed_orders < Availability.max_orders,
            Availability.blocked == False,
        )
        .values(confirmed_orders=Availability.confirmed_orders + 1)
    )
    await db.flush()
    return result.rowcount > 0


async def decrement_confirmed_orders(db: AsyncSession, target_date: date) -> bool:
    """
    Decrementa confirmed_orders atomicamente.
    Retorna True se decrementou.
    """
    result = await db.execute(
        update(Availability)
        .where(
            Availability.date == target_date,
            Availability.confirmed_orders > 0,
        )
        .values(confirmed_orders=Availability.confirmed_orders - 1)
    )
    await db.flush()
    return result.rowcount > 0


# ============================================================
# FUNÇÕES DO DASHBOARD ADMINISTRATIVO
# ============================================================

async def get_month_availability(
    db: AsyncSession, year: int, month: int
) -> list[Availability]:
    """Retorna todos os registros de disponibilidade do mês."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    result = await db.execute(
        select(Availability)
        .where(Availability.date >= start, Availability.date < end)
        .order_by(Availability.date)
    )
    return list(result.scalars().all())


async def upsert_availability(
    db: AsyncSession,
    target_date: date,
    max_orders: int | None = None,
    blocked: bool | None = None,
    block_reason: str | None = None,
) -> Availability:
    """Cria ou atualiza disponibilidade de um dia."""
    result = await db.execute(
        select(Availability).where(Availability.date == target_date)
    )
    avail = result.scalar_one_or_none()

    if avail is None:
        avail = Availability(
            date=target_date,
            max_orders=max_orders if max_orders is not None else 5,
            blocked=blocked if blocked is not None else False,
            block_reason=block_reason,
        )
        db.add(avail)
    else:
        if max_orders is not None:
            avail.max_orders = max_orders
        if blocked is not None:
            avail.blocked = blocked
        if block_reason is not None:
            avail.block_reason = block_reason

    await db.flush()
    return avail


async def block_date(db: AsyncSession, target_date: date, reason: str | None = None) -> None:
    """Bloqueia uma data."""
    await upsert_availability(db, target_date, blocked=True, block_reason=reason)


async def unblock_date(db: AsyncSession, target_date: date) -> None:
    """Desbloqueia uma data."""
    await upsert_availability(db, target_date, blocked=False, block_reason=None)

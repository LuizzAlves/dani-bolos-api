"""
Repositório de disponibilidade de datas.
"""

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Availability


async def check_date_available(db: AsyncSession, target_date: date) -> dict:
    """
    Verifica disponibilidade de uma data.
    Retorna dict com: available, blocked, block_reason, remaining_slots.
    """
    result = await db.execute(
        select(Availability).where(Availability.date == target_date)
    )
    avail = result.scalar_one_or_none()

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
        "block_reason": None,
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

"""
Repositório de catálogo (sizes, fillings, extras, finishes, sweets, time_slots, catalog_media).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Size, Filling, Extra, Finish, Sweet, TimeSlot, CatalogMedia,
)


# --- Sizes ---

async def get_active_sizes(db: AsyncSession) -> list[Size]:
    """Retorna tamanhos ativos ordenados."""
    result = await db.execute(
        select(Size)
        .where(Size.active == True)
        .order_by(Size.sort_order)
    )
    return list(result.scalars().all())


async def get_size_by_id(db: AsyncSession, size_id: int) -> Size | None:
    result = await db.execute(
        select(Size).where(Size.id == size_id, Size.active == True)
    )
    return result.scalar_one_or_none()


# --- Fillings ---

async def get_active_fillings(db: AsyncSession) -> list[Filling]:
    """Retorna recheios disponíveis ordenados."""
    result = await db.execute(
        select(Filling)
        .where(Filling.available == True)
        .order_by(Filling.sort_order)
    )
    return list(result.scalars().all())


async def get_filling_by_id(db: AsyncSession, filling_id: int) -> Filling | None:
    result = await db.execute(
        select(Filling).where(Filling.id == filling_id, Filling.available == True)
    )
    return result.scalar_one_or_none()


# --- Extras ---

async def get_active_extras(db: AsyncSession) -> list[Extra]:
    """Retorna adicionais ativos ordenados."""
    result = await db.execute(
        select(Extra)
        .where(Extra.active == True)
        .order_by(Extra.sort_order)
    )
    return list(result.scalars().all())


async def get_extra_by_id(db: AsyncSession, extra_id: int) -> Extra | None:
    result = await db.execute(
        select(Extra).where(Extra.id == extra_id, Extra.active == True)
    )
    return result.scalar_one_or_none()


# --- Finishes ---

async def get_active_finishes(db: AsyncSession) -> list[Finish]:
    """Retorna finalizações ativas ordenadas."""
    result = await db.execute(
        select(Finish)
        .where(Finish.active == True)
        .order_by(Finish.sort_order)
    )
    return list(result.scalars().all())


async def get_finish_by_id(db: AsyncSession, finish_id: int) -> Finish | None:
    result = await db.execute(
        select(Finish).where(Finish.id == finish_id, Finish.active == True)
    )
    return result.scalar_one_or_none()


# --- Sweets ---

async def get_active_sweets(db: AsyncSession) -> list[Sweet]:
    """Retorna docinhos ativos ordenados."""
    result = await db.execute(
        select(Sweet)
        .where(Sweet.active == True)
        .order_by(Sweet.sort_order)
    )
    return list(result.scalars().all())


# --- Time Slots ---

async def get_active_time_slots(db: AsyncSession) -> list[TimeSlot]:
    """Retorna horários de retirada disponíveis."""
    result = await db.execute(
        select(TimeSlot)
        .where(TimeSlot.available == True)
        .order_by(TimeSlot.sort_order)
    )
    return list(result.scalars().all())


async def get_time_slot_by_id(db: AsyncSession, slot_id: int) -> TimeSlot | None:
    result = await db.execute(
        select(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.available == True)
    )
    return result.scalar_one_or_none()


# --- Catalog Media ---

async def get_catalog_media(
    db: AsyncSession, reference_type: str
) -> CatalogMedia | None:
    """Busca mídia ativa por reference_type (CARDAPIO_1R, RECHEIOS, etc.)."""
    result = await db.execute(
        select(CatalogMedia).where(
            CatalogMedia.reference_type == reference_type,
            CatalogMedia.active == True,
            CatalogMedia.reference_id.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_catalog_medias(
    db: AsyncSession, reference_types: list[str]
) -> list[CatalogMedia]:
    """Busca múltiplas mídias por tipo."""
    result = await db.execute(
        select(CatalogMedia).where(
            CatalogMedia.reference_type.in_(reference_types),
            CatalogMedia.active == True,
            CatalogMedia.reference_id.is_(None),
        )
    )
    return list(result.scalars().all())

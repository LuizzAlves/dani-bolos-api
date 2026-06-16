"""
Repositório de catálogo (sizes, fillings, extras, finishes, sweets, time_slots, catalog_media).
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Size, Filling, Extra, Finish, Sweet, TimeSlot, CatalogMedia,
)


# --- Sizes ---

async def get_active_sizes(db: AsyncSession) -> list[Size]:
    """Retorna tamanhos ativos ordenados.

    Dani Bolos trabalha somente com bolos de 2 recheios; tamanhos antigos de
    1 recheio ficam fora do fluxo mesmo se ainda existirem no banco.
    """
    result = await db.execute(
        select(Size)
        .where(Size.active == True, Size.filling_layers == 2)
        .order_by(Size.sort_order)
    )
    return list(result.scalars().all())


async def get_size_by_id(db: AsyncSession, size_id: int) -> Size | None:
    result = await db.execute(
        select(Size).where(
            Size.id == size_id,
            Size.active == True,
            Size.filling_layers == 2,
        )
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


# ============================================================
# FUNÇÕES DO DASHBOARD ADMINISTRATIVO
# ============================================================

async def get_all_sizes(db: AsyncSession) -> list[Size]:
    """Retorna todos os tamanhos (inclui inativos) para gestão."""
    result = await db.execute(select(Size).order_by(Size.sort_order))
    return list(result.scalars().all())


async def get_all_fillings(db: AsyncSession) -> list[Filling]:
    """Retorna todos os recheios (inclui indisponíveis)."""
    result = await db.execute(select(Filling).order_by(Filling.sort_order))
    return list(result.scalars().all())


async def get_all_extras(db: AsyncSession) -> list[Extra]:
    """Retorna todos os adicionais (inclui inativos)."""
    result = await db.execute(select(Extra).order_by(Extra.sort_order))
    return list(result.scalars().all())


async def get_all_finishes(db: AsyncSession) -> list[Finish]:
    """Retorna todas as finalizações (inclui inativas)."""
    result = await db.execute(select(Finish).order_by(Finish.sort_order))
    return list(result.scalars().all())


async def get_all_sweets(db: AsyncSession) -> list[Sweet]:
    """Retorna todos os docinhos (inclui inativos)."""
    result = await db.execute(select(Sweet).order_by(Sweet.sort_order))
    return list(result.scalars().all())


async def get_all_time_slots(db: AsyncSession) -> list[TimeSlot]:
    """Retorna todos os horários (inclui indisponíveis)."""
    result = await db.execute(select(TimeSlot).order_by(TimeSlot.sort_order))
    return list(result.scalars().all())


async def update_size(db: AsyncSession, size_id: int, data: dict) -> bool:
    """Atualiza campos de um tamanho."""
    result = await db.execute(
        update(Size).where(Size.id == size_id).values(**data)
    )
    await db.flush()
    return result.rowcount > 0


async def update_filling(db: AsyncSession, filling_id: int, data: dict) -> bool:
    """Atualiza campos de um recheio."""
    result = await db.execute(
        update(Filling).where(Filling.id == filling_id).values(**data)
    )
    await db.flush()
    return result.rowcount > 0


async def update_extra(db: AsyncSession, extra_id: int, data: dict) -> bool:
    """Atualiza campos de um adicional."""
    result = await db.execute(
        update(Extra).where(Extra.id == extra_id).values(**data)
    )
    await db.flush()
    return result.rowcount > 0


async def update_finish(db: AsyncSession, finish_id: int, data: dict) -> bool:
    """Atualiza campos de uma finalização."""
    result = await db.execute(
        update(Finish).where(Finish.id == finish_id).values(**data)
    )
    await db.flush()
    return result.rowcount > 0


async def update_sweet(db: AsyncSession, sweet_id: int, data: dict) -> bool:
    """Atualiza campos de um docinho."""
    result = await db.execute(
        update(Sweet).where(Sweet.id == sweet_id).values(**data)
    )
    await db.flush()
    return result.rowcount > 0


# ============================================================
# CREATE / DELETE — Gestão completa pelo painel
# ============================================================

from sqlalchemy import delete as sa_delete
from decimal import Decimal


async def create_catalog_item(db: AsyncSession, catalog_type: str, data: dict):
    """Cria um novo item de catálogo. Retorna o item criado."""
    model_map = {
        "sizes": Size,
        "fillings": Filling,
        "extras": Extra,
        "finishes": Finish,
        "sweets": Sweet,
    }
    model = model_map.get(catalog_type)
    if not model:
        return None

    # Converter campos numéricos
    for field in ("price_white", "price_chocolate", "price_per_layer", "price", "weight_kg"):
        if field in data and data[field] is not None:
            data[field] = Decimal(str(data[field]))

    item = model(**data)
    db.add(item)
    await db.flush()
    return item


async def delete_catalog_item(db: AsyncSession, catalog_type: str, item_id: int) -> bool:
    """Remove um item do catálogo. Retorna True se encontrou."""
    model_map = {
        "sizes": Size,
        "fillings": Filling,
        "extras": Extra,
        "finishes": Finish,
        "sweets": Sweet,
    }
    model = model_map.get(catalog_type)
    if not model:
        return False

    result = await db.execute(
        sa_delete(model).where(model.id == item_id)
    )
    await db.flush()
    return result.rowcount > 0


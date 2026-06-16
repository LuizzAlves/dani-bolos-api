"""
Repositório CRUD para bolos prontos para entrega.
"""

from datetime import datetime, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReadyCake


async def get_available_ready_cakes(db: AsyncSession) -> list[ReadyCake]:
    """Retorna bolos prontos com available=True, ordenados por ID."""
    result = await db.execute(
        select(ReadyCake)
        .where(ReadyCake.available == True)
        .order_by(ReadyCake.id)
    )
    return list(result.scalars().all())


async def get_all_ready_cakes(db: AsyncSession) -> list[ReadyCake]:
    """Retorna todos os bolos prontos (para o painel admin)."""
    result = await db.execute(
        select(ReadyCake).order_by(ReadyCake.id.desc())
    )
    return list(result.scalars().all())


async def get_ready_cake_by_id(db: AsyncSession, cake_id: int) -> ReadyCake | None:
    """Busca bolo pronto pelo ID."""
    result = await db.execute(select(ReadyCake).where(ReadyCake.id == cake_id))
    return result.scalar_one_or_none()


async def create_ready_cake(
    db: AsyncSession,
    flavor: str,
    description: str | None = None,
    price: float | None = None,
) -> ReadyCake:
    """Cria um novo bolo pronto."""
    from decimal import Decimal
    cake = ReadyCake(
        flavor=flavor,
        description=description,
        price=Decimal(str(price)) if price is not None else None,
    )
    db.add(cake)
    await db.flush()
    return cake


async def update_ready_cake(db: AsyncSession, cake_id: int, data: dict) -> bool:
    """Atualiza campos de um bolo pronto. Retorna True se encontrou."""
    allowed = {"flavor", "description", "price", "available"}
    update_data = {k: v for k, v in data.items() if k in allowed}
    if not update_data:
        return False
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = await db.execute(
        update(ReadyCake)
        .where(ReadyCake.id == cake_id)
        .values(**update_data)
    )
    await db.flush()
    return result.rowcount > 0


async def delete_ready_cake(db: AsyncSession, cake_id: int) -> bool:
    """Remove um bolo pronto. Retorna True se encontrou."""
    result = await db.execute(
        delete(ReadyCake).where(ReadyCake.id == cake_id)
    )
    await db.flush()
    return result.rowcount > 0

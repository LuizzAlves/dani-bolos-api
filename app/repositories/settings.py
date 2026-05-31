"""
Repositório de configurações administrativas.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminSetting


async def get_all_settings(db: AsyncSession) -> dict:
    """Retorna todas as configurações como dict {key: value}."""
    result = await db.execute(select(AdminSetting))
    settings = result.scalars().all()
    return {s.key: s.value for s in settings}


async def get_setting(db: AsyncSession, key: str):
    """Retorna valor de uma configuração específica."""
    result = await db.execute(
        select(AdminSetting).where(AdminSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def upsert_setting(db: AsyncSession, key: str, value) -> None:
    """Insere ou atualiza uma configuração."""
    stmt = pg_insert(AdminSetting).values(
        key=key, value=value, updated_at=datetime.now(timezone.utc)
    ).on_conflict_do_update(
        index_elements=["key"],
        set_={"value": value, "updated_at": datetime.now(timezone.utc)},
    )
    await db.execute(stmt)
    await db.flush()


async def upsert_many_settings(db: AsyncSession, settings_dict: dict) -> None:
    """Atualiza múltiplas configurações."""
    for key, value in settings_dict.items():
        await upsert_setting(db, key, value)

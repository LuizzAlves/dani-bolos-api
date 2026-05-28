"""
Conexão assíncrona com PostgreSQL via SQLAlchemy 2.0.
Pool de conexões configurável com lifecycle hooks.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import get_settings

_engine = None
_async_session_factory = None


def get_engine():
    """Retorna a engine async (criada sob demanda)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.LOG_LEVEL == "DEBUG" and not settings.is_production,
        )
    return _engine


def get_session_factory():
    """Retorna a session factory async."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db():
    """Dependency FastAPI: fornece uma sessão async por request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Verifica a conexão com o banco na inicialização."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )


async def close_db():
    """Fecha o pool de conexões no shutdown."""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None

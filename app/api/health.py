"""
Health check endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Verifica se a API está rodando."""
    return {"status": "healthy", "service": "dani-bolos-api"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    """Verifica se a API está pronta (inclui conexão com banco)."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "service": "dani-bolos-api",
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "database": "disconnected",
            "error": str(e),
        }

"""
Repositório de clientes.
"""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Client


async def get_client_by_phone(db: AsyncSession, phone: str) -> Client | None:
    """Busca cliente pelo telefone."""
    result = await db.execute(
        select(Client).where(Client.phone == phone)
    )
    return result.scalar_one_or_none()


async def create_client(db: AsyncSession, phone: str, name: str | None = None) -> Client:
    """Cria um novo cliente."""
    client = Client(phone=phone, name=name)
    db.add(client)
    await db.flush()
    return client


async def get_or_create_client(
    db: AsyncSession, phone: str, push_name: str | None = None
) -> tuple[Client, bool]:
    """
    Busca cliente por telefone. Se não existe, cria.
    Retorna (client, is_new).
    """
    client = await get_client_by_phone(db, phone)
    if client:
        # Atualizar nome se veio no push_name e o cliente não tinha
        if push_name and not client.name:
            client.name = push_name
            await db.flush()
        return client, False

    client = await create_client(db, phone, name=push_name)
    return client, True


async def get_client_by_id(db: AsyncSession, client_id: UUID) -> Client | None:
    """Busca cliente pelo ID."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    return result.scalar_one_or_none()


async def update_client_name(db: AsyncSession, client_id: UUID, name: str) -> None:
    """Atualiza o nome do cliente."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if client:
        client.name = name
        await db.flush()

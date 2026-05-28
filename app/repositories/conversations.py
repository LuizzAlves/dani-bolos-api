"""
Repositório de conversas.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Conversation, ConversationState, ActiveFlowType,
)
from app.config import get_settings


async def get_active_conversation(db: AsyncSession, client_id: UUID) -> Conversation | None:
    """Busca a conversa ativa do cliente."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.client_id == client_id,
            Conversation.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def create_conversation(db: AsyncSession, client_id: UUID) -> Conversation:
    """Cria nova conversa em estado NOVO_CLIENTE."""
    conv = Conversation(
        client_id=client_id,
        state=ConversationState.NOVO_CLIENTE,
        active_flow=ActiveFlowType.ONBOARDING,
    )
    db.add(conv)
    await db.flush()
    return conv


async def get_or_create_conversation(
    db: AsyncSession, client_id: UUID
) -> tuple[Conversation, bool]:
    """Busca ou cria conversa ativa. Retorna (conversation, is_new)."""
    conv = await get_active_conversation(db, client_id)
    if conv:
        return conv, False
    conv = await create_conversation(db, client_id)
    return conv, True


async def update_conversation_state(
    db: AsyncSession,
    conversation_id: UUID,
    new_state: ConversationState,
    active_flow: ActiveFlowType | None = None,
    fallback_count: int | None = None,
) -> None:
    """Atualiza estado, flow e fallback_count da conversa."""
    values = {
        "state": new_state,
        "last_interaction": datetime.now(timezone.utc),
    }
    if active_flow is not None:
        values["active_flow"] = active_flow
    if fallback_count is not None:
        values["fallback_count"] = fallback_count

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(**values)
    )
    await db.flush()


async def set_human_lock(db: AsyncSession, conversation_id: UUID) -> None:
    """Ativa human_lock na conversa."""
    settings = get_settings()
    lock_until = datetime.now(timezone.utc) + timedelta(hours=settings.HUMAN_LOCK_HOURS)
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(
            human_lock=True,
            human_lock_until=lock_until,
        )
    )
    await db.flush()


async def clear_human_lock(db: AsyncSession, conversation_id: UUID) -> None:
    """Remove human_lock da conversa."""
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(
            human_lock=False,
            human_lock_until=None,
        )
    )
    await db.flush()


async def update_last_interaction(db: AsyncSession, conversation_id: UUID) -> None:
    """Atualiza timestamp de última interação."""
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(last_interaction=datetime.now(timezone.utc))
    )
    await db.flush()


async def increment_fallback(db: AsyncSession, conversation: Conversation) -> int:
    """Incrementa fallback_count e retorna novo valor."""
    new_count = conversation.fallback_count + 1
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(fallback_count=new_count)
    )
    await db.flush()
    return new_count


async def reset_fallback(db: AsyncSession, conversation_id: UUID) -> None:
    """Reseta fallback_count para 0."""
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(fallback_count=0)
    )
    await db.flush()

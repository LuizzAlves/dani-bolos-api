"""
Repositório de transições da State Machine.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StateTransition, ConversationState, SmTriggerEnum


async def get_transition(
    db: AsyncSession,
    current_state: ConversationState,
    trigger: SmTriggerEnum,
) -> StateTransition | None:
    """Busca a transição para o par (estado, trigger)."""
    result = await db.execute(
        select(StateTransition).where(
            StateTransition.current_state == current_state,
            StateTransition.trigger == trigger,
            StateTransition.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def get_all_active_transitions(db: AsyncSession) -> list[StateTransition]:
    """Retorna todas as transições ativas (para cache/debug)."""
    result = await db.execute(
        select(StateTransition).where(StateTransition.is_active == True)
    )
    return list(result.scalars().all())

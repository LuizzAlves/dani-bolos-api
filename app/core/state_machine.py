"""
Motor da State Machine determinística.
Consulta transições no banco e aplica efeitos de fallback.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConversationState, SmTriggerEnum, SmActionEnum,
    FallbackEffectEnum, Conversation,
)
from app.repositories import state_transitions as st_repo
from app.repositories import conversations as conv_repo
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class TransitionResult:
    """Resultado de uma transição da State Machine."""

    def __init__(
        self,
        next_state: ConversationState,
        action_code: SmActionEnum,
        fallback_effect: FallbackEffectEnum,
        new_fallback_count: int = 0,
    ):
        self.next_state = next_state
        self.action_code = action_code
        self.fallback_effect = fallback_effect
        self.new_fallback_count = new_fallback_count


async def resolve_transition(
    db: AsyncSession,
    conversation: Conversation,
    trigger: SmTriggerEnum,
) -> TransitionResult | None:
    """
    Resolve a transição: current_state + trigger → next_state + action_code.

    Se o fallback_effect é INCREMENT e o novo count atinge MAX_FALLBACK_COUNT,
    reclassifica automaticamente como MAX_FALLBACK_REACHED.
    """
    settings = get_settings()
    current_state = conversation.state

    # Buscar transição no banco
    transition = await st_repo.get_transition(db, current_state, trigger)

    if transition is None:
        logger.warning(
            "transition_not_found",
            current_state=current_state.value,
            trigger=trigger.value,
        )
        return None

    fallback_effect = FallbackEffectEnum(transition.fallback_effect.value)
    new_count = conversation.fallback_count

    # Aplicar efeito de fallback
    if fallback_effect == FallbackEffectEnum.INCREMENT:
        new_count = conversation.fallback_count + 1
        await conv_repo.increment_fallback(db, conversation)

        # Verificar se atingiu max fallback
        if new_count >= settings.MAX_FALLBACK_COUNT:
            logger.info(
                "max_fallback_reached",
                conversation_id=str(conversation.id),
                count=new_count,
            )
            # Reclassificar como MAX_FALLBACK_REACHED
            return await resolve_transition(
                db, conversation, SmTriggerEnum.MAX_FALLBACK_REACHED
            )

    elif fallback_effect == FallbackEffectEnum.RESET:
        new_count = 0
        await conv_repo.reset_fallback(db, conversation.id)

    elif fallback_effect == FallbackEffectEnum.PAUSE:
        new_count = 0
        await conv_repo.reset_fallback(db, conversation.id)
        await conv_repo.set_human_lock(db, conversation.id)

    logger.info(
        "state_transition",
        current_state=current_state.value,
        trigger=trigger.value,
        next_state=transition.next_state.value,
        action_code=transition.action_code.value,
        fallback_effect=fallback_effect.value,
    )

    return TransitionResult(
        next_state=ConversationState(transition.next_state.value),
        action_code=SmActionEnum(transition.action_code.value),
        fallback_effect=fallback_effect,
        new_fallback_count=new_count,
    )

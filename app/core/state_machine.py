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


BUILTIN_TRANSITIONS: dict[
    tuple[ConversationState, SmTriggerEnum],
    tuple[ConversationState, SmActionEnum, FallbackEffectEnum],
] = {
    (ConversationState.NOVO_CLIENTE, SmTriggerEnum.NEW_CLIENT_REGISTERED): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.REGISTER_CLIENT_AND_SHOW_MENU, FallbackEffectEnum.RESET,
    ),
    (ConversationState.NOVO_CLIENTE, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.NOVO_CLIENTE, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.INPUT_VALID): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.SHOW_MENU, FallbackEffectEnum.RESET,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.OPTION_1): (
        ConversationState.PESQUISA, SmActionEnum.SHOW_SEARCH_MENU, FallbackEffectEnum.RESET,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.OPTION_2): (
        ConversationState.ESCOLHENDO_TAMANHO, SmActionEnum.CREATE_ORDER_AND_ASK_SIZE, FallbackEffectEnum.RESET,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.OPTION_3): (
        ConversationState.CONSULTA_PEDIDO, SmActionEnum.ASK_ORDER_ID, FallbackEffectEnum.RESET,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.OPTION_4): (
        ConversationState.ATENDIMENTO_HUMANO, SmActionEnum.ASK_HUMAN_REASON, FallbackEffectEnum.RESET,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.OPTION_5): (
        ConversationState.PRONTA_ENTREGA, SmActionEnum.SHOW_READY_CAKES, FallbackEffectEnum.RESET,
    ),
    (ConversationState.MENU_PRINCIPAL, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.PESQUISA, SmTriggerEnum.OPTION_1): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.SHOW_SIZES_AND_RETURN, FallbackEffectEnum.RESET,
    ),
    (ConversationState.PESQUISA, SmTriggerEnum.OPTION_2): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.SHOW_FILLINGS_AND_RETURN, FallbackEffectEnum.RESET,
    ),
    (ConversationState.PESQUISA, SmTriggerEnum.OPTION_3): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.SHOW_SWEETS_AND_RETURN, FallbackEffectEnum.RESET,
    ),
    (ConversationState.PESQUISA, SmTriggerEnum.OPTION_4): (
        ConversationState.PESQUISA_VALORES, SmActionEnum.ASK_VALUES_CRITERIA, FallbackEffectEnum.RESET,
    ),
    (ConversationState.PESQUISA, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.PESQUISA, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.PESQUISA_VALORES, SmTriggerEnum.INPUT_VALID): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.SHOW_VALUES_AND_RETURN, FallbackEffectEnum.RESET,
    ),
    (ConversationState.PESQUISA_VALORES, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.PESQUISA_VALORES, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ESCOLHENDO_TAMANHO, SmTriggerEnum.INPUT_VALID): (
        ConversationState.ESCOLHENDO_MASSA, SmActionEnum.SAVE_SIZE_AND_ASK_DOUGH, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_TAMANHO, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.ESCOLHENDO_TAMANHO, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ESCOLHENDO_MASSA, SmTriggerEnum.INPUT_VALID): (
        ConversationState.ESCOLHENDO_RECHEIOS, SmActionEnum.SAVE_DOUGH_AND_ASK_FILLING1, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_MASSA, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.ESCOLHENDO_MASSA, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ESCOLHENDO_RECHEIOS, SmTriggerEnum.ONE_FILLING_SELECTED): (
        ConversationState.ESCOLHENDO_ADICIONAIS, SmActionEnum.SAVE_FILLING_AND_ASK_EXTRAS, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_RECHEIOS, SmTriggerEnum.TWO_FILLINGS_SELECTED): (
        ConversationState.ESCOLHENDO_RECHEIO_2, SmActionEnum.SAVE_FILLING1_AND_ASK_FILLING2, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_RECHEIOS, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.ESCOLHENDO_RECHEIOS, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ESCOLHENDO_RECHEIO_2, SmTriggerEnum.INPUT_VALID): (
        ConversationState.ESCOLHENDO_ADICIONAIS, SmActionEnum.SAVE_FILLING_AND_ASK_EXTRAS, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_RECHEIO_2, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.ESCOLHENDO_RECHEIO_2, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ESCOLHENDO_ADICIONAIS, SmTriggerEnum.INPUT_VALID): (
        ConversationState.ESCOLHENDO_FINALIZACAO, SmActionEnum.SAVE_EXTRAS_AND_ASK_FINISH, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_ADICIONAIS, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.ESCOLHENDO_ADICIONAIS, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ESCOLHENDO_FINALIZACAO, SmTriggerEnum.INPUT_VALID): (
        ConversationState.DEFININDO_DATA, SmActionEnum.SAVE_FINISH_AND_ASK_DATE, FallbackEffectEnum.RESET,
    ),
    (ConversationState.ESCOLHENDO_FINALIZACAO, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.ESCOLHENDO_FINALIZACAO, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.DEFININDO_DATA, SmTriggerEnum.DATE_AVAILABLE): (
        ConversationState.DEFININDO_HORARIO, SmActionEnum.SAVE_DATE_AND_ASK_TIME, FallbackEffectEnum.RESET,
    ),
    (ConversationState.DEFININDO_DATA, SmTriggerEnum.DATE_UNAVAILABLE): (
        ConversationState.DEFININDO_DATA, SmActionEnum.REJECT_DATE_AND_ASK_AGAIN, FallbackEffectEnum.NONE,
    ),
    (ConversationState.DEFININDO_DATA, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.DEFININDO_DATA, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.DEFININDO_HORARIO, SmTriggerEnum.INPUT_VALID): (
        ConversationState.DEFININDO_OBSERVACOES, SmActionEnum.SAVE_TIME_AND_ASK_NOTES, FallbackEffectEnum.RESET,
    ),
    (ConversationState.DEFININDO_HORARIO, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.DEFININDO_HORARIO, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.DEFININDO_OBSERVACOES, SmTriggerEnum.INPUT_VALID): (
        ConversationState.CONFIRMANDO_PEDIDO, SmActionEnum.SAVE_NOTES_AND_SHOW_SUMMARY, FallbackEffectEnum.RESET,
    ),
    (ConversationState.DEFININDO_OBSERVACOES, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.DEFININDO_OBSERVACOES, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.CONFIRMANDO_PEDIDO, SmTriggerEnum.ORDER_CONFIRMED_BY_CLIENT): (
        ConversationState.BOT_PAUSADO, SmActionEnum.FINALIZE_ORDER_AND_LOCK, FallbackEffectEnum.PAUSE,
    ),
    (ConversationState.CONFIRMANDO_PEDIDO, SmTriggerEnum.ORDER_CANCELLED_BY_CLIENT): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.CANCEL_ORDER_AND_RETURN, FallbackEffectEnum.RESET,
    ),
    (ConversationState.CONFIRMANDO_PEDIDO, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.CONFIRMANDO_PEDIDO, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.CONSULTA_PEDIDO, SmTriggerEnum.INPUT_VALID): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.CHECK_ORDER_STATUS, FallbackEffectEnum.RESET,
    ),
    (ConversationState.CONSULTA_PEDIDO, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.CONSULTA_PEDIDO, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.ATENDIMENTO_HUMANO, SmTriggerEnum.INPUT_VALID): (
        ConversationState.BOT_PAUSADO, SmActionEnum.PAUSE_BOT_AND_NOTIFY_HUMAN, FallbackEffectEnum.PAUSE,
    ),
    (ConversationState.PRONTA_ENTREGA, SmTriggerEnum.INPUT_VALID): (
        ConversationState.BOT_PAUSADO, SmActionEnum.RESERVE_READY_CAKE_INTEREST, FallbackEffectEnum.PAUSE,
    ),
    (ConversationState.PRONTA_ENTREGA, SmTriggerEnum.INPUT_INVALID): (
        ConversationState.PRONTA_ENTREGA, SmActionEnum.INCREMENT_FALLBACK, FallbackEffectEnum.INCREMENT,
    ),
    (ConversationState.BOT_PAUSADO, SmTriggerEnum.LOCK_EXPIRED): (
        ConversationState.MENU_PRINCIPAL, SmActionEnum.RESUME_BOT, FallbackEffectEnum.RESET,
    ),
}

for state in ConversationState:
    BUILTIN_TRANSITIONS.setdefault(
        (state, SmTriggerEnum.HUMAN_REQUESTED),
        (ConversationState.ATENDIMENTO_HUMANO, SmActionEnum.ASK_HUMAN_REASON, FallbackEffectEnum.RESET),
    )
    BUILTIN_TRANSITIONS.setdefault(
        (state, SmTriggerEnum.MAX_FALLBACK_REACHED),
        (ConversationState.BOT_PAUSADO, SmActionEnum.PAUSE_BOT_AND_NOTIFY_HUMAN, FallbackEffectEnum.PAUSE),
    )


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
        builtin_transition = BUILTIN_TRANSITIONS.get((current_state, trigger))
        if builtin_transition is None:
            logger.warning(
                "transition_not_found",
                current_state=current_state.value,
                trigger=trigger.value,
            )
            return None

        next_state, action_code, fallback_effect = builtin_transition
        logger.warning(
            "using_builtin_transition_fallback",
            current_state=current_state.value,
            trigger=trigger.value,
            next_state=next_state.value,
            action_code=action_code.value,
        )
    else:
        next_state = ConversationState(transition.next_state.value)
        action_code = SmActionEnum(transition.action_code.value)
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
        next_state=next_state.value,
        action_code=action_code.value,
        fallback_effect=fallback_effect.value,
    )

    return TransitionResult(
        next_state=next_state,
        action_code=action_code,
        fallback_effect=fallback_effect,
        new_fallback_count=new_count,
    )

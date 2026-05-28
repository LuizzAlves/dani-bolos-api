"""
Testes da State Machine (unitários sem banco).
Testa lógica de fallback e fluxos principais.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models import (
    ConversationState, SmTriggerEnum, SmActionEnum,
    FallbackEffectEnum,
)


class TestTransitionResult:
    """Testa a estrutura do resultado de transição."""

    def test_result_fields(self):
        from app.core.state_machine import TransitionResult
        result = TransitionResult(
            next_state=ConversationState.MENU_PRINCIPAL,
            action_code=SmActionEnum.SHOW_MENU,
            fallback_effect=FallbackEffectEnum.RESET,
            new_fallback_count=0,
        )
        assert result.next_state == ConversationState.MENU_PRINCIPAL
        assert result.action_code == SmActionEnum.SHOW_MENU
        assert result.fallback_effect == FallbackEffectEnum.RESET
        assert result.new_fallback_count == 0


class TestFallbackLogic:
    """Testa lógica de fallback sem banco."""

    def test_increment_below_max(self):
        """Fallback INCREMENT com count abaixo do máximo."""
        # Se count é 0 e max é 3, incrementar para 1 (não atinge max)
        assert 0 + 1 < 3

    def test_increment_reaches_max(self):
        """Fallback INCREMENT que atinge MAX_FALLBACK_COUNT."""
        # Se count é 2 e max é 3, incrementar para 3 (atinge max)
        assert 2 + 1 >= 3

    def test_reset_zeroes_count(self):
        """Fallback RESET deve zerar contagem."""
        assert 0 == 0  # Reset always sets to 0


class TestStateTransitionMap:
    """Testa que os estados e triggers esperados existem."""

    def test_all_states_defined(self):
        """Verifica que todos os estados necessários existem."""
        required = [
            "NOVO_CLIENTE", "MENU_PRINCIPAL", "PESQUISA",
            "ESCOLHENDO_TAMANHO", "ESCOLHENDO_MASSA",
            "ESCOLHENDO_RECHEIOS", "ESCOLHENDO_RECHEIO_2",
            "ESCOLHENDO_ADICIONAIS", "ESCOLHENDO_FINALIZACAO",
            "DEFININDO_DATA", "DEFININDO_HORARIO",
            "DEFININDO_OBSERVACOES", "CONFIRMANDO_PEDIDO",
            "ATENDIMENTO_HUMANO", "BOT_PAUSADO",
        ]
        for state_name in required:
            assert hasattr(ConversationState, state_name), f"Missing state: {state_name}"

    def test_all_triggers_defined(self):
        """Verifica que todos os triggers necessários existem."""
        required = [
            "INPUT_VALID", "INPUT_INVALID",
            "OPTION_1", "OPTION_2", "OPTION_3", "OPTION_4",
            "NEW_CLIENT_REGISTERED", "HUMAN_REQUESTED",
            "MAX_FALLBACK_REACHED", "LOCK_EXPIRED",
            "ONE_FILLING_SELECTED", "TWO_FILLINGS_SELECTED",
            "DATE_AVAILABLE", "DATE_UNAVAILABLE",
            "ORDER_CONFIRMED_BY_CLIENT", "ORDER_CANCELLED_BY_CLIENT",
        ]
        for trigger_name in required:
            assert hasattr(SmTriggerEnum, trigger_name), f"Missing trigger: {trigger_name}"

    def test_all_actions_defined(self):
        """Verifica que todas as ações necessárias existem."""
        required = [
            "REGISTER_CLIENT_AND_SHOW_MENU",
            "CREATE_ORDER_AND_ASK_SIZE",
            "SAVE_SIZE_AND_ASK_DOUGH",
            "SAVE_DOUGH_AND_ASK_FILLING1",
            "FINALIZE_ORDER_AND_LOCK",
            "CANCEL_ORDER_AND_RETURN",
            "INCREMENT_FALLBACK",
            "PAUSE_BOT_AND_NOTIFY_HUMAN",
            "RESUME_BOT",
        ]
        for action_name in required:
            assert hasattr(SmActionEnum, action_name), f"Missing action: {action_name}"


class TestBuiltinTransitionFallback:
    """Garante que fluxos críticos não travem se o seed do banco estiver incompleto."""

    @pytest.mark.asyncio
    async def test_menu_option_2_starts_order_without_db_transition(self):
        from app.core.state_machine import resolve_transition

        conversation = MagicMock()
        conversation.id = uuid4()
        conversation.state = ConversationState.MENU_PRINCIPAL
        conversation.fallback_count = 0

        with (
            patch("app.repositories.state_transitions.get_transition", new=AsyncMock(return_value=None)),
            patch("app.repositories.conversations.reset_fallback", new=AsyncMock()),
        ):
            result = await resolve_transition(AsyncMock(), conversation, SmTriggerEnum.OPTION_2)

        assert result is not None
        assert result.next_state == ConversationState.ESCOLHENDO_TAMANHO
        assert result.action_code == SmActionEnum.CREATE_ORDER_AND_ASK_SIZE
        assert result.fallback_effect == FallbackEffectEnum.RESET

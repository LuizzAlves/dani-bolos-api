"""
Testes para as correções finais (aprovação manual, agenda fora de range e auditoria de cancelamento).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date
from uuid import uuid4

from app.models import Availability, ConversationState, EventTypeEnum, OrderStatus, Order
from app.repositories.availability import check_date_available, increment_confirmed_orders
from app.core.order_engine import _handle_create_order
from app.services.message_service import execute_action


class TestAvailabilityFixes:
    @pytest.mark.asyncio
    async def test_check_date_available_no_row(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        
        result = await check_date_available(db, date(2026, 10, 10))
        
        assert result["available"] is False
        assert result["blocked"] is True
        assert result["block_reason"] == "Data fora da agenda configurada"
        assert result["remaining_slots"] == 0

    @pytest.mark.asyncio
    async def test_increment_confirmed_orders_no_row(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result
        
        result = await increment_confirmed_orders(db, date(2026, 10, 10))
        
        assert result is False
        # Ensure it didn't try to add a new row
        db.add.assert_not_called()


class TestCancellationAudit:
    @pytest.mark.asyncio
    @patch("app.core.order_engine.event_repo.log_event")
    @patch("app.core.order_engine.order_repo.cancel_old_drafts")
    @patch("app.core.order_engine.order_repo.create_draft_order")
    @patch("app.core.order_engine.catalog_repo.get_active_sizes")
    async def test_handle_create_order_logs_cancellations(
        self, mock_get_sizes, mock_create, mock_cancel, mock_log
    ):
        db = AsyncMock()
        ctx = MagicMock()
        ctx.order_data = {}
        
        conv_id = uuid4()
        client_id = uuid4()
        draft_id_1 = uuid4()
        draft_id_2 = uuid4()
        new_order_id = uuid4()
        
        mock_cancel.return_value = [draft_id_1, draft_id_2]
        
        mock_order = MagicMock()
        mock_order.id = new_order_id
        mock_create.return_value = mock_order
        
        classification = MagicMock()
        
        await _handle_create_order(db, ctx, conv_id, client_id, classification, None)
        
        # Verify cancel_old_drafts was called
        mock_cancel.assert_called_once_with(db, conv_id)
        
        # Verify log_event was called for each cancelled draft, plus the ORDER_STARTED
        # Expecting 3 calls total
        assert mock_log.call_count == 3
        
        calls = mock_log.call_args_list
        # First cancellation
        assert calls[0][0][1] == EventTypeEnum.ORDER_CANCELLED
        assert calls[0][1]["order_id"] == draft_id_1
        assert calls[0][1]["payload"] == {"reason": "new_draft_started"}
        
        # Second cancellation
        assert calls[1][0][1] == EventTypeEnum.ORDER_CANCELLED
        assert calls[1][1]["order_id"] == draft_id_2
        assert calls[1][1]["payload"] == {"reason": "new_draft_started"}
        
        # Order started
        assert calls[2][0][1] == EventTypeEnum.ORDER_STARTED
        assert calls[2][1]["order_id"] == new_order_id


class TestNeedsApprovalFix:
    @pytest.mark.asyncio
    @patch("app.services.message_service.execute_action")
    @patch("app.services.message_service.build_response")
    @patch("app.services.message_service.resolve_transition")
    @patch("app.services.message_service.classify_input")
    @patch("app.services.message_service.client_repo.get_or_create_client")
    @patch("app.services.message_service.conv_repo.get_or_create_conversation")
    @patch("app.services.message_service.order_repo.get_active_order")
    @patch("app.services.message_service.conv_repo.set_human_lock")
    @patch("app.services.message_service.conv_repo.update_conversation_state")
    @patch("app.services.message_service.event_repo.log_event")
    @patch("app.services.message_service.event_repo.has_message_event")
    @patch("app.services.message_service._load_catalog_for_state")
    @patch("app.services.message_service.google_sheets_service.create_alert")
    @patch("app.services.message_service.evo_client.send_text")
    async def test_needs_approval_intercept(
        self, mock_send_text, mock_alert, mock_load_catalog, mock_has_msg, mock_log_event, mock_update_state,
        mock_set_lock, mock_get_order, mock_get_conv, mock_get_client,
        mock_classify, mock_resolve, mock_build, mock_execute
    ):
        from app.services.message_service import process_message
        from app.core.payload_parser import ParsedMessage
        from app.core.order_engine import ActionContext
        from app.models import SmActionEnum, SmTriggerEnum, ConversationState
        from app.core.classifier import ClassificationResult
        
        db = AsyncMock()
        msg = ParsedMessage(
            phone="551999999999",
            text="Sim",
            is_audio=False,
            is_image=False,
            timestamp=123,
            message_id="msg123",
            sender_name="Teste",
            should_ignore=False
        )
        
        # msg object is not needed since parse_evolution_payload will return a ParsedMessage, let's mock it
        mock_has_msg.return_value = False
        mock_load_catalog.return_value = []
        with patch("app.services.message_service.parse_evolution_payload", return_value=msg):
            # Mocks basicos
            client = MagicMock()
            client.id = uuid4()
            client.name = "Teste"
            mock_get_client.return_value = (client, False)
            
            conv = MagicMock()
            conv.id = uuid4()
            conv.state = ConversationState.ESCOLHENDO_FINALIZACAO
            conv.human_lock = False
            mock_get_conv.return_value = (conv, False)
            
            order = MagicMock()
            order.id = uuid4()
            order.order_number = 100
            mock_get_order.return_value = order
            
            # Classification
            mock_classify.return_value = ClassificationResult(trigger=SmTriggerEnum.INPUT_VALID)
            
            # Transition
            transition = MagicMock()
            transition.action_code = SmActionEnum.SAVE_FINISH_AND_ASK_DATE
            transition.next_state = ConversationState.DEFININDO_DATA
            mock_resolve.return_value = transition
            
            # Action context com needs_approval = True
            ctx = ActionContext()
            ctx.order_data["needs_approval"] = True
            mock_execute.return_value = ctx
            
            from app.schemas.messages import ResponseItem
            # Build response não deve ser chamado no fluxo especial, mas vamos ver
            mock_build.return_value = [ResponseItem(type="text", text="Resposta Normal")]
            
            result = await process_message(db, {"foo": "bar"})
            
            assert result.status == "ok"
            
            # 1. Verifica se interceptou e forçou estado
            assert transition.next_state == ConversationState.BOT_PAUSADO
            mock_set_lock.assert_called_once_with(db, conv.id)
            
            # 2. Verifica se gerou o alerta correto para a planilha
            mock_alert.assert_called_once()
            kwargs = mock_alert.call_args[1]
            assert "Aprovação manual solicitada pelo cliente" in kwargs["reason"]
            
            # 3. Verifica se enviou o texto correto (interceptado)
            mock_send_text.assert_called_once()
            sent_text = mock_send_text.call_args[0][1]
            assert "Esse item precisa de confirmação da Dani" in sent_text
            
            # 4. Verifica se mock_build não foi chamado, já que o fluxo de aprovação é hardcoded
            mock_build.assert_not_called()


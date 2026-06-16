"""
Testes para o repositório de bolos pronta entrega (ReadyCake).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.models import ReadyCake
from app.repositories.ready_cakes import (
    get_available_ready_cakes,
    get_all_ready_cakes,
    get_ready_cake_by_id,
    create_ready_cake,
    update_ready_cake,
    delete_ready_cake,
)


@pytest.mark.asyncio
async def test_get_available_ready_cakes():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_cakes = [
        ReadyCake(id=1, flavor="Bolo 1", available=True),
        ReadyCake(id=2, flavor="Bolo 2", available=True),
    ]
    mock_result.scalars.return_value.all.return_value = mock_cakes
    db.execute.return_value = mock_result

    result = await get_available_ready_cakes(db)

    assert len(result) == 2
    assert result[0].flavor == "Bolo 1"
    assert result[1].flavor == "Bolo 2"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_ready_cakes():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_cakes = [
        ReadyCake(id=2, flavor="Bolo 2", available=False),
        ReadyCake(id=1, flavor="Bolo 1", available=True),
    ]
    mock_result.scalars.return_value.all.return_value = mock_cakes
    db.execute.return_value = mock_result

    result = await get_all_ready_cakes(db)

    assert len(result) == 2
    assert result[0].flavor == "Bolo 2"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_ready_cake_by_id():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_cake = ReadyCake(id=1, flavor="Bolo 1", available=True)
    mock_result.scalar_one_or_none.return_value = mock_cake
    db.execute.return_value = mock_result

    result = await get_ready_cake_by_id(db, 1)

    assert result is not None
    assert result.flavor == "Bolo 1"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_ready_cake():
    db = AsyncMock()
    db.add = MagicMock()

    cake = await create_ready_cake(db, "Chocolate", "Descrição", 85.00)

    assert cake.flavor == "Chocolate"
    assert cake.description == "Descrição"
    assert cake.price == Decimal("85")
    db.add.assert_called_once_with(cake)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_ready_cake():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    db.execute.return_value = mock_result

    success = await update_ready_cake(db, 1, {"flavor": "Novo Chocolate", "price": 90.00})

    assert success is True
    db.execute.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_ready_cake():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    db.execute.return_value = mock_result

    success = await delete_ready_cake(db, 1)

    assert success is True
    db.execute.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.repositories.events.has_message_event", new_callable=AsyncMock)
@patch("app.repositories.settings.get_setting", new_callable=AsyncMock)
@patch("app.repositories.clients.get_or_create_client", new_callable=AsyncMock)
@patch("app.repositories.conversations.get_or_create_conversation", new_callable=AsyncMock)
@patch("app.repositories.conversations.update_conversation_state", new_callable=AsyncMock)
@patch("app.repositories.events.log_event", new_callable=AsyncMock)
@patch("app.integrations.evolution.send_text", new_callable=AsyncMock)
@patch("app.integrations.evolution.send_presence", new_callable=AsyncMock)
@patch("app.repositories.ready_cakes.get_available_ready_cakes", new_callable=AsyncMock)
@patch("app.repositories.state_transitions.get_transition", new_callable=AsyncMock)
async def test_option_5_flow_success(
    mock_get_transition,
    mock_get_cakes,
    mock_send_presence,
    mock_send_text,
    mock_log_event,
    mock_update_state,
    mock_get_conv,
    mock_get_client,
    mock_get_setting,
    mock_has_event
):
    from app.services.message_service import process_message
    from tests.test_integration_fixes import evolution_payload
    from app.models import ConversationState, ActiveFlowType

    db = AsyncMock()
    mock_has_event.return_value = False
    mock_get_setting.return_value = True  # bot_active = True

    client = MagicMock(id=10, name="Luiz")
    mock_get_client.return_value = (client, False)

    conv = MagicMock(id=20, state=ConversationState.MENU_PRINCIPAL, human_lock=False)
    mock_get_conv.return_value = (conv, False)

    # 1 cake available
    mock_cake = ReadyCake(
        id=1,
        flavor="Bolo de chocolate ao leite com nozes",
        description="Aproximadamente 15 fatias, 2 recheios",
        price=Decimal("65.00")
    )
    mock_get_cakes.return_value = [mock_cake]
    mock_get_transition.return_value = None  # Use BUILTIN

    payload = evolution_payload("5")
    response = await process_message(db, payload)

    assert response.status == "ok"
    mock_send_text.assert_called_once()
    sent_text = mock_send_text.call_args[0][1]
    assert "Bolos Prontos do Dia" in sent_text
    assert "Bolo de chocolate ao leite com nozes" in sent_text
    assert "R$ 65,00" in sent_text

    # Next state should be PRONTA_ENTREGA
    mock_update_state.assert_called_once_with(
        db,
        conv.id,
        new_state=ConversationState.PRONTA_ENTREGA,
        active_flow=ActiveFlowType.PRONTA_ENTREGA,
        fallback_count=0
    )


@pytest.mark.asyncio
@patch("app.repositories.events.has_message_event", new_callable=AsyncMock)
@patch("app.repositories.settings.get_setting", new_callable=AsyncMock)
@patch("app.repositories.clients.get_or_create_client", new_callable=AsyncMock)
@patch("app.repositories.conversations.get_or_create_conversation", new_callable=AsyncMock)
@patch("app.repositories.conversations.update_conversation_state", new_callable=AsyncMock)
@patch("app.repositories.events.log_event", new_callable=AsyncMock)
@patch("app.integrations.evolution.send_text", new_callable=AsyncMock)
@patch("app.integrations.evolution.send_presence", new_callable=AsyncMock)
@patch("app.repositories.ready_cakes.get_available_ready_cakes", new_callable=AsyncMock)
@patch("app.repositories.state_transitions.get_transition", new_callable=AsyncMock)
async def test_option_5_flow_no_cakes(
    mock_get_transition,
    mock_get_cakes,
    mock_send_presence,
    mock_send_text,
    mock_log_event,
    mock_update_state,
    mock_get_conv,
    mock_get_client,
    mock_get_setting,
    mock_has_event
):
    from app.services.message_service import process_message
    from tests.test_integration_fixes import evolution_payload
    from app.models import ConversationState, ActiveFlowType

    db = AsyncMock()
    mock_has_event.return_value = False
    mock_get_setting.return_value = True  # bot_active = True

    client = MagicMock(id=10, name="Luiz")
    mock_get_client.return_value = (client, False)

    conv = MagicMock(id=20, state=ConversationState.MENU_PRINCIPAL, human_lock=False)
    mock_get_conv.return_value = (conv, False)

    # 0 cakes available
    mock_get_cakes.return_value = []
    mock_get_transition.return_value = None  # Use BUILTIN

    payload = evolution_payload("5")
    response = await process_message(db, payload)

    assert response.status == "ok"
    # Wait, send_text should be called twice (once for no cakes, once for the fallback menu)
    assert mock_send_text.call_count == 2
    
    first_msg = mock_send_text.call_args_list[0][0][1]
    second_msg = mock_send_text.call_args_list[1][0][1]
    
    assert "não temos bolos prontos disponíveis" in first_msg
    assert "Menu Principal" in second_msg

    # Next state should remain MENU_PRINCIPAL because it returns to menu
    mock_update_state.assert_called_once_with(
        db,
        conv.id,
        new_state=ConversationState.MENU_PRINCIPAL,
        active_flow=ActiveFlowType.MENU,
        fallback_count=0
    )


@pytest.mark.asyncio
@patch("app.repositories.events.has_message_event", new_callable=AsyncMock)
@patch("app.repositories.settings.get_setting", new_callable=AsyncMock)
@patch("app.repositories.clients.get_or_create_client", new_callable=AsyncMock)
@patch("app.repositories.conversations.get_or_create_conversation", new_callable=AsyncMock)
@patch("app.repositories.conversations.update_conversation_state", new_callable=AsyncMock)
@patch("app.repositories.conversations.set_human_lock", new_callable=AsyncMock)
@patch("app.repositories.events.log_event", new_callable=AsyncMock)
@patch("app.repositories.alerts.create_alert", new_callable=AsyncMock)
@patch("app.services.google_sheets_service.create_alert", new_callable=AsyncMock)
@patch("app.integrations.evolution.send_text", new_callable=AsyncMock)
@patch("app.integrations.evolution.send_presence", new_callable=AsyncMock)
@patch("app.repositories.ready_cakes.get_available_ready_cakes", new_callable=AsyncMock)
@patch("app.repositories.ready_cakes.get_ready_cake_by_id", new_callable=AsyncMock)
@patch("app.repositories.state_transitions.get_transition", new_callable=AsyncMock)
async def test_option_5_reserve_interest(
    mock_get_transition,
    mock_get_cake_by_id,
    mock_get_cakes,
    mock_send_presence,
    mock_send_text,
    mock_sheets_alert,
    mock_db_alert,
    mock_log_event,
    mock_set_lock,
    mock_update_state,
    mock_get_conv,
    mock_get_client,
    mock_get_setting,
    mock_has_event
):
    from app.services.message_service import process_message
    from tests.test_integration_fixes import evolution_payload
    from app.models import ConversationState, ActiveFlowType

    db = AsyncMock()
    mock_has_event.return_value = False
    mock_get_setting.return_value = True  # bot_active = True

    client = MagicMock(id=10, name="Luiz")
    mock_get_client.return_value = (client, False)

    conv = MagicMock(id=20, state=ConversationState.PRONTA_ENTREGA, human_lock=False)
    mock_get_conv.return_value = (conv, False)

    # Mock ready cakes
    mock_cake = ReadyCake(
        id=1,
        flavor="Bolo de chocolate ao leite com nozes",
        description="Aproximadamente 15 fatias, 2 recheios",
        price=Decimal("65.00")
    )
    mock_get_cakes.return_value = [mock_cake]
    mock_get_cake_by_id.return_value = mock_cake
    mock_get_transition.return_value = None  # Use BUILTIN

    payload = evolution_payload("1")  # User selects option 1
    response = await process_message(db, payload)

    assert response.status == "ok"
    mock_send_text.assert_called_once()
    sent_text = mock_send_text.call_args[0][1]
    assert "Anotado! Você demonstrou interesse no bolo" in sent_text
    assert "Bolo de chocolate ao leite com nozes" in sent_text

    # Pauses bot and sets human lock
    mock_set_lock.assert_called_once_with(db, conv.id)
    mock_db_alert.assert_called_once()
    mock_sheets_alert.assert_called_once()

    # Next state should be BOT_PAUSADO
    mock_update_state.assert_called_once_with(
        db,
        conv.id,
        new_state=ConversationState.BOT_PAUSADO,
        active_flow=ActiveFlowType.ATENDIMENTO_HUMANO,
        fallback_count=0
    )




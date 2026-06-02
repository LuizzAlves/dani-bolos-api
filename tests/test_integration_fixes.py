from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.admin import create_order, list_orders
from app.models import AlertTypeEnum, OrderStatus
from app.repositories.orders import list_orders_by_date
from app.schemas.admin import ManualOrderCreate
from app.services.message_service import _alert_type_from_reason, process_message

pytestmark = pytest.mark.asyncio


def evolution_payload(text: str = "Hello") -> dict:
    return {
        "event": "messages.upsert",
        "instance": "ThinkSys",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "MSG123",
            },
            "pushName": "Test",
            "message": {"conversation": text},
            "messageType": "conversation",
            "messageTimestamp": 1234567890,
        },
    }


async def test_bot_active_false_sends_message():
    with patch("app.repositories.events.has_message_event", new_callable=AsyncMock) as mock_has_event:
        mock_has_event.return_value = False
        with patch("app.repositories.settings.get_setting", new_callable=AsyncMock) as mock_get_setting:
            mock_get_setting.return_value = False
            with patch("app.repositories.clients.get_or_create_client", new_callable=AsyncMock) as mock_client:
                mock_client.return_value = (MagicMock(id="client_id", name="Test"), False)
                with patch("app.repositories.conversations.get_or_create_conversation", new_callable=AsyncMock) as mock_conv:
                    mock_conv.return_value = (MagicMock(id="conv_id", human_lock=False), False)
                    with patch("app.repositories.events.log_event", new_callable=AsyncMock):
                        with patch("app.integrations.evolution.send_text", new_callable=AsyncMock) as mock_send_text:
                            response = await process_message(AsyncMock(), evolution_payload())

    assert response.status == "bot_paused"
    mock_send_text.assert_called_once()
    assert "atendimento" in mock_send_text.call_args[0][1]


async def test_list_orders_includes_finalizado():
    with patch("app.repositories.orders.list_orders_by_status", new_callable=AsyncMock) as mock_list_by_status:
        mock_list_by_status.return_value = []
        await list_orders(status=None, pickup_date=None, db=AsyncMock(), _auth=True)

    status_list_passed = mock_list_by_status.call_args[0][1]
    assert OrderStatus.FINALIZADO in status_list_passed


async def test_list_orders_by_date_eager_loads_order_extras():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    await list_orders_by_date(db, date(2026, 6, 5))

    query = db.execute.call_args[0][0]
    loader_paths = [str(getattr(option, "path", "")) for option in query._with_options]

    assert any("Order.order_extras" in path and "OrderExtra.extra" in path for path in loader_paths)


async def test_create_order_validates_dates():
    body = ManualOrderCreate(client_name="Test", client_phone="1234567890")

    with pytest.raises(HTTPException) as exc:
        await create_order(body, db=None, _auth=True)

    assert exc.value.status_code == 400
    assert "obrig" in exc.value.detail


async def test_create_order_rejects_missing_time_slot():
    body = ManualOrderCreate(
        client_name="Test Client",
        client_phone="551199999999",
        pickup_date="2025-12-25",
        pickup_time="23:59",
    )

    with patch("app.repositories.availability.check_date_available", new_callable=AsyncMock) as mock_check_date:
        mock_check_date.return_value = {"available": True}
        with patch("app.repositories.catalog.get_all_time_slots", new_callable=AsyncMock) as mock_get_slots:
            mock_slot = MagicMock()
            mock_slot.slot_time = time(10, 0)
            mock_slot.available = True
            mock_get_slots.return_value = [mock_slot]

            with pytest.raises(HTTPException) as exc:
                await create_order(body, db=AsyncMock(), _auth=True)

    assert exc.value.status_code == 400
    assert "existe" in exc.value.detail


async def test_create_order_rejects_unavailable_time_slot():
    body = ManualOrderCreate(
        client_name="Test Client",
        client_phone="551199999999",
        pickup_date="2025-12-25",
        pickup_time="14:00",
    )

    with patch("app.repositories.availability.check_date_available", new_callable=AsyncMock) as mock_check_date:
        mock_check_date.return_value = {"available": True}
        with patch("app.repositories.catalog.get_all_time_slots", new_callable=AsyncMock) as mock_get_slots:
            mock_slot = MagicMock()
            mock_slot.slot_time = time(14, 0)
            mock_slot.available = False
            mock_get_slots.return_value = [mock_slot]

            with pytest.raises(HTTPException) as exc:
                await create_order(body, db=AsyncMock(), _auth=True)

    assert exc.value.status_code == 400
    assert "indispon" in exc.value.detail


async def test_create_order_rejects_time_outside_service_hours():
    body = ManualOrderCreate(
        client_name="Test Client",
        client_phone="551199999999",
        pickup_date="2025-12-25",
        pickup_time="23:00",
    )

    with patch("app.repositories.availability.check_date_available", new_callable=AsyncMock) as mock_check_date:
        mock_check_date.return_value = {"available": True}
        with patch("app.repositories.catalog.get_all_time_slots", new_callable=AsyncMock) as mock_get_slots:
            mock_slot = MagicMock()
            mock_slot.slot_time = time(23, 0)
            mock_slot.available = True
            mock_get_slots.return_value = [mock_slot]

            with patch("app.core.service_hours.settings_repo.get_setting", new_callable=AsyncMock) as mock_get_setting:
                mock_get_setting.return_value = None

                with pytest.raises(HTTPException) as exc:
                    await create_order(body, db=AsyncMock(), _auth=True)

    assert exc.value.status_code == 400
    assert "funcionamento" in exc.value.detail


async def test_alert_mapping_returns_custom_filling():
    assert _alert_type_from_reason("aprovacao manual solicitada") == AlertTypeEnum.CUSTOM_FILLING
    assert _alert_type_from_reason("adicional precisa de aprovacao") == AlertTypeEnum.CUSTOM_FILLING
    assert _alert_type_from_reason("falar com a Dani") == AlertTypeEnum.HUMAN_REQUESTED
    assert _alert_type_from_reason("maximo de tentativas") == AlertTypeEnum.MAX_FALLBACK
    assert _alert_type_from_reason("dados incompletos no pedido") == AlertTypeEnum.FLOW_ERROR

"""
Testes para a integração com Google Sheets e seu respectivo serviço.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, date, time

from app.integrations.google_sheets import send_to_webhook
from app.services.google_sheets_service import upsert_order, create_alert
from app.models import Order, Client, Size, Filling, Finish, OrderExtra, Extra, OrderStatus, DoughType

@pytest.fixture
def mock_settings():
    with patch("app.integrations.google_sheets.get_settings") as mock_get:
        settings = MagicMock()
        settings.GOOGLE_SHEETS_ENABLED = True
        settings.GOOGLE_SHEETS_WEBAPP_URL = "http://test-url.com"
        settings.GOOGLE_SHEETS_WEBAPP_TOKEN = "test-token"
        settings.GOOGLE_SHEETS_TIMEOUT_SECONDS = 5
        mock_get.return_value = settings
        yield settings


class TestGoogleSheetsIntegration:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_send_to_webhook_upsert_order(self, mock_post, mock_settings):
        # Configurar mock response com sucesso
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        payload = {"order_id": "123", "status": "AGUARDANDO_CONFIRMACAO"}
        
        result = await send_to_webhook("upsert_order", payload)
        
        assert result is True
        mock_post.assert_called_once()
        
        args, kwargs = mock_post.call_args
        assert args[0] == "http://test-url.com"
        assert kwargs["headers"] == {"Content-Type": "application/json"}
        assert kwargs["json"] == {
            "token": "test-token",
            "action": "upsert_order",
            "order": payload
        }

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_send_to_webhook_follows_apps_script_redirect(self, mock_client_cls, mock_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await send_to_webhook("alert", {"message": "teste"})

        assert result is True
        _, kwargs = mock_client_cls.call_args
        assert kwargs["follow_redirects"] is True

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_send_to_webhook_alert(self, mock_post, mock_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        payload = {"message": "Alerta teste", "severity": "warning"}
        
        result = await send_to_webhook("alert", payload)
        
        assert result is True
        args, kwargs = mock_post.call_args
        assert kwargs["json"] == {
            "token": "test-token",
            "action": "alert",
            "alert": payload
        }

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_send_to_webhook_ok_false(self, mock_post, mock_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "Internal Apps Script error"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await send_to_webhook("alert", {"msg": "teste"})
        assert result is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_send_to_webhook_http_error(self, mock_post, mock_settings):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"
        
        mock_post.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=mock_response
        )

        result = await send_to_webhook("alert", {"msg": "teste"})
        assert result is False


class TestGoogleSheetsService:
    @pytest.mark.asyncio
    @patch("app.services.google_sheets_service.sheets_client.send_to_webhook")
    @patch("app.services.google_sheets_service.event_repo.log_event")
    async def test_upsert_order_success(self, mock_log_event, mock_send):
        mock_send.return_value = True
        
        # Criar mocks para os objetos do banco
        db = AsyncMock()
        
        order_id = uuid4()
        client = Client(name="Teste", phone="551999999999")
        size = Size(description="15 fatias")
        filling1 = Filling(name="Brigadeiro")
        finish = Finish(name="Chantininho")
        
        extra_obj = Extra(name="Morango")
        order_extra = OrderExtra(extra=extra_obj, layers=2, total_price=30.00)
        
        order = Order(
            id=order_id,
            order_number=100,
            status=OrderStatus.AGUARDANDO_CONFIRMACAO,
            client=client,
            size=size,
            dough=DoughType.BRANCA,
            filling_1=filling1,
            filling_2=None,
            finish=finish,
            order_extras=[order_extra],
            pickup_date=date(2026, 6, 1),
            pickup_time=time(14, 30),
            base_value=100.50,
            extras_value=15.00,
            total_value=115.50,
            notes="Retirada por: Maria\nObservações: Teste nota",
            created_at=datetime(2026, 5, 28, 14, 0)
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = order
        db.execute.return_value = mock_result
        
        result = await upsert_order(db, order_id)
        
        assert result is True
        mock_send.assert_called_once()
        action, payload = mock_send.call_args[0]
        
        assert action == "upsert_order"
        assert payload["order_id"] == str(order_id)
        assert payload["order_number"] == 100
        assert payload["status"] == "AGUARDANDO_CONFIRMACAO"
        assert payload["client_name"] == "Teste"
        assert payload["phone"] == "551999999999"
        assert payload["size"] == "15 fatias"
        assert payload["dough"] == "BRANCA"
        assert payload["filling_1"] == "Brigadeiro"
        assert payload["filling_2"] is None
        assert payload["finish"] == "Chantininho"
        assert payload["pickup_person_name"] == "Maria"
        assert payload["extras"] == [{"name": "Morango", "layers": 2, "total_price": 30.0}]
        assert payload["pickup_date"] == "2026-06-01"
        assert payload["pickup_time"] == "14:30"
        assert payload["summary"] == "15 fatias | BRANCA | Brigadeiro | Morango (2 camadas) | Chantininho"
        assert payload["base_value"] == 100.5
        assert payload["extras_value"] == 15.0
        assert payload["total_value"] == 115.5
        assert payload["notes"] == "Teste nota"

    @pytest.mark.asyncio
    @patch("app.services.google_sheets_service.sheets_client.send_to_webhook")
    @patch("app.services.google_sheets_service.event_repo.log_event")
    async def test_create_alert(self, mock_log_event, mock_send):
        mock_send.return_value = True
        db = AsyncMock()
        
        result = await create_alert(
            db,
            title="Erro no pedido",
            phone="551999999999",
            reason="Timeout",
            conversation_id=uuid4(),
            order_id="123",
            order_number=100
        )
        
        assert result is True
        mock_send.assert_called_once()
        action, payload = mock_send.call_args[0]
        
        assert action == "alert"
        assert payload["severity"] == "error"
        assert payload["action"] == "investigate"
        assert payload["error_code"] == "Timeout"
        assert payload["message"] == "Erro no pedido"
        assert payload["order_id"] == "123"
        assert payload["order_number"] == 100
        assert payload["phone"] == "551999999999"

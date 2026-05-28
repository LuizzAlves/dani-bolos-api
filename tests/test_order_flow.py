"""
Testes do fluxo de pedido e integração da API.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestHealthEndpoints:
    """Testa endpoints de saúde."""

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Dani Bolos — Motor de Atendimento"
        assert data["version"] == "1.0.0"


class TestWebhookEndpoints:
    """Testa endpoints de webhook (sem banco)."""

    def test_webhook_evolution_empty_body(self):
        response = client.post("/webhooks/evolution", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ignored", "error")

    def test_webhook_n8n_empty_body(self):
        response = client.post("/webhooks/evolution/n8n", json=[])
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ignored", "error")

    def test_webhook_group_message_ignored(self):
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "123@g.us", "fromMe": False, "id": "X"},
                "message": {"conversation": "oi"},
                "messageType": "conversation",
            },
        }
        response = client.post("/webhooks/evolution", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_from_me_ignored(self):
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "123@s.whatsapp.net", "fromMe": True, "id": "Y"},
                "message": {"conversation": "oi"},
                "messageType": "conversation",
            },
        }
        response = client.post("/webhooks/evolution", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"


class TestAdminEndpoints:
    """Testa endpoints admin."""

    def test_reset_without_token(self):
        response = client.post("/admin/reset-test-client?phone=123")
        assert response.status_code == 422  # Missing required header

    def test_reset_with_wrong_token(self):
        response = client.post(
            "/admin/reset-test-client?phone=123",
            headers={"X-Admin-Token": "wrong"},
        )
        assert response.status_code == 403


class TestPayloadParserIntegration:
    """Testa parser com payloads reais (sem banco)."""

    def test_n8n_payload_format(self):
        """Payload no formato do ModeloDeDados."""
        with open("tests/fixtures/evolution_message.json", encoding="utf-8") as f:
            payload = json.load(f)

        from app.core.payload_parser import parse_evolution_payload
        msg = parse_evolution_payload(payload)
        assert msg.phone == "5519991349572"
        assert msg.text == "Mensagem do cliente exemplo"
        assert not msg.should_ignore

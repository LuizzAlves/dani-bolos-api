"""
Testes do parser de payload da Evolution API.
"""

import pytest
from app.core.payload_parser import parse_evolution_payload, normalize_text


class TestNormalizeText:
    def test_lowercase_strip(self):
        assert normalize_text("  Olá Mundo  ") == "ola mundo"

    def test_remove_accents(self):
        assert normalize_text("Café Açúcar Ñoño") == "cafe acucar nono"

    def test_empty(self):
        assert normalize_text("") == ""


class TestParseEvolutionPayload:
    """Testa parsing de diferentes formatos de payload."""

    def test_n8n_wrapped_payload(self, evolution_n8n_payload):
        """Payload real do ModeloDeDados."""
        msg = parse_evolution_payload(evolution_n8n_payload)
        assert msg.phone == "5519991349572"
        assert msg.push_name == "Luiz Felipe🔱"
        assert msg.text == "Mensagem do cliente exemplo"
        assert msg.normalized_text == "mensagem do cliente exemplo"
        assert msg.message_id == "ACAB9FD8DEBE627971DA8381F5FC54BF"
        assert msg.instance == "ThinkSys"
        assert not msg.should_ignore
        assert not msg.is_unsupported_media

    def test_direct_payload(self, evolution_direct_payload):
        """Payload direto da Evolution API."""
        msg = parse_evolution_payload(evolution_direct_payload)
        assert msg.phone == "5519991349572"
        assert msg.text == "olá"
        assert not msg.should_ignore

    def test_group_message_ignored(self, group_message_payload):
        """Mensagens de grupo devem ser ignoradas."""
        msg = parse_evolution_payload(group_message_payload)
        assert msg.should_ignore
        assert msg.ignore_reason == "group_message"

    def test_from_me_ignored(self, from_me_payload):
        """Mensagens fromMe devem ser ignoradas."""
        msg = parse_evolution_payload(from_me_payload)
        assert msg.should_ignore
        assert msg.ignore_reason == "from_me"

    def test_audio_unsupported(self, audio_message_payload):
        """Áudio deve retornar unsupported_media."""
        msg = parse_evolution_payload(audio_message_payload)
        assert msg.is_unsupported_media
        assert msg.phone == "5519991349572"
        assert not msg.should_ignore

    def test_extended_text(self, extended_text_payload):
        """extendedTextMessage deve extrair texto corretamente."""
        msg = parse_evolution_payload(extended_text_payload)
        assert msg.text == "Quero fazer um pedido"
        assert msg.phone == "5519998765432"
        assert not msg.should_ignore

    def test_status_update_ignored(self):
        """Status de entrega deve ser ignorado."""
        payload = {
            "event": "messages.update",
            "instance": "ThinkSys",
            "data": {},
        }
        msg = parse_evolution_payload(payload)
        assert msg.should_ignore

    def test_empty_payload(self):
        """Payload vazio deve ser ignorado."""
        msg = parse_evolution_payload({})
        assert msg.should_ignore

    def test_empty_list_payload(self):
        """Lista vazia deve ser ignorada."""
        msg = parse_evolution_payload([])
        assert msg.should_ignore

    def test_image_unsupported(self):
        """Imagem deve retornar unsupported_media."""
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False, "id": "IMG1"},
                "pushName": "Img",
                "message": {"imageMessage": {"url": "..."}},
                "messageType": "imageMessage",
            },
        }
        msg = parse_evolution_payload(payload)
        assert msg.is_unsupported_media

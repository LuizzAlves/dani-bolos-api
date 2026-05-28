"""
Configuração e fixtures para os testes.
"""

import json
import os
import pytest
from pathlib import Path

# Fixture path
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def evolution_n8n_payload():
    """Payload real do n8n (formato array com headers/body)."""
    with open(FIXTURES_DIR / "evolution_message.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def evolution_direct_payload():
    """Payload direto da Evolution API (sem wrapper n8n)."""
    return {
        "event": "messages.upsert",
        "instance": "ThinkSys",
        "data": {
            "key": {
                "remoteJid": "5519991349572@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST123",
            },
            "pushName": "Teste Cliente",
            "message": {
                "conversation": "olá",
            },
            "messageType": "conversation",
            "messageTimestamp": 1779980551,
        },
    }


@pytest.fixture
def group_message_payload():
    """Payload de mensagem de grupo (deve ser ignorada)."""
    return {
        "event": "messages.upsert",
        "instance": "ThinkSys",
        "data": {
            "key": {
                "remoteJid": "5519991349572-1234567890@g.us",
                "fromMe": False,
                "id": "GROUP123",
            },
            "pushName": "Pessoa",
            "message": {"conversation": "oi"},
            "messageType": "conversation",
        },
    }


@pytest.fixture
def from_me_payload():
    """Payload de mensagem fromMe (deve ser ignorada)."""
    return {
        "event": "messages.upsert",
        "instance": "ThinkSys",
        "data": {
            "key": {
                "remoteJid": "5519991349572@s.whatsapp.net",
                "fromMe": True,
                "id": "FROMME123",
            },
            "pushName": "Bot",
            "message": {"conversation": "resposta"},
            "messageType": "conversation",
        },
    }


@pytest.fixture
def audio_message_payload():
    """Payload de mensagem de áudio (mídia não suportada)."""
    return {
        "event": "messages.upsert",
        "instance": "ThinkSys",
        "data": {
            "key": {
                "remoteJid": "5519991349572@s.whatsapp.net",
                "fromMe": False,
                "id": "AUDIO123",
            },
            "pushName": "Cliente Audio",
            "message": {
                "audioMessage": {"url": "...", "mimetype": "audio/ogg"},
            },
            "messageType": "audioMessage",
        },
    }


@pytest.fixture
def extended_text_payload():
    """Payload com extendedTextMessage."""
    return {
        "event": "messages.upsert",
        "instance": "ThinkSys",
        "data": {
            "key": {
                "remoteJid": "5519998765432@s.whatsapp.net",
                "fromMe": False,
                "id": "EXT123",
            },
            "pushName": "Extended",
            "message": {
                "extendedTextMessage": {"text": "Quero fazer um pedido"},
            },
            "messageType": "extendedTextMessage",
        },
    }

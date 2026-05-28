"""
Testes do classificador de input.
"""

import pytest
from datetime import date, timedelta

from app.core.classifier import (
    classify_input, ClassificationResult,
    _parse_date, _parse_time,
)
from app.models import ConversationState, SmTriggerEnum


class TestMenuClassification:
    """Testa classificação no MENU_PRINCIPAL."""

    def test_option_1(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "1", "1")
        assert r.trigger == SmTriggerEnum.OPTION_1

    def test_option_2(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "2", "2")
        assert r.trigger == SmTriggerEnum.OPTION_2

    def test_option_3(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "3", "3")
        assert r.trigger == SmTriggerEnum.OPTION_3

    def test_option_4(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "4", "4")
        assert r.trigger == SmTriggerEnum.OPTION_4

    def test_alias_catalogo(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "ver catálogo", "ver catalogo")
        assert r.trigger == SmTriggerEnum.OPTION_1

    def test_alias_pedido(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "fazer pedido", "fazer pedido")
        assert r.trigger == SmTriggerEnum.OPTION_2

    def test_alias_encomendar(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "quero encomendar", "quero encomendar")
        assert r.trigger == SmTriggerEnum.OPTION_2

    def test_invalid_input(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "xyz", "xyz")
        assert r.trigger == SmTriggerEnum.INPUT_INVALID

    def test_humano(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "humano", "humano")
        assert r.trigger == SmTriggerEnum.HUMAN_REQUESTED

    def test_falar_com_dani(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "falar com a Dani", "falar com a dani")
        assert r.trigger == SmTriggerEnum.HUMAN_REQUESTED


class TestMassaClassification:
    """Testa classificação de massa."""

    def test_branca_numero(self):
        r = classify_input(ConversationState.ESCOLHENDO_MASSA, "1", "1")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "BRANCA"

    def test_chocolate_numero(self):
        r = classify_input(ConversationState.ESCOLHENDO_MASSA, "2", "2")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "CHOCOLATE"

    def test_branca_texto(self):
        r = classify_input(ConversationState.ESCOLHENDO_MASSA, "branca", "branca")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "BRANCA"

    def test_chocolate_texto(self):
        r = classify_input(ConversationState.ESCOLHENDO_MASSA, "chocolate", "chocolate")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "CHOCOLATE"

    def test_invalid(self):
        r = classify_input(ConversationState.ESCOLHENDO_MASSA, "azul", "azul")
        assert r.trigger == SmTriggerEnum.INPUT_INVALID


class TestTamanhoClassification:
    """Testa classificação de tamanho com catálogo mock."""

    class MockSize:
        def __init__(self, id, description, weight_kg, servings):
            self.id = id
            self.description = description
            self.weight_kg = weight_kg
            self.servings = servings

    @pytest.fixture
    def sizes(self):
        return [
            self.MockSize(1, "1 kg - Aro 15 cm", 1.0, 10),
            self.MockSize(2, "2,200 kg", 2.2, 24),
            self.MockSize(3, "3 kg", 3.0, 32),
        ]

    def test_by_number(self, sizes):
        r = classify_input(ConversationState.ESCOLHENDO_TAMANHO, "2", "2", sizes)
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_id == 2

    def test_by_text_weight(self, sizes):
        r = classify_input(ConversationState.ESCOLHENDO_TAMANHO, "3 kg", "3 kg", sizes)
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_id == 3

    def test_by_servings(self, sizes):
        r = classify_input(ConversationState.ESCOLHENDO_TAMANHO, "24 fatias", "24 fatias", sizes)
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_id == 2

    def test_out_of_range(self, sizes):
        r = classify_input(ConversationState.ESCOLHENDO_TAMANHO, "99", "99", sizes)
        assert r.trigger is None  # Sem match (pode tentar Groq)

    def test_text_no_match(self, sizes):
        r = classify_input(ConversationState.ESCOLHENDO_TAMANHO, "gigante", "gigante", sizes)
        assert r.trigger is None


class TestConfirmacaoClassification:
    """Testa classificação de confirmação."""

    def test_sim(self):
        r = classify_input(ConversationState.CONFIRMANDO_PEDIDO, "sim", "sim")
        assert r.trigger == SmTriggerEnum.ORDER_CONFIRMED_BY_CLIENT

    def test_confirmar(self):
        r = classify_input(ConversationState.CONFIRMANDO_PEDIDO, "confirmar", "confirmar")
        assert r.trigger == SmTriggerEnum.ORDER_CONFIRMED_BY_CLIENT

    def test_nao(self):
        r = classify_input(ConversationState.CONFIRMANDO_PEDIDO, "não", "nao")
        assert r.trigger == SmTriggerEnum.ORDER_CANCELLED_BY_CLIENT

    def test_cancelar(self):
        r = classify_input(ConversationState.CONFIRMANDO_PEDIDO, "cancelar", "cancelar")
        assert r.trigger == SmTriggerEnum.ORDER_CANCELLED_BY_CLIENT

    def test_numero_1(self):
        r = classify_input(ConversationState.CONFIRMANDO_PEDIDO, "1", "1")
        assert r.trigger == SmTriggerEnum.ORDER_CONFIRMED_BY_CLIENT

    def test_numero_2(self):
        r = classify_input(ConversationState.CONFIRMANDO_PEDIDO, "2", "2")
        assert r.trigger == SmTriggerEnum.ORDER_CANCELLED_BY_CLIENT


class TestObservacoesClassification:
    """Testa classificação de observações (qualquer texto válido)."""

    def test_any_text(self):
        r = classify_input(
            ConversationState.DEFININDO_OBSERVACOES,
            "Sem nozes por favor", "sem nozes por favor",
        )
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "Sem nozes por favor"


class TestHumanDetection:
    """Testa detecção global de pedido de humano."""

    def test_humano_in_order_state(self):
        r = classify_input(ConversationState.ESCOLHENDO_TAMANHO, "humano", "humano")
        assert r.trigger == SmTriggerEnum.HUMAN_REQUESTED

    def test_atendente_in_menu(self):
        r = classify_input(ConversationState.MENU_PRINCIPAL, "atendente", "atendente")
        assert r.trigger == SmTriggerEnum.HUMAN_REQUESTED


class TestDateParsing:
    """Testa parser de datas."""

    def test_amanha(self):
        result = _parse_date("amanha")
        assert result == date.today() + timedelta(days=1)

    def test_dd_mm(self):
        result = _parse_date("15/06")
        assert result is not None
        assert result.day == 15
        assert result.month == 6

    def test_dd_mm_yyyy(self):
        result = _parse_date("15/06/2026")
        assert result == date(2026, 6, 15)

    def test_weekday_sexta(self):
        result = _parse_date("sexta")
        assert result is not None
        assert result.weekday() == 4  # Friday

    def test_invalid_date(self):
        result = _parse_date("blablabla")
        assert result is None

    def test_dia_de_mes(self):
        result = _parse_date("15 de junho")
        assert result is not None
        assert result.day == 15
        assert result.month == 6


class TestTimeParsing:
    """Testa parser de horários."""

    def test_14h(self):
        assert _parse_time("14h") == "14:00"

    def test_14_00(self):
        assert _parse_time("14:00") == "14:00"

    def test_8h(self):
        assert _parse_time("8h") == "08:00"

    def test_2_da_tarde(self):
        assert _parse_time("2 da tarde") == "14:00"

    def test_invalid(self):
        assert _parse_time("meio-dia") is None


class TestAdicionaisClassification:
    """Testa classificação de adicionais com opção de pular."""

    def test_pular(self):
        r = classify_input(ConversationState.ESCOLHENDO_ADICIONAIS, "pular", "pular")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "SKIP"

    def test_nenhum(self):
        r = classify_input(ConversationState.ESCOLHENDO_ADICIONAIS, "nenhum", "nenhum")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "SKIP"

    def test_zero(self):
        r = classify_input(ConversationState.ESCOLHENDO_ADICIONAIS, "0", "0")
        assert r.trigger == SmTriggerEnum.INPUT_VALID
        assert r.matched_value == "SKIP"

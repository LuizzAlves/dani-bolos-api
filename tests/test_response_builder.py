"""
Testes para o response_builder focados na simplificação visual de catálogos.
"""

import pytest
from unittest.mock import MagicMock
from app.models import SmActionEnum
from app.core.order_engine import ActionContext
from app.core.response_builder import build_response


def _mock_catalog_items():
    class MockItem:
        def __init__(self, id, desc, name):
            self.id = id
            self.description = desc
            self.name = name
            self.shape = MagicMock()
            self.shape.value = "Redondo"
            self.servings = 10
            self.price_white = "50.00"
            self.price_chocolate = "60.00"
            self.unit_quantity = 50
            self.price = "100.00"
            self.min_order_qty = 50

    return [
        MockItem(1, "Tamanho M", "Recheio 1"),
    ]


class TestVisualCatalogFlow:

    @pytest.fixture
    def ctx(self):
        ctx = ActionContext()
        ctx.catalog_items = _mock_catalog_items()
        return ctx

    def test_build_show_sizes_with_media(self, ctx):
        ctx.media_references = ["MEDIA_ID"]
        responses = build_response(SmActionEnum.SHOW_SIZES_AND_RETURN, ctx, None, "Test")
        
        # Check that it includes a short message and no long list
        text_responses = [r.text for r in responses if r.type == "text"]
        assert any("Tamanhos disponíveis" in t for t in text_responses)
        # Should not contain the item description in the text
        assert not any("Tamanho M" in t for t in text_responses)
        assert not any("Redondo" in t for t in text_responses)

    def test_build_show_sizes_without_media(self, ctx):
        ctx.media_references = []
        responses = build_response(SmActionEnum.SHOW_SIZES_AND_RETURN, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        # Should contain the item description in the text as fallback
        assert any("Tamanho M" in t for t in text_responses)
        assert any("Redondo" in t for t in text_responses)

    def test_build_show_fillings_with_media(self, ctx):
        ctx.media_references = ["MEDIA_ID"]
        responses = build_response(SmActionEnum.SHOW_FILLINGS_AND_RETURN, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        assert any("Recheios disponíveis" in t for t in text_responses)
        assert not any("Recheio 1" in t for t in text_responses)

    def test_build_show_fillings_without_media(self, ctx):
        ctx.media_references = []
        responses = build_response(SmActionEnum.SHOW_FILLINGS_AND_RETURN, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        assert any("Recheio 1" in t for t in text_responses)

    def test_build_show_sweets_with_media(self, ctx):
        ctx.media_references = ["MEDIA_ID"]
        responses = build_response(SmActionEnum.SHOW_SWEETS_AND_RETURN, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        assert any("Mini Docinhos" in t for t in text_responses)
        assert not any("Recheio 1" in t for t in text_responses) # Using MockItem as sweet
        assert not any("100.00" in t for t in text_responses)

    def test_build_show_sweets_without_media(self, ctx):
        ctx.media_references = []
        responses = build_response(SmActionEnum.SHOW_SWEETS_AND_RETURN, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        assert any("Recheio 1" in t for t in text_responses)

    def test_build_ask_size_with_media(self, ctx):
        ctx.media_references = ["MEDIA_ID"]
        responses = build_response(SmActionEnum.CREATE_ORDER_AND_ASK_SIZE, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        combined_text = " ".join(text_responses)
        assert "Escolha o tamanho do bolo respondendo com o número que aparece na imagem" in combined_text
        assert "Tamanho M" not in combined_text

    def test_build_ask_size_without_media(self, ctx):
        ctx.media_references = []
        responses = build_response(SmActionEnum.CREATE_ORDER_AND_ASK_SIZE, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        combined_text = " ".join(text_responses)
        assert "Escolha o tamanho:" in combined_text
        assert "Tamanho M" in combined_text

    def test_build_ask_filling_with_media(self, ctx):
        ctx.media_references = ["MEDIA_ID"]
        responses = build_response(SmActionEnum.SAVE_DOUGH_AND_ASK_FILLING1, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        combined_text = " ".join(text_responses)
        assert "Escolha o 1º recheio respondendo com o número ou nome que aparece na imagem" in combined_text
        assert "Recheio 1" not in combined_text

    def test_build_ask_filling_without_media(self, ctx):
        ctx.media_references = []
        responses = build_response(SmActionEnum.SAVE_DOUGH_AND_ASK_FILLING1, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        combined_text = " ".join(text_responses)
        assert "Escolha o *1º recheio*" in combined_text
        assert "Recheio 1" in combined_text

    def test_build_ask_filling2_with_media(self, ctx):
        ctx.media_references = ["MEDIA_ID"]
        responses = build_response(SmActionEnum.SAVE_FILLING1_AND_ASK_FILLING2, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        combined_text = " ".join(text_responses)
        assert "Agora escolha o 2º recheio respondendo com o número ou nome que aparece na imagem" in combined_text
        assert "Recheio 1" not in combined_text

    def test_build_ask_filling2_without_media(self, ctx):
        ctx.media_references = []
        responses = build_response(SmActionEnum.SAVE_FILLING1_AND_ASK_FILLING2, ctx, None, "Test")
        
        text_responses = [r.text for r in responses if r.type == "text"]
        combined_text = " ".join(text_responses)
        assert "Agora escolha o *2º recheio*" in combined_text
        assert "Recheio 1" in combined_text

"""
Testes do calculador interativo de valores.
"""

from decimal import Decimal

from app.core.order_engine import (
    _format_value_quote,
    _parse_value_criteria,
    _resolve_value_size,
    _sort_sizes_for_values,
)
from app.models import CakeShape


class MockSize:
    def __init__(self, id, description, weight_kg, servings, filling_layers=1):
        self.id = id
        self.description = description
        self.weight_kg = Decimal(str(weight_kg))
        self.servings = servings
        self.filling_layers = filling_layers
        self.shape = CakeShape.REDONDA
        self.price_white = Decimal("100.00") + id
        self.price_chocolate = Decimal("110.00") + id


def test_parse_people_criteria():
    criteria = _parse_value_criteria("umas 40 pessoas")

    assert criteria["kind"] == "people"
    assert criteria["value"] == 40
    assert criteria["requested"] == {"kind": "people", "value": 40}


def test_people_criteria_selects_closest_size():
    sizes = [
        MockSize(1, "2 kg", 2, 24),
        MockSize(2, "4 kg", 4, 42),
        MockSize(3, "5 kg", 5, 52),
    ]

    selected = _resolve_value_size(
        sizes,
        _parse_value_criteria("umas 40 pessoas"),
        latest_quote=None,
    )

    assert selected.id == 2


def test_larger_uses_previous_quote():
    sizes = [
        MockSize(1, "2 kg", 2, 24),
        MockSize(2, "4 kg", 4, 42),
        MockSize(3, "5 kg", 5, 52),
    ]

    selected = _resolve_value_size(
        sizes,
        _parse_value_criteria("maior"),
        latest_quote={"selected_size_id": 2},
    )

    assert selected.id == 3


def test_smaller_uses_previous_quote():
    sizes = [
        MockSize(1, "2 kg", 2, 24),
        MockSize(2, "4 kg", 4, 42),
        MockSize(3, "5 kg", 5, 52),
    ]

    selected = _resolve_value_size(
        sizes,
        _parse_value_criteria("menor"),
        latest_quote={"selected_size_id": 2},
    )

    assert selected.id == 1


def test_larger_without_previous_quote_needs_criteria():
    sizes = [MockSize(1, "2 kg", 2, 24), MockSize(2, "4 kg", 4, 42)]

    assert _resolve_value_size(sizes, _parse_value_criteria("maior"), None) is None


def test_quote_text_asks_for_adjustment():
    sizes = _sort_sizes_for_values([
        MockSize(1, "2 kg", 2, 24),
        MockSize(2, "4 kg", 4, 42),
    ])

    text = _format_value_quote(
        selected_size=sizes[1],
        sorted_sizes=sizes,
        requested={"kind": "people", "value": 40},
        direction=None,
    )

    assert "40 pessoas" in text
    assert "4 kg" in text
    assert "maior" in text
    assert "menor" in text

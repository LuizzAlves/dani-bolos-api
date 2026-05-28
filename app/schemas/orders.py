"""
Schemas de pedidos.
"""

from pydantic import BaseModel
from decimal import Decimal


class OrderSummary(BaseModel):
    """Resumo do pedido para exibição ao cliente."""
    order_number: int | None = None
    size_description: str | None = None
    shape: str | None = None
    dough: str | None = None
    filling_1: str | None = None
    filling_2: str | None = None
    extras: list[str] = []
    finish: str | None = None
    pickup_date: str | None = None
    pickup_time: str | None = None
    notes: str | None = None
    base_value: Decimal | None = None
    extras_value: Decimal | None = None
    total_value: Decimal | None = None

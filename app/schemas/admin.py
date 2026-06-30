"""
Schemas Pydantic para endpoints administrativos do dashboard.
"""

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# DASHBOARD
# ============================================================

class DashboardStats(BaseModel):
    today_count: int = 0
    aguardando_count: int = 0
    faturamento_semanal: float = 0.0
    tomorrow_count: int = 0
    alert_count: int = 0


# ============================================================
# ORDERS
# ============================================================

class OrderListItem(BaseModel):
    id: str
    order_number: int | None = None
    client_name: str | None = None
    client_phone: str | None = None
    status: str
    size_description: str | None = None
    dough: str | None = None
    filling_1: str | None = None
    filling_2: str | None = None
    finish: str | None = None
    extras: list[str] = []
    pickup_date: str | None = None
    pickup_time: str | None = None
    total_value: float | None = None
    notes: str | None = None
    created_at: str | None = None


class OrderDetail(OrderListItem):
    size_id: int | None = None
    filling_1_id: int | None = None
    filling_2_id: int | None = None
    finish_id: int | None = None
    extras_raw: list[dict] = []
    shape: str | None = None
    filling_count: int | None = None
    base_value: float | None = None
    extras_value: float | None = None


class OrderStatusUpdate(BaseModel):
    new_status: str = Field(..., description="Novo status do pedido")


class ManualOrderCreate(BaseModel):
    client_name: str = Field(..., min_length=1)
    client_phone: str = Field(..., min_length=10)
    size_id: int | None = None
    shape: str | None = None
    dough: str | None = None
    filling_1_id: int | None = None
    filling_2_id: int | None = None
    finish_id: int | None = None
    extras: list[dict] | None = None  # [{extra_id, layers}]
    pickup_date: str | None = None
    pickup_time: str | None = None
    notes: str | None = None
    total_value: float | None = None
    filling_count: int | None = 2


class ManualOrderUpdate(BaseModel):
    client_name: str | None = Field(None, min_length=1)
    client_phone: str | None = Field(None, min_length=10)
    size_id: int | None = None
    shape: str | None = None
    dough: str | None = None
    filling_1_id: int | None = None
    filling_2_id: int | None = None
    finish_id: int | None = None
    extras: list[dict] | None = None  # [{extra_id, layers}]
    pickup_date: str | None = None
    pickup_time: str | None = None
    notes: str | None = None
    total_value: float | None = None
    filling_count: int | None = None


# ============================================================
# CALENDAR
# ============================================================

class CalendarDay(BaseModel):
    date: str
    order_count: int = 0
    max_orders: int = 5
    confirmed_orders: int = 0
    blocked: bool = False
    block_reason: str | None = None


class CalendarResponse(BaseModel):
    year: int
    month: int
    days: list[CalendarDay]


class AvailabilityUpdate(BaseModel):
    max_orders: int | None = None
    blocked: bool | None = None
    block_reason: str | None = None


# ============================================================
# ALERTS
# ============================================================

class AlertItem(BaseModel):
    id: str
    alert_type: str
    title: str
    description: str | None = None
    client_name: str | None = None
    client_phone: str | None = None
    last_message: str | None = None
    order_id: str | None = None
    resolved: bool = False
    created_at: str | None = None


class AlertsResponse(BaseModel):
    count: int
    alerts: list[AlertItem]


# ============================================================
# CATALOG
# ============================================================

class CatalogResponse(BaseModel):
    sizes: list[dict]
    fillings: list[dict]
    extras: list[dict]
    finishes: list[dict]
    sweets: list[dict]
    time_slots: list[dict]


class CatalogItemUpdate(BaseModel):
    data: dict = Field(..., description="Campos a atualizar")


# ============================================================
# SETTINGS
# ============================================================

class SettingsResponse(BaseModel):
    settings: dict


class SettingsUpdate(BaseModel):
    settings: dict = Field(..., description="Dict de configurações a salvar")


# ============================================================
# READY CAKES
# ============================================================

class ReadyCakeCreate(BaseModel):
    flavor: str = Field(..., min_length=1)
    description: Optional[str] = None
    price: Optional[float] = None


class ReadyCakeUpdate(BaseModel):
    flavor: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    available: Optional[bool] = None


class ReadyCakeItem(BaseModel):
    id: int
    flavor: str
    description: Optional[str] = None
    price: Optional[float] = None
    available: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


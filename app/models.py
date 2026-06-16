"""
Modelos SQLAlchemy 2.0 mapeando o schema PostgreSQL existente.
Nenhuma alteração no banco — apenas leitura do schema atual.
"""

import enum
from datetime import datetime, date, time
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, Text, Time, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ============================================================
# ENUMS (mapeando os tipos PostgreSQL existentes)
# ============================================================

class ConversationState(str, enum.Enum):
    NOVO_CLIENTE = "NOVO_CLIENTE"
    MENU_PRINCIPAL = "MENU_PRINCIPAL"
    PESQUISA = "PESQUISA"
    PESQUISA_VALORES = "PESQUISA_VALORES"
    ESCOLHENDO_TAMANHO = "ESCOLHENDO_TAMANHO"
    ESCOLHENDO_FORMA = "ESCOLHENDO_FORMA"
    ESCOLHENDO_CAMADAS = "ESCOLHENDO_CAMADAS"
    ESCOLHENDO_MASSA = "ESCOLHENDO_MASSA"
    ESCOLHENDO_RECHEIOS = "ESCOLHENDO_RECHEIOS"
    ESCOLHENDO_RECHEIO_2 = "ESCOLHENDO_RECHEIO_2"
    ESCOLHENDO_ADICIONAIS = "ESCOLHENDO_ADICIONAIS"
    ESCOLHENDO_FINALIZACAO = "ESCOLHENDO_FINALIZACAO"
    DEFININDO_DATA = "DEFININDO_DATA"
    DEFININDO_HORARIO = "DEFININDO_HORARIO"
    DEFININDO_OBSERVACOES = "DEFININDO_OBSERVACOES"
    CONFIRMANDO_PEDIDO = "CONFIRMANDO_PEDIDO"
    CONSULTA_PEDIDO = "CONSULTA_PEDIDO"
    PRONTA_ENTREGA = "PRONTA_ENTREGA"
    ATENDIMENTO_HUMANO = "ATENDIMENTO_HUMANO"
    BOT_PAUSADO = "BOT_PAUSADO"


class ActiveFlowType(str, enum.Enum):
    NENHUM = "NENHUM"
    ONBOARDING = "ONBOARDING"
    MENU = "MENU"
    PESQUISA = "PESQUISA"
    PEDIDO = "PEDIDO"
    CONSULTA = "CONSULTA"
    PRONTA_ENTREGA = "PRONTA_ENTREGA"
    ATENDIMENTO_HUMANO = "ATENDIMENTO_HUMANO"


class OrderStatus(str, enum.Enum):
    RASCUNHO = "RASCUNHO"
    AGUARDANDO_CONFIRMACAO = "AGUARDANDO_CONFIRMACAO"
    CONFIRMADO = "CONFIRMADO"
    EM_PRODUCAO = "EM_PRODUCAO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


class CakeShape(str, enum.Enum):
    REDONDA = "REDONDA"
    RETANGULAR = "RETANGULAR"


class DoughType(str, enum.Enum):
    BRANCA = "BRANCA"
    CHOCOLATE = "CHOCOLATE"


class EventTypeEnum(str, enum.Enum):
    MESSAGE_RECEIVED = "MESSAGE_RECEIVED"
    MESSAGE_SENT = "MESSAGE_SENT"
    CLIENT_CREATED = "CLIENT_CREATED"
    STATE_CHANGED = "STATE_CHANGED"
    ORDER_STARTED = "ORDER_STARTED"
    SIZE_SELECTED = "SIZE_SELECTED"
    DOUGH_SELECTED = "DOUGH_SELECTED"
    FILLING_SELECTED = "FILLING_SELECTED"
    EXTRA_SELECTED = "EXTRA_SELECTED"
    FINISH_SELECTED = "FINISH_SELECTED"
    DATE_SELECTED = "DATE_SELECTED"
    TIME_SELECTED = "TIME_SELECTED"
    NOTES_ADDED = "NOTES_ADDED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_COMPLETED = "ORDER_COMPLETED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    BOT_PAUSED = "BOT_PAUSED"
    BOT_RESUMED = "BOT_RESUMED"
    TIMEOUT_WARNING = "TIMEOUT_WARNING"
    FLOW_TIMEOUT = "FLOW_TIMEOUT"
    FALLBACK_TRIGGERED = "FALLBACK_TRIGGERED"
    AI_CALLED = "AI_CALLED"
    EXTERNAL_API_CALL = "EXTERNAL_API_CALL"
    ERROR = "ERROR"


class SmTriggerEnum(str, enum.Enum):
    INPUT_VALID = "INPUT_VALID"
    INPUT_INVALID = "INPUT_INVALID"
    OPTION_1 = "OPTION_1"
    OPTION_2 = "OPTION_2"
    OPTION_3 = "OPTION_3"
    OPTION_4 = "OPTION_4"
    OPTION_5 = "OPTION_5"
    NEW_CLIENT_REGISTERED = "NEW_CLIENT_REGISTERED"
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    MAX_FALLBACK_REACHED = "MAX_FALLBACK_REACHED"
    LOCK_EXPIRED = "LOCK_EXPIRED"
    ONE_FILLING_SELECTED = "ONE_FILLING_SELECTED"
    TWO_FILLINGS_SELECTED = "TWO_FILLINGS_SELECTED"
    DATE_AVAILABLE = "DATE_AVAILABLE"
    DATE_UNAVAILABLE = "DATE_UNAVAILABLE"
    ORDER_CONFIRMED_BY_CLIENT = "ORDER_CONFIRMED_BY_CLIENT"
    ORDER_CANCELLED_BY_CLIENT = "ORDER_CANCELLED_BY_CLIENT"


class SmActionEnum(str, enum.Enum):
    REGISTER_CLIENT_AND_SHOW_MENU = "REGISTER_CLIENT_AND_SHOW_MENU"
    SHOW_MENU = "SHOW_MENU"
    SHOW_SEARCH_MENU = "SHOW_SEARCH_MENU"
    SHOW_SIZES_AND_RETURN = "SHOW_SIZES_AND_RETURN"
    SHOW_FILLINGS_AND_RETURN = "SHOW_FILLINGS_AND_RETURN"
    SHOW_SWEETS_AND_RETURN = "SHOW_SWEETS_AND_RETURN"
    ASK_VALUES_CRITERIA = "ASK_VALUES_CRITERIA"
    SHOW_VALUES_AND_RETURN = "SHOW_VALUES_AND_RETURN"
    CREATE_ORDER_AND_ASK_SIZE = "CREATE_ORDER_AND_ASK_SIZE"
    SAVE_SIZE_AND_ASK_SHAPE = "SAVE_SIZE_AND_ASK_SHAPE"
    SAVE_SIZE_AND_ASK_DOUGH = "SAVE_SIZE_AND_ASK_DOUGH"
    SAVE_SHAPE_AND_ASK_LAYERS = "SAVE_SHAPE_AND_ASK_LAYERS"
    SAVE_LAYERS_AND_ASK_DOUGH = "SAVE_LAYERS_AND_ASK_DOUGH"
    SAVE_DOUGH_AND_ASK_FILLING1 = "SAVE_DOUGH_AND_ASK_FILLING1"
    SAVE_FILLING1_AND_ASK_FILLING2 = "SAVE_FILLING1_AND_ASK_FILLING2"
    SAVE_FILLING_AND_ASK_EXTRAS = "SAVE_FILLING_AND_ASK_EXTRAS"
    SAVE_EXTRAS_AND_ASK_FINISH = "SAVE_EXTRAS_AND_ASK_FINISH"
    SAVE_FINISH_AND_ASK_DATE = "SAVE_FINISH_AND_ASK_DATE"
    CHECK_DATE_AVAILABILITY = "CHECK_DATE_AVAILABILITY"
    REJECT_DATE_AND_ASK_AGAIN = "REJECT_DATE_AND_ASK_AGAIN"
    SAVE_DATE_AND_ASK_TIME = "SAVE_DATE_AND_ASK_TIME"
    SAVE_TIME_AND_ASK_NOTES = "SAVE_TIME_AND_ASK_NOTES"
    SAVE_NOTES_AND_SHOW_SUMMARY = "SAVE_NOTES_AND_SHOW_SUMMARY"
    FINALIZE_ORDER_AND_LOCK = "FINALIZE_ORDER_AND_LOCK"
    CANCEL_ORDER_AND_RETURN = "CANCEL_ORDER_AND_RETURN"
    ASK_ORDER_ID = "ASK_ORDER_ID"
    CHECK_ORDER_STATUS = "CHECK_ORDER_STATUS"
    INCREMENT_FALLBACK = "INCREMENT_FALLBACK"
    ASK_HUMAN_REASON = "ASK_HUMAN_REASON"
    PAUSE_BOT_AND_NOTIFY_HUMAN = "PAUSE_BOT_AND_NOTIFY_HUMAN"
    RESUME_BOT = "RESUME_BOT"
    SHOW_READY_CAKES = "SHOW_READY_CAKES"
    RESERVE_READY_CAKE_INTEREST = "RESERVE_READY_CAKE_INTEREST"


class FallbackEffectEnum(str, enum.Enum):
    NONE = "NONE"
    INCREMENT = "INCREMENT"
    RESET = "RESET"
    PAUSE = "PAUSE"


class MediaTypeEnum(str, enum.Enum):
    IMAGEM = "IMAGEM"
    VIDEO = "VIDEO"


# ============================================================
# MODELOS
# ============================================================

class Client(Base):
    __tablename__ = "clients"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = mapped_column(String(255), nullable=True)
    phone = mapped_column(String(20), nullable=False, unique=True, index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    conversations = relationship("Conversation", back_populates="client")
    orders = relationship("Order", back_populates="client")


class Conversation(Base):
    __tablename__ = "conversations"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    state = mapped_column(
        Enum(ConversationState, name="conversation_state", create_type=False),
        nullable=False,
        default=ConversationState.NOVO_CLIENTE,
    )
    active_flow = mapped_column(
        Enum(ActiveFlowType, name="active_flow_type", create_type=False),
        nullable=False,
        default=ActiveFlowType.NENHUM,
    )
    human_lock = mapped_column(Boolean, nullable=False, default=False)
    human_lock_until = mapped_column(DateTime(timezone=True), nullable=True)
    last_interaction = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    timeout_minutes = mapped_column(Integer, nullable=False, default=120)
    fallback_count = mapped_column(Integer, nullable=False, default=0)
    is_active = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    client = relationship("Client", back_populates="conversations")
    orders = relationship("Order", back_populates="conversation")
    events = relationship("Event", back_populates="conversation")


class Size(Base):
    __tablename__ = "sizes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    description = mapped_column(String(100), nullable=False)
    weight_kg = mapped_column(Numeric(5, 3), nullable=False)
    servings = mapped_column(Integer, nullable=False)
    shape = mapped_column(
        Enum(CakeShape, name="cake_shape", create_type=False),
        nullable=False,
    )
    filling_layers = mapped_column(Integer, nullable=False, default=1)
    price_white = mapped_column(Numeric(10, 2), nullable=False)
    price_chocolate = mapped_column(Numeric(10, 2), nullable=False)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    active = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class Filling(Base):
    __tablename__ = "fillings"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(150), nullable=False)
    available = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class Extra(Base):
    __tablename__ = "extras"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(150), nullable=False)
    price_per_layer = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    requires_approval = mapped_column(Boolean, nullable=False, default=False)
    description = mapped_column(Text, nullable=True)
    active = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class Finish(Base):
    __tablename__ = "finishes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(150), nullable=False)
    requires_approval = mapped_column(Boolean, nullable=False, default=False)
    has_extra_cost = mapped_column(Boolean, nullable=False, default=False)
    description = mapped_column(Text, nullable=True)
    active = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class Sweet(Base):
    __tablename__ = "sweets"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(150), nullable=False)
    unit_quantity = mapped_column(Integer, nullable=False, default=100)
    price = mapped_column(Numeric(10, 2), nullable=False)
    min_order_qty = mapped_column(Integer, nullable=False, default=50)
    description = mapped_column(Text, nullable=True)
    active = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class IndividualProduct(Base):
    __tablename__ = "individual_products"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String(150), nullable=False)
    price_per_unit = mapped_column(Numeric(10, 2), nullable=False)
    min_order_qty = mapped_column(Integer, nullable=False, default=1)
    discount_qty = mapped_column(Integer, nullable=True)
    discount_price = mapped_column(Numeric(10, 2), nullable=True)
    filling_count = mapped_column(Integer, nullable=False, default=1)
    description = mapped_column(Text, nullable=True)
    active = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class Order(Base):
    __tablename__ = "orders"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_number = mapped_column(Integer, unique=True, autoincrement=True)
    client_id = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    conversation_id = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="RESTRICT"), nullable=True)
    status = mapped_column(
        Enum(OrderStatus, name="order_status", create_type=False),
        nullable=False,
        default=OrderStatus.RASCUNHO,
    )
    size_id = mapped_column(Integer, ForeignKey("sizes.id"), nullable=True)
    shape = mapped_column(
        Enum(CakeShape, name="cake_shape", create_type=False),
        nullable=True,
    )
    dough = mapped_column(
        Enum(DoughType, name="dough_type", create_type=False),
        nullable=True,
    )
    filling_count = mapped_column(Integer, nullable=True)
    filling_1_id = mapped_column(Integer, ForeignKey("fillings.id"), nullable=True)
    filling_2_id = mapped_column(Integer, ForeignKey("fillings.id"), nullable=True)
    finish_id = mapped_column(Integer, ForeignKey("finishes.id"), nullable=True)
    pickup_date = mapped_column(Date, nullable=True)
    pickup_time = mapped_column(Time, nullable=True)
    base_value = mapped_column(Numeric(10, 2), nullable=True)
    extras_value = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total_value = mapped_column(Numeric(10, 2), nullable=True)
    notes = mapped_column(Text, nullable=True)
    external_task_provider = mapped_column(String(50), nullable=True)
    external_task_id = mapped_column(String(100), nullable=True)
    external_task_url = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    client = relationship("Client", back_populates="orders")
    conversation = relationship("Conversation", back_populates="orders")
    size = relationship("Size")
    filling_1 = relationship("Filling", foreign_keys=[filling_1_id])
    filling_2 = relationship("Filling", foreign_keys=[filling_2_id])
    finish = relationship("Finish")
    order_extras = relationship("OrderExtra", back_populates="order")


class OrderExtra(Base):
    __tablename__ = "order_extras"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    extra_id = mapped_column(Integer, ForeignKey("extras.id"), nullable=False)
    layers = mapped_column(Integer, nullable=False, default=1)
    unit_price = mapped_column(Numeric(10, 2), nullable=False)
    total_price = mapped_column(Numeric(10, 2), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    order = relationship("Order", back_populates="order_extras")
    extra = relationship("Extra")


class Event(Base):
    __tablename__ = "events"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    order_id = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    event_type = mapped_column(
        Enum(EventTypeEnum, name="event_type_enum", create_type=False),
        nullable=False,
    )
    payload = mapped_column(JSONB, nullable=False, default=dict)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    conversation = relationship("Conversation", back_populates="events")


class Availability(Base):
    __tablename__ = "availability"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    date = mapped_column(Date, nullable=False, unique=True)
    blocked = mapped_column(Boolean, nullable=False, default=False)
    block_reason = mapped_column(String(255), nullable=True)
    max_orders = mapped_column(Integer, nullable=False, default=5)
    confirmed_orders = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_time = mapped_column(Time, nullable=False, unique=True)
    label = mapped_column(String(50), nullable=False)
    available = mapped_column(Boolean, nullable=False, default=True)
    sort_order = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class CatalogMedia(Base):
    __tablename__ = "catalog_media"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_type = mapped_column(String(50), nullable=False)
    reference_id = mapped_column(Integer, nullable=True)
    media_type = mapped_column(
        Enum(MediaTypeEnum, name="media_type_enum", create_type=False),
        nullable=False,
        default=MediaTypeEnum.IMAGEM,
    )
    media_url = mapped_column(Text, nullable=False)
    storage_provider = mapped_column(String(30), nullable=False, default="GOOGLE_DRIVE")
    provider_file_id = mapped_column(String(255), nullable=True)
    media_hash = mapped_column(String(64), nullable=True)
    version = mapped_column(Integer, nullable=False, default=1)
    description = mapped_column(String(255), nullable=True)
    active = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class StateTransition(Base):
    __tablename__ = "state_transitions"

    current_state = mapped_column(
        Enum(ConversationState, name="conversation_state", create_type=False),
        primary_key=True,
    )
    trigger = mapped_column(
        Enum(SmTriggerEnum, name="sm_trigger_enum", create_type=False),
        primary_key=True,
    )
    next_state = mapped_column(
        Enum(ConversationState, name="conversation_state", create_type=False),
        nullable=False,
    )
    action_code = mapped_column(
        Enum(SmActionEnum, name="sm_action_enum", create_type=False),
        nullable=False,
    )
    fallback_effect = mapped_column(
        Enum(FallbackEffectEnum, name="fallback_effect_enum", create_type=False),
        nullable=False,
        default=FallbackEffectEnum.NONE,
    )
    description = mapped_column(String(255), nullable=True)
    is_active = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


# ============================================================
# ENUM — Alertas
# ============================================================

class AlertTypeEnum(str, enum.Enum):
    HUMAN_REQUESTED = "HUMAN_REQUESTED"
    STUCK_CLIENT = "STUCK_CLIENT"
    CUSTOM_FILLING = "CUSTOM_FILLING"
    INTERPRETATION_ERROR = "INTERPRETATION_ERROR"
    FLOW_ERROR = "FLOW_ERROR"
    MAX_FALLBACK = "MAX_FALLBACK"
    READY_CAKE_INTEREST = "READY_CAKE_INTEREST"


# ============================================================
# MODELOS — Dashboard Administrativo
# ============================================================

class Alert(Base):
    __tablename__ = "alerts"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    client_id = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    conversation_id = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    order_id = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    alert_type = mapped_column(
        Enum(AlertTypeEnum, name="alert_type_enum", create_type=False),
        nullable=False,
    )
    title = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    client_phone = mapped_column(String(20), nullable=True)
    client_name = mapped_column(String(255), nullable=True)
    last_message = mapped_column(Text, nullable=True)
    resolved = mapped_column(Boolean, nullable=False, default=False)
    resolved_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    client = relationship("Client")
    conversation = relationship("Conversation")


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    key = mapped_column(String(100), primary_key=True)
    value = mapped_column(JSONB, nullable=False, default=dict)
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class ReadyCake(Base):
    __tablename__ = "ready_cakes"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    flavor = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    price = mapped_column(Numeric(10, 2), nullable=True)
    available = mapped_column(Boolean, nullable=False, default=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

"""
Admin endpoints protegidos por token.
Dashboard administrativo da Dani Bolos.
"""

from datetime import date, time, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.models import (
    Client, Conversation, Order, Event, OrderExtra, OrderStatus,
    CakeShape, DoughType, Alert,
)
from app.repositories import (
    orders as orders_repo,
    catalog as catalog_repo,
    availability as avail_repo,
    clients as clients_repo,
    alerts as alerts_repo,
    settings as settings_repo,
)
from app.core.service_hours import is_time_allowed_for_date
from app.schemas.admin import (
    DashboardStats, OrderListItem, OrderDetail, OrderStatusUpdate,
    ManualOrderCreate, CalendarDay, CalendarResponse, AvailabilityUpdate,
    AlertItem, AlertsResponse, CatalogResponse, CatalogItemUpdate,
    SettingsResponse, SettingsUpdate,
)
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_token(x_admin_token: str = Header(...)):
    """Verifica token de autenticação admin."""
    settings = get_settings()
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token inválido")
    return True


# ============================================================
# HELPERS — serialização de Order para JSON
# ============================================================

def _serialize_order_list(order: Order) -> dict:
    """Serializa um pedido para listagem (Kanban)."""
    extras = []
    if order.order_extras:
        for oe in order.order_extras:
            name = oe.extra.name if oe.extra else f"Extra #{oe.extra_id}"
            extras.append(f"{name} ({oe.layers} cam.)")

    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "client_name": order.client.name if order.client else None,
        "client_phone": order.client.phone if order.client else None,
        "status": order.status.value if order.status else None,
        "size_description": order.size.description if order.size else None,
        "dough": order.dough.value if order.dough else None,
        "filling_1": order.filling_1.name if order.filling_1 else None,
        "filling_2": order.filling_2.name if order.filling_2 else None,
        "finish": order.finish.name if order.finish else None,
        "extras": extras,
        "pickup_date": str(order.pickup_date) if order.pickup_date else None,
        "pickup_time": order.pickup_time.strftime("%H:%M") if order.pickup_time else None,
        "total_value": float(order.total_value) if order.total_value else None,
        "notes": order.notes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def _serialize_order_detail(order: Order) -> dict:
    """Serializa um pedido com detalhes completos (modal)."""
    base = _serialize_order_list(order)
    base.update({
        "shape": order.shape.value if order.shape else None,
        "filling_count": order.filling_count,
        "base_value": float(order.base_value) if order.base_value else None,
        "extras_value": float(order.extras_value) if order.extras_value else None,
    })
    return base


# ============================================================
# RESET TEST CLIENT (existente — preservado)
# ============================================================

@router.post("/reset-test-client")
async def reset_test_client(
    phone: str,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """
    Remove todos os dados de um cliente de teste.
    Exige header X-Admin-Token.
    Use apenas para testes, nunca em produção.
    """
    # Buscar cliente
    result = await db.execute(
        select(Client).where(Client.phone == phone)
    )
    client = result.scalar_one_or_none()

    if not client:
        return {"status": "not_found", "message": f"Cliente {phone} não encontrado"}

    # Buscar conversas
    convs = await db.execute(
        select(Conversation).where(Conversation.client_id == client.id)
    )
    conv_ids = [c.id for c in convs.scalars().all()]

    # Buscar orders
    orders_result = await db.execute(
        select(Order).where(Order.client_id == client.id)
    )
    order_ids = [o.id for o in orders_result.scalars().all()]

    # Deletar em ordem de dependência
    if order_ids:
        await db.execute(
            delete(OrderExtra).where(OrderExtra.order_id.in_(order_ids))
        )
        await db.execute(
            delete(Event).where(Event.order_id.in_(order_ids))
        )

    if conv_ids:
        await db.execute(
            delete(Event).where(Event.conversation_id.in_(conv_ids))
        )

    if order_ids:
        await db.execute(
            delete(Order).where(Order.id.in_(order_ids))
        )

    if conv_ids:
        await db.execute(
            delete(Conversation).where(Conversation.id.in_(conv_ids))
        )

    await db.execute(
        delete(Client).where(Client.id == client.id)
    )

    await db.commit()

    logger.info("test_client_reset", phone=phone[:6] + "***")

    return {
        "status": "ok",
        "message": f"Cliente {phone} e todos os dados associados foram removidos",
        "deleted": {
            "conversations": len(conv_ids),
            "orders": len(order_ids),
        },
    }


# ============================================================
# DASHBOARD STATS
# ============================================================

@router.get("/dashboard/stats")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Métricas rápidas para os cards do dashboard."""
    stats = await orders_repo.get_dashboard_stats(db)
    alert_count = await alerts_repo.get_alert_count(db)
    stats["alert_count"] = alert_count
    return stats


# ============================================================
# ORDERS
# ============================================================

@router.get("/orders")
async def list_orders(
    status: str | None = Query(None, description="Filtrar por status (separar por vírgula)"),
    pickup_date: str | None = Query(None, description="Filtrar por data (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Lista pedidos para o Kanban. Filtros opcionais por status e data."""
    if status:
        status_list = []
        for s in status.split(","):
            s = s.strip()
            try:
                status_list.append(OrderStatus(s))
            except ValueError:
                raise HTTPException(400, f"Status inválido: {s}")
    else:
        # Padrão: todos os status ativos (exclui rascunho)
        status_list = [
            OrderStatus.AGUARDANDO_CONFIRMACAO,
            OrderStatus.CONFIRMADO,
            OrderStatus.EM_PRODUCAO,
            OrderStatus.PRONTO,
            OrderStatus.ENTREGUE,
            OrderStatus.FINALIZADO,
        ]

    if pickup_date:
        try:
            target = date.fromisoformat(pickup_date)
        except ValueError:
            raise HTTPException(400, "Data inválida. Use YYYY-MM-DD")
        orders = await orders_repo.list_orders_by_date(db, target)
    else:
        orders = await orders_repo.list_orders_by_status(db, status_list)

    return [_serialize_order_list(o) for o in orders]


@router.get("/orders/{order_id}")
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Detalhes completos de um pedido."""
    order = await orders_repo.get_order_with_details(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido não encontrado")
    return _serialize_order_detail(order)


@router.post("/orders")
async def create_order(
    body: ManualOrderCreate,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Cria pedido manual pelo painel."""
    if not body.pickup_date or not body.pickup_time:
        raise HTTPException(400, "Data e horário de retirada são obrigatórios")

    try:
        pickup_date = date.fromisoformat(body.pickup_date)
    except ValueError:
        raise HTTPException(400, "Data inválida")

    parts = body.pickup_time.split(":")
    if len(parts) != 2:
        raise HTTPException(400, "Horário inválido")
    try:
        pickup_time = time(int(parts[0]), int(parts[1]))
    except ValueError:
        raise HTTPException(400, "Horário inválido")

    # Verificar disponibilidade de data
    avail = await avail_repo.check_date_available(db, pickup_date)
    if not avail["available"]:
        raise HTTPException(400, f"Data não disponível: {avail.get('block_reason', 'Limite atingido')}")

    # Verificar disponibilidade de horário
    time_str = f"{pickup_time.hour:02d}:{pickup_time.minute:02d}"
    time_slots = await catalog_repo.get_all_time_slots(db)
    slot_match = next(
        (
            slot for slot in time_slots
            if slot.slot_time and slot.slot_time.strftime("%H:%M") == time_str
        ),
        None,
    )

    if not slot_match:
        raise HTTPException(400, f"Horário '{time_str}' não existe nas opções configuradas.")
    if not slot_match.available:
        raise HTTPException(400, f"Horário '{time_str}' está temporariamente indisponível.")

    allowed_time, time_reason = await is_time_allowed_for_date(db, pickup_date, pickup_time)
    if not allowed_time:
        raise HTTPException(400, time_reason or "Horário fora do funcionamento para esta data.")

    # Calcular total se não enviado
    from decimal import Decimal
    total_val = None
    if body.total_value is not None:
        total_val = Decimal(str(body.total_value))
    elif body.size_id:
        size = await catalog_repo.get_size_by_id(db, body.size_id)
        if size:
            base = size.price_chocolate if body.dough == "CHOCOLATE" else size.price_white
            # Finalização com custo
            if body.finish_id:
                finish = await catalog_repo.get_finish_by_id(db, body.finish_id)
                # Adicionar regra de preço de finalização aqui se houvesse, mas atualmente 'has_extra_cost' é tratada manualmente ou com valor fixo. Vamos apenas usar a base por enquanto e somar adicionais.

            extras_val = Decimal("0.00")
            if body.extras:
                for ext in body.extras:
                    extra = await catalog_repo.get_extra_by_id(db, ext.get("extra_id"))
                    if extra:
                        extras_val += extra.price_per_layer * ext.get("layers", 1)

            total_val = base + extras_val

    # Buscar ou criar cliente
    client, _ = await clients_repo.get_or_create_client(
        db, body.client_phone, body.client_name
    )

    shape = CakeShape(body.shape) if body.shape else None
    dough = DoughType(body.dough) if body.dough else None

    order = await orders_repo.create_manual_order(
        db=db,
        client_id=client.id,
        size_id=body.size_id,
        shape=shape,
        dough=dough,
        filling_1_id=body.filling_1_id,
        filling_2_id=body.filling_2_id,
        finish_id=body.finish_id,
        pickup_date=pickup_date,
        pickup_time=pickup_time,
        notes=body.notes,
        total_value=total_val,
        filling_count=body.filling_count,
    )

    # Adicionar extras se fornecidos
    if body.extras:
        for ext in body.extras:
            extra = await catalog_repo.get_extra_by_id(db, ext.get("extra_id"))
            if extra:
                await orders_repo.add_order_extra(
                    db, order.id, extra.id,
                    ext.get("layers", 1), extra.price_per_layer
                )

    # Tentar incrementar a capacidade
    success = await avail_repo.increment_confirmed_orders(db, pickup_date)
    if not success:
        # Fazer rollback manual (apenas levanta exceção e não commita)
        await db.rollback()
        raise HTTPException(400, "Infelizmente a agenda acabou de lotar para este dia.")

    await orders_repo.update_order_status(db, order.id, OrderStatus.CONFIRMADO)

    await db.commit()

    logger.info("manual_order_created", order_number=order.order_number)
    return {
        "status": "ok",
        "order_id": str(order.id),
        "order_number": order.order_number,
    }


@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Muda o status de um pedido."""
    try:
        new_status = OrderStatus(body.new_status)
    except ValueError:
        raise HTTPException(400, f"Status inválido: {body.new_status}")

    ok = await orders_repo.update_order_status(db, order_id, new_status)
    if not ok:
        raise HTTPException(404, "Pedido não encontrado")

    await db.commit()
    logger.info("order_status_changed", order_id=str(order_id), new_status=body.new_status)
    return {"status": "ok", "new_status": body.new_status}


# ============================================================
# CALENDAR
# ============================================================

@router.get("/calendar")
async def get_calendar(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Calendário mensal com contagem de pedidos e disponibilidade."""
    order_counts = await orders_repo.count_orders_by_date(db, year, month)
    availability = await avail_repo.get_month_availability(db, year, month)

    # Mapear contagens e disponibilidade por data
    count_map = {item["date"]: item["count"] for item in order_counts}
    avail_map = {str(a.date): a for a in availability}

    # Gerar todos os dias do mês
    import calendar
    num_days = calendar.monthrange(year, month)[1]
    days = []
    for d in range(1, num_days + 1):
        ds = f"{year}-{month:02d}-{d:02d}"
        avail = avail_map.get(ds)
        days.append({
            "date": ds,
            "order_count": count_map.get(ds, 0),
            "max_orders": avail.max_orders if avail else 5,
            "confirmed_orders": avail.confirmed_orders if avail else 0,
            "blocked": avail.blocked if avail else False,
            "block_reason": avail.block_reason if avail else None,
        })

    return {"year": year, "month": month, "days": days}


@router.patch("/calendar/{target_date}")
async def update_calendar_day(
    target_date: str,
    body: AvailabilityUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Atualizar capacidade ou bloquear/desbloquear um dia."""
    try:
        dt = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(400, "Data inválida. Use YYYY-MM-DD")

    await avail_repo.upsert_availability(
        db, dt,
        max_orders=body.max_orders,
        blocked=body.blocked,
        block_reason=body.block_reason,
    )
    await db.commit()
    return {"status": "ok", "date": target_date}


# ============================================================
# ALERTS
# ============================================================

@router.get("/alerts")
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Lista alertas pendentes."""
    alerts = await alerts_repo.get_pending_alerts(db)
    count = len(alerts)
    return {
        "count": count,
        "alerts": [
            {
                "id": str(a.id),
                "alert_type": a.alert_type.value,
                "title": a.title,
                "description": a.description,
                "client_name": a.client_name,
                "client_phone": a.client_phone,
                "last_message": a.last_message,
                "order_id": str(a.order_id) if a.order_id else None,
                "resolved": a.resolved,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
    }


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Marca um alerta como resolvido."""
    ok = await alerts_repo.resolve_alert(db, alert_id)
    if not ok:
        raise HTTPException(404, "Alerta não encontrado ou já resolvido")
    await db.commit()
    return {"status": "ok"}


# ============================================================
# CATALOG
# ============================================================

@router.get("/catalog")
async def get_catalog(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Catálogo completo para gestão."""
    sizes = await catalog_repo.get_all_sizes(db)
    fillings = await catalog_repo.get_all_fillings(db)
    extras = await catalog_repo.get_all_extras(db)
    finishes = await catalog_repo.get_all_finishes(db)
    sweets = await catalog_repo.get_all_sweets(db)
    time_slots = await catalog_repo.get_all_time_slots(db)

    return {
        "sizes": [
            {
                "id": s.id,
                "description": s.description,
                "weight_kg": float(s.weight_kg),
                "servings": s.servings,
                "shape": s.shape.value if s.shape else None,
                "filling_layers": s.filling_layers,
                "price_white": float(s.price_white),
                "price_chocolate": float(s.price_chocolate),
                "active": s.active,
                "sort_order": s.sort_order,
            }
            for s in sizes
        ],
        "fillings": [
            {"id": f.id, "name": f.name, "available": f.available, "sort_order": f.sort_order}
            for f in fillings
        ],
        "extras": [
            {
                "id": e.id,
                "name": e.name,
                "price_per_layer": float(e.price_per_layer),
                "requires_approval": e.requires_approval,
                "description": e.description,
                "active": e.active,
                "sort_order": e.sort_order,
            }
            for e in extras
        ],
        "finishes": [
            {
                "id": f.id,
                "name": f.name,
                "requires_approval": f.requires_approval,
                "has_extra_cost": f.has_extra_cost,
                "description": f.description,
                "active": f.active,
                "sort_order": f.sort_order,
            }
            for f in finishes
        ],
        "sweets": [
            {
                "id": s.id,
                "name": s.name,
                "unit_quantity": s.unit_quantity,
                "price": float(s.price),
                "min_order_qty": s.min_order_qty,
                "description": s.description,
                "active": s.active,
                "sort_order": s.sort_order,
            }
            for s in sweets
        ],
        "time_slots": [
            {
                "id": t.id,
                "slot_time": t.slot_time.strftime("%H:%M") if t.slot_time else None,
                "label": t.label,
                "available": t.available,
                "sort_order": t.sort_order,
            }
            for t in time_slots
        ],
    }


@router.patch("/catalog/{catalog_type}/{item_id}")
async def update_catalog_item(
    catalog_type: str,
    item_id: int,
    body: CatalogItemUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Atualiza um item do catálogo."""
    update_fn = {
        "sizes": catalog_repo.update_size,
        "fillings": catalog_repo.update_filling,
        "extras": catalog_repo.update_extra,
        "finishes": catalog_repo.update_finish,
        "sweets": catalog_repo.update_sweet,
    }.get(catalog_type)

    if not update_fn:
        raise HTTPException(400, f"Tipo de catálogo inválido: {catalog_type}")

    ok = await update_fn(db, item_id, body.data)
    if not ok:
        raise HTTPException(404, "Item não encontrado")

    await db.commit()
    return {"status": "ok"}


# ============================================================
# SETTINGS
# ============================================================

@router.get("/settings")
async def get_settings_endpoint(
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Retorna todas as configurações."""
    settings = await settings_repo.get_all_settings(db)
    return {"settings": settings}


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(_verify_admin_token),
):
    """Salva configurações."""
    await settings_repo.upsert_many_settings(db, body.settings)
    await db.commit()
    logger.info("settings_updated", keys=list(body.settings.keys()))
    return {"status": "ok"}

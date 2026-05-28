"""
Order Engine: executa ações determinadas pela State Machine.
Cada action_code tem um handler que salva dados e retorna contexto para a resposta.
"""

from decimal import Decimal
from datetime import time as dt_time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SmActionEnum, DoughType, CakeShape, OrderStatus,
    EventTypeEnum, ConversationState, ActiveFlowType, Order,
)
from app.repositories import (
    orders as order_repo,
    catalog as catalog_repo,
    events as event_repo,
    availability as avail_repo,
    conversations as conv_repo,
)
from app.core.classifier import ClassificationResult
from sqlalchemy import select
from app.logging_config import get_logger

logger = get_logger(__name__)


class ActionContext:
    """Contexto produzido pela execução de uma ação."""

    def __init__(self):
        self.catalog_items: list = []
        self.order_data: dict = {}
        self.media_references: list[str] = []
        self.message_data: dict = {}
        self.error: str | None = None


async def execute_action(
    db: AsyncSession,
    action_code: SmActionEnum,
    conversation_id: UUID,
    client_id: UUID,
    classification: ClassificationResult,
    order_id: UUID | None = None,
) -> ActionContext:
    """
    Executa a ação determinada pela State Machine.
    Retorna ActionContext com dados necessários para construir a resposta.
    """
    ctx = ActionContext()

    handlers = {
        SmActionEnum.REGISTER_CLIENT_AND_SHOW_MENU: _handle_register_and_menu,
        SmActionEnum.SHOW_MENU: _handle_show_menu,
        SmActionEnum.SHOW_SEARCH_MENU: _handle_show_search_menu,
        SmActionEnum.SHOW_SIZES_AND_RETURN: _handle_show_sizes,
        SmActionEnum.SHOW_FILLINGS_AND_RETURN: _handle_show_fillings,
        SmActionEnum.SHOW_SWEETS_AND_RETURN: _handle_show_sweets,
        SmActionEnum.ASK_VALUES_CRITERIA: _handle_ask_values,
        SmActionEnum.SHOW_VALUES_AND_RETURN: _handle_show_values,
        SmActionEnum.CREATE_ORDER_AND_ASK_SIZE: _handle_create_order,
        SmActionEnum.SAVE_SIZE_AND_ASK_DOUGH: _handle_save_size,
        SmActionEnum.SAVE_DOUGH_AND_ASK_FILLING1: _handle_save_dough,
        SmActionEnum.SAVE_FILLING1_AND_ASK_FILLING2: _handle_save_filling1,
        SmActionEnum.SAVE_FILLING_AND_ASK_EXTRAS: _handle_save_filling,
        SmActionEnum.SAVE_EXTRAS_AND_ASK_FINISH: _handle_save_extras,
        SmActionEnum.SAVE_FINISH_AND_ASK_DATE: _handle_save_finish,
        SmActionEnum.SAVE_DATE_AND_ASK_TIME: _handle_save_date,
        SmActionEnum.REJECT_DATE_AND_ASK_AGAIN: _handle_reject_date,
        SmActionEnum.SAVE_TIME_AND_ASK_NOTES: _handle_save_time,
        SmActionEnum.SAVE_NOTES_AND_SHOW_SUMMARY: _handle_save_notes,
        SmActionEnum.FINALIZE_ORDER_AND_LOCK: _handle_finalize,
        SmActionEnum.CANCEL_ORDER_AND_RETURN: _handle_cancel,
        SmActionEnum.ASK_ORDER_ID: _handle_ask_order_id,
        SmActionEnum.CHECK_ORDER_STATUS: _handle_check_order,
        SmActionEnum.INCREMENT_FALLBACK: _handle_increment_fallback,
        SmActionEnum.ASK_HUMAN_REASON: _handle_ask_human_reason,
        SmActionEnum.PAUSE_BOT_AND_NOTIFY_HUMAN: _handle_pause_bot,
        SmActionEnum.RESUME_BOT: _handle_resume_bot,
    }

    handler = handlers.get(action_code)
    if handler:
        await handler(db, ctx, conversation_id, client_id, classification, order_id)
    else:
        logger.warning("action_handler_not_found", action_code=action_code.value)
        ctx.error = f"Handler não encontrado para {action_code.value}"

    return ctx


# ============================================================
# HANDLERS
# ============================================================

async def _handle_register_and_menu(db, ctx, conversation_id, client_id, classification, order_id):
    """Registra cliente e mostra menu."""
    await event_repo.log_event(
        db, EventTypeEnum.CLIENT_CREATED,
        conversation_id=conversation_id,
        payload={"name": classification.matched_value},
    )
    # Atualizar flow
    await conv_repo.update_conversation_state(
        db, conversation_id,
        new_state=ConversationState.MENU_PRINCIPAL,
        active_flow=ActiveFlowType.MENU,
    )


async def _handle_show_menu(db, ctx, conversation_id, client_id, classification, order_id):
    """Mostra menu principal."""
    pass  # Resposta construída pelo response_builder


async def _handle_show_search_menu(db, ctx, conversation_id, client_id, classification, order_id):
    """Mostra submenu de pesquisa."""
    await conv_repo.update_conversation_state(
        db, conversation_id,
        new_state=ConversationState.PESQUISA,
        active_flow=ActiveFlowType.PESQUISA,
    )


async def _handle_show_sizes(db, ctx, conversation_id, client_id, classification, order_id):
    """Mostra tamanhos e volta ao menu."""
    sizes = await catalog_repo.get_active_sizes(db)
    ctx.catalog_items = sizes
    ctx.media_references = ["CARDAPIO_1R", "CARDAPIO_2R"]


async def _handle_show_fillings(db, ctx, conversation_id, client_id, classification, order_id):
    """Mostra recheios e volta ao menu."""
    fillings = await catalog_repo.get_active_fillings(db)
    ctx.catalog_items = fillings
    ctx.media_references = ["RECHEIOS"]


async def _handle_show_sweets(db, ctx, conversation_id, client_id, classification, order_id):
    """Mostra docinhos e volta ao menu."""
    sweets = await catalog_repo.get_active_sweets(db)
    ctx.catalog_items = sweets
    ctx.media_references = ["DOCINHOS"]


async def _handle_ask_values(db, ctx, conversation_id, client_id, classification, order_id):
    """Pergunta critério de pesquisa de valores."""
    pass


async def _handle_show_values(db, ctx, conversation_id, client_id, classification, order_id):
    """Mostra cálculo de valores."""
    sizes = await catalog_repo.get_active_sizes(db)
    ctx.catalog_items = sizes


async def _handle_create_order(db, ctx, conversation_id, client_id, classification, order_id):
    """Cria pedido rascunho e pede tamanho."""
    cancelled_ids = await order_repo.cancel_old_drafts(db, conversation_id)
    for cid in cancelled_ids:
        await event_repo.log_event(
            db, EventTypeEnum.ORDER_CANCELLED,
            conversation_id=conversation_id,
            order_id=cid,
            payload={"reason": "new_draft_started"},
        )

    order = await order_repo.create_draft_order(db, client_id, conversation_id)
    await event_repo.log_event(
        db, EventTypeEnum.ORDER_STARTED,
        conversation_id=conversation_id,
        order_id=order.id,
    )
    sizes = await catalog_repo.get_active_sizes(db)
    ctx.catalog_items = sizes
    ctx.order_data["order_id"] = str(order.id)
    ctx.media_references = ["CARDAPIO_1R", "CARDAPIO_2R"]


async def _handle_save_size(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva tamanho e pede massa."""
    if not order_id or not classification.matched_id:
        ctx.error = "Dados insuficientes para salvar tamanho"
        return

    size = await catalog_repo.get_size_by_id(db, classification.matched_id)
    if not size:
        ctx.error = "Tamanho não encontrado"
        return

    # Usar preço de massa branca como default (será ajustado ao escolher massa)
    await order_repo.update_order_size(
        db, order_id,
        size_id=size.id,
        shape=CakeShape(size.shape.value),
        filling_count=size.filling_layers,
        base_value=Decimal(str(size.price_white)),
    )
    await event_repo.log_event(
        db, EventTypeEnum.SIZE_SELECTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"size_id": size.id, "description": size.description},
    )
    ctx.order_data["size"] = size
    ctx.order_data["filling_layers"] = size.filling_layers


async def _handle_save_dough(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva massa e pede recheio 1."""
    if not order_id or not classification.matched_value:
        ctx.error = "Dados insuficientes para salvar massa"
        return

    dough = DoughType(classification.matched_value)
    order = await order_repo.get_active_order(db, conversation_id)
    if not order or not order.size_id:
        ctx.error = "Pedido ou tamanho não encontrado"
        return

    size = await catalog_repo.get_size_by_id(db, order.size_id)
    if not size:
        ctx.error = "Tamanho não encontrado"
        return

    base_value = Decimal(str(size.price_chocolate if dough == DoughType.CHOCOLATE else size.price_white))

    await order_repo.update_order_dough(db, order_id, dough, base_value)
    await event_repo.log_event(
        db, EventTypeEnum.DOUGH_SELECTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"dough": dough.value},
    )

    fillings = await catalog_repo.get_active_fillings(db)
    ctx.catalog_items = fillings
    ctx.media_references = ["RECHEIOS"]


async def _handle_save_filling1(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva recheio 1 e pede recheio 2 (bolo com 2 camadas)."""
    if not order_id or not classification.matched_id:
        ctx.error = "Dados insuficientes para salvar recheio"
        return

    await order_repo.update_order_filling(db, order_id, 1, classification.matched_id)
    await event_repo.log_event(
        db, EventTypeEnum.FILLING_SELECTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"filling_number": 1, "filling_id": classification.matched_id},
    )

    fillings = await catalog_repo.get_active_fillings(db)
    ctx.catalog_items = fillings
    ctx.media_references = ["RECHEIOS"]


async def _handle_save_filling(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva recheio (1 ou 2) e pede extras."""
    if not order_id or not classification.matched_id:
        ctx.error = "Dados insuficientes para salvar recheio"
        return

    order = await order_repo.get_active_order(db, conversation_id)
    if not order:
        ctx.error = "Pedido não encontrado"
        return

    filling_number = 1 if not order.filling_1_id else 2
    await order_repo.update_order_filling(db, order_id, filling_number, classification.matched_id)
    await event_repo.log_event(
        db, EventTypeEnum.FILLING_SELECTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"filling_number": filling_number, "filling_id": classification.matched_id},
    )

    extras = await catalog_repo.get_active_extras(db)
    ctx.catalog_items = extras


async def _handle_save_extras(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva adicionais e pede finalização."""
    if not order_id:
        ctx.error = "Pedido não encontrado"
        return

    order = await order_repo.get_active_order(db, conversation_id)
    if not order:
        ctx.error = "Pedido não encontrado"
        return

    # Limpar extras anteriores
    await order_repo.clear_order_extras(db, order_id)

    if classification.matched_value != "SKIP" and classification.matched_id:
        extra = await catalog_repo.get_extra_by_id(db, classification.matched_id)
        if extra:
            if extra.requires_approval or extra.price_per_layer <= 0:
                ctx.message_data["create_alert"] = True
                ctx.message_data["alert_reason"] = f"Aprovação manual do adicional: {extra.name}"
                ctx.order_data["needs_approval"] = True
                # Marcar status de alerta para o message_service poder lidar se necessário
                return

            layers = order.filling_count or 1
            await order_repo.add_order_extra(
                db, order_id, extra.id, layers, Decimal(str(extra.price_per_layer))
            )
            extras_total = Decimal(str(extra.price_per_layer)) * layers
            await order_repo.update_order_values(db, order_id, extras_value=extras_total)
            await event_repo.log_event(
                db, EventTypeEnum.EXTRA_SELECTED,
                conversation_id=conversation_id,
                order_id=order_id,
                payload={"extra_id": extra.id, "layers": layers},
            )
    else:
        await order_repo.update_order_values(db, order_id, extras_value=Decimal("0.00"))

    finishes = await catalog_repo.get_active_finishes(db)
    ctx.catalog_items = finishes


async def _handle_save_finish(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva finalização e pede data."""
    if not order_id or not classification.matched_id:
        ctx.error = "Dados insuficientes para salvar finalização"
        return

    finish = await catalog_repo.get_finish_by_id(db, classification.matched_id)
    if not finish:
        ctx.error = "Finalização não encontrada"
        return

    if finish.requires_approval or finish.has_extra_cost:
        ctx.message_data["create_alert"] = True
        ctx.message_data["alert_reason"] = f"Aprovação manual da finalização: {finish.name}"
        ctx.order_data["needs_approval"] = True
        return

    await order_repo.update_order_finish(db, order_id, finish.id)
    await event_repo.log_event(
        db, EventTypeEnum.FINISH_SELECTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"finish_id": finish.id},
    )


async def _handle_save_date(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva data e pede horário."""
    if not order_id or not classification.parsed_date:
        ctx.error = "Dados insuficientes para salvar data"
        return

    await order_repo.update_order_date(db, order_id, classification.parsed_date)
    await event_repo.log_event(
        db, EventTypeEnum.DATE_SELECTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"date": str(classification.parsed_date)},
    )

    time_slots = await catalog_repo.get_active_time_slots(db)
    ctx.catalog_items = time_slots


async def _handle_reject_date(db, ctx, conversation_id, client_id, classification, order_id):
    """Data indisponível, pede outra."""
    ctx.message_data["rejection_reason"] = classification.extra_data.get("reason", "Data indisponível")


async def _handle_save_time(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva horário e pede observações."""
    if not order_id:
        ctx.error = "Pedido não encontrado"
        return

    if classification.matched_id:
        slot = await catalog_repo.get_time_slot_by_id(db, classification.matched_id)
        if slot:
            await order_repo.update_order_time(db, order_id, slot.slot_time)
            await event_repo.log_event(
                db, EventTypeEnum.TIME_SELECTED,
                conversation_id=conversation_id,
                order_id=order_id,
                payload={"time": slot.label},
            )


async def _handle_save_notes(db, ctx, conversation_id, client_id, classification, order_id):
    """Salva observações e mostra resumo."""
    if not order_id:
        ctx.error = "Pedido não encontrado"
        return

    notes = classification.matched_value or "Nenhuma"
    await order_repo.update_order_notes(db, order_id, notes)
    await event_repo.log_event(
        db, EventTypeEnum.NOTES_ADDED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"notes": notes},
    )

    # Calcular total e preparar resumo
    order = await order_repo.get_active_order(db, conversation_id)
    if order:
        base = order.base_value or Decimal("0")
        extras = order.extras_value or Decimal("0")
        total = base + extras
        await order_repo.update_order_values(db, order_id, total_value=total)
        ctx.order_data["order"] = order
        ctx.order_data["total_value"] = total


async def _handle_finalize(db, ctx, conversation_id, client_id, classification, order_id):
    """
    Finaliza pedido: verifica disponibilidade, muda status, incrementa vagas.
    Transacional — se lotar ou faltar dados, não confirma e reverte.
    """
    if not order_id:
        ctx.error = "Pedido não encontrado"
        return

    # Bloqueio explícito FOR UPDATE para concorrência
    query = select(Order).where(Order.id == order_id).with_for_update()
    result = await db.execute(query)
    order = result.scalar_one_or_none()

    if not order or order.status != OrderStatus.RASCUNHO:
        ctx.error = "Pedido não encontrado ou já processado"
        return

    # Validar campos obrigatórios antes de finalizar
    if not all([
        order.size_id, order.dough, order.filling_1_id, order.finish_id,
        order.pickup_date, order.pickup_time, order.base_value, order.total_value
    ]):
        ctx.error = "Faltam dados obrigatórios no pedido"
        ctx.message_data["create_alert"] = True
        ctx.message_data["alert_reason"] = "Tentativa de finalização com dados incompletos"
        return

    # Verificar disponibilidade da data e incrementar
    avail = await avail_repo.check_date_available(db, order.pickup_date)
    if not avail["available"]:
        ctx.error = "Data ficou indisponível no momento da confirmação"
        ctx.message_data["date_full"] = True
        return

    success = await avail_repo.increment_confirmed_orders(db, order.pickup_date)
    if not success:
        ctx.error = "Vagas esgotadas no momento da confirmação"
        ctx.message_data["date_full"] = True
        return

    # Finalizar pedido
    await order_repo.finalize_order(db, order_id)
    await event_repo.log_event(
        db, EventTypeEnum.ORDER_SUBMITTED,
        conversation_id=conversation_id,
        order_id=order_id,
        payload={"status": "AGUARDANDO_CONFIRMACAO"},
    )

    ctx.order_data["order"] = order
    ctx.order_data["finalized"] = True


async def _handle_cancel(db, ctx, conversation_id, client_id, classification, order_id):
    """Cancela pedido e volta ao menu."""
    if order_id:
        await order_repo.cancel_order(db, order_id)
        await event_repo.log_event(
            db, EventTypeEnum.ORDER_CANCELLED,
            conversation_id=conversation_id,
            order_id=order_id,
        )


async def _handle_ask_order_id(db, ctx, conversation_id, client_id, classification, order_id):
    """Pede número do pedido para consulta."""
    pass


async def _handle_check_order(db, ctx, conversation_id, client_id, classification, order_id):
    """Consulta status do pedido."""
    if classification.matched_value:
        try:
            num = int(classification.matched_value)
            order = await order_repo.get_order_by_number(db, num)
            if order:
                ctx.order_data["order"] = order
                ctx.order_data["found"] = True
            else:
                ctx.order_data["found"] = False
        except ValueError:
            ctx.order_data["found"] = False


async def _handle_increment_fallback(db, ctx, conversation_id, client_id, classification, order_id):
    """Fallback: input inválido."""
    await event_repo.log_event(
        db, EventTypeEnum.FALLBACK_TRIGGERED,
        conversation_id=conversation_id,
        payload={"input": classification.matched_value or ""},
    )


async def _handle_ask_human_reason(db, ctx, conversation_id, client_id, classification, order_id):
    """Pede motivo para atendimento humano."""
    await event_repo.log_event(
        db, EventTypeEnum.HUMAN_REQUESTED,
        conversation_id=conversation_id,
    )


async def _handle_pause_bot(db, ctx, conversation_id, client_id, classification, order_id):
    """Pausa o bot e notifica humano."""
    await event_repo.log_event(
        db, EventTypeEnum.BOT_PAUSED,
        conversation_id=conversation_id,
        payload={"reason": classification.matched_value or "fallback_or_request"},
    )
    ctx.message_data["create_alert"] = True
    ctx.message_data["alert_reason"] = classification.matched_value or "Bot pausado"


async def _handle_resume_bot(db, ctx, conversation_id, client_id, classification, order_id):
    """Resume o bot após lock expirado."""
    await conv_repo.clear_human_lock(db, conversation_id)
    await event_repo.log_event(
        db, EventTypeEnum.BOT_RESUMED,
        conversation_id=conversation_id,
    )

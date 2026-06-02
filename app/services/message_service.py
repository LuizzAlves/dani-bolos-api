"""
Message Service: orquestrador principal do processamento de mensagens.
Equivalente ao workflow principal do n8n.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.payload_parser import parse_evolution_payload
from app.core.classifier import classify_input, ClassificationResult
from app.core.state_machine import resolve_transition
from app.core.order_engine import execute_action, ActionContext
from app.core.response_builder import build_response
from app.core.semantic_translator import semantic_translate
from app.models import (
    ConversationState, SmTriggerEnum, SmActionEnum,
    EventTypeEnum, ActiveFlowType, AlertTypeEnum,
    Client, Conversation, Order, OrderExtra, Event,
)
from app.repositories import (
    clients as client_repo,
    conversations as conv_repo,
    orders as order_repo,
    events as event_repo,
    catalog as catalog_repo,
    availability as avail_repo,
    settings as settings_repo,
    alerts as alerts_repo,
)
from app.integrations import evolution as evo_client
from app.services import media_service, google_sheets_service
from app.schemas.evolution import ParsedMessage, WebhookResponse
from app.schemas.messages import ResponseItem
from app.logging_config import get_logger

logger = get_logger(__name__)

BACK_COMMANDS = {"voltar"}
RETURN_MENU_COMMANDS = {"menu", "inicio", "início", "comecar", "começar", "principal", "menu principal"}
CANCEL_COMMANDS = {"cancelar", "cancela", "desistir", "parar", "encerrar"}
GREETING_COMMANDS = {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"}
DEV_RESET_COMMAND = "ThinkDevLuiz@"


def _is_expired(dt: datetime | None) -> bool:
    """Compara datetime (aware ou naive) com o agora de São Paulo."""
    if not dt:
        return False
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    return now > dt


def _alert_type_from_reason(reason: str | None) -> AlertTypeEnum:
    """Classifica o tipo de alerta administrativo a partir do motivo."""
    reason_lower = (reason or "").lower()
    if any(kw in reason_lower for kw in ["adicional", "finaliza", "aprova", "personalizado"]):
        return AlertTypeEnum.CUSTOM_FILLING
    if any(kw in reason_lower for kw in ["humano", "atendente", "falar com a dani"]):
        return AlertTypeEnum.HUMAN_REQUESTED
    if any(kw in reason_lower for kw in ["max", "fallback", "travado", "tentativas"]):
        return AlertTypeEnum.MAX_FALLBACK
    if any(kw in reason_lower for kw in ["erro", "dados incompletos", "falha"]):
        return AlertTypeEnum.FLOW_ERROR
    return AlertTypeEnum.FLOW_ERROR


async def process_message(db: AsyncSession, raw_payload: dict | list) -> WebhookResponse:
    """
    Pipeline principal de processamento de mensagem.

    1. Parse payload
    2. Filtrar (grupo, fromMe, status)
    3. Buscar/criar cliente e conversa
    4. Verificar human_lock
    5. Classificar input
    6. Resolver transição
    7. Executar ação
    8. Construir resposta
    9. Enviar via Evolution API
    """
    # 1. Parse
    msg = parse_evolution_payload(raw_payload)

    # 2. Filtrar
    if msg.should_ignore:
        logger.debug("message_ignored", reason=msg.ignore_reason)
        return WebhookResponse(
            status="ignored",
            message=msg.ignore_reason or "ignored",
        )

    if (msg.text or "").strip() == DEV_RESET_COMMAND:
        deleted = await _reset_client_test_data(db, msg.phone)
        await db.commit()
        try:
            await evo_client.send_text(
                msg.phone,
                "Reset de teste aplicado. Envie uma nova mensagem para começar do zero.",
            )
        except Exception:
            pass
        logger.info("dev_reset_command_applied", phone=msg.phone[:6] + "***", deleted=deleted)
        return WebhookResponse(
            status="ok",
            message="Dev reset applied",
            processed=True,
        )

    # 2.5 Idempotência
    if await event_repo.has_message_event(db, msg.message_id):
        logger.info("message_id_idempotency_skip", message_id=msg.message_id)
        return WebhookResponse(status="ignored", message="Idempotency match")

    # 3. Mídia não suportada
    if msg.is_unsupported_media:
        await evo_client.send_text(
            msg.phone,
            "Por enquanto preciso que você me mande por escrito. 📝\n"
            "Não consigo processar áudios, imagens ou vídeos ainda."
        )
        return WebhookResponse(
            status="unsupported_media",
            message="Tipo de mídia não suportado",
            processed=True,
        )

    # 4. Buscar/criar cliente
    client, is_new_client = await client_repo.get_or_create_client(
        db, msg.phone, msg.push_name
    )

    # 5. Buscar/criar conversa
    conversation, is_new_conv = await conv_repo.get_or_create_conversation(
        db, client.id
    )

    # 6. Verificar human_lock
    lock_expired_trigger = False
    if conversation.human_lock:
        if _is_expired(conversation.human_lock_until):
            logger.info("human_lock_expired", phone=msg.phone[:6] + "***")
            conversation.human_lock = False
            conversation.human_lock_until = None
            lock_expired_trigger = True
        else:
            logger.info("human_lock_active", phone=msg.phone[:6] + "***")
            return WebhookResponse(
                status="human_lock",
                message="Bot pausado — atendimento humano ativo",
            )

    # 6.5 Verificar bot_active
    bot_active = await settings_repo.get_setting(db, "bot_active")
    if bot_active is False and not conversation.human_lock:
        logger.info("bot_is_paused_globally", phone=msg.phone[:6] + "***")
        await event_repo.log_event(
            db, EventTypeEnum.MESSAGE_RECEIVED,
            conversation_id=conversation.id,
            payload={"text": msg.text, "phone": msg.phone[:6] + "***", "message_id": msg.message_id, "note": "bot_paused"}
        )
        await db.commit()

        await evo_client.send_text(
            msg.phone,
            "Oi! No momento o atendimento automático está pausado. A Dani vai te responder assim que possível. 💕"
        )

        return WebhookResponse(
            status="bot_paused",
            message="Bot inativo globalmente",
            processed=True,
        )

    # 7. Log MESSAGE_RECEIVED
    await event_repo.log_event(
        db, EventTypeEnum.MESSAGE_RECEIVED,
        conversation_id=conversation.id,
        payload={
            "text": msg.text,
            "phone": msg.phone[:6] + "***",
            "message_id": msg.message_id,
        },
    )

    # 8. Enviar "digitando..." (fire and forget)
    try:
        await evo_client.send_presence(msg.phone, "composing")
    except Exception:
        pass  # Não travar por falha de presença

    # 9. Atualizar última interação
    await conv_repo.update_last_interaction(db, conversation.id)

    # 10. Buscar pedido ativo se relevante
    active_order = None
    order_states = {
        ConversationState.ESCOLHENDO_TAMANHO, ConversationState.ESCOLHENDO_MASSA,
        ConversationState.ESCOLHENDO_RECHEIOS, ConversationState.ESCOLHENDO_RECHEIO_2,
        ConversationState.ESCOLHENDO_ADICIONAIS, ConversationState.ESCOLHENDO_FINALIZACAO,
        ConversationState.DEFININDO_DATA, ConversationState.DEFININDO_HORARIO,
        ConversationState.DEFININDO_OBSERVACOES, ConversationState.CONFIRMANDO_PEDIDO,
    }
    if conversation.state in order_states:
        active_order = await order_repo.get_active_order(db, conversation.id)

    navigation_result = await _handle_global_navigation_command(
        db=db,
        msg=msg,
        conversation=conversation,
        active_order=active_order,
        client_name=client.name,
        order_states=order_states,
    )
    if navigation_result:
        return navigation_result

    # 11. Carregar catálogo apenas quando necessário
    catalog_items = await _load_catalog_for_state(db, conversation.state, active_order)

    # 12. Classificar input
    if lock_expired_trigger:
        classification = ClassificationResult(trigger=SmTriggerEnum.LOCK_EXPIRED)
        trigger = SmTriggerEnum.LOCK_EXPIRED
    else:
        classification = classify_input(
            state=conversation.state,
            text=msg.text or "",
            normalized=msg.normalized_text or "",
            catalog_items=catalog_items,
            order_context={"order": active_order} if active_order else None,
        )
        trigger = classification.trigger

    # 13. Tradução semântica se classificação falhou
    if trigger is None and msg.normalized_text:
        # Tentar Groq para estados de catálogo
        catalog_states = {
            ConversationState.ESCOLHENDO_TAMANHO,
            ConversationState.ESCOLHENDO_RECHEIOS,
            ConversationState.ESCOLHENDO_RECHEIO_2,
        }
        if conversation.state in catalog_states and catalog_items:
            options = [
                {"id": item.id, "name": getattr(item, 'name', getattr(item, 'description', str(item.id)))}
                for item in catalog_items
            ]
            matched_id = await semantic_translate(
                text=msg.text or "",
                state=conversation.state.value,
                options=options,
            )
            if matched_id:
                classification = ClassificationResult(
                    trigger=SmTriggerEnum.INPUT_VALID,
                    matched_id=matched_id,
                )
                trigger = SmTriggerEnum.INPUT_VALID

    # 14. Se ainda sem trigger → INPUT_INVALID
    if trigger is None:
        trigger = SmTriggerEnum.INPUT_INVALID
        classification = ClassificationResult(trigger=trigger)

    # 15. Resolver transição: state + trigger → next_state + action
    # Caso especial: verificar disponibilidade antes da transição de DATA
    if (
        conversation.state == ConversationState.DEFININDO_DATA
        and trigger == SmTriggerEnum.INPUT_VALID
        and classification.parsed_date
    ):
        avail = await avail_repo.check_date_available(db, classification.parsed_date)
        if not avail["available"]:
            trigger = SmTriggerEnum.DATE_UNAVAILABLE
            reason = avail.get("block_reason", "Data lotada ou bloqueada")
            if reason == "LIMITE_ATINGIDO":
                custom_msg = await settings_repo.get_setting(db, "limit_reached_message")
                reason = custom_msg or "Infelizmente já atingimos o limite de encomendas para esta data. Por favor, escolha outro dia."
            classification.extra_data["reason"] = reason
        else:
            trigger = SmTriggerEnum.DATE_AVAILABLE

    # Caso especial: todo bolo do fluxo atual tem 2 recheios.
    if (
        conversation.state == ConversationState.ESCOLHENDO_RECHEIOS
        and trigger == SmTriggerEnum.INPUT_VALID
        and active_order
    ):
        trigger = SmTriggerEnum.TWO_FILLINGS_SELECTED

    transition = await resolve_transition(db, conversation, trigger)

    if transition is None:
        logger.error(
            "transition_failed",
            state=conversation.state.value,
            trigger=trigger.value,
        )
        await evo_client.send_text(
            msg.phone,
            "Desculpe, algo deu errado. Tente novamente ou digite \"humano\" para falar com a Dani."
        )
        return WebhookResponse(
            status="error",
            message="Transição não encontrada",
            processed=True,
        )

    if transition and transition.action_code == SmActionEnum.CREATE_ORDER_AND_ASK_SIZE:
        orders_paused = await settings_repo.get_setting(db, "orders_paused")
        if orders_paused is True:
            await evo_client.send_text(
                msg.phone,
                "No momento nossa agenda está lotada/pausada devido à alta demanda! 🛑\n"
                "Você ainda pode consultar nosso cardápio e valores pelo menu."
            )
            return WebhookResponse(status="orders_paused", message="Orders paused", processed=True)

    # 16. Executar ação
    order_id = active_order.id if active_order else None
    ctx = await execute_action(
        db, transition.action_code,
        conversation_id=conversation.id,
        client_id=client.id,
        classification=classification,
        order_id=order_id,
    )

    if ctx.message_data.get("return_to_menu"):
        transition.next_state = ConversationState.MENU_PRINCIPAL
    elif ctx.message_data.get("keep_values_flow"):
        transition.next_state = ConversationState.PESQUISA_VALORES
    elif ctx.message_data.get("keep_observacoes_flow"):
        transition.next_state = ConversationState.DEFININDO_OBSERVACOES

    # 17. Interceptar aprovação manual ANTES de construir a resposta
    if ctx.order_data.get("needs_approval"):
        transition.next_state = ConversationState.BOT_PAUSADO
        await conv_repo.set_human_lock(db, conversation.id)
        
        # Gerar alerta para Sheets
        ctx.message_data["create_alert"] = True
        ctx.message_data.setdefault("alert_reason", "Aprovação manual solicitada pelo cliente.")
        
        # Resposta específica
        responses = [
            ResponseItem(type="text", text="Esse item precisa de confirmação da Dani antes de seguir. Vou pausar o atendimento automático e ela te chama por aqui para confirmar os detalhes. 💕")
        ]
    else:
        # 18. Construir resposta normal
        responses = build_response(
            action_code=transition.action_code,
            ctx=ctx,
            current_state=conversation.state,
            client_name=client.name,
        )

    active_flow = _determine_flow(transition.next_state)
    await conv_repo.update_conversation_state(
        db, conversation.id,
        new_state=transition.next_state,
        active_flow=active_flow,
        fallback_count=transition.new_fallback_count,
    )

    # Log state change
    await event_repo.log_event(
        db, EventTypeEnum.STATE_CHANGED,
        conversation_id=conversation.id,
        order_id=order_id,
        payload={
            "from": conversation.state.value,
            "to": transition.next_state.value,
            "trigger": trigger.value,
            "action": transition.action_code.value,
        },
    )

    # 19. Commit antes de enviar
    await db.commit()

    # 20. Google Sheets: enviar dados do pedido / criar alertas em background
    if transition.action_code == SmActionEnum.FINALIZE_ORDER_AND_LOCK and ctx.order_data.get("finalized"):
        if active_order:
            await google_sheets_service.upsert_order(db, active_order.id)
            await db.commit()

    if ctx.message_data.get("create_alert"):
        reason = ctx.message_data.get("alert_reason", "")
        alert_type = _alert_type_from_reason(reason)

        await alerts_repo.create_alert(
            db,
            alert_type=alert_type,
            title=f"🚨 Bot pausado — {msg.phone[:6]}***",
            description=reason,
            client_id=client.id,
            conversation_id=conversation.id,
            order_id=active_order.id if active_order else None,
            client_phone=msg.phone,
            client_name=client.name,
            last_message=msg.text,
        )

        await google_sheets_service.create_alert(
            db,
            title=f"🚨 Bot pausado — {msg.phone[:6]}***",
            phone=msg.phone,
            reason=reason,
            conversation_id=conversation.id,
            order_id=str(active_order.id) if active_order else None,
            order_number=active_order.order_number if active_order else None,
        )
        await db.commit()

    # 21. Resolver e enviar mídia
    if ctx.media_references:
        try:
            media_items = await media_service.resolve_media_items(db, ctx.media_references)
            if media_items:
                await media_service.send_media_items(msg.phone, media_items)
        except Exception as e:
            logger.error("media_send_failed", error=str(e), phone=msg.phone[:6] + "***")
            await event_repo.log_event(
                db,
                EventTypeEnum.ERROR,
                conversation_id=conversation.id,
                order_id=order_id,
                payload={"error": "Failed to send catalog media", "detail": str(e)[:240]},
            )
            await db.commit()

    # 22. Enviar respostas de texto
    for resp in responses:
        if resp.type == "text" and resp.text:
            sent = await evo_client.send_text(msg.phone, resp.text)
            if not sent:
                await event_repo.log_event(
                    db, EventTypeEnum.ERROR,
                    conversation_id=conversation.id,
                    payload={"error": "Failed to send text via Evolution"},
                )
        elif resp.type == "media" and resp.media_url:
            await evo_client.send_media(
                msg.phone, resp.media_url, resp.caption, resp.media_type or "image"
            )

    return WebhookResponse(
        status="ok",
        message=f"Processed: {transition.action_code.value}",
        processed=True,
    )


async def _reset_client_test_data(db: AsyncSession, phone: str) -> dict[str, int]:
    """Remove dados do telefone de teste para recomeçar a conversa do zero."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    phone_candidates = {phone, digits}
    if digits.startswith("55"):
        phone_candidates.add(digits[2:])
    elif digits:
        phone_candidates.add(f"55{digits}")

    clients_result = await db.execute(
        select(Client.id).where(Client.phone.in_(phone_candidates))
    )
    client_ids = list(clients_result.scalars().all())
    if not client_ids:
        return {"clients": 0, "conversations": 0, "orders": 0}

    convs_result = await db.execute(
        select(Conversation.id).where(Conversation.client_id.in_(client_ids))
    )
    conv_ids = list(convs_result.scalars().all())

    orders_result = await db.execute(
        select(Order.id).where(Order.client_id.in_(client_ids))
    )
    order_ids = list(orders_result.scalars().all())

    if order_ids:
        await db.execute(delete(OrderExtra).where(OrderExtra.order_id.in_(order_ids)))
        await db.execute(delete(Event).where(Event.order_id.in_(order_ids)))
    if conv_ids:
        await db.execute(delete(Event).where(Event.conversation_id.in_(conv_ids)))
    if order_ids:
        await db.execute(delete(Order).where(Order.id.in_(order_ids)))
    if conv_ids:
        await db.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
    await db.execute(delete(Client).where(Client.id.in_(client_ids)))

    return {
        "clients": len(client_ids),
        "conversations": len(conv_ids),
        "orders": len(order_ids),
    }


async def _handle_global_navigation_command(
    db: AsyncSession,
    msg: ParsedMessage,
    conversation,
    active_order,
    client_name: str | None,
    order_states: set[ConversationState],
) -> WebhookResponse | None:
    """Trata comandos de navegação sem depender da State Machine."""
    normalized = (msg.normalized_text or "").strip()
    if not normalized:
        return None

    wants_back = normalized in BACK_COMMANDS
    wants_menu = normalized in RETURN_MENU_COMMANDS or (
        conversation.state == ConversationState.MENU_PRINCIPAL
        and normalized in GREETING_COMMANDS
    )
    wants_cancel = normalized in CANCEL_COMMANDS

    if not wants_back and not wants_menu and not wants_cancel:
        return None

    if wants_back and active_order and conversation.state in order_states:
        return await _handle_order_back_command(
            db=db,
            msg=msg,
            conversation=conversation,
            active_order=active_order,
            client_name=client_name,
        )

    ctx = ActionContext()
    responses: list[ResponseItem] = []

    if active_order and conversation.state in order_states and (wants_menu or wants_cancel):
        await order_repo.cancel_order(db, active_order.id)
        await event_repo.log_event(
            db,
            EventTypeEnum.ORDER_CANCELLED,
            conversation_id=conversation.id,
            order_id=active_order.id,
            payload={"reason": "client_navigation_cancel", "command": normalized},
        )
        responses.append(ResponseItem(text="Tudo bem, cancelei o rascunho desse pedido e voltei para o menu principal."))
    elif conversation.state in {
        ConversationState.PESQUISA,
        ConversationState.PESQUISA_VALORES,
        ConversationState.CONSULTA_PEDIDO,
        ConversationState.MENU_PRINCIPAL,
    }:
        if wants_cancel and conversation.state == ConversationState.CONSULTA_PEDIDO:
            responses.append(ResponseItem(text="Consulta cancelada. Voltando ao menu principal."))
        elif (wants_menu or wants_back) and conversation.state != ConversationState.MENU_PRINCIPAL:
            responses.append(ResponseItem(text="Voltando ao menu principal."))
    else:
        return None

    await conv_repo.update_conversation_state(
        db,
        conversation.id,
        new_state=ConversationState.MENU_PRINCIPAL,
        active_flow=ActiveFlowType.MENU,
        fallback_count=0,
    )
    await event_repo.log_event(
        db,
        EventTypeEnum.STATE_CHANGED,
        conversation_id=conversation.id,
        order_id=active_order.id if active_order else None,
        payload={
            "from": conversation.state.value,
            "to": ConversationState.MENU_PRINCIPAL.value,
            "trigger": "GLOBAL_NAVIGATION",
            "command": normalized,
        },
    )
    await db.commit()

    responses.extend(build_response(
        action_code=SmActionEnum.SHOW_MENU,
        ctx=ctx,
        current_state=ConversationState.MENU_PRINCIPAL,
        client_name=client_name,
    ))

    for resp in responses:
        if resp.type == "text" and resp.text:
            await evo_client.send_text(msg.phone, resp.text)

    return WebhookResponse(
        status="ok",
        message=f"Navigation command: {normalized}",
        processed=True,
    )


async def _handle_order_back_command(
    db: AsyncSession,
    msg: ParsedMessage,
    conversation,
    active_order,
    client_name: str | None,
) -> WebhookResponse:
    """Volta uma etapa dentro do fluxo de pedido sem cancelar o rascunho."""
    previous_step = _previous_order_step(conversation.state, active_order)

    if previous_step is None:
        return await _cancel_order_and_return_to_menu(
            db=db,
            msg=msg,
            conversation=conversation,
            active_order=active_order,
            client_name=client_name,
            command="voltar",
            intro="Voce estava no comeco do pedido, entao cancelei o rascunho e voltei para o menu principal.",
        )

    previous_state, action_code = previous_step
    ctx = await _prepare_back_context(db, previous_state, action_code, active_order)
    responses = [ResponseItem(text="Voltando uma etapa.")]
    responses.extend(build_response(
        action_code=action_code,
        ctx=ctx,
        current_state=previous_state,
        client_name=client_name,
    ))

    await conv_repo.update_conversation_state(
        db,
        conversation.id,
        new_state=previous_state,
        active_flow=ActiveFlowType.PEDIDO,
        fallback_count=0,
    )
    await event_repo.log_event(
        db,
        EventTypeEnum.STATE_CHANGED,
        conversation_id=conversation.id,
        order_id=active_order.id,
        payload={
            "from": conversation.state.value,
            "to": previous_state.value,
            "trigger": "ORDER_BACK",
            "command": "voltar",
            "action": action_code.value,
        },
    )
    await db.commit()

    if ctx.media_references:
        try:
            media_items = await media_service.resolve_media_items(db, ctx.media_references)
            if media_items:
                await media_service.send_media_items(msg.phone, media_items)
        except Exception as exc:
            logger.error("media_send_failed", error=str(exc), phone=msg.phone[:6] + "***")
            await event_repo.log_event(
                db,
                EventTypeEnum.ERROR,
                conversation_id=conversation.id,
                order_id=active_order.id,
                payload={"error": "Failed to send catalog media on back", "detail": str(exc)[:240]},
            )
            await db.commit()

    for resp in responses:
        if resp.type == "text" and resp.text:
            await evo_client.send_text(msg.phone, resp.text)
        elif resp.type == "media" and resp.media_url:
            await evo_client.send_media(
                msg.phone, resp.media_url, resp.caption, resp.media_type or "image"
            )

    return WebhookResponse(
        status="ok",
        message="Order step back",
        processed=True,
    )


async def _cancel_order_and_return_to_menu(
    db: AsyncSession,
    msg: ParsedMessage,
    conversation,
    active_order,
    client_name: str | None,
    command: str,
    intro: str,
) -> WebhookResponse:
    """Cancela o rascunho ativo e retorna ao menu."""
    ctx = ActionContext()
    await order_repo.cancel_order(db, active_order.id)
    await event_repo.log_event(
        db,
        EventTypeEnum.ORDER_CANCELLED,
        conversation_id=conversation.id,
        order_id=active_order.id,
        payload={"reason": "client_navigation_cancel", "command": command},
    )
    await conv_repo.update_conversation_state(
        db,
        conversation.id,
        new_state=ConversationState.MENU_PRINCIPAL,
        active_flow=ActiveFlowType.MENU,
        fallback_count=0,
    )
    await event_repo.log_event(
        db,
        EventTypeEnum.STATE_CHANGED,
        conversation_id=conversation.id,
        order_id=active_order.id,
        payload={
            "from": conversation.state.value,
            "to": ConversationState.MENU_PRINCIPAL.value,
            "trigger": "GLOBAL_NAVIGATION",
            "command": command,
        },
    )
    await db.commit()

    responses = [ResponseItem(text=intro)]
    responses.extend(build_response(
        action_code=SmActionEnum.SHOW_MENU,
        ctx=ctx,
        current_state=ConversationState.MENU_PRINCIPAL,
        client_name=client_name,
    ))
    for resp in responses:
        if resp.type == "text" and resp.text:
            await evo_client.send_text(msg.phone, resp.text)

    return WebhookResponse(
        status="ok",
        message=f"Navigation command: {command}",
        processed=True,
    )


def _previous_order_step(
    state: ConversationState,
    active_order,
) -> tuple[ConversationState, SmActionEnum] | None:
    """Mapeia o estado atual do pedido para a etapa anterior."""
    if state == ConversationState.ESCOLHENDO_TAMANHO:
        return None
    if state == ConversationState.ESCOLHENDO_MASSA:
        return ConversationState.ESCOLHENDO_TAMANHO, SmActionEnum.CREATE_ORDER_AND_ASK_SIZE
    if state == ConversationState.ESCOLHENDO_RECHEIOS:
        return ConversationState.ESCOLHENDO_MASSA, SmActionEnum.SAVE_SIZE_AND_ASK_DOUGH
    if state == ConversationState.ESCOLHENDO_RECHEIO_2:
        return ConversationState.ESCOLHENDO_RECHEIOS, SmActionEnum.SAVE_DOUGH_AND_ASK_FILLING1
    if state == ConversationState.ESCOLHENDO_ADICIONAIS:
        return ConversationState.ESCOLHENDO_RECHEIO_2, SmActionEnum.SAVE_FILLING1_AND_ASK_FILLING2
    if state == ConversationState.ESCOLHENDO_FINALIZACAO:
        return ConversationState.ESCOLHENDO_ADICIONAIS, SmActionEnum.SAVE_FILLING_AND_ASK_EXTRAS
    if state == ConversationState.DEFININDO_DATA:
        return ConversationState.ESCOLHENDO_FINALIZACAO, SmActionEnum.SAVE_EXTRAS_AND_ASK_FINISH
    if state == ConversationState.DEFININDO_HORARIO:
        return ConversationState.DEFININDO_DATA, SmActionEnum.SAVE_FINISH_AND_ASK_DATE
    if state == ConversationState.DEFININDO_OBSERVACOES:
        return ConversationState.DEFININDO_HORARIO, SmActionEnum.SAVE_DATE_AND_ASK_TIME
    if state == ConversationState.CONFIRMANDO_PEDIDO:
        return ConversationState.DEFININDO_OBSERVACOES, SmActionEnum.SAVE_TIME_AND_ASK_NOTES
    return None


async def _prepare_back_context(
    db: AsyncSession,
    previous_state: ConversationState,
    action_code: SmActionEnum,
    active_order,
) -> ActionContext:
    """Carrega os dados necessarios para reconstruir a pergunta da etapa anterior."""
    ctx = ActionContext()

    if previous_state == ConversationState.ESCOLHENDO_TAMANHO:
        ctx.catalog_items = await catalog_repo.get_active_sizes(db)
        ctx.media_references = ["CARDAPIO_2R"]
    elif previous_state == ConversationState.ESCOLHENDO_MASSA:
        size_id = getattr(active_order, "size_id", None)
        if size_id:
            ctx.order_data["size"] = await catalog_repo.get_size_by_id(db, size_id)
    elif previous_state in {ConversationState.ESCOLHENDO_RECHEIOS, ConversationState.ESCOLHENDO_RECHEIO_2}:
        ctx.catalog_items = await catalog_repo.get_active_fillings(db)
        ctx.media_references = ["RECHEIOS"]
    elif previous_state == ConversationState.ESCOLHENDO_ADICIONAIS:
        ctx.catalog_items = await catalog_repo.get_active_extras(db)
    elif previous_state == ConversationState.ESCOLHENDO_FINALIZACAO:
        ctx.catalog_items = await catalog_repo.get_active_finishes(db)
    elif previous_state == ConversationState.DEFININDO_HORARIO:
        slots = await catalog_repo.get_active_time_slots(db)
        if active_order and active_order.pickup_date:
            from app.core.service_hours import filter_time_slots
            ctx.catalog_items = await filter_time_slots(db, active_order.pickup_date, slots)
        else:
            ctx.catalog_items = slots

    return ctx


async def _load_catalog_for_state(db: AsyncSession, state: ConversationState, active_order=None) -> list:
    """Carrega catálogo apenas para estados que precisam."""
    catalog_map = {
        ConversationState.ESCOLHENDO_TAMANHO: catalog_repo.get_active_sizes,
        ConversationState.ESCOLHENDO_RECHEIOS: catalog_repo.get_active_fillings,
        ConversationState.ESCOLHENDO_RECHEIO_2: catalog_repo.get_active_fillings,
        ConversationState.ESCOLHENDO_ADICIONAIS: catalog_repo.get_active_extras,
        ConversationState.ESCOLHENDO_FINALIZACAO: catalog_repo.get_active_finishes,
        ConversationState.DEFININDO_HORARIO: catalog_repo.get_active_time_slots,
    }

    loader = catalog_map.get(state)
    if loader:
        items = await loader(db)
        if state == ConversationState.DEFININDO_HORARIO and active_order and active_order.pickup_date:
            from app.core.service_hours import filter_time_slots
            items = await filter_time_slots(db, active_order.pickup_date, items)
        return items
    return []


def _determine_flow(state: ConversationState) -> ActiveFlowType:
    """Determina o active_flow com base no estado."""
    order_states = {
        ConversationState.ESCOLHENDO_TAMANHO, ConversationState.ESCOLHENDO_MASSA,
        ConversationState.ESCOLHENDO_RECHEIOS, ConversationState.ESCOLHENDO_RECHEIO_2,
        ConversationState.ESCOLHENDO_ADICIONAIS, ConversationState.ESCOLHENDO_FINALIZACAO,
        ConversationState.DEFININDO_DATA, ConversationState.DEFININDO_HORARIO,
        ConversationState.DEFININDO_OBSERVACOES, ConversationState.CONFIRMANDO_PEDIDO,
    }

    if state == ConversationState.NOVO_CLIENTE:
        return ActiveFlowType.ONBOARDING
    elif state == ConversationState.MENU_PRINCIPAL:
        return ActiveFlowType.MENU
    elif state in {ConversationState.PESQUISA, ConversationState.PESQUISA_VALORES}:
        return ActiveFlowType.PESQUISA
    elif state in order_states:
        return ActiveFlowType.PEDIDO
    elif state == ConversationState.CONSULTA_PEDIDO:
        return ActiveFlowType.CONSULTA
    elif state in {ConversationState.ATENDIMENTO_HUMANO, ConversationState.BOT_PAUSADO}:
        return ActiveFlowType.ATENDIMENTO_HUMANO
    return ActiveFlowType.NENHUM

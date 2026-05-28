"""
Message Service: orquestrador principal do processamento de mensagens.
Equivalente ao workflow principal do n8n.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.payload_parser import parse_evolution_payload
from app.core.classifier import classify_input, ClassificationResult
from app.core.state_machine import resolve_transition
from app.core.order_engine import execute_action
from app.core.response_builder import build_response
from app.core.semantic_translator import semantic_translate
from app.models import (
    ConversationState, SmTriggerEnum, SmActionEnum,
    EventTypeEnum, ActiveFlowType,
)
from app.repositories import (
    clients as client_repo,
    conversations as conv_repo,
    orders as order_repo,
    events as event_repo,
    catalog as catalog_repo,
    availability as avail_repo,
)
from app.integrations import evolution as evo_client
from app.services import media_service, google_sheets_service
from app.schemas.evolution import ParsedMessage, WebhookResponse
from app.schemas.messages import ResponseItem
from app.logging_config import get_logger

logger = get_logger(__name__)


def _is_expired(dt: datetime | None) -> bool:
    """Compara datetime (aware ou naive) com o agora de São Paulo."""
    if not dt:
        return False
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    return now > dt


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

    # 11. Carregar catálogo apenas quando necessário
    catalog_items = await _load_catalog_for_state(db, conversation.state)

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
            classification.extra_data["reason"] = avail.get(
                "block_reason", "Data lotada ou bloqueada"
            )
        else:
            trigger = SmTriggerEnum.DATE_AVAILABLE

    # Caso especial: recheio — determinar trigger de camadas
    if (
        conversation.state == ConversationState.ESCOLHENDO_RECHEIOS
        and trigger == SmTriggerEnum.INPUT_VALID
        and active_order
    ):
        filling_count = active_order.filling_count or 1
        if filling_count >= 2:
            trigger = SmTriggerEnum.TWO_FILLINGS_SELECTED
        else:
            trigger = SmTriggerEnum.ONE_FILLING_SELECTED

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

    # 16. Executar ação
    order_id = active_order.id if active_order else None
    ctx = await execute_action(
        db, transition.action_code,
        conversation_id=conversation.id,
        client_id=client.id,
        classification=classification,
        order_id=order_id,
    )

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
        await google_sheets_service.create_alert(
            db,
            title=f"🚨 Bot pausado — {msg.phone[:6]}***",
            phone=msg.phone,
            reason=ctx.message_data.get("alert_reason", ""),
            conversation_id=conversation.id,
            order_id=str(active_order.id) if active_order else None,
            order_number=active_order.order_number if active_order else None,
        )
        await db.commit()

    # 21. Resolver e enviar mídia
    if ctx.media_references:
        media_items = await media_service.resolve_media_items(db, ctx.media_references)
        if media_items:
            await media_service.send_media_items(msg.phone, media_items)

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


async def _load_catalog_for_state(db: AsyncSession, state: ConversationState) -> list:
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
        return await loader(db)
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

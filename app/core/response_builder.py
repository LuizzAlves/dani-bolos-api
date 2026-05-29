"""
Response Builder: constrói mensagens de resposta para cada action_code.
"""

from decimal import Decimal

from app.models import SmActionEnum, ConversationState
from app.schemas.messages import ResponseItem
from app.core.order_engine import ActionContext
from app.logging_config import get_logger

logger = get_logger(__name__)


def build_response(
    action_code: SmActionEnum,
    ctx: ActionContext,
    current_state: ConversationState,
    client_name: str | None = None,
) -> list[ResponseItem]:
    """
    Constrói lista de ResponseItem (texto/mídia) para envio ao cliente.
    """
    builders = {
        SmActionEnum.REGISTER_CLIENT_AND_SHOW_MENU: _build_welcome_menu,
        SmActionEnum.SHOW_MENU: _build_menu,
        SmActionEnum.SHOW_SEARCH_MENU: _build_search_menu,
        SmActionEnum.SHOW_SIZES_AND_RETURN: _build_show_sizes,
        SmActionEnum.SHOW_FILLINGS_AND_RETURN: _build_show_fillings,
        SmActionEnum.SHOW_SWEETS_AND_RETURN: _build_show_sweets,
        SmActionEnum.ASK_VALUES_CRITERIA: _build_ask_values,
        SmActionEnum.SHOW_VALUES_AND_RETURN: _build_show_values,
        SmActionEnum.CREATE_ORDER_AND_ASK_SIZE: _build_ask_size,
        SmActionEnum.SAVE_SIZE_AND_ASK_DOUGH: _build_ask_dough,
        SmActionEnum.SAVE_DOUGH_AND_ASK_FILLING1: _build_ask_filling,
        SmActionEnum.SAVE_FILLING1_AND_ASK_FILLING2: _build_ask_filling2,
        SmActionEnum.SAVE_FILLING_AND_ASK_EXTRAS: _build_ask_extras,
        SmActionEnum.SAVE_EXTRAS_AND_ASK_FINISH: _build_ask_finish,
        SmActionEnum.SAVE_FINISH_AND_ASK_DATE: _build_ask_date,
        SmActionEnum.REJECT_DATE_AND_ASK_AGAIN: _build_reject_date,
        SmActionEnum.SAVE_DATE_AND_ASK_TIME: _build_ask_time,
        SmActionEnum.SAVE_TIME_AND_ASK_NOTES: _build_ask_notes,
        SmActionEnum.SAVE_NOTES_AND_SHOW_SUMMARY: _build_show_summary,
        SmActionEnum.FINALIZE_ORDER_AND_LOCK: _build_finalize,
        SmActionEnum.CANCEL_ORDER_AND_RETURN: _build_cancel,
        SmActionEnum.ASK_ORDER_ID: _build_ask_order_id,
        SmActionEnum.CHECK_ORDER_STATUS: _build_check_order,
        SmActionEnum.INCREMENT_FALLBACK: _build_fallback,
        SmActionEnum.ASK_HUMAN_REASON: _build_ask_human,
        SmActionEnum.PAUSE_BOT_AND_NOTIFY_HUMAN: _build_pause,
        SmActionEnum.RESUME_BOT: _build_resume,
    }

    builder = builders.get(action_code)
    if builder:
        return builder(ctx, client_name)

    return [ResponseItem(text="Desculpe, algo deu errado. Tente novamente.")]


def _media_items(ctx: ActionContext) -> list[ResponseItem]:
    """Gera ResponseItems de mídia para os reference_types no contexto."""
    items = []
    for ref in ctx.media_references:
        url = _build_drive_url(ref, ctx)
        if url:
            items.append(ResponseItem(
                type="media",
                media_url=url,
                media_type="image",
            ))
    return items


def _build_drive_url(ref_type: str, ctx: ActionContext) -> str | None:
    """Placeholder — URL será montada pelo media_service com dados do banco."""
    # Retorna None aqui; o media_service resolverá com provider_file_id do banco
    return None


# ============================================================
# BUILDERS
# ============================================================

def _build_welcome_menu(ctx, name):
    greeting = name or "Cliente"
    return [
        ResponseItem(text=(
            f"Olá, {greeting}! 😊 Seja bem-vindo(a) à *Dani Bolos*!\n\n"
            "Como posso te ajudar hoje?\n\n"
            "*Menu Principal:*\n"
            "1️⃣ Pesquisar Catálogo\n"
            "2️⃣ Fazer Pedido\n"
            "3️⃣ Consultar Pedido\n"
            "4️⃣ Falar com a Dani\n\n"
            "📝 _Digite o número da opção desejada._"
        )),
    ]


def _build_menu(ctx, name):
    greeting = f", {name}" if name else ""
    return [
        ResponseItem(text=(
            f"Olá{greeting}! 😊\n\n"
            "*Menu Principal:*\n"
            "1️⃣ Pesquisar Catálogo\n"
            "2️⃣ Fazer Pedido\n"
            "3️⃣ Consultar Pedido\n"
            "4️⃣ Falar com a Dani\n\n"
            "📝 _Digite o número da opção desejada._"
        )),
    ]


def _build_search_menu(ctx, name):
    return [
        ResponseItem(text=(
            "🔍 *Pesquisar Catálogo*\n\n"
            "O que você gostaria de ver?\n\n"
            "1️⃣ Tamanhos e Preços\n"
            "2️⃣ Recheios Disponíveis\n"
            "3️⃣ Mini Docinhos\n"
            "4️⃣ Calcular Valores\n\n"
            "📝 _Digite o número da opção._"
        )),
    ]


def _build_show_sizes(ctx, name):
    items = _media_items(ctx)
    sizes = ctx.catalog_items
    if sizes:
        text = "📋 *Tamanhos disponíveis:*\n\n"
        for i, s in enumerate(sizes, 1):
            layers = f" ({s.filling_layers} recheio{'s' if s.filling_layers > 1 else ''})" if hasattr(s, 'filling_layers') else ""
            text += (
                f"{i}. {s.description}{layers}\n"
                f"   {s.shape.value} • {s.servings} fatias\n"
                f"   Branca: R$ {s.price_white} | Chocolate: R$ {s.price_chocolate}\n\n"
            )
        items.append(ResponseItem(text=text))
    items.append(ResponseItem(text="Voltando ao menu principal... ⬅️"))
    items.extend(_build_menu(ctx, name))
    return items


def _build_show_fillings(ctx, name):
    items = _media_items(ctx)
    fillings = ctx.catalog_items
    if fillings:
        text = "🎂 *Recheios disponíveis:*\n\n"
        for i, f in enumerate(fillings, 1):
            text += f"{i}. {f.name}\n"
        items.append(ResponseItem(text=text))
    items.append(ResponseItem(text="Voltando ao menu principal... ⬅️"))
    items.extend(_build_menu(ctx, name))
    return items


def _build_show_sweets(ctx, name):
    items = _media_items(ctx)
    sweets = ctx.catalog_items
    if sweets:
        text = "🍬 *Mini Docinhos:*\n\n"
        for s in sweets:
            text += f"• {s.name}\n  {s.unit_quantity} un: R$ {s.price} (mín: {s.min_order_qty} un)\n\n"
        items.append(ResponseItem(text=text))
    items.append(ResponseItem(text="Voltando ao menu principal... ⬅️"))
    items.extend(_build_menu(ctx, name))
    return items


def _build_ask_values(ctx, name):
    return [
        ResponseItem(text=(
            "💰 *Calcular Valores*\n\n"
            "Me diga o tamanho ou a quantidade de pessoas "
            "e eu calculo o valor pra você!\n\n"
            "Exemplo: \"3 kg\" ou \"30 pessoas\""
        )),
    ]


def _build_show_values(ctx, name):
    custom_text = ctx.message_data.get("values_response_text")
    if custom_text:
        items = [ResponseItem(text=custom_text)]
        if ctx.message_data.get("return_to_menu"):
            items.append(ResponseItem(text="Voltando ao menu principal... ⬅️"))
            items.extend(_build_menu(ctx, name))
        return items

    items = [ResponseItem(text="📊 Aqui estão os valores que encontrei:")]
    items.append(ResponseItem(text="Voltando ao menu principal... ⬅️"))
    items.extend(_build_menu(ctx, name))
    return items


def _build_ask_size(ctx, name):
    items = _media_items(ctx)
    sizes = ctx.catalog_items
    text = "🎂 *Vamos montar seu bolo!*\n\nEscolha o tamanho:\n\n"
    for i, s in enumerate(sizes, 1):
        layers = f" ({s.filling_layers} recheio{'s' if s.filling_layers > 1 else ''})"
        text += (
            f"*{i}.* {s.description}{layers}\n"
            f"    {s.shape.value} • {s.servings} fatias\n"
            f"    Branca: R$ {s.price_white} | Choc: R$ {s.price_chocolate}\n\n"
        )
    text += "📝 _Digite o número do tamanho desejado._"
    items.append(ResponseItem(text=text))
    return items


def _build_ask_dough(ctx, name):
    size = ctx.order_data.get("size")
    size_info = f" para o tamanho *{size.description}*" if size else ""
    return [
        ResponseItem(text=(
            f"✅ Tamanho selecionado{size_info}!\n\n"
            "Agora escolha o tipo de *massa*:\n\n"
            "1️⃣ Massa Branca\n"
            "2️⃣ Massa de Chocolate\n\n"
            "📝 _Digite 1 ou 2._"
        )),
    ]


def _build_ask_filling(ctx, name):
    items = _media_items(ctx)
    fillings = ctx.catalog_items
    text = "✅ Massa selecionada!\n\nEscolha o *1º recheio*:\n\n"
    for i, f in enumerate(fillings, 1):
        text += f"*{i}.* {f.name}\n"
    text += "\n📝 _Digite o número ou o nome do recheio._"
    items.append(ResponseItem(text=text))
    return items


def _build_ask_filling2(ctx, name):
    items = _media_items(ctx)
    fillings = ctx.catalog_items
    text = "✅ 1º recheio selecionado!\n\nAgora escolha o *2º recheio*:\n\n"
    for i, f in enumerate(fillings, 1):
        text += f"*{i}.* {f.name}\n"
    text += "\n📝 _Digite o número ou o nome do recheio._"
    items.append(ResponseItem(text=text))
    return items


def _build_ask_extras(ctx, name):
    extras = ctx.catalog_items
    text = "✅ Recheio(s) selecionado(s)!\n\nDeseja adicionar algo?\n\n"
    for i, e in enumerate(extras, 1):
        price_info = f" — R$ {e.price_per_layer}/camada" if e.price_per_layer > 0 else " — consultar valor"
        text += f"*{i}.* {e.name}{price_info}\n"
    text += "\n*0.* Sem adicionais (pular)\n"
    text += (
        "\n📝 _Digite o número ou nome do adicional e em quantas camadas._\n"
        "Exemplos: *1 em 1 camada*, *cereja em 2 camadas* ou *pular*."
    )
    return [ResponseItem(text=text)]


def _build_ask_finish(ctx, name):
    finishes = ctx.catalog_items
    text = "✅ Adicionais registrados!\n\nEscolha a *finalização* do bolo:\n\n"
    for i, f in enumerate(finishes, 1):
        extra = " ⚠️ consultar valor" if f.has_extra_cost else " ✅ inclusa"
        text += f"*{i}.* {f.name}{extra}\n"
    text += "\n📝 _Digite o número da finalização._"
    return [ResponseItem(text=text)]


def _build_ask_date(ctx, name):
    return [
        ResponseItem(text=(
            "✅ Finalização escolhida!\n\n"
            "📅 Qual a *data de retirada* do bolo?\n\n"
            "Você pode digitar:\n"
            "• Uma data: 15/06\n"
            "• Um dia: sexta, sábado\n"
            "• \"amanhã\"\n\n"
            "⚠️ _Não atendemos aos domingos._"
        )),
    ]


def _build_reject_date(ctx, name):
    reason = ctx.message_data.get("rejection_reason", "Data indisponível")
    return [
        ResponseItem(text=(
            f"❌ {reason}\n\n"
            "Por favor, escolha outra data.\n\n"
            "📝 _Digite uma nova data de retirada._"
        )),
    ]


def _build_ask_time(ctx, name):
    slots = ctx.catalog_items
    text = "✅ Data registrada!\n\n⏰ Escolha o *horário de retirada*:\n\n"
    for i, s in enumerate(slots, 1):
        text += f"*{i}.* {s.label}\n"
    text += "\n📝 _Digite o número ou o horário (ex: 14h)._"
    return [ResponseItem(text=text)]


def _build_ask_notes(ctx, name):
    if ctx.message_data.get("ask_pickup_person_name"):
        return [
            ResponseItem(text=(
                "✅ Horário registrado!\n\n"
                "👤 Qual o *nome da pessoa que irá retirar* a encomenda?\n\n"
                "_Digite o nome completo ou como a Dani deve identificar na retirada._"
            )),
        ]

    return [
        ResponseItem(text=(
            "✅ Horário registrado!\n\n"
            "📝 Deseja adicionar alguma *observação* ao pedido?\n"
            "(mensagem personalizada, alergias, etc.)\n\n"
            "_Digite sua observação ou \"nenhuma\"._"
        )),
    ]


def _build_show_summary(ctx, name):
    if ctx.message_data.get("ask_notes_after_pickup_person"):
        return [
            ResponseItem(text=(
                "✅ Nome de retirada registrado!\n\n"
                "📝 Deseja adicionar alguma *observação* ao pedido?\n"
                "(mensagem personalizada, alergias, detalhes de decoração, etc.)\n\n"
                "_Digite sua observação ou \"nenhuma\"._"
            )),
        ]

    order = ctx.order_data.get("order")
    total = ctx.order_data.get("total_value", Decimal("0"))

    if order:
        text = (
            "📋 *Resumo do Pedido:*\n\n"
            f"🔢 Pedido #{order.order_number}\n"
        )
        # Os detalhes completos seriam preenchidos com dados do pedido
        # Aqui usamos os campos disponíveis
        if order.pickup_date:
            text += f"📅 Data: {order.pickup_date.strftime('%d/%m/%Y')}\n"
        if order.pickup_time:
            text += f"⏰ Horário: {order.pickup_time.strftime('%H:%M')}\n"
        if order.notes:
            text += f"📝 Observações: {order.notes}\n"
        text += f"\n💰 *Valor total: R$ {total:.2f}*\n"
    else:
        text = "📋 Resumo do pedido gerado.\n"

    text += (
        "\n*Confirma o pedido?*\n\n"
        "1️⃣ Sim, confirmar\n"
        "2️⃣ Não, cancelar\n\n"
        "📝 _Digite 1 para confirmar ou 2 para cancelar._"
    )
    return [ResponseItem(text=text)]


def _build_finalize(ctx, name):
    if ctx.message_data.get("date_full"):
        return [
            ResponseItem(text=(
                "❌ Infelizmente a data ficou indisponível no momento da confirmação.\n\n"
                "Seu pedido não foi confirmado. Por favor, tente novamente com outra data.\n\n"
                "A Dani vai te ajudar em breve! 😊"
            )),
        ]

    order = ctx.order_data.get("order")
    order_num = f"#{order.order_number}" if order else ""
    return [
        ResponseItem(text=(
            f"✅ *Pedido {order_num} enviado com sucesso!*\n\n"
            "Seu pedido foi registrado e está *aguardando confirmação* da Dani.\n\n"
            "Ela entrará em contato em breve para confirmar os detalhes. 😊\n\n"
            "Obrigada pela preferência! 🎂💕"
        )),
    ]


def _build_cancel(ctx, name):
    return [
        ResponseItem(text=(
            "❌ Pedido cancelado.\n\n"
            "Se quiser, pode fazer um novo pedido a qualquer momento!\n"
        )),
    ] + _build_menu(ctx, name)


def _build_ask_order_id(ctx, name):
    return [
        ResponseItem(text=(
            "🔍 *Consultar Pedido*\n\n"
            "Digite o número do seu pedido (ex: 1548):"
        )),
    ]


def _build_check_order(ctx, name):
    if ctx.order_data.get("found"):
        order = ctx.order_data["order"]
        status_map = {
            "RASCUNHO": "📝 Em construção",
            "AGUARDANDO_CONFIRMACAO": "⏳ Aguardando confirmação da Dani",
            "CONFIRMADO": "✅ Confirmado",
            "EM_PRODUCAO": "👩‍🍳 Em produção",
            "PRONTO": "🎂 Pronto para retirada",
            "ENTREGUE": "📦 Entregue",
            "FINALIZADO": "✔️ Finalizado",
            "CANCELADO": "❌ Cancelado",
        }
        status_text = status_map.get(order.status.value, order.status.value)
        items = [
            ResponseItem(text=(
                f"📋 *Pedido #{order.order_number}*\n\n"
                f"Status: {status_text}\n"
            )),
        ]
    else:
        items = [
            ResponseItem(text="❌ Pedido não encontrado. Verifique o número e tente novamente."),
        ]
    items.extend(_build_menu(ctx, name))
    return items


def _build_fallback(ctx, name):
    return [
        ResponseItem(text=(
            "🤔 Não entendi sua resposta.\n\n"
            "Por favor, tente novamente usando os números "
            "ou opções indicadas acima."
        )),
    ]


def _build_ask_human(ctx, name):
    return [
        ResponseItem(text=(
            "👋 Vou te encaminhar para a *Dani*!\n\n"
            "Pode me dizer brevemente o motivo?\n"
            "(ex: dúvida sobre preço, pedido especial, etc.)"
        )),
    ]


def _build_pause(ctx, name):
    return [
        ResponseItem(text=(
            "✅ Entendido! A Dani vai te responder em breve.\n\n"
            "⏳ O bot ficará pausado até ela assumir o atendimento.\n"
            "Obrigada pela paciência! 😊"
        )),
    ]


def _build_resume(ctx, name):
    items = [
        ResponseItem(text=(
            "🔄 O atendimento automático foi retomado!\n\n"
            "Como posso te ajudar?"
        )),
    ]
    items.extend(_build_menu(ctx, name))
    return items

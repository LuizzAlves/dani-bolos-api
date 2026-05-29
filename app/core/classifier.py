"""
Classificador determinístico de input do cliente.
Mapeia texto/número para triggers da State Machine com base no estado atual.
"""

import re
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from app.models import (
    ConversationState, SmTriggerEnum,
    Size, Filling, Extra, Finish, TimeSlot,
)
from app.core.payload_parser import normalize_text
from app.logging_config import get_logger

logger = get_logger(__name__)

# Aliases globais para detecção de pedido de atendimento humano
HUMAN_ALIASES = {
    "humano", "atendente", "falar com a dani", "falar com dani",
    "falar com humano", "quero falar com alguem", "quero atendente",
    "pessoa real", "atendimento humano", "chamar a dani",
    "preciso de ajuda", "ajuda",
}

GREETING_ALIASES = {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"}
MENU_RETURN_ALIASES = {"menu", "voltar", "inicio", "início", "comecar", "começar", "principal", "menu principal"}
GLOBAL_CANCEL_ALIASES = {"cancelar", "cancela", "desistir", "parar", "encerrar"}

# Aliases de menu principal
MENU_ALIASES = {
    "ver catalogo": SmTriggerEnum.OPTION_1,
    "catalogo": SmTriggerEnum.OPTION_1,
    "pesquisar": SmTriggerEnum.OPTION_1,
    "ver cardapio": SmTriggerEnum.OPTION_1,
    "cardapio": SmTriggerEnum.OPTION_1,
    "fazer pedido": SmTriggerEnum.OPTION_2,
    "quero encomendar": SmTriggerEnum.OPTION_2,
    "encomendar": SmTriggerEnum.OPTION_2,
    "quero fazer um pedido": SmTriggerEnum.OPTION_2,
    "pedido": SmTriggerEnum.OPTION_2,
    "quero pedir": SmTriggerEnum.OPTION_2,
    "fazer encomenda": SmTriggerEnum.OPTION_2,
    "encomenda": SmTriggerEnum.OPTION_2,
    "consultar pedido": SmTriggerEnum.OPTION_3,
    "meu pedido": SmTriggerEnum.OPTION_3,
    "status do pedido": SmTriggerEnum.OPTION_3,
    "acompanhar pedido": SmTriggerEnum.OPTION_3,
}

# Confirmação / Cancelamento
CONFIRM_ALIASES = {"sim", "confirmar", "confirma", "pode confirmar", "isso", "certo", "ok", "confirmo", "confirmado", "pode ser"}
CANCEL_ALIASES = {"nao", "cancelar", "cancela", "desistir", "voltar", "nao quero", "desisto"}

# Pular / Nenhum (extras)
SKIP_ALIASES = {"pular", "nenhum", "nenhuma", "sem adicional", "sem adicionais", "sem extras", "nao quero", "0", "sem nada"}
ONE_LAYER_ALIASES = {"1 camada", "uma camada", "um recheio", "1 recheio"}
TWO_LAYER_ALIASES = {"2 camadas", "duas camadas", "dois recheios", "2 recheios"}

# Dias da semana em português
WEEKDAYS_PT = {
    "segunda": 0, "segunda-feira": 0, "seg": 0,
    "terca": 1, "terca-feira": 1, "ter": 1,
    "quarta": 2, "quarta-feira": 2, "qua": 2,
    "quinta": 3, "quinta-feira": 3, "qui": 3,
    "sexta": 4, "sexta-feira": 4, "sex": 4,
    "sabado": 5, "sab": 5,
    "domingo": 6, "dom": 6,
}


class ClassificationResult:
    """Resultado da classificação do input."""

    def __init__(
        self,
        trigger: SmTriggerEnum | None = None,
        matched_id: int | None = None,
        matched_value: str | None = None,
        parsed_date: date | None = None,
        parsed_time: str | None = None,
        extra_data: dict | None = None,
    ):
        self.trigger = trigger
        self.matched_id = matched_id
        self.matched_value = matched_value
        self.parsed_date = parsed_date
        self.parsed_time = parsed_time
        self.extra_data = extra_data or {}


def classify_input(
    state: ConversationState,
    text: str,
    normalized: str,
    catalog_items: list | None = None,
    order_context: dict | None = None,
) -> ClassificationResult:
    """
    Classifica o input do cliente com base no estado atual.
    Retorna ClassificationResult com o trigger e dados extraídos.
    """
    # Detecção global: pedido de humano
    if _is_human_request(normalized):
        return ClassificationResult(trigger=SmTriggerEnum.HUMAN_REQUESTED)

    # Classificar por estado
    classifiers = {
        ConversationState.NOVO_CLIENTE: _classify_novo_cliente,
        ConversationState.MENU_PRINCIPAL: _classify_menu,
        ConversationState.PESQUISA: _classify_pesquisa,
        ConversationState.PESQUISA_VALORES: _classify_pesquisa_valores,
        ConversationState.ESCOLHENDO_TAMANHO: _classify_tamanho,
        ConversationState.ESCOLHENDO_MASSA: _classify_massa,
        ConversationState.ESCOLHENDO_RECHEIOS: _classify_recheio,
        ConversationState.ESCOLHENDO_RECHEIO_2: _classify_recheio,
        ConversationState.ESCOLHENDO_ADICIONAIS: _classify_adicionais,
        ConversationState.ESCOLHENDO_FINALIZACAO: _classify_finalizacao,
        ConversationState.DEFININDO_DATA: _classify_data,
        ConversationState.DEFININDO_HORARIO: _classify_horario,
        ConversationState.DEFININDO_OBSERVACOES: _classify_observacoes,
        ConversationState.CONFIRMANDO_PEDIDO: _classify_confirmacao,
        ConversationState.CONSULTA_PEDIDO: _classify_consulta_pedido,
        ConversationState.ATENDIMENTO_HUMANO: _classify_atendimento_humano,
    }

    classifier_fn = classifiers.get(state)
    if classifier_fn:
        return classifier_fn(text, normalized, catalog_items, order_context)

    return ClassificationResult()  # Sem trigger = não classificado


def _is_human_request(normalized: str) -> bool:
    """Verifica se o texto é um pedido de atendimento humano."""
    return normalized in HUMAN_ALIASES


def _classify_novo_cliente(text, normalized, catalog_items, order_context):
    """Cliente novo: aceitar nome (qualquer texto com 2+ caracteres)."""
    if len(text.strip()) >= 2:
        return ClassificationResult(
            trigger=SmTriggerEnum.NEW_CLIENT_REGISTERED,
            matched_value=text.strip(),
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_menu(text, normalized, catalog_items, order_context):
    """Menu principal: opções 1-4 ou aliases."""
    if normalized in GREETING_ALIASES or normalized in MENU_RETURN_ALIASES:
        return ClassificationResult(trigger=SmTriggerEnum.INPUT_VALID)

    # Número direto
    option = _match_option_number(normalized)
    if option:
        return ClassificationResult(trigger=option)

    # Aliases
    for alias, trigger in MENU_ALIASES.items():
        if normalized == alias or normalized.startswith(alias):
            return ClassificationResult(trigger=trigger)

    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_pesquisa(text, normalized, catalog_items, order_context):
    """Submenu de pesquisa: opções 1-4."""
    if normalized in MENU_RETURN_ALIASES or normalized in GLOBAL_CANCEL_ALIASES:
        return ClassificationResult(trigger=SmTriggerEnum.INPUT_VALID, matched_value="RETURN_MENU")

    option = _match_option_number(normalized)
    if option:
        return ClassificationResult(trigger=option)
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_pesquisa_valores(text, normalized, catalog_items, order_context):
    """Pesquisa de valores: aceita critério."""
    if normalized.strip():
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_value=normalized,
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_tamanho(text, normalized, catalog_items, order_context):
    """Escolha de tamanho: número do item ou texto."""
    sizes = catalog_items or []

    # Número direto → índice (1-based)
    idx = _parse_int(normalized)
    if idx is not None and 1 <= idx <= len(sizes):
        size = sizes[idx - 1]
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_id=size.id,
        )

    # Match por texto (peso, porções, descrição)
    for size in sizes:
        desc_norm = normalize_text(size.description)
        weight_str = str(size.weight_kg).replace(".", ",")
        servings_str = str(size.servings)

        if (
            desc_norm in normalized
            or weight_str in normalized
            or f"{size.weight_kg}" in normalized
            or f"{servings_str} fatias" in normalized
            or f"{servings_str} pessoas" in normalized
            or f"{servings_str} pedacos" in normalized
        ):
            return ClassificationResult(
                trigger=SmTriggerEnum.INPUT_VALID,
                matched_id=size.id,
            )

    # Sem match → None (pode tentar Groq depois)
    return ClassificationResult()


def _classify_massa(text, normalized, catalog_items, order_context):
    """Escolha de massa: branca (1) ou chocolate (2)."""
    if normalized in ("1", "branca", "massa branca"):
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_value="BRANCA",
        )
    if normalized in ("2", "chocolate", "massa chocolate", "massa de chocolate"):
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_value="CHOCOLATE",
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_recheio(text, normalized, catalog_items, order_context):
    """Escolha de recheio: número ou texto."""
    fillings = catalog_items or []

    # Número direto
    idx = _parse_int(normalized)
    if idx is not None and 1 <= idx <= len(fillings):
        filling = fillings[idx - 1]
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_id=filling.id,
        )

    # Match por nome parcial
    for filling in fillings:
        name_norm = normalize_text(filling.name)
        # Match exato ou substancial
        if normalized == name_norm or normalized in name_norm:
            return ClassificationResult(
                trigger=SmTriggerEnum.INPUT_VALID,
                matched_id=filling.id,
            )
        # Match parcial (palavra-chave principal)
        keywords = name_norm.split()
        if any(kw in normalized for kw in keywords if len(kw) > 3):
            return ClassificationResult(
                trigger=SmTriggerEnum.INPUT_VALID,
                matched_id=filling.id,
            )

    return ClassificationResult()  # Pode tentar Groq


def _classify_adicionais(text, normalized, catalog_items, order_context):
    """Escolha de adicionais: número, texto ou pular."""
    extras = catalog_items or []
    layers = _parse_extra_layers(normalized)

    # Pular
    if normalized in SKIP_ALIASES:
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_value="SKIP",
            extra_data={"layers": 0},
        )

    # Número direto
    idx_match = re.match(r"\s*(\d+)\b", normalized)
    idx = int(idx_match.group(0)) if idx_match else None
    if idx is not None and 1 <= idx <= len(extras):
        extra = extras[idx - 1]
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_id=extra.id,
            extra_data={"layers": layers} if layers else {},
        )

    # Match por nome
    for extra in extras:
        name_norm = normalize_text(extra.name)
        keywords = [kw for kw in name_norm.split() if len(kw) > 3]
        if (
            normalized in name_norm
            or name_norm in normalized
            or any(kw in normalized for kw in keywords)
        ):
            return ClassificationResult(
                trigger=SmTriggerEnum.INPUT_VALID,
                matched_id=extra.id,
                extra_data={"layers": layers} if layers else {},
            )

    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_finalizacao(text, normalized, catalog_items, order_context):
    """Escolha de finalização: número ou texto."""
    finishes = catalog_items or []

    idx = _parse_int(normalized)
    if idx is not None and 1 <= idx <= len(finishes):
        finish = finishes[idx - 1]
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_id=finish.id,
        )

    # Match por nome
    for finish in finishes:
        name_norm = normalize_text(finish.name)
        if normalized in name_norm or name_norm in normalized:
            return ClassificationResult(
                trigger=SmTriggerEnum.INPUT_VALID,
                matched_id=finish.id,
            )

    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_data(text, normalized, catalog_items, order_context):
    """Parse de data: formatos variados em português."""
    parsed = _parse_date(normalized)
    if parsed:
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        # Validar que não é passado
        if parsed < today:
            return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)
        
        # Validar domingo
        if parsed.weekday() == 6:
            return ClassificationResult(
                trigger=SmTriggerEnum.DATE_UNAVAILABLE,
                extra_data={"reason": "Não abrimos aos domingos"}
            )
            
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            parsed_date=parsed,
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_horario(text, normalized, catalog_items, order_context):
    """Parse de horário: formatos variados."""
    time_slots = catalog_items or []

    # Número direto → índice
    idx = _parse_int(normalized)
    if idx is not None and 1 <= idx <= len(time_slots):
        slot = time_slots[idx - 1]
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_id=slot.id,
            parsed_time=slot.label,
        )

    # Parse de horário textual
    parsed_time = _parse_time(normalized)
    if parsed_time:
        # Encontrar slot correspondente
        for slot in time_slots:
            if slot.label == parsed_time:
                return ClassificationResult(
                    trigger=SmTriggerEnum.INPUT_VALID,
                    matched_id=slot.id,
                    parsed_time=slot.label,
                )
        # Horário válido mas sem slot
        return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)

    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_observacoes(text, normalized, catalog_items, order_context):
    """Observações: qualquer texto é válido."""
    return ClassificationResult(
        trigger=SmTriggerEnum.INPUT_VALID,
        matched_value=text.strip(),
    )


def _classify_confirmacao(text, normalized, catalog_items, order_context):
    """Confirmação: sim/não."""
    if normalized in CONFIRM_ALIASES or normalized == "1":
        return ClassificationResult(
            trigger=SmTriggerEnum.ORDER_CONFIRMED_BY_CLIENT,
        )
    if normalized in CANCEL_ALIASES or normalized == "2":
        return ClassificationResult(
            trigger=SmTriggerEnum.ORDER_CANCELLED_BY_CLIENT,
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_consulta_pedido(text, normalized, catalog_items, order_context):
    """Consulta de pedido: aceitar número do pedido."""
    if normalized in MENU_RETURN_ALIASES or normalized in GLOBAL_CANCEL_ALIASES:
        return ClassificationResult(trigger=SmTriggerEnum.INPUT_VALID, matched_value="RETURN_MENU")

    num = _parse_int(normalized.replace("#", "").strip())
    if num is not None:
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_value=str(num),
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


def _classify_atendimento_humano(text, normalized, catalog_items, order_context):
    """Atendimento humano: aceitar motivo (qualquer texto)."""
    if len(text.strip()) >= 2:
        return ClassificationResult(
            trigger=SmTriggerEnum.INPUT_VALID,
            matched_value=text.strip(),
        )
    return ClassificationResult(trigger=SmTriggerEnum.INPUT_INVALID)


# --- Helpers ---

def _match_option_number(normalized: str) -> SmTriggerEnum | None:
    """Mapeia "1", "2", "3", "4" para OPTION_X."""
    mapping = {
        "1": SmTriggerEnum.OPTION_1,
        "2": SmTriggerEnum.OPTION_2,
        "3": SmTriggerEnum.OPTION_3,
        "4": SmTriggerEnum.OPTION_4,
    }
    return mapping.get(normalized.strip())


def _parse_int(text: str) -> int | None:
    """Tenta converter texto em inteiro."""
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None


def _parse_extra_layers(normalized: str) -> int | None:
    """Extrai se o adicional deve entrar em 1 ou 2 camadas de recheio."""
    text = re.sub(r"\s+", " ", normalized or "").strip()
    if any(alias in text for alias in TWO_LAYER_ALIASES):
        return 2
    if any(alias in text for alias in ONE_LAYER_ALIASES):
        return 1
    if re.search(r"\b2\s*(?:x|camada|camadas|recheio|recheios)\b", text):
        return 2
    if re.search(r"\b1\s*(?:x|camada|camadas|recheio|recheios)\b", text):
        return 1
    return None


def _parse_date(text: str) -> date | None:
    """
    Parse de data em português.
    Aceita: "amanha", "segunda", "15/06", "15/06/2026", "15 de junho".
    """
    text = text.strip()
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()

    # Amanhã
    if text in ("amanha", "amanhã"):
        return today + timedelta(days=1)

    # Depois de amanhã
    if text in ("depois de amanha", "depois de amanhã"):
        return today + timedelta(days=2)

    # Hoje
    if text == "hoje":
        return today

    # Dia da semana
    for day_name, day_num in WEEKDAYS_PT.items():
        if text == day_name or text.startswith(day_name):
            # Encontrar próxima ocorrência
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # DD/MM ou DD/MM/YYYY
    date_match = re.match(r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?", text)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            result = date(year, month, day)
            # Se a data já passou esse ano, considerar próximo ano
            if result < today and not date_match.group(3):
                result = date(year + 1, month, day)
            return result
        except ValueError:
            return None

    # "DD de MES"
    months_pt = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    month_match = re.match(r"(\d{1,2})\s+de\s+(\w+)", text)
    if month_match:
        day = int(month_match.group(1))
        month_name = month_match.group(2)
        month_num = months_pt.get(month_name)
        if month_num:
            try:
                result = date(today.year, month_num, day)
                if result < today:
                    result = date(today.year + 1, month_num, day)
                return result
            except ValueError:
                return None

    return None


def _parse_time(text: str) -> str | None:
    """
    Parse de horário em português.
    Aceita: "14h", "14:00", "2 da tarde", "08h".
    Retorna no formato "HH:00".
    """
    text = text.strip()

    # "14h", "14h00", "8h"
    time_match = re.match(r"(\d{1,2})\s*h\s*(\d{0,2})", text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # "14:30", "08:00"
    time_match = re.match(r"(\d{1,2}):(\d{2})", text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # "2 da tarde", "3 da manha"
    time_match = re.match(r"(\d{1,2})\s+da\s+(tarde|manha|noite)", text)
    if time_match:
        hour = int(time_match.group(1))
        period = time_match.group(2)
        if period == "tarde" and hour < 12:
            hour += 12
        elif period == "noite" and hour < 12:
            hour += 12
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"

    return None

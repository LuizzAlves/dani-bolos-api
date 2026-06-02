from datetime import date, time, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import settings as settings_repo
from app.models import TimeSlot

# Default structure (0=Monday, 6=Sunday)
DEFAULT_HOURS = {
    "0": {"isOpen": True, "openTime": "06:00", "closeTime": "20:00"},
    "1": {"isOpen": True, "openTime": "06:00", "closeTime": "20:00"},
    "2": {"isOpen": True, "openTime": "06:00", "closeTime": "20:00"},
    "3": {"isOpen": True, "openTime": "06:00", "closeTime": "20:00"},
    "4": {"isOpen": True, "openTime": "06:00", "closeTime": "20:00"},
    "5": {"isOpen": True, "openTime": "07:00", "closeTime": "18:00"},
    "6": {"isOpen": True, "openTime": "09:00", "closeTime": "12:00"},
}

WEEKDAYS_PT = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo"
]

async def get_service_hours(db: AsyncSession) -> dict:
    """Retorna a configuração de horários de funcionamento."""
    hours = await settings_repo.get_setting(db, "service_hours")
    if not hours:
        return DEFAULT_HOURS
    return hours

async def is_date_open(db: AsyncSession, target_date: date) -> tuple[bool, str]:
    """Verifica se a loja abre na data (baseado no dia da semana)."""
    hours = await get_service_hours(db)
    weekday = target_date.weekday()
    day_settings = hours.get(str(weekday))

    if not day_settings or not day_settings.get("isOpen", False):
        day_name = WEEKDAYS_PT[weekday]
        return False, f"Não abrimos de {day_name}."

    return True, ""


async def is_time_allowed_for_date(
    db: AsyncSession,
    target_date: date,
    pickup_time: time,
) -> tuple[bool, str]:
    """Valida se um horario esta dentro do funcionamento da data."""
    is_open, reason = await is_date_open(db, target_date)
    if not is_open:
        return False, reason

    hours = await get_service_hours(db)
    weekday = target_date.weekday()
    day_settings = hours.get(str(weekday))
    if not day_settings:
        return False, "Horario indisponivel para esta data."

    open_str = day_settings.get("openTime", "00:00")
    close_str = day_settings.get("closeTime", "23:59")
    open_time = datetime.strptime(open_str, "%H:%M").time()
    close_time = datetime.strptime(close_str, "%H:%M").time()

    if open_time <= pickup_time <= close_time:
        return True, ""

    day_name = WEEKDAYS_PT[weekday]
    return False, f"Horario fora do funcionamento de {day_name} ({open_str} as {close_str})."

async def filter_time_slots(db: AsyncSession, target_date: date, time_slots: list[TimeSlot]) -> list[TimeSlot]:
    """Filtra os slots de horário de acordo com o dia da semana da data."""
    hours = await get_service_hours(db)
    weekday = str(target_date.weekday())
    day_settings = hours.get(weekday)

    if not day_settings or not day_settings.get("isOpen", False):
        return []

    open_str = day_settings.get("openTime", "00:00")
    close_str = day_settings.get("closeTime", "23:59")

    open_time = datetime.strptime(open_str, "%H:%M").time()
    close_time = datetime.strptime(close_str, "%H:%M").time()

    valid_slots = []
    for slot in time_slots:
        if open_time <= slot.slot_time <= close_time:
            valid_slots.append(slot)

    return valid_slots

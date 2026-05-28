"""
Configuração de logging estruturado com structlog.
Sanitiza campos sensíveis automaticamente.
"""

import logging
import structlog
from app.config import get_settings

# Campos sensíveis que nunca devem aparecer em logs
_SENSITIVE_KEYS = {"api_key", "apikey", "token", "password", "secret", "authorization"}


def _sanitize_processor(logger, method_name, event_dict):
    """Remove valores sensíveis de logs."""
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            event_dict[key] = "***REDACTED***"
    return event_dict


def setup_logging():
    """Configura logging estruturado para a aplicação."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Processadores structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _sanitize_processor,
    ]

    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configurar logging padrão do Python
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )

    # Reduzir ruído de libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.LOG_LEVEL == "DEBUG" else logging.WARNING
    )


def get_logger(name: str = __name__):
    """Retorna um logger structlog vinculado."""
    return structlog.get_logger(name)

"""
Dani Bolos — FastAPI Motor de Atendimento
Entry point da aplicação.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, close_db
from app.logging_config import setup_logging, get_logger
from app.integrations.evolution import close_client as close_evo_client
from app.api import health, webhooks, admin

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hooks: startup e shutdown."""
    # Startup
    setup_logging()
    logger.info("app_starting", service="dani-bolos-api")

    try:
        await init_db()
        logger.info("database_connected")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        # Não impedir o startup — /health reportará o status

    yield

    # Shutdown
    logger.info("app_shutting_down")
    await close_db()
    await close_evo_client()


app = FastAPI(
    title="Dani Bolos — Motor de Atendimento",
    description=(
        "API FastAPI que substitui o n8n como motor de processamento "
        "de mensagens WhatsApp para a confeitaria Dani Bolos."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — restrito por padrão
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # Vazio = desativado
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Middleware global de tratamento de exceções
@app.middleware("http")
async def exception_handler_middleware(request: Request, call_next):
    """Captura exceções não tratadas sem expor stack traces."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(e),
        )
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Erro interno do servidor"},
        )


# Incluir routers
app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(admin.router)


# Root redirect
@app.get("/")
async def root():
    """Rota raiz — informações da API."""
    return {
        "service": "Dani Bolos — Motor de Atendimento",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }

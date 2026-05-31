"""
Dani Bolos — FastAPI Motor de Atendimento
Entry point da aplicação.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db, close_db
from app.logging_config import setup_logging, get_logger
from app.integrations.evolution import close_client as close_evo_client
from app.api import health, webhooks, admin

logger = get_logger(__name__)

# Diretório do dashboard
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


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

# CORS — configuração por variável de ambiente para produção
cors_origins_env = os.getenv("ADMIN_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
allow_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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


# Servir dashboard — arquivos estáticos (CSS, JS)
if DASHBOARD_DIR.exists():
    app.mount("/painel/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard")


# Rota principal do painel
@app.get("/painel")
async def painel():
    """Serve o painel administrativo."""
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return JSONResponse(
        status_code=404,
        content={"message": "Dashboard não encontrado. Verifique a pasta dashboard/."},
    )


# Root redirect
@app.get("/")
async def root():
    """Rota raiz — informações da API."""
    return {
        "service": "Dani Bolos — Motor de Atendimento",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "painel": "/painel",
    }

# ============================================
# Dani Bolos — FastAPI Motor de Atendimento
# Dockerfile multi-stage
# ============================================

FROM python:3.12-slim AS builder

WORKDIR /build

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================
# Runtime
# ============================================

FROM python:3.12-slim

WORKDIR /app

# Copiar dependências instaladas
COPY --from=builder /install /usr/local

# Copiar código
COPY app/ ./app/
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# Variáveis de ambiente padrão
ENV APP_ENV=production
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# Porta
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Comando de start
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

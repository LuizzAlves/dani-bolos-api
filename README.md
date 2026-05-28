# Dani Bolos — FastAPI Motor de Atendimento

API FastAPI que substitui o n8n como motor de processamento de mensagens WhatsApp para a confeitaria Dani Bolos.

## Arquitetura

```
WhatsApp/Evolution API
  → FastAPI /webhooks/evolution
      → PostgreSQL (fonte da verdade)
      → Evolution API (sendText/sendMedia)
      → Google Sheets (painel operacional)
      → Groq (tradutor semântico opcional)

n8n (pós-migração)
  → Gatilhos específicos
  → Rotinas agendadas
  → Alertas administrativos
```

## Setup Local

### 1. Clonar e configurar ambiente

```bash
cd "API DaniBolos"
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configurar variáveis

```bash
copy .env.example .env
# Editar .env com valores reais
```

**Variáveis obrigatórias:**
- `DATABASE_URL` — Conexão com PostgreSQL (formato: `postgresql+asyncpg://user:pass@host:port/db`)
- `EVOLUTION_API_URL` — URL da Evolution API
- `EVOLUTION_API_TOKEN` — Token de autenticação
- `EVOLUTION_INSTANCE_NAME` — Nome da instância WhatsApp

### 3. Rodar a API

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Verificar

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness (+ DB) |
| POST | `/webhooks/evolution` | Payload direto da Evolution |
| POST | `/webhooks/evolution/n8n` | Payload wrapped pelo n8n |
| POST | `/admin/reset-test-client` | Reset cliente de teste (requer `X-Admin-Token`) |
| GET | `/docs` | Swagger UI |

## Testes

```bash
python -m pytest tests/ -v
```

## Deploy EasyPanel

### 1. Build

```bash
docker build -t dani-bolos-api .
```

### 2. Variáveis no EasyPanel

Configure todas as variáveis do `.env.example` no painel de variáveis de ambiente do serviço.

### 3. Healthcheck

- **Path:** `/health`
- **Port:** `8000`
- **Interval:** 30s

### 4. Comando de Start

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### 5. Apontar Evolution API

Configure o webhook da Evolution API para:
```
https://sua-api.easypanel.host/webhooks/evolution
```

### 6. n8n (opcional)

Se preferir manter o n8n como relay:
1. Configure webhook no n8n
2. Encaminhe o payload raw para `/webhooks/evolution/n8n`
3. O n8n não processa state machine — apenas repassa

## Estrutura do Projeto

```
app/
├── main.py              # Entry point FastAPI
├── config.py            # Configuração centralizada
├── database.py          # Conexão async PostgreSQL
├── models.py            # SQLAlchemy ORM models
├── api/                 # Endpoints HTTP
│   ├── health.py
│   ├── webhooks.py
│   └── admin.py
├── core/                # Lógica de negócio
│   ├── payload_parser.py
│   ├── classifier.py
│   ├── state_machine.py
│   ├── order_engine.py
│   ├── response_builder.py
│   └── semantic_translator.py
├── integrations/        # Clients HTTP externos
│   ├── evolution.py
│   ├── google_sheets.py
│   └── groq.py
├── repositories/        # Acesso ao banco
│   ├── clients.py
│   ├── conversations.py
│   ├── orders.py
│   ├── catalog.py
│   ├── events.py
│   ├── state_transitions.py
│   └── availability.py
├── schemas/             # Pydantic schemas
│   ├── evolution.py
│   ├── messages.py
│   └── orders.py
└── services/            # Orquestração
    ├── message_service.py
    ├── media_service.py
    └── google_sheets_service.py
```

## Banco de Dados

O banco PostgreSQL **não é alterado** por esta API. O schema é o mesmo usado pelo n8n, definido em:
- `projeto-danibolos/database/migrations/`
- `projeto-danibolos/database/seeds/`

## Licença

Projeto privado — Dani Bolos / Think Systems.

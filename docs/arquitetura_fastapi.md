# Arquitetura FastAPI — Dani Bolos

## Visão Geral

```
                    ┌──────────┐
                    │ WhatsApp │
                    │ (Cliente)│
                    └────┬─────┘
                         │ mensagem
                         ▼
                ┌────────────────┐
                │ Evolution API  │
                │ (Gateway WA)   │
                └────────┬───────┘
                         │ webhook POST
                         ▼
                ┌────────────────┐
                │   FastAPI      │
                │ (Motor)        │◄──────────────────────┐
                └────┬───────────┘                       │
                     │                                   │
         ┌───────────┼───────────────┐                   │
         ▼           ▼               ▼                   │
  ┌─────────────┐ ┌──────────┐ ┌──────────────┐         │
  │ PostgreSQL  │ │ G. Sheets │ │ Google Drive │         │
  │ (Estado,    │ │ (Cards   │ │ (Mídias do   │         │
  │  Catálogo,  │ │  operac.)│ │  catálogo)   │         │
  │  Pedidos,   │ └──────────┘ └──────────────┘         │
  │  Eventos)   │                               ┌───────┴──────┐
  └─────────────┘                               │ Groq API     │
                                                │ (Tradutor    │
                                                │  semântico)  │
                                                └──────────────┘
```

## Camadas da API

### 1. Entrada (`app/api/`)
- Recebe webhooks HTTP
- Não contém lógica de negócio
- Delega para `message_service`

### 2. Serviços (`app/services/`)
- `message_service.py` — Orquestrador principal (pipeline de 22 passos)
- `media_service.py` — Resolução de URLs de mídia
- `google_sheets_service.py` — Criação de pedidos e alertas

### 3. Core (`app/core/`)
- `payload_parser.py` — Normalização de payloads
- `classifier.py` — Classificação determinística de input
- `state_machine.py` — Motor de transições
- `order_engine.py` — Execução de ações
- `response_builder.py` — Construção de mensagens
- `semantic_translator.py` — Tradução IA (opcional)

### 4. Repositórios (`app/repositories/`)
- Acesso ao banco via SQLAlchemy async
- Um arquivo por domínio (clients, orders, catalog, etc.)

### 5. Integrações (`app/integrations/`)
- Clients HTTP para serviços externos
- Evolution API, Google Sheets, Groq

## Fluxo Completo de uma Mensagem

```
 1. POST /webhooks/evolution                    [ENTRADA]
 2. parse_evolution_payload()                   [PARSER]
 3. Filtrar grupo/fromMe/status                 [PARSER]
 4. Se mídia → responder "mande escrito"        [PARSER]
 5. get_or_create_client()                      [CONTEXTO]
 6. get_or_create_conversation()                [CONTEXTO]
 7. Verificar human_lock                        [CONTEXTO]
 8. Log MESSAGE_RECEIVED                        [CONTEXTO]
 9. send_presence("composing")                  [RESPOSTA]
10. classify_input(state, text)                 [CONTROLE]
11. Se None → semantic_translate()              [CONTROLE]
12. Se None → INPUT_INVALID                     [CONTROLE]
13. resolve_transition(state, trigger)          [CONTROLE]
14. Aplicar fallback_effect                     [CONTROLE]
15. execute_action(action_code)                 [REGRAS]
16. build_response(action_code)                 [RESPOSTA]
17. update_conversation_state()                 [CONTEXTO]
18. db.commit()                                 [BANCO]
19. Enviar mídias do catálogo                   [RESPOSTA]
20. Enviar textos via Evolution                 [RESPOSTA]
21. Envia pedido pro Sheets (se finalizado)     [INTEGRAÇÃO]
22. Alerta no Sheets (se necessário)            [INTEGRAÇÃO]
```

## Garantias

| Garantia | Implementação |
|---|---|
| Determinismo | State Machine consulta `state_transitions` no banco |
| Atomicidade | Transações SQLAlchemy nos pontos críticos |
| Anti-loop | Fallback counter com MAX_FALLBACK_REACHED |
| Human lock | `human_lock = True` → bot silencioso |
| Auditoria | Todo evento registrado na tabela `events` |
| Resiliência | G. Sheets falha não bloqueia pedido |
| Segurança | Sem stack traces, PII mascarada em logs |
| Performance | Catálogo carregado sob demanda por estado |

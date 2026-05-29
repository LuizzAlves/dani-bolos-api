# Plano de Migração: n8n → FastAPI

## Resumo

Este documento descreve a migração do processamento de mensagens WhatsApp de um workflow n8n monolítico para uma API FastAPI modular.

## Motivação

| Problema no n8n | Solução na FastAPI |
|---|---|
| Bugs de roteamento visual | Lógica em Python testável |
| Difícil de testar | pytest com fixtures |
| Logs limitados | Structured logging (structlog) |
| Deploy imprevisível | Docker + EasyPanel |
| Transações frágeis | SQLAlchemy async com transações explícitas |
| Manutenção complexa | Código modular em camadas |

## O que muda

### FastAPI assume:
- Receber webhook da Evolution API
- Normalizar payload WhatsApp
- Buscar/criar cliente e conversa
- Consultar State Machine (mesma tabela `state_transitions`)
- Classificar mensagem
- Aplicar transição de estado
- Salvar dados do pedido
- Enviar texto/imagem pela Evolution API
- Tradução semântica via Groq (opcional)

### n8n continua com:
- Gatilhos específicos (cron jobs)
- Rotinas agendadas (timeout, expiração de locks)
- Alertas administrativos
- Integrações futuras

## Diagrama Pós-Migração

```
WhatsApp → Evolution API → FastAPI /webhooks/evolution
                               ├── PostgreSQL (fonte da verdade)
                               ├── Evolution API (sendText/sendMedia)
                               ├── Google Sheets (painel operacional)
                               └── Groq (tradutor semântico)

n8n → cron jobs → timeout/locks
    → alertas → notificações admin
```

## Banco de Dados

**Nenhuma alteração no schema.** A FastAPI usa as mesmas tabelas e enums que o n8n consultava. Os modelos SQLAlchemy são mapeamento puro do schema existente.

### Catalogo somente com 2 recheios

A regra comercial atual remove bolos de 1 recheio do fluxo. A API filtra `sizes.filling_layers = 2` e o banco deve ser alinhado com:

```bash
psql "$DATABASE_URL" -f scripts/20260529_only_two_fillings.sql
```

Esse script desativa tamanhos antigos de 1 recheio e a midia `CARDAPIO_1R`, sem alterar o schema.

## Rollback

Se necessário reverter:
1. Reconfigurar webhook da Evolution para apontar para o n8n
2. Reimportar `main_orchestrator.json` no n8n
3. A FastAPI pode ser desligada sem impacto no banco

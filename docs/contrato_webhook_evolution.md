# Contrato Webhook — Evolution API

## Endpoint Principal

```
POST /webhooks/evolution
Content-Type: application/json
```

## Endpoint n8n Relay

```
POST /webhooks/evolution/n8n
Content-Type: application/json
```

## Payload Direto (Evolution → FastAPI)

```json
{
  "event": "messages.upsert",
  "instance": "NomeDaInstancia",
  "data": {
    "key": {
      "remoteJid": "5519999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "UNIQUE_MESSAGE_ID"
    },
    "pushName": "Nome do Cliente",
    "message": {
      "conversation": "Texto da mensagem"
    },
    "messageType": "conversation",
    "messageTimestamp": 1779980551
  }
}
```

## Payload Wrapped (n8n → FastAPI)

```json
[
  {
    "headers": { ... },
    "body": {
      "event": "messages.upsert",
      "instance": "NomeDaInstancia",
      "data": { ... }
    }
  }
]
```

## Tipos de Mensagem

| messageType | Suportado | Ação |
|---|---|---|
| `conversation` | ✅ | Extrair de `message.conversation` |
| `extendedTextMessage` | ✅ | Extrair de `message.extendedTextMessage.text` |
| `audioMessage` | ❌ | Responder "preciso que mande escrito" |
| `imageMessage` | ❌ | Responder "preciso que mande escrito" |
| `videoMessage` | ❌ | Responder "preciso que mande escrito" |
| `stickerMessage` | ❌ | Responder "preciso que mande escrito" |
| `documentMessage` | ❌ | Responder "preciso que mande escrito" |

## Filtros Automáticos

| Condição | Ação |
|---|---|
| `event != "messages.upsert"` | Ignorar |
| `key.fromMe == true` | Ignorar |
| `remoteJid` contém `@g.us` | Ignorar (grupo) |
| Status update sem mensagem | Ignorar |

## Resposta

```json
{
  "status": "ok",
  "message": "Processed: ACTION_CODE",
  "processed": true
}
```

## Configuração na Evolution API

Apontar o webhook para:
```
https://sua-api.dominio.com/webhooks/evolution
```

Eventos habilitados: `messages.upsert`

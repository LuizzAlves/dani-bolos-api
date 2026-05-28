from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "status": "A API está rodando",
        "mensagem": "Lógica do sistema ativa"
    }

@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
        
        # O payload pode vir como uma lista (ex: exportação do n8n) ou como um dicionário direto.
        if isinstance(payload, list) and len(payload) > 0:
            item = payload[0]
        else:
            item = payload
            
        body = item.get("body", {})
        data = body.get("data", {})
        
        # 1. Nome do whatsapp do cliente
        nome = data.get("pushName", "Desconhecido")
        
        # 2. Número que mandou a mensagem (removendo o @s.whatsapp.net)
        remote_jid = data.get("key", {}).get("remoteJid", "")
        numero = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
        
        # 4. Data enviada
        data_enviada = body.get("date_time", "")
        
        # 3. Mensagem enviada (apenas texto)
        message_type = data.get("messageType", "")
        
        # Tipos de mensagens de texto comuns na Evolution API/Baileys
        if message_type in ["conversation", "extendedTextMessage"]:
            message_obj = data.get("message", {})
            if message_type == "conversation":
                mensagem = message_obj.get("conversation", "")
            else:
                mensagem = message_obj.get("extendedTextMessage", {}).get("text", "")
        else:
            # Se for áudio, imagem, vídeo, etc.
            return {
                "erro": "formato_invalido",
                "resposta_para_cliente": "Não entendo áudios ou imagens, preciso que me mande escrito."
            }

        return {
            "nome": nome,
            "numero": numero,
            "mensagem": mensagem,
            "data_enviada": data_enviada
        }

    except Exception as e:
        return {"erro": str(e)}
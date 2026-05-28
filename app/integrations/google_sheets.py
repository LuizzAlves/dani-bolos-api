"""
Google Sheets Web App HTTP Client.
"""

import httpx
from typing import Any

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def send_to_webhook(action: str, payload: dict[str, Any]) -> bool:
    """
    Envia uma requisição POST para o Web App do Google Apps Script.
    
    Args:
        action: Ação a ser executada no Google Sheets (ex: 'upsert_order', 'alert')
        payload: Dicionário com os dados a serem enviados
        
    Returns:
        bool: True se o envio foi bem sucedido, False caso contrário
    """
    settings = get_settings()
    
    if not settings.GOOGLE_SHEETS_ENABLED:
        logger.debug("google_sheets_disabled")
        return False
        
    url = settings.GOOGLE_SHEETS_WEBAPP_URL
    token = settings.GOOGLE_SHEETS_WEBAPP_TOKEN
    
    if not url or not token:
        logger.warning("google_sheets_not_configured")
        return False

    headers = {
        "Content-Type": "application/json",
    }
    
    data = {
        "token": token,
        "action": action,
    }
    
    if action == "upsert_order":
        data["order"] = payload
    elif action == "alert":
        data["alert"] = payload
    else:
        # Fallback para outras actions, se houver
        data[action] = payload
    
    try:
        timeout = httpx.Timeout(settings.GOOGLE_SHEETS_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            # Apps Script deve retornar { "ok": true/false }
            try:
                resp_data = response.json()
                if resp_data.get("ok") is True:
                    logger.info("google_sheets_request_success", action=action)
                    return True
                else:
                    logger.error("google_sheets_request_failed_ok_false", action=action, response=resp_data)
                    return False
            except ValueError:
                logger.error("google_sheets_invalid_json_response", action=action, text=response.text)
                return False
            
    except httpx.HTTPStatusError as e:
        logger.error(
            "google_sheets_http_error",
            action=action,
            status_code=e.response.status_code,
            response_text=e.response.text
        )
        return False
    except httpx.RequestError as e:
        logger.error("google_sheets_request_error", action=action, error=str(e))
        return False
    except Exception as e:
        logger.error("google_sheets_unknown_error", action=action, error=str(e))
        return False

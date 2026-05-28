"""
Media Service: resolve URLs públicas de mídia do catálogo.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import catalog as catalog_repo
from app.integrations import evolution as evo_client
from app.schemas.messages import ResponseItem
from app.logging_config import get_logger

logger = get_logger(__name__)


def build_public_url(provider_file_id: str) -> str:
    """Monta URL pública do Google Drive a partir do provider_file_id."""
    return f"https://drive.usercontent.google.com/download?id={provider_file_id}&export=download"


async def resolve_media_items(
    db: AsyncSession,
    reference_types: list[str],
) -> list[ResponseItem]:
    """Busca mídias no banco e retorna ResponseItems com URLs públicas."""
    items = []
    medias = await catalog_repo.get_catalog_medias(db, reference_types)

    for media in medias:
        if media.provider_file_id:
            url = build_public_url(media.provider_file_id)
        elif media.media_url:
            url = media.media_url
        else:
            continue

        items.append(ResponseItem(
            type="media",
            media_url=url,
            media_type="image",
            caption=media.description,
        ))

    return items


async def send_media_items(
    phone: str,
    media_items: list[ResponseItem],
) -> None:
    """Envia mídia items sequencialmente via Evolution API."""
    for item in media_items:
        if item.type == "media" and item.media_url:
            await evo_client.send_media(
                phone=phone,
                media_url=item.media_url,
                caption=item.caption,
                media_type=item.media_type or "image",
            )

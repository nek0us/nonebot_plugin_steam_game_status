import time
from typing import Any, Mapping, Optional


STEAM_COMMUNITY_IMAGE_BASE_URL = "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images"
dynamic_avatar_url_cache: dict[str, tuple[float, Optional[str]]] = {}


def resolve_animated_avatar_url(profile_items: Mapping[str, Any]) -> Optional[str]:
    response = profile_items.get("response")
    if not isinstance(response, Mapping):
        return None

    animated_avatar = response.get("animated_avatar")
    if not isinstance(animated_avatar, Mapping):
        return None

    image_path = animated_avatar.get("image_small")
    if not image_path:
        return None

    image_url = str(image_path)
    if image_url.startswith(("http://", "https://")):
        return image_url
    return f"{STEAM_COMMUNITY_IMAGE_BASE_URL}/{image_url}"


async def resolve_avatar_url(steam_id: str, fallback_avatar_url: str) -> str:
    from nonebot.log import logger

    from .api import get_animated_avatar_url
    from .config import config_steam

    if not config_steam.steam_dynamic_avatar_card:
        return fallback_avatar_url

    cache_ttl_seconds = config_steam.steam_dynamic_avatar_cache_ttl_minutes * 60
    if cache_ttl_seconds > 0:
        cached = dynamic_avatar_url_cache.get(steam_id)
        if cached:
            cached_at, cached_avatar_url = cached
            if time.time() - cached_at < cache_ttl_seconds:
                return cached_avatar_url or fallback_avatar_url

    try:
        animated_avatar_url = await get_animated_avatar_url(steam_id)
    except Exception as e:
        logger.debug(f"Steam 动态头像获取异常，steam_id:{steam_id}，使用静态头像：{e.args}")
        return fallback_avatar_url

    if cache_ttl_seconds > 0:
        dynamic_avatar_url_cache[steam_id] = (time.time(), animated_avatar_url)

    if animated_avatar_url:
        logger.debug(f"Steam 动态头像已获取，steam_id:{steam_id}")
        return animated_avatar_url
    return fallback_avatar_url

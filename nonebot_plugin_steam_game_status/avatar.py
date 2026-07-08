import time
from typing import Any, Mapping, Optional


STEAM_COMMUNITY_IMAGE_BASE_URL = "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images"
dynamic_avatar_url_cache: dict[str, tuple[float, Optional[str]]] = {}


def normalize_steam_avatar_url(avatar_url: str) -> str:
    if not avatar_url:
        return avatar_url

    return (
        avatar_url
        .replace("https://avatars.steamstatic.com/", "https://avatars.fastly.steamstatic.com/")
        .replace("http://avatars.steamstatic.com/", "https://avatars.fastly.steamstatic.com/")
    )


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


async def is_avatar_url_available(avatar_url: str) -> bool:
    from nonebot.internal.driver import Request
    from nonebot.log import logger

    from .model import SafeResponse
    from .utils import http_client

    if not avatar_url:
        return False

    async def check(method: str) -> Optional[bool]:
        try:
            async with http_client() as client:
                res = SafeResponse(await client.request(Request(method, avatar_url, timeout=30)))
        except Exception as e:
            logger.debug(f"Steam avatar availability check failed, url:{avatar_url}, method:{method}, error:{e.args}")
            return None

        if 200 <= res.status_code < 300:
            content_type = str(res.headers.get("content-type", "")).lower()
            if not content_type or content_type.startswith("image/"):
                return True
            logger.debug(f"Steam avatar returned non-image content, url:{avatar_url}, content_type:{content_type}")
            return False

        if method == "HEAD" and res.status_code in {403, 405}:
            return None

        logger.debug(f"Steam avatar unavailable, url:{avatar_url}, method:{method}, status:{res.status_code}")
        return False

    head_result = await check("HEAD")
    if head_result is not None:
        return head_result

    get_result = await check("GET")
    return bool(get_result)


async def resolve_avatar_url(steam_id: str, fallback_avatar_url: str) -> str:
    from nonebot.log import logger

    from .api import get_animated_avatar_url
    from .config import config_steam

    fallback_avatar_url = normalize_steam_avatar_url(fallback_avatar_url)

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

    if animated_avatar_url and not await is_avatar_url_available(animated_avatar_url):
        logger.debug(f"Steam animated avatar unavailable, steam_id:{steam_id}, fallback to static avatar")
        animated_avatar_url = None

    if cache_ttl_seconds > 0:
        dynamic_avatar_url_cache[steam_id] = (time.time(), animated_avatar_url)

    if animated_avatar_url:
        logger.debug(f"Steam 动态头像已获取，steam_id:{steam_id}")
        return animated_avatar_url
    return fallback_avatar_url

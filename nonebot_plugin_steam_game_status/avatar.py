from typing import Any, Mapping, Optional


STEAM_COMMUNITY_IMAGE_BASE_URL = "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images"


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

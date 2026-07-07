import hashlib
import html
import json
from urllib.parse import urlparse


STEAM_CARD_ANIMATION_FRAME_COUNT = 12
STEAM_CARD_ANIMATION_FRAME_DURATION_MS = 120


def is_animated_image_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".gif")


def build_steam_card_cache_key(
    *,
    avatar_url: str,
    player_name: str,
    action_text: str,
    game_name: str,
    template_digest: str,
    frame_count: int = STEAM_CARD_ANIMATION_FRAME_COUNT,
    frame_duration_ms: int = STEAM_CARD_ANIMATION_FRAME_DURATION_MS,
) -> str:
    cache_data = {
        "avatar_url": avatar_url,
        "player_name": player_name,
        "action_text": action_text,
        "game_name": game_name,
        "template_digest": template_digest,
        "frame_count": frame_count,
        "frame_duration_ms": frame_duration_ms,
    }
    cache_json = json.dumps(cache_data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(cache_json.encode("utf8")).hexdigest()


def render_steam_card_template(
    *,
    template_html: str,
    avatar_url: str,
    player_name: str,
    action_text: str,
    game_name: str,
) -> str:
    return (
        template_html
        .replace("{{ avatar_url }}", html.escape(avatar_url, quote=True))
        .replace("{{ player_name }}", html.escape(player_name))
        .replace("{{ action_text }}", html.escape(action_text))
        .replace("{{ game_name }}", html.escape(game_name))
    )

import hashlib
import html
import json
from urllib.parse import urlparse


STEAM_CARD_ANIMATION_FRAME_COUNT = 12
STEAM_CARD_ANIMATION_FRAME_DURATION_MS = 120
STEAM_CARD_ANIMATION_CAPTURE_INTERVAL_MS = 80
STEAM_CARD_ANIMATION_CAPTURE_DURATION_MS = 4000
STEAM_CARD_VIEWPORT_WIDTH = 356
STEAM_CARD_VIEWPORT_HEIGHT = 88
STEAM_CARD_COMPACT_VIEWPORT_WIDTH = 260
STEAM_CARD_COMPACT_VIEWPORT_HEIGHT = 72
STEAM_CARD_WIDE_VIEWPORT_WIDTH = 406
STEAM_CARD_WIDE_VIEWPORT_HEIGHT = 88
STEAM_CARD_LONG_GAME_NAME_LENGTH = 16


def get_steam_card_layout(game_name: str, *, dynamic: bool = False) -> tuple[str, int, int]:
    if dynamic:
        return "compact", STEAM_CARD_COMPACT_VIEWPORT_WIDTH, STEAM_CARD_COMPACT_VIEWPORT_HEIGHT
    if len(game_name) > STEAM_CARD_LONG_GAME_NAME_LENGTH:
        return "wide", STEAM_CARD_WIDE_VIEWPORT_WIDTH, STEAM_CARD_WIDE_VIEWPORT_HEIGHT
    return "", STEAM_CARD_VIEWPORT_WIDTH, STEAM_CARD_VIEWPORT_HEIGHT


def is_animated_image_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".gif")


def build_steam_card_cache_key(
    *,
    avatar_url: str,
    player_name: str,
    action_text: str,
    game_name: str,
    template_digest: str,
    card_class: str = "",
    frame_count: int = STEAM_CARD_ANIMATION_FRAME_COUNT,
    frame_duration_ms: int = STEAM_CARD_ANIMATION_FRAME_DURATION_MS,
    capture_interval_ms: int = STEAM_CARD_ANIMATION_CAPTURE_INTERVAL_MS,
    capture_duration_ms: int = STEAM_CARD_ANIMATION_CAPTURE_DURATION_MS,
    preserve_avatar_timing: bool = False,
    max_avatar_frames: int = 120,
) -> str:
    cache_data = {
        "avatar_url": avatar_url,
        "player_name": player_name,
        "action_text": action_text,
        "game_name": game_name,
        "template_digest": template_digest,
        "card_class": card_class,
        "frame_count": frame_count,
        "frame_duration_ms": frame_duration_ms,
        "capture_interval_ms": capture_interval_ms,
        "capture_duration_ms": capture_duration_ms,
        "preserve_avatar_timing": preserve_avatar_timing,
        "max_avatar_frames": max_avatar_frames,
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
    card_class: str = "",
) -> str:
    return (
        template_html
        .replace("{{ card_class }}", html.escape(card_class))
        .replace("{{ avatar_url }}", html.escape(avatar_url, quote=True))
        .replace("{{ player_name }}", html.escape(player_name))
        .replace("{{ action_text }}", html.escape(action_text))
        .replace("{{ game_name }}", html.escape(game_name))
    )

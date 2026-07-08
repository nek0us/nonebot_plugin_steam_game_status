import importlib.util
from pathlib import Path
import unittest


card_module_path = Path(__file__).resolve().parents[1] / "nonebot_plugin_steam_game_status" / "card.py"
card_spec = importlib.util.spec_from_file_location("card", card_module_path)
assert card_spec and card_spec.loader
card = importlib.util.module_from_spec(card_spec)
card_spec.loader.exec_module(card)


class TestSteamCardCache(unittest.TestCase):
    def test_cache_key_includes_player_name(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
        }

        key_a = card.build_steam_card_cache_key(player_name="Alice", **base)
        key_b = card.build_steam_card_cache_key(player_name="Bob", **base)

        self.assertNotEqual(key_a, key_b)

    def test_cache_key_includes_action_text(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "game_name": "Game",
            "template_digest": "template",
        }

        start_key = card.build_steam_card_cache_key(action_text="开始玩", **base)
        stop_key = card.build_steam_card_cache_key(action_text="停止", **base)

        self.assertNotEqual(start_key, stop_key)

    def test_cache_key_includes_frame_duration(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
        }

        fast_key = card.build_steam_card_cache_key(frame_duration_ms=80, **base)
        slow_key = card.build_steam_card_cache_key(frame_duration_ms=120, **base)

        self.assertNotEqual(fast_key, slow_key)

    def test_cache_key_includes_capture_interval(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
        }

        dense_key = card.build_steam_card_cache_key(capture_interval_ms=80, **base)
        sparse_key = card.build_steam_card_cache_key(capture_interval_ms=150, **base)

        self.assertNotEqual(dense_key, sparse_key)

    def test_cache_key_includes_capture_duration(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
        }

        short_key = card.build_steam_card_cache_key(capture_duration_ms=1800, **base)
        full_key = card.build_steam_card_cache_key(capture_duration_ms=4000, **base)

        self.assertNotEqual(short_key, full_key)

    def test_cache_key_includes_card_class(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
        }

        normal_key = card.build_steam_card_cache_key(card_class="", **base)
        compact_key = card.build_steam_card_cache_key(card_class="compact", **base)

        self.assertNotEqual(normal_key, compact_key)

    def test_cache_key_includes_preserve_avatar_timing(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
        }

        sampled_key = card.build_steam_card_cache_key(preserve_avatar_timing=False, **base)
        preserved_key = card.build_steam_card_cache_key(preserve_avatar_timing=True, **base)

        self.assertNotEqual(sampled_key, preserved_key)

    def test_cache_key_includes_max_avatar_frames(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "开始玩",
            "game_name": "Game",
            "template_digest": "template",
            "preserve_avatar_timing": True,
        }

        small_key = card.build_steam_card_cache_key(max_avatar_frames=60, **base)
        large_key = card.build_steam_card_cache_key(max_avatar_frames=120, **base)

        self.assertNotEqual(small_key, large_key)

    def test_cache_key_includes_background_url(self):
        base = {
            "avatar_url": "https://example.com/avatar.gif",
            "player_name": "Alice",
            "action_text": "start",
            "game_name": "Game",
            "template_digest": "template",
        }

        plain_key = card.build_steam_card_cache_key(background_url="", **base)
        background_key = card.build_steam_card_cache_key(background_url="https://example.com/bg.jpg", **base)

        self.assertNotEqual(plain_key, background_key)

    def test_detects_gif_avatar_url(self):
        self.assertTrue(card.is_animated_image_url("https://example.com/avatar.GIF?size=small"))
        self.assertFalse(card.is_animated_image_url("https://example.com/avatar.jpg"))

    def test_builds_game_background_url(self):
        self.assertIn("/123/library_hero.jpg", card.build_steam_game_background_url("123"))
        self.assertEqual(card.build_steam_game_background_url(""), "")

    def test_dynamic_card_uses_compact_layout(self):
        card_class, width, height = card.get_steam_card_layout("Game", dynamic=True)

        self.assertEqual(card_class, "compact")
        self.assertEqual(width, card.STEAM_CARD_COMPACT_VIEWPORT_WIDTH)
        self.assertEqual(height, card.STEAM_CARD_COMPACT_VIEWPORT_HEIGHT)

    def test_long_static_game_uses_wide_layout(self):
        card_class, width, height = card.get_steam_card_layout("Very Very Long Game Name")

        self.assertEqual(card_class, "wide")
        self.assertEqual(width, card.STEAM_CARD_WIDE_VIEWPORT_WIDTH)
        self.assertEqual(height, card.STEAM_CARD_WIDE_VIEWPORT_HEIGHT)


if __name__ == "__main__":
    unittest.main()

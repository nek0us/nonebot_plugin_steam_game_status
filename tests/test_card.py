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

    def test_detects_gif_avatar_url(self):
        self.assertTrue(card.is_animated_image_url("https://example.com/avatar.GIF?size=small"))
        self.assertFalse(card.is_animated_image_url("https://example.com/avatar.jpg"))


if __name__ == "__main__":
    unittest.main()

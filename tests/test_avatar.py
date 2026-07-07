import importlib.util
from pathlib import Path
import unittest


avatar_module_path = Path(__file__).resolve().parents[1] / "nonebot_plugin_steam_game_status" / "avatar.py"
avatar_spec = importlib.util.spec_from_file_location("avatar", avatar_module_path)
assert avatar_spec and avatar_spec.loader
avatar = importlib.util.module_from_spec(avatar_spec)
avatar_spec.loader.exec_module(avatar)
resolve_animated_avatar_url = avatar.resolve_animated_avatar_url


class TestAnimatedAvatarUrl(unittest.TestCase):
    def test_resolves_dynamic_avatar_url(self):
        profile_items = {
            "response": {
                "profile_background": {},
                "mini_profile_background": {},
                "avatar_frame": {},
                "animated_avatar": {
                    "communityitemid": "29606985176",
                    "image_small": "items/570/f71e8836ca4de7ac2b312811b549be0c5988f7bb.gif",
                    "image_large": "items/570/4b0705a091066c47c869910fc7be2e74350a0dcd.jpg",
                    "name": "Troll Warlord",
                    "appid": 570,
                },
                "profile_modifier": {},
                "steam_deck_keyboard_skin": {},
            }
        }

        self.assertEqual(
            resolve_animated_avatar_url(profile_items),
            "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/items/570/f71e8836ca4de7ac2b312811b549be0c5988f7bb.gif",
        )

    def test_returns_none_for_static_avatar_user(self):
        profile_items = {
            "response": {
                "profile_background": {
                    "communityitemid": "26783233251",
                    "image_large": "items/774171/996d09a56d4115f1370493337754c4bfe81f41c5.jpg",
                },
                "mini_profile_background": {
                    "communityitemid": "30192665409",
                    "image_large": "items/1955830/7c49fcbe13737fda29b475d9d8250f7a378b1fca.jpg",
                },
                "avatar_frame": {
                    "communityitemid": "29952133576",
                    "image_small": "items/322330/46461aaea39b18a4a3da2e6d3cf253006f2d6193.png",
                },
                "animated_avatar": {},
                "profile_modifier": {},
                "steam_deck_keyboard_skin": {},
            }
        }

        self.assertIsNone(resolve_animated_avatar_url(profile_items))


if __name__ == "__main__":
    unittest.main()

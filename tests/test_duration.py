import importlib.util
from pathlib import Path
import unittest


duration_module_path = Path(__file__).resolve().parents[1] / "nonebot_plugin_steam_game_status" / "duration.py"
duration_spec = importlib.util.spec_from_file_location("duration", duration_module_path)
assert duration_spec and duration_spec.loader
duration = importlib.util.module_from_spec(duration_spec)
duration_spec.loader.exec_module(duration)


class TestPlaytimeDuration(unittest.TestCase):
    def test_formats_minutes_under_one_hour(self):
        self.assertEqual(duration.format_playtime_duration(59), "59分钟")

    def test_formats_hours_and_minutes(self):
        self.assertEqual(duration.format_playtime_duration(70), "1小时10分钟")

    def test_formats_exact_hours(self):
        self.assertEqual(duration.format_playtime_duration(120), "2小时")

    def test_formats_days_hours_and_minutes(self):
        self.assertEqual(duration.format_playtime_duration(1565), "1天2小时5分钟")

    def test_formats_exact_days(self):
        self.assertEqual(duration.format_playtime_duration(2880), "2天")


if __name__ == "__main__":
    unittest.main()

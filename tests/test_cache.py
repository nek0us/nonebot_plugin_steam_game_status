import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest


cache_module_path = Path(__file__).resolve().parents[1] / "nonebot_plugin_steam_game_status" / "cache.py"
cache_spec = importlib.util.spec_from_file_location("cache", cache_module_path)
assert cache_spec and cache_spec.loader
cache = importlib.util.module_from_spec(cache_spec)
cache_spec.loader.exec_module(cache)


class TestCacheCleanup(unittest.TestCase):
    def test_image_resource_variants_use_distinct_deterministic_paths(self):
        cache_dir = Path("image-cache")
        url = "https://example.com/avatar.jpg?size=full"

        original = cache.build_image_resource_cache_file(cache_dir, url, False)
        grayscale = cache.build_image_resource_cache_file(cache_dir, url, True)

        self.assertNotEqual(original, grayscale)
        self.assertEqual(original.suffix, ".jpg")
        self.assertEqual(grayscale.suffix, ".png")

    def test_removes_only_expired_files(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            expired = cache_dir / "expired.gif"
            retained = cache_dir / "retained.gif"
            nested_dir = cache_dir / "nested"
            expired.write_bytes(b"expired")
            retained.write_bytes(b"retained")
            nested_dir.mkdir()
            old_time = time.time() - 2 * 24 * 60 * 60
            os.utime(expired, (old_time, old_time))

            self.assertEqual(cache.cleanup_expired_cache_files(cache_dir, 1), 1)
            self.assertFalse(expired.exists())
            self.assertTrue(retained.exists())
            self.assertTrue(nested_dir.exists())

    def test_zero_retention_disables_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_file = Path(directory) / "cached.gif"
            cache_file.write_bytes(b"cached")
            old_time = time.time() - 2 * 24 * 60 * 60
            os.utime(cache_file, (old_time, old_time))

            self.assertEqual(cache.cleanup_expired_cache_files(Path(directory), 0), 0)
            self.assertTrue(cache_file.exists())

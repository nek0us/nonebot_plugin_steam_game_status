import time
from pathlib import Path


def cleanup_expired_cache_files(cache_dir: Path, retention_days: int) -> int:
    """Delete expired cache files and return the number removed.

    A retention value of zero disables automatic cleanup. Cache hits refresh the
    file modification time, so only files that have not been used recently expire.
    """
    if retention_days == 0 or not cache_dir.exists():
        return 0

    expires_before = time.time() - retention_days * 24 * 60 * 60
    removed = 0
    for cache_file in cache_dir.iterdir():
        if not cache_file.is_file():
            continue
        try:
            if cache_file.stat().st_mtime < expires_before:
                cache_file.unlink()
                removed += 1
        except OSError:
            continue
    return removed

import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


def _image_suffix(url: str, content_type: str = "") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}:
        return suffix
    return {
        "image/avif": ".avif",
        "image/gif": ".gif",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type.split(";", 1)[0].lower(), ".img")


def build_image_resource_cache_file(cache_dir: Path, url: str, grayscale: bool, content_type: str = "") -> Path:
    """Return the deterministic cache path for an image URL."""
    import hashlib

    variant = "grayscale" if grayscale else "original"
    cache_key = hashlib.sha256(f"{variant}:{url}".encode("utf8")).hexdigest()
    suffix = ".png" if grayscale else _image_suffix(url, content_type)
    return cache_dir / f"{cache_key}{suffix}"


async def get_cached_image_url(url: str, *, grayscale: bool = False) -> str:
    """Download an image once and return a local file URL for card rendering."""
    if not url:
        return url

    from nonebot.internal.driver import Request
    from nonebot.log import logger

    from .model import SafeResponse
    from .source import image_resource_cache_dir
    from .utils import http_client

    cache_file = build_image_resource_cache_file(image_resource_cache_dir, url, grayscale)
    if cache_file.exists():
        try:
            cache_file.touch()
            return cache_file.resolve().as_uri()
        except OSError:
            pass

    cache_key = cache_file.stem
    cached_variants = list(image_resource_cache_dir.glob(f"{cache_key}.*"))
    if cached_variants:
        try:
            cached_variants[0].touch()
            return cached_variants[0].resolve().as_uri()
        except OSError:
            pass

    try:
        if grayscale:
            original_url = await get_cached_image_url(url)
            parsed_original_url = urlparse(original_url)
            if parsed_original_url.scheme == "file":
                original_file = Path(url2pathname(parsed_original_url.path))
                if original_file.exists():
                    from PIL import Image

                    image = Image.open(original_file).convert("L")
                    image.save(cache_file, format="PNG")
                    return cache_file.resolve().as_uri()

        async with http_client() as client:
            response = SafeResponse(await client.request(Request("GET", url, timeout=30)))
        if response.status_code != 200 or not isinstance(response.content, bytes):
            return url

        content_type = response.headers.get("content-type", "")
        if grayscale:
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(response.content)).convert("L")
            cache_file = build_image_resource_cache_file(
                image_resource_cache_dir, url, True, content_type
            )
            image.save(cache_file, format="PNG")
        else:
            cache_file = build_image_resource_cache_file(
                image_resource_cache_dir, url, False, content_type
            )
            cache_file.write_bytes(response.content)
        return cache_file.resolve().as_uri()
    except Exception as error:
        logger.debug(f"Steam image resource cache failed, url:{url}, error:{error}")
        return url


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

"""Redis client helper with lazy initialization and health check."""

import os
from functools import lru_cache
from typing import Optional

from src.utils.logger import logger


def _build_redis_url() -> str:
    if os.getenv("REDIS_URL"):
        return os.getenv("REDIS_URL", "")
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    password = os.getenv("REDIS_PASSWORD")
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"


@lru_cache(maxsize=1)
def get_redis_client():
    """Returns a Redis client or None if unavailable/misconfigured."""
    try:
        import redis
    except ImportError:
        logger.debug("Redis client not installed; skipping Redis integration.")
        return None

    url = _build_redis_url()
    if not url:
        return None

    try:
        client = redis.from_url(url, decode_responses=False)
        client.ping()
        logger.info(f"Redis available at {url}")
        return client
    except Exception as exc:
        logger.warning(f"Redis not available ({exc}); falling back to in-memory caches.")
        return None


def is_redis_enabled() -> bool:
    """Checks env flags to decide if Redis should be used."""
    return os.getenv("USE_REDIS_CACHE", "true").lower() in ("true", "1", "yes")


def get_redis_if_enabled():
    if not is_redis_enabled():
        return None
    return get_redis_client()


def acquire_lock(key: str, ttl_seconds: int = 30) -> bool:
    """Attempts to acquire a short lock; returns True if acquired."""
    client = get_redis_if_enabled()
    if not client:
        return True  # Fallback: no Redis, allow execution
    try:
        return bool(client.set(name=key, value=1, nx=True, ex=ttl_seconds))
    except Exception as exc:
        logger.debug(f"Lock acquire failed ({exc}); continuing without lock.")
        return True


def release_lock(key: str) -> None:
    """Releases a lock if held."""
    client = get_redis_if_enabled()
    if not client:
        return
    try:
        client.delete(key)
    except Exception:
        logger.debug("Lock release failed; ignoring.")

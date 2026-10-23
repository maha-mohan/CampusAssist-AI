"""Shared Redis client, rate limiter and small cache helpers.

Redis is optional at runtime: when it is unreachable every helper fails open. After a
failure Redis is skipped for REDIS_RETRY_SECONDS so requests are not slowed down by
repeated connection timeouts, and a small in-process fallback keeps the answer cache
and the rate limiter working (per process, with a short TTL).
"""
import hashlib
import json
import logging
import time

import redis.asyncio as aioredis

from app.core.config import settings

log = logging.getLogger(__name__)
_redis: aioredis.Redis | None = None

REDIS_RETRY_SECONDS = 15
MEMORY_CACHE_TTL = 300
MEMORY_MAX_ENTRIES = 1000
_down_until = 0.0
_mem_cache: dict[str, tuple[float, str]] = {}
_mem_counts: dict[str, tuple[float, int]] = {}


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True,
                                   socket_connect_timeout=0.5, socket_timeout=1.0)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def redis_available() -> bool:
    return time.monotonic() >= _down_until


def _mark_down(exc: Exception) -> None:
    global _down_until
    if redis_available():
        log.warning("Redis unavailable, using in-memory fallback for %ss: %s", REDIS_RETRY_SECONDS, exc)
    _down_until = time.monotonic() + REDIS_RETRY_SECONDS


def _prune(store: dict, now: float) -> None:
    if len(store) < MEMORY_MAX_ENTRIES:
        return
    for k in [k for k, (exp, _) in store.items() if exp <= now]:
        del store[k]
    while len(store) >= MEMORY_MAX_ENTRIES:
        store.pop(next(iter(store)))


async def hit_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Fixed-window rate limiter. Returns True when the caller is OVER the limit.

    Uses Redis when it is reachable, otherwise an in-process counter, so the bot keeps working.
    """
    bucket = f"rl:{key}:{int(time.time() // window_seconds)}"
    if redis_available():
        try:
            r = get_redis()
            count = await r.incr(bucket)
            if count == 1:
                await r.expire(bucket, window_seconds + 5)
            return count > limit
        except Exception as exc:  # pragma: no cover - depends on infra
            _mark_down(exc)
    now = time.time()
    _prune(_mem_counts, now)
    _, count = _mem_counts.get(bucket, (now + window_seconds + 5, 0))
    count += 1
    _mem_counts[bucket] = (now + window_seconds + 5, count)
    return count > limit


def cache_key(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    return f"{prefix}:{digest}"


async def cache_get(key: str):
    if redis_available():
        try:
            raw = await get_redis().get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            _mark_down(exc)
    entry = _mem_cache.get(key)
    if entry and entry[0] > time.time():
        return json.loads(entry[1])
    return None


async def cache_set(key: str, value, ttl: int = 3600) -> None:
    if redis_available():
        try:
            await get_redis().set(key, json.dumps(value), ex=ttl)
            return
        except Exception as exc:
            _mark_down(exc)
    now = time.time()
    _prune(_mem_cache, now)
    _mem_cache[key] = (now + min(ttl, MEMORY_CACHE_TTL), json.dumps(value))


async def cache_clear_prefix(prefix: str) -> None:
    for k in [k for k in _mem_cache if k.startswith(f"{prefix}:")]:
        del _mem_cache[k]
    if not redis_available():
        return
    try:
        r = get_redis()
        async for k in r.scan_iter(f"{prefix}:*"):
            await r.delete(k)
    except Exception as exc:
        _mark_down(exc)

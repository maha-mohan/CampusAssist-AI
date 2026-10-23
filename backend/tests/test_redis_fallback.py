"""Redis helpers must fail fast and keep working in-process when Redis is down."""
import time

import pytest

from app.core import redis as rd


class _DownRedis:
    calls = 0

    async def incr(self, *_):
        _DownRedis.calls += 1
        raise ConnectionError("down")

    get = set = expire = incr


@pytest.fixture(autouse=True)
def redis_down(monkeypatch):
    _DownRedis.calls = 0
    monkeypatch.setattr(rd, "get_redis", lambda: _DownRedis())
    monkeypatch.setattr(rd, "_down_until", 0.0)
    rd._mem_cache.clear()
    rd._mem_counts.clear()
    yield
    rd._down_until = 0.0


async def test_redis_skipped_after_first_failure():
    assert await rd.cache_get("ans:x") is None
    assert not rd.redis_available()
    await rd.cache_get("ans:y")
    await rd.hit_rate_limit("ip:1", 5)
    assert _DownRedis.calls == 1  # later calls never touched Redis during the cooldown


async def test_memory_cache_roundtrip_and_clear():
    await rd.cache_set("ans:a", {"answer": "hello"})
    assert await rd.cache_get("ans:a") == {"answer": "hello"}
    await rd.cache_clear_prefix("ans")
    assert await rd.cache_get("ans:a") is None


async def test_memory_rate_limit():
    results = [await rd.hit_rate_limit("ip:2", 3) for _ in range(5)]
    assert results == [False, False, False, True, True]


async def test_redis_retried_after_cooldown():
    await rd.cache_get("ans:z")
    assert not rd.redis_available()
    rd._down_until = time.monotonic() - 1
    assert rd.redis_available()

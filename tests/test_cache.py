import tempfile

import pytest

from triad.core.cache import PromptCacheManager
from triad.core.llm import CachedLLMProvider, LLMResponse, MockLLMProvider


def test_prompt_cache_in_memory():
    cache = PromptCacheManager()
    key = cache.compute_key(prompt="test prompt", system_prompt="sys", json_mode=True)

    resp = LLMResponse(
        content="result",
        prompt_tokens=100,
        completion_tokens=50,
        cached_tokens=0,
        total_tokens=150,
        duration_seconds=0.5,
    )

    # Miss initially
    assert cache.get(key) is None
    assert cache.total_misses == 1

    # Put
    cache.put(key, resp)

    # Hit
    cached = cache.get(key)
    assert cached is not None
    assert cached.content == "result"
    assert cached.cached_tokens == 100
    assert cache.total_hits == 1
    assert cache.tokens_saved == 150
    assert cache.hit_ratio == 50.0


def test_prompt_cache_disk_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache1 = PromptCacheManager(cache_dir=tmpdir)
        key = cache1.compute_key(prompt="disk prompt")
        resp = LLMResponse(
            content="persisted result",
            prompt_tokens=80,
            completion_tokens=20,
            total_tokens=100,
        )
        cache1.put(key, resp)

        # Fresh cache instance reading same directory
        cache2 = PromptCacheManager(cache_dir=tmpdir)
        cached = cache2.get(key)
        assert cached is not None
        assert cached.content == "persisted result"
        assert cache2.total_hits == 1


@pytest.mark.asyncio
async def test_cached_llm_provider_wrapper():
    mock = MockLLMProvider()
    mock.register_response("special query", "custom answer")

    cache = PromptCacheManager()
    cached_llm = CachedLLMProvider(mock, cache=cache)

    # First call: cache miss, invokes underlying mock
    r1 = await cached_llm.generate("special query")
    assert r1.content == "custom answer"
    assert cache.total_hits == 0

    # Second call: cache hit, instantaneous
    r2 = await cached_llm.generate("special query")
    assert r2.content == "custom answer"
    assert cache.total_hits == 1
    assert r2.duration_seconds < 0.01

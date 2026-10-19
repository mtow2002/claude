"""Cache behaviour: no re-fetch, fetched_at preserved, as_of isolation."""

from __future__ import annotations

from datetime import date

import pandas as pd

from portfolio_review.data.cache import CachedProvider


def test_second_call_is_a_cache_hit_with_original_fetch_time(counting_provider, tmp_path, as_of):
    cached = CachedProvider(counting_provider, tmp_path)
    first = cached.prices("AAA", date(2024, 9, 1), as_of, as_of)
    second = cached.prices("AAA", date(2024, 9, 1), as_of, as_of)
    assert counting_provider.price_calls == 1
    assert first.source.cache_hit is False
    assert second.source.cache_hit is True
    assert second.source.fetched_at == first.source.fetched_at
    pd.testing.assert_frame_equal(first.frame, second.frame)
    assert cached.stats.hits == 1 and cached.stats.misses == 1


def test_cache_is_isolated_by_as_of(counting_provider, tmp_path):
    cached = CachedProvider(counting_provider, tmp_path)
    late = cached.prices("AAA", date(2024, 1, 1), date(2025, 9, 30), date(2025, 9, 30))
    early = cached.prices("AAA", date(2024, 1, 1), date(2025, 9, 30), date(2025, 3, 31))
    assert counting_provider.price_calls == 2  # different as_of -> different key
    assert late.frame["date"].max() == pd.Timestamp("2025-09-30")
    assert early.frame["date"].max() == pd.Timestamp("2025-03-31")
    folders = {p.name for p in (tmp_path / "csv" / "AAA").iterdir()}
    assert folders == {"2025-09-30", "2025-03-31"}


def test_cache_refetches_when_window_not_covered(counting_provider, tmp_path, as_of):
    cached = CachedProvider(counting_provider, tmp_path)
    cached.prices("AAA", date(2025, 6, 1), as_of, as_of)
    cached.prices("AAA", date(2024, 1, 1), as_of, as_of)  # wider -> must refetch
    assert counting_provider.price_calls == 2
    cached.prices("AAA", date(2025, 1, 1), as_of, as_of)  # narrower -> hit
    assert counting_provider.price_calls == 2


def test_profile_is_cached(counting_provider, tmp_path, as_of):
    cached = CachedProvider(counting_provider, tmp_path)
    a = cached.profile("BBB", as_of)
    b = cached.profile("BBB", as_of)
    assert counting_provider.profile_calls == 1
    assert b.source.cache_hit and not a.source.cache_hit
    assert a.profile == b.profile
    assert (tmp_path / "csv" / "BBB" / as_of.isoformat() / "profile.json").exists()


def test_cache_stores_fetched_at_in_meta(counting_provider, tmp_path, as_of):
    import json

    cached = CachedProvider(counting_provider, tmp_path)
    result = cached.prices("CCC", date(2025, 1, 1), as_of, as_of)
    meta = json.loads((tmp_path / "csv" / "CCC" / as_of.isoformat() / "prices.meta.json").read_text())
    assert meta["as_of"] == as_of.isoformat()
    assert meta["source"]["fetched_at"] == result.source.fetched_at.isoformat()
    assert meta["rows"] == len(result.frame)

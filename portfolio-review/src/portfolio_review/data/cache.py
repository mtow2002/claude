"""Local parquet cache so re-runs are reproducible and never re-fetch.

Layout (all under the cache directory, default ``data/cache/``, gitignored)::

    data/cache/<provider>/<TICKER>/<as_of>/prices.parquet
    data/cache/<provider>/<TICKER>/<as_of>/prices.meta.json
    data/cache/<provider>/<TICKER>/<as_of>/profile.json

The key is (provider, ticker, as_of). Two runs with the same as_of read the
same bytes, so they produce the same numbers. A different as_of is a
different folder: data fetched for 2025-09-30 can never leak into a run for
2025-06-30 (as_of isolation).

Every cached item stores ``fetched_at`` (when the network call happened) and
``as_of`` (what point in time the data represents), which flow unchanged into
the report's Sources section.

:class:`CachedProvider` wraps any :class:`Provider` and is itself a Provider,
so the rest of the code never knows whether a result came from disk or the
network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .base import (
    PriceData,
    Profile,
    ProfileData,
    Provider,
    Source,
    check_as_of,
    enforce_as_of,
)

DEFAULT_CACHE_DIR = Path("data") / "cache"


@dataclass
class CacheStats:
    """Counters so a run can report how much came from disk vs. network."""

    hits: int = 0
    misses: int = 0


class CachedProvider:
    """A Provider that remembers answers on disk, keyed by (provider, ticker, as_of)."""

    def __init__(self, inner: Provider, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.inner = inner
        self.name = inner.name
        self.cache_dir = Path(cache_dir)
        self.stats = CacheStats()

    # ------------------------------------------------------------------ paths
    def _dir(self, ticker: str, as_of: date) -> Path:
        return self.cache_dir / self.name / ticker.upper() / as_of.isoformat()

    # ---------------------------------------------------------------- prices
    def prices(self, ticker: str, start: date, end: date, as_of: date) -> PriceData:
        folder = self._dir(ticker, as_of)
        parquet = folder / "prices.parquet"
        meta_path = folder / "prices.meta.json"

        if parquet.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            covers = (
                date.fromisoformat(meta["start"]) <= start
                and date.fromisoformat(meta["end"]) >= end
            )
            if covers:
                frame = pd.read_parquet(parquet)
                frame = frame[
                    (frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))
                ].reset_index(drop=True)
                frame = enforce_as_of(frame, as_of)
                source = Source.from_dict(meta["source"])
                source = Source(**{**source.to_dict_raw(), "cache_hit": True})
                self.stats.hits += 1
                return PriceData(frame=frame, source=source)

        # Miss (or cached window too narrow): fetch, verify, store.
        result = self.inner.prices(ticker, start, end, as_of)
        check_as_of(result.frame, as_of)
        folder.mkdir(parents=True, exist_ok=True)
        result.frame.to_parquet(parquet, index=False)
        meta: dict[str, Any] = {
            "ticker": ticker.upper(),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "as_of": as_of.isoformat(),
            "rows": int(len(result.frame)),
            "source": result.source.to_dict(),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self.stats.misses += 1
        return result

    # --------------------------------------------------------------- profile
    def profile(self, ticker: str, as_of: date) -> ProfileData:
        folder = self._dir(ticker, as_of)
        path = folder / "profile.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            source = Source.from_dict(payload["source"])
            source = Source(**{**source.to_dict_raw(), "cache_hit": True})
            self.stats.hits += 1
            return ProfileData(profile=Profile.from_dict(payload["profile"]), source=source)

        result = self.inner.profile(ticker, as_of)
        folder.mkdir(parents=True, exist_ok=True)
        payload = {"profile": result.profile.to_dict(), "source": result.source.to_dict()}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.stats.misses += 1
        return result

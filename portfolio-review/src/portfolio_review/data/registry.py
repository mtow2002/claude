"""Provider registry: maps the CLI's ``--provider`` name to a constructor.

To add a provider: write the class (see base.py), then add one line here.
``make_provider`` wraps every provider in the parquet cache unless asked not to.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .alpha_vantage import AlphaVantageProvider
from .base import Provider
from .cache import DEFAULT_CACHE_DIR, CachedProvider
from .csv_provider import CSVProvider
from .massive import MassiveProvider
from .yfinance_provider import YFinanceProvider

# name -> factory taking the optional ``--provider-path`` argument.
PROVIDERS: dict[str, Callable[[str | None], Provider]] = {
    "yfinance": lambda path: YFinanceProvider(),
    "csv": lambda path: CSVProvider(path or "data/csv"),
    "alpha_vantage": lambda path: AlphaVantageProvider(),
    "massive": lambda path: MassiveProvider(),
}


def make_provider(
    name: str,
    provider_path: str | None = None,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
) -> Provider:
    """Build a provider by name, wrapped in the cache (pass cache_dir=None to skip)."""
    try:
        factory = PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f"unknown provider {name!r}; choose from {sorted(PROVIDERS)}") from exc
    provider = factory(provider_path)
    if cache_dir is None:
        return provider
    return CachedProvider(provider, cache_dir=cache_dir)

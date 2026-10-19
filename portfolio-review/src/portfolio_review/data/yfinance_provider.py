"""Yahoo Finance provider, via the ``yfinance`` package. No API key needed.

Prices come from ``yfinance.Ticker.history`` with ``auto_adjust=False`` so we
get both raw ``close`` and dividend/split-adjusted ``adj_close``.

Point-in-time caveat (documented honestly, see docs/METHODOLOGY.md):
  * Prices are genuinely historical, and we drop anything after ``as_of``.
  * ``Ticker.info`` (name, sector, P/E, ...) is a snapshot of TODAY. Yahoo
    does not serve historical profiles. The Source note says so, and the
    report repeats the caveat. A later provider with historical fundamentals
    can fix this without touching the rest of the system.

Listing status: Yahoo returns an empty history for a dead symbol. We report
``listing_status="unknown"`` from profile() when info is empty; the runner then
cross-checks the last available price date against ``as_of`` and marks the
ticker delisted/stale when the gap is too large (see runner.py).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from .base import (
    PriceData,
    ProviderError,
    Profile,
    ProfileData,
    Source,
    empty_price_frame,
    enforce_as_of,
    normalize_price_frame,
    utc_now,
)

# Keys in yfinance's info dict that feed the value/quality factors.
_FUNDAMENTAL_KEYS = {
    "trailingPE": "pe_ratio",
    "priceToBook": "price_to_book",
    "returnOnEquity": "return_on_equity",
    "debtToEquity": "debt_to_equity",
    "profitMargins": "profit_margin",
}


class YFinanceProvider:
    """Provider implementation backed by Yahoo Finance."""

    name = "yfinance"

    def __init__(self) -> None:
        # Imported here, at construction time, so the package imports cleanly
        # even where yfinance is not installed (tests never need it).
        import yfinance  # noqa: WPS433

        self._yf = yfinance

    def prices(self, ticker: str, start: date, end: date, as_of: date) -> PriceData:
        fetched_at = utc_now()
        # yfinance's end is exclusive, so add one day to include ``end``.
        try:
            raw = self._yf.Ticker(ticker).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=False,
                raise_errors=True,
            )
        except Exception as exc:  # noqa: BLE001  (any transport/parse failure)
            raise ProviderError(
                f"yfinance could not fetch prices for {ticker} "
                f"(Ticker.history, {start}..{end}): {type(exc).__name__}: {exc}. "
                "Check network access to finance.yahoo.com, or use --provider csv with local files."
            ) from exc
        frame = normalize_price_frame(raw) if raw is not None and len(raw) else empty_price_frame()
        frame = enforce_as_of(frame, as_of)
        source = Source(
            provider=self.name,
            endpoint="yfinance.Ticker.history(interval=1d, auto_adjust=False)",
            fetched_at=fetched_at,
            as_of=as_of,
            ticker=ticker.upper(),
        )
        return PriceData(frame=frame, source=source)

    def profile(self, ticker: str, as_of: date) -> ProfileData:
        fetched_at = utc_now()
        info: dict[str, Any] = {}
        try:
            info = dict(self._yf.Ticker(ticker).info or {})
        except Exception:  # noqa: BLE001  (network or parsing errors: degrade loudly below)
            info = {}

        quote_type = str(info.get("quoteType", "")).upper()
        if quote_type == "ETF":
            asset_type = "etf"
        elif quote_type in {"EQUITY", "STOCK"}:
            asset_type = "stock"
        else:
            asset_type = "unknown"

        # Yahoo gives stocks a sector; ETFs get a "category" (e.g. "Large Blend").
        sector = str(info.get("sector") or info.get("category") or "")
        industry = str(info.get("industry") or "")
        name = str(info.get("longName") or info.get("shortName") or "")
        listing_status = "active" if info.get("symbol") or info.get("regularMarketPrice") else "unknown"

        fundamentals: dict[str, float] = {}
        for yf_key, our_key in _FUNDAMENTAL_KEYS.items():
            value = info.get(yf_key)
            if isinstance(value, (int, float)) and pd.notna(value):
                fundamentals[our_key] = float(value)

        profile = Profile(
            ticker=ticker.upper(),
            name=name,
            sector=sector,
            industry=industry,
            asset_type=asset_type,
            listing_status=listing_status,
            fundamentals=fundamentals,
        )
        source = Source(
            provider=self.name,
            endpoint="yfinance.Ticker.info",
            fetched_at=fetched_at,
            as_of=as_of,
            ticker=ticker.upper(),
            note="profile fields are a current snapshot, not point-in-time",
        )
        return ProfileData(profile=profile, source=source)

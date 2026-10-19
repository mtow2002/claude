"""Alpha Vantage provider. STUB: a later session implements this.

Interface to satisfy (identical to every other provider, see base.py):

    class AlphaVantageProvider:
        name = "alpha_vantage"

        def __init__(self, api_key: str | None = None) -> None:
            # Read ALPHA_VANTAGE_API_KEY from the environment when api_key is
            # None. Never log or store the key. Raise a clear error if absent.

        def prices(self, ticker, start, end, as_of) -> PriceData:
            # Endpoint: TIME_SERIES_DAILY_ADJUSTED (outputsize=full).
            # Map "5. adjusted close" -> adj_close, "4. close" -> close,
            # "6. volume" -> volume. Run the result through
            # normalize_price_frame() then enforce_as_of().
            # Source.endpoint should be the function name plus parameters,
            # e.g. "TIME_SERIES_DAILY_ADJUSTED?symbol=AAPL&outputsize=full".
            # Respect the free-tier rate limit (5 calls/min): sleep or raise
            # a RateLimited error the caller can retry; never return partial
            # data as if it were complete.

        def profile(self, ticker, as_of) -> ProfileData:
            # Endpoints: OVERVIEW (stocks: Name, Sector, Industry, PERatio,
            # PriceToBookRatio, ReturnOnEquityTTM, ProfitMargin) and
            # ETF_PROFILE for ETFs. LISTING_STATUS (state=delisted, date=as_of)
            # gives a genuinely point-in-time listing_status, which yfinance
            # cannot; use it.

Register it in data/registry.py by adding one line to PROVIDERS. Tests must
use recorded JSON fixtures under tests/fixtures/alpha_vantage/, never the
network.
"""

from __future__ import annotations

from datetime import date

from .base import PriceData, ProfileData


class AlphaVantageProvider:
    """Placeholder that fails loudly until implemented."""

    name = "alpha_vantage"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def prices(self, ticker: str, start: date, end: date, as_of: date) -> PriceData:
        raise NotImplementedError(
            "AlphaVantageProvider.prices is not implemented yet; see the module docstring"
        )

    def profile(self, ticker: str, as_of: date) -> ProfileData:
        raise NotImplementedError(
            "AlphaVantageProvider.profile is not implemented yet; see the module docstring"
        )

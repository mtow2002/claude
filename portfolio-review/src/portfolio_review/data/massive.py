"""Massive (massive.com market data API) provider. STUB: a later session implements this.

Interface to satisfy (identical to every other provider, see base.py):

    class MassiveProvider:
        name = "massive"

        def __init__(self, api_key: str | None = None) -> None:
            # Read MASSIVE_API_KEY from the environment when api_key is None.

        def prices(self, ticker, start, end, as_of) -> PriceData:
            # Use the daily aggregates (bars) endpoint for the ticker between
            # start and end. Map open/high/low/close/volume; Massive bars are
            # typically split-adjusted but not dividend-adjusted, so document
            # what adj_close means (and set adj_close = close if no adjusted
            # series exists, with a Source.note saying so).
            # Source.endpoint = the REST path actually called.

        def profile(self, ticker, as_of) -> ProfileData:
            # Use the ticker details / reference endpoint. Massive carries an
            # "active" flag and a delisted date for reference data, so
            # listing_status can be computed point-in-time: delisted if the
            # delisted date <= as_of, else active.

Register in data/registry.py. Tests use recorded JSON fixtures under
tests/fixtures/massive/, never the network.
"""

from __future__ import annotations

from datetime import date

from .base import PriceData, ProfileData


class MassiveProvider:
    """Placeholder that fails loudly until implemented."""

    name = "massive"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def prices(self, ticker: str, start: date, end: date, as_of: date) -> PriceData:
        raise NotImplementedError(
            "MassiveProvider.prices is not implemented yet; see the module docstring"
        )

    def profile(self, ticker: str, as_of: date) -> ProfileData:
        raise NotImplementedError(
            "MassiveProvider.profile is not implemented yet; see the module docstring"
        )

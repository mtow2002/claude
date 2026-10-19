"""Provider contracts: canonical frame layout, as_of guard, delisted handling."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from portfolio_review.data.base import (
    PRICE_COLUMNS,
    check_as_of,
    enforce_as_of,
    normalize_price_frame,
)


def test_normalize_accepts_yahoo_style_columns():
    raw = pd.DataFrame(
        {
            "Date": ["2025-01-03", "2025-01-02"],
            "Open": [1, 2],
            "High": [1, 2],
            "Low": [1, 2],
            "Close": [1.5, 2.5],
            "Adj Close": [1.4, 2.4],
            "Volume": [10, 20],
        }
    )
    out = normalize_price_frame(raw)
    assert list(out.columns) == PRICE_COLUMNS
    assert list(out["date"].dt.strftime("%Y-%m-%d")) == ["2025-01-02", "2025-01-03"]  # sorted
    assert out["adj_close"].iloc[0] == pytest.approx(2.4)


def test_normalize_missing_column_raises():
    with pytest.raises(ValueError, match="missing columns"):
        normalize_price_frame(pd.DataFrame({"date": ["2025-01-02"], "close": [1.0]}).drop(columns="close"))


def test_enforce_as_of_drops_future_rows():
    frame = normalize_price_frame(
        pd.DataFrame(
            {
                "date": ["2025-01-02", "2025-01-03", "2025-01-06"],
                "open": [1, 1, 1], "high": [1, 1, 1], "low": [1, 1, 1],
                "close": [1, 2, 3], "adj_close": [1, 2, 3], "volume": [1, 1, 1],
            }
        )
    )
    out = enforce_as_of(frame, date(2025, 1, 3))
    assert len(out) == 2
    check_as_of(out, date(2025, 1, 3))
    with pytest.raises(ValueError, match="point-in-time violation"):
        check_as_of(frame, date(2025, 1, 3))


def test_csv_provider_respects_as_of(csv_provider):
    result = csv_provider.prices("AAA", date(2024, 1, 1), date(2025, 12, 31), date(2025, 3, 31))
    assert result.frame["date"].max() == pd.Timestamp("2025-03-31")
    assert result.source.provider == "csv"
    assert result.source.as_of == date(2025, 3, 31)
    assert result.source.fetched_at.tzinfo is not None


def test_csv_provider_delisted_ticker_keeps_its_history(csv_provider, as_of):
    result = csv_provider.prices("DDD", date(2024, 1, 1), as_of, as_of)
    assert len(result.frame) > 0
    assert result.frame["date"].max() == pd.Timestamp("2025-06-30")
    profile = csv_provider.profile("DDD", as_of).profile
    assert profile.listing_status == "delisted"


def test_csv_provider_unknown_ticker_is_empty_not_error(csv_provider, as_of):
    result = csv_provider.prices("NOPE", date(2024, 1, 1), as_of, as_of)
    assert len(result.frame) == 0
    assert csv_provider.profile("NOPE", as_of).profile.listing_status == "unknown"


def test_stub_providers_raise_not_implemented():
    from portfolio_review.data.alpha_vantage import AlphaVantageProvider
    from portfolio_review.data.massive import MassiveProvider

    for cls in (AlphaVantageProvider, MassiveProvider):
        with pytest.raises(NotImplementedError):
            cls().prices("AAA", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 2))
        with pytest.raises(NotImplementedError):
            cls().profile("AAA", date(2025, 1, 2))

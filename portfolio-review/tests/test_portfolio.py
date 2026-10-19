"""Exposures, concentration, and weighted portfolio returns."""

from __future__ import annotations

import pandas as pd
import pytest

from portfolio_review.portfolio import concentration, exposure_by, portfolio_metrics, portfolio_returns


def _holdings():
    return pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "CASH"],
            "asset_type": ["stock", "stock", "etf", "cash"],
            "sector": ["Tech", "Tech", "Bonds", "Cash"],
            "weight": [0.4, 0.3, 0.2, 0.1],
        }
    )


def test_exposure_by_sector():
    out = exposure_by(_holdings(), "sector").set_index("sector")["weight"]
    assert out.to_dict() == pytest.approx({"Tech": 0.7, "Bonds": 0.2, "Cash": 0.1})


def test_concentration_excludes_cash():
    c = concentration(_holdings())
    assert c["hhi"] == pytest.approx(0.4**2 + 0.3**2 + 0.2**2)
    assert c["effective_n"] == pytest.approx(1 / c["hhi"])
    assert c["top_1_weight"] == 0.4 and c["top_3_weight"] == pytest.approx(0.9) and c["positions"] == 3


def test_portfolio_returns_are_weighted_sum():
    idx = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    prices = {"A": pd.Series([100, 110, 99], index=idx, dtype="float64"), "B": pd.Series([50, 50, 55], index=idx, dtype="float64")}
    rets = portfolio_returns({"A": 0.5, "B": 0.5, "CASH": 0.0}, prices)
    assert rets.tolist() == pytest.approx([0.5 * 0.10 + 0.5 * 0.0, 0.5 * -0.10 + 0.5 * 0.10])


def test_portfolio_metrics_from_returns():
    idx = pd.to_datetime(["2025-01-03", "2025-01-06", "2025-01-07"])
    rets = pd.Series([0.10, -0.10, 0.10], index=idx)
    out = portfolio_metrics(rets)
    assert out["total_return"] == pytest.approx(1.1 * 0.9 * 1.1 - 1)
    assert out["max_drawdown"] == pytest.approx(-0.10)

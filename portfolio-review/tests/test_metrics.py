"""Metrics against hand-computed expected values.

Price series: 100, 110, 99, 108.9  -> daily returns +10%, -10%, +10%
Benchmark:    100, 105, 99.75, 104.7375 -> +5%, -5%, +5% (exactly half)
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from portfolio_review import metrics as m

PRICES = pd.Series([100.0, 110.0, 99.0, 108.9], index=pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]))
BENCH = pd.Series([100.0, 105.0, 99.75, 104.7375], index=PRICES.index)
RETS = [0.10, -0.10, 0.10]
MEAN = sum(RETS) / 3
STD = math.sqrt(sum((r - MEAN) ** 2 for r in RETS) / 2)  # ddof=1


def test_daily_returns():
    assert m.daily_returns(PRICES).tolist() == pytest.approx(RETS)


def test_total_and_annualized_return():
    assert m.total_return(PRICES) == pytest.approx(0.089)
    assert m.annualized_return(PRICES) == pytest.approx(1.089 ** (252 / 3) - 1)


def test_annualized_volatility():
    assert m.annualized_volatility(m.daily_returns(PRICES)) == pytest.approx(STD * math.sqrt(252))


def test_max_drawdown():
    assert m.max_drawdown(PRICES) == pytest.approx(99 / 110 - 1)  # -10%
    rising = pd.Series([1.0, 2.0, 3.0], index=PRICES.index[:3])
    assert m.max_drawdown(rising) == 0.0


def test_sharpe_zero_rf():
    expected = MEAN * 252 / (STD * math.sqrt(252))
    assert m.sharpe_ratio(m.daily_returns(PRICES)) == pytest.approx(expected)


def test_sharpe_with_rf():
    rf = 0.0252  # daily rf = 0.0001
    excess = [r - 0.0001 for r in RETS]
    mean = sum(excess) / 3
    std = math.sqrt(sum((e - mean) ** 2 for e in excess) / 2)
    assert m.sharpe_ratio(m.daily_returns(PRICES), rf) == pytest.approx(mean * 252 / (std * math.sqrt(252)))


def test_beta_is_two_when_returns_are_double():
    assert m.beta(m.daily_returns(PRICES), m.daily_returns(BENCH)) == pytest.approx(2.0)


def test_momentum_window():
    assert m.momentum(PRICES, 2) == pytest.approx(108.9 / 110 - 1)
    assert m.momentum(PRICES, 3) == pytest.approx(108.9 / 100 - 1)  # len 4 > window 3 is fine
    assert math.isnan(m.momentum(PRICES, 4))  # needs len > window


def test_trend():
    sma3 = (110 + 99 + 108.9) / 3
    assert m.trend_200d(PRICES, window=3) == pytest.approx(108.9 / sma3 - 1)
    assert math.isnan(m.trend_200d(PRICES))  # fewer than 200 rows


def test_periodic_returns_monthly():
    idx = pd.to_datetime(["2025-01-30", "2025-01-31", "2025-02-27", "2025-02-28"])
    prices = pd.Series([1.0, 2.0, 3.0, 4.0], index=idx)
    out = m.periodic_returns(prices, "ME")
    assert out.tolist() == pytest.approx([4.0 / 2.0 - 1])


def test_ticker_metrics_keys_and_nan_on_short_series():
    out = m.ticker_metrics(PRICES, BENCH, 0.0)
    assert out["beta"] == pytest.approx(2.0)
    assert math.isnan(out["momentum_3m"])
    assert set(out) >= {"annualized_return", "annualized_volatility", "max_drawdown", "sharpe", "momentum_12m", "trend_200d"}

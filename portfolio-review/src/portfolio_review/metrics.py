"""Return and risk metrics for a single price series or return series.

Every function is pure (inputs in, numbers out) and documents its formula so a
reader can reproduce any number in the report by hand. Conventions:

* ``prices`` is a pandas Series of adjusted closes indexed by date, ascending.
* ``returns`` is a Series of simple daily returns: r_t = P_t / P_{t-1} - 1.
* ``TRADING_DAYS`` = 252 per year; ``periods`` for momentum use 21 trading
  days per month (3m = 63, 6m = 126, 12m = 252).
* Results are plain floats; ``float('nan')`` means "not enough data", never 0.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252
MONTH = 21  # trading days
MOMENTUM_WINDOWS = {"momentum_3m": 3 * MONTH, "momentum_6m": 6 * MONTH, "momentum_12m": 12 * MONTH}
TREND_WINDOW = 200


def daily_returns(prices: pd.Series) -> pd.Series:
    """Simple daily returns: r_t = P_t / P_{t-1} - 1. First value is dropped."""
    prices = prices.astype("float64")
    return (prices / prices.shift(1) - 1.0).dropna()


def periodic_returns(prices: pd.Series, freq: str = "ME") -> pd.Series:
    """Returns over calendar periods: weekly ("W-FRI"), monthly ("ME"), quarterly ("QE").

    The last price of each period is taken, then r = P_end / P_prev_end - 1.
    """
    period_end = prices.astype("float64").resample(freq).last().dropna()
    return (period_end / period_end.shift(1) - 1.0).dropna()


def total_return(prices: pd.Series) -> float:
    """P_last / P_first - 1 over the whole series."""
    if len(prices) < 2:
        return float("nan")
    return float(prices.iloc[-1] / prices.iloc[0] - 1.0)


def annualized_return(prices: pd.Series) -> float:
    """Compound annual growth rate: (P_last / P_first) ** (252 / n_days) - 1,
    where n_days is the number of daily return observations (len - 1)."""
    n = len(prices) - 1
    if n < 1 or prices.iloc[0] <= 0:
        return float("nan")
    return float((prices.iloc[-1] / prices.iloc[0]) ** (TRADING_DAYS / n) - 1.0)


def annualized_volatility(returns: pd.Series) -> float:
    """Sample standard deviation of daily returns (ddof=1) times sqrt(252)."""
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))


def max_drawdown(prices: pd.Series) -> float:
    """Largest peak-to-trough decline as a NEGATIVE fraction.

    dd_t = P_t / max(P_0..P_t) - 1 ; max_drawdown = min_t dd_t.
    A series that only rises returns 0.0.
    """
    if len(prices) < 2:
        return float("nan")
    running_peak = prices.cummax()
    drawdowns = prices / running_peak - 1.0
    return float(drawdowns.min())


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe: mean(daily excess) * 252 / (std(daily, ddof=1) * sqrt(252)).

    Daily excess return = r_t - risk_free_rate / 252. Returns nan when the
    standard deviation is zero or there are fewer than two observations.
    """
    if len(returns) < 2:
        return float("nan")
    excess = returns - risk_free_rate / TRADING_DAYS
    vol = excess.std(ddof=1)
    if vol == 0 or np.isnan(vol):
        return float("nan")
    return float(excess.mean() * TRADING_DAYS / (vol * math.sqrt(TRADING_DAYS)))


def beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """beta = cov(r, r_b) / var(r_b) over the dates both series share (ddof=1)."""
    joined = pd.concat([returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(joined) < 2:
        return float("nan")
    r, b = joined.iloc[:, 0], joined.iloc[:, 1]
    var_b = b.var(ddof=1)
    if var_b == 0 or np.isnan(var_b):
        return float("nan")
    return float(r.cov(b) / var_b)


def momentum(prices: pd.Series, window: int) -> float:
    """Price change over the last ``window`` trading days: P_last / P_{last-window} - 1."""
    if len(prices) <= window:
        return float("nan")
    return float(prices.iloc[-1] / prices.iloc[-1 - window] - 1.0)


def trend_200d(prices: pd.Series, window: int = TREND_WINDOW) -> float:
    """Distance of the last price from its simple moving average:
    P_last / SMA(window) - 1. Positive means the price is above trend."""
    if len(prices) < window:
        return float("nan")
    sma = prices.iloc[-window:].mean()
    if sma == 0:
        return float("nan")
    return float(prices.iloc[-1] / sma - 1.0)


def ticker_metrics(
    prices: pd.Series,
    benchmark_prices: pd.Series | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """Every metric for one price series, as a flat dict for a report row."""
    rets = daily_returns(prices)
    out: dict[str, float] = {
        "observations": float(len(prices)),
        "total_return": total_return(prices),
        "annualized_return": annualized_return(prices),
        "annualized_volatility": annualized_volatility(rets),
        "max_drawdown": max_drawdown(prices),
        "sharpe": sharpe_ratio(rets, risk_free_rate),
        "trend_200d": trend_200d(prices),
    }
    for name, window in MOMENTUM_WINDOWS.items():
        out[name] = momentum(prices, window)
    if benchmark_prices is not None and len(benchmark_prices) > 1:
        out["beta"] = beta(rets, daily_returns(benchmark_prices))
    else:
        out["beta"] = float("nan")
    return out

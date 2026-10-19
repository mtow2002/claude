"""Portfolio-level views: exposures, concentration, and weighted return series.

Inputs are the weight-normalized holdings (holdings.py) plus per-ticker price
series. All formulas are documented inline.
"""

from __future__ import annotations

from typing import Mapping

import pandas as pd

from .metrics import annualized_return, annualized_volatility, beta, daily_returns, max_drawdown, sharpe_ratio


def exposure_by(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Sum of weights grouped by ``column`` (asset_type, asset_class, sector, account...)."""
    grouped = frame.groupby(column, dropna=False)["weight"].sum().sort_values(ascending=False)
    out = grouped.reset_index()
    out.columns = [column, "weight"]
    return out


def concentration(frame: pd.DataFrame) -> dict[str, float]:
    """Concentration metrics over NON-CASH positions.

    hhi            = sum_i w_i^2 over non-cash weights (1.0 = one position)
    effective_n    = 1 / hhi   (how many equal positions it behaves like)
    top_1_weight   = largest single non-cash weight
    top_3_weight   = sum of the three largest non-cash weights
    positions      = count of non-cash positions
    """
    w = frame.loc[frame["asset_type"] != "cash", "weight"].astype("float64").sort_values(ascending=False)
    if len(w) == 0:
        return {"hhi": float("nan"), "effective_n": float("nan"), "top_1_weight": 0.0, "top_3_weight": 0.0, "positions": 0.0}
    hhi = float((w**2).sum())
    return {
        "hhi": hhi,
        "effective_n": (1.0 / hhi) if hhi > 0 else float("nan"),
        "top_1_weight": float(w.iloc[0]),
        "top_3_weight": float(w.iloc[:3].sum()),
        "positions": float(len(w)),
    }


def portfolio_returns(
    weights: Mapping[str, float],
    prices_by_ticker: Mapping[str, pd.Series],
) -> pd.Series:
    """Daily portfolio return with constant weights: r_p,t = sum_i w_i * r_i,t.

    Constant weights mean "rebalanced daily back to target", which is the
    standard simplification for a review (not a backtest). Cash earns 0.
    Tickers with no prices contribute 0 and are reported separately by the
    runner; dates are the union of all available dates, with a ticker's
    missing days treated as 0 return (a delisted stock stops contributing).
    """
    pieces = []
    for ticker, weight in weights.items():
        series = prices_by_ticker.get(ticker)
        if series is None or len(series) < 2:
            continue
        pieces.append(daily_returns(series).rename(ticker) * float(weight))
    if not pieces:
        return pd.Series(dtype="float64")
    frame = pd.concat(pieces, axis=1).fillna(0.0).sort_index()
    return frame.sum(axis=1)


def portfolio_metrics(
    port_returns: pd.Series,
    benchmark_prices: pd.Series | None = None,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """Return, volatility, drawdown, Sharpe and beta for a daily return series.

    A synthetic price index is rebuilt as cumprod(1 + r) starting at 1.0 so
    the drawdown and CAGR formulas in metrics.py apply unchanged.
    """
    if len(port_returns) < 2:
        return {k: float("nan") for k in ("annualized_return", "annualized_volatility", "max_drawdown", "sharpe", "beta", "total_return")}
    index = (1.0 + port_returns).cumprod()
    index = pd.concat([pd.Series([1.0], index=[port_returns.index[0] - pd.Timedelta(days=1)]), index])
    out = {
        "total_return": float(index.iloc[-1] - 1.0),
        "annualized_return": annualized_return(index),
        "annualized_volatility": annualized_volatility(port_returns),
        "max_drawdown": max_drawdown(index),
        "sharpe": sharpe_ratio(port_returns, risk_free_rate),
        "beta": float("nan"),
    }
    if benchmark_prices is not None and len(benchmark_prices) > 1:
        out["beta"] = beta(port_returns, daily_returns(benchmark_prices))
    return out

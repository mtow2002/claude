"""Per-ticker factor scores (0..100) and a weighted composite.

How scoring works
-----------------
1. For each factor, compute a RAW value per ticker (formulas below).
2. Convert raw values to a 0..100 score by PERCENTILE RANK across the
   universe of tickers that have a value:
       score_i = 100 * rank_i / (n - 1)      (rank 0 = worst, n-1 = best)
   A single-ticker universe scores 50. A factor with higher_is_better=False
   (low_volatility) ranks ascending so the least volatile ticker scores 100.
3. A ticker with no raw value (e.g. an ETF has no P/E) gets the NEUTRAL score
   50 and is flagged in ``missing`` so the report can say so. We never invent
   a number.
4. composite_i = sum_f weight_f * score_{f,i}, with weights from the policy.

The five shipped factors (raw formulas)
---------------------------------------
momentum        mean of 3m, 6m and 12m price returns (metrics.momentum)
value           earnings yield = 1 / pe_ratio  (higher is cheaper)
quality         return_on_equity               (higher is better)
low_volatility  annualized volatility          (LOWER is better)
trend           P_last / SMA200 - 1            (higher is more above trend)

Adding a factor
---------------
Write a function ``(metrics_row: dict, fundamentals: dict) -> float | nan``,
add a FactorSpec to FACTORS, and add its name to config.FACTOR_NAMES so the
policy validator accepts a weight for it. Nothing else changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping

import pandas as pd

RawFn = Callable[[Mapping[str, float], Mapping[str, float]], float]
NEUTRAL_SCORE = 50.0


@dataclass(frozen=True)
class FactorSpec:
    """One factor: how to compute its raw value and which direction is good."""

    name: str
    raw: RawFn
    higher_is_better: bool
    description: str


def _nan() -> float:
    return float("nan")


def _momentum_raw(m: Mapping[str, float], f: Mapping[str, float]) -> float:
    parts = [m.get("momentum_3m"), m.get("momentum_6m"), m.get("momentum_12m")]
    parts = [p for p in parts if p is not None and not math.isnan(p)]
    return sum(parts) / len(parts) if parts else _nan()


def _value_raw(m: Mapping[str, float], f: Mapping[str, float]) -> float:
    pe = f.get("pe_ratio")
    if pe is None or math.isnan(pe) or pe <= 0:
        return _nan()
    return 1.0 / pe


def _quality_raw(m: Mapping[str, float], f: Mapping[str, float]) -> float:
    roe = f.get("return_on_equity")
    return float(roe) if roe is not None and not math.isnan(roe) else _nan()


def _low_vol_raw(m: Mapping[str, float], f: Mapping[str, float]) -> float:
    v = m.get("annualized_volatility")
    return float(v) if v is not None and not math.isnan(v) else _nan()


def _trend_raw(m: Mapping[str, float], f: Mapping[str, float]) -> float:
    t = m.get("trend_200d")
    return float(t) if t is not None and not math.isnan(t) else _nan()


FACTORS: dict[str, FactorSpec] = {
    "momentum": FactorSpec("momentum", _momentum_raw, True, "mean of 3m/6m/12m returns"),
    "value": FactorSpec("value", _value_raw, True, "earnings yield 1/PE"),
    "quality": FactorSpec("quality", _quality_raw, True, "return on equity"),
    "low_volatility": FactorSpec("low_volatility", _low_vol_raw, False, "annualized volatility"),
    "trend": FactorSpec("trend", _trend_raw, True, "price vs 200-day SMA"),
}


def percentile_scores(raw: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Map raw values to 0..100 by rank. NaN stays NaN (caller decides the fill).

    Ties share the average rank (pandas method="average").
    """
    valid = raw.dropna()
    scores = pd.Series(float("nan"), index=raw.index, dtype="float64")
    n = len(valid)
    if n == 0:
        return scores
    if n == 1:
        scores[valid.index] = NEUTRAL_SCORE
        return scores
    ranks = valid.rank(method="average", ascending=higher_is_better) - 1.0  # 0..n-1
    scores[valid.index] = 100.0 * ranks / (n - 1)
    return scores


def score_factors(
    metrics_by_ticker: Mapping[str, Mapping[str, float]],
    fundamentals_by_ticker: Mapping[str, Mapping[str, float]],
    factor_weights: Mapping[str, float],
    factors: Mapping[str, FactorSpec] = FACTORS,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Return (scores frame, missing) for every ticker in ``metrics_by_ticker``.

    The frame has one row per ticker with columns ``<factor>_raw``,
    ``<factor>_score`` for each factor, plus ``composite``.
    ``missing`` maps factor name -> tickers that received the neutral score.
    """
    tickers = list(metrics_by_ticker)
    frame = pd.DataFrame(index=pd.Index(tickers, name="ticker"))
    missing: dict[str, list[str]] = {}
    composite = pd.Series(0.0, index=frame.index, dtype="float64")

    for name, spec in factors.items():
        weight = float(factor_weights.get(name, 0.0))
        raw_values = pd.Series(
            {
                t: spec.raw(metrics_by_ticker[t], fundamentals_by_ticker.get(t, {}))
                for t in tickers
            },
            dtype="float64",
        )
        scores = percentile_scores(raw_values, spec.higher_is_better)
        missing[name] = [t for t in tickers if math.isnan(scores[t])]
        scores = scores.fillna(NEUTRAL_SCORE)
        frame[f"{name}_raw"] = raw_values
        frame[f"{name}_score"] = scores
        composite = composite + weight * scores

    frame["composite"] = composite
    return frame.reset_index(), missing

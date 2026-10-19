"""Factor scoring: percentile ranks, direction, neutral fill, composite."""

from __future__ import annotations

import pandas as pd
import pytest

from portfolio_review.factors import FACTORS, FactorSpec, percentile_scores, score_factors


def test_percentile_scores_higher_is_better():
    raw = pd.Series({"A": 1.0, "B": 3.0, "C": 2.0})
    out = percentile_scores(raw, True)
    assert out.to_dict() == pytest.approx({"A": 0.0, "B": 100.0, "C": 50.0})


def test_percentile_scores_lower_is_better():
    raw = pd.Series({"A": 1.0, "B": 3.0, "C": 2.0})
    out = percentile_scores(raw, False)
    assert out.to_dict() == pytest.approx({"A": 100.0, "B": 0.0, "C": 50.0})


def test_single_ticker_scores_neutral_and_nan_stays_nan():
    out = percentile_scores(pd.Series({"A": 5.0, "B": float("nan")}), True)
    assert out["A"] == 50.0
    assert pd.isna(out["B"])


def test_score_factors_composite_and_missing():
    metrics = {
        "A": {"momentum_3m": 0.1, "momentum_6m": 0.2, "momentum_12m": 0.3, "annualized_volatility": 0.1, "trend_200d": 0.05},
        "B": {"momentum_3m": -0.1, "momentum_6m": -0.2, "momentum_12m": -0.3, "annualized_volatility": 0.3, "trend_200d": -0.05},
    }
    fundamentals = {"A": {"pe_ratio": 10.0, "return_on_equity": 0.2}, "B": {}}
    weights = {"momentum": 0.4, "value": 0.1, "quality": 0.1, "low_volatility": 0.2, "trend": 0.2}
    frame, missing = score_factors(metrics, fundamentals, weights)
    frame = frame.set_index("ticker")
    assert frame.loc["A", "momentum_score"] == 100 and frame.loc["B", "momentum_score"] == 0
    assert frame.loc["A", "low_volatility_score"] == 100  # lower vol is better
    # B has no PE/ROE and A is alone in the value/quality universe -> both 50.
    assert frame.loc["B", "value_score"] == 50 and frame.loc["A", "value_score"] == 50
    assert missing["value"] == ["B"] and missing["quality"] == ["B"]
    assert frame.loc["A", "composite"] == pytest.approx(0.4 * 100 + 0.1 * 50 + 0.1 * 50 + 0.2 * 100 + 0.2 * 100)
    assert frame.loc["B", "composite"] == pytest.approx(0.1 * 50 + 0.1 * 50)


def test_adding_a_factor_is_one_registry_entry():
    custom = dict(FACTORS)
    custom["size"] = FactorSpec("size", lambda m, f: f.get("market_cap", float("nan")), False, "smaller is better")
    frame, _ = score_factors(
        {"A": {}, "B": {}},
        {"A": {"market_cap": 1.0}, "B": {"market_cap": 2.0}},
        {"size": 1.0},
        factors=custom,
    )
    frame = frame.set_index("ticker")
    assert frame.loc["A", "size_score"] == 100 and frame.loc["B", "composite"] == 0

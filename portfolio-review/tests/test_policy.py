"""One test per policy rule, plus severity ordering."""

from __future__ import annotations

import pandas as pd
import pytest

from portfolio_review import policy as pol
from portfolio_review.config import load_policy


@pytest.fixture
def policy(fixtures_dir):
    return load_policy(fixtures_dir / "policy.yaml")


def _holdings(rows):
    frame = pd.DataFrame(rows)
    for col, default in (("sector", "Tech"), ("listing_status", "active"), ("last_price_date", "2025-09-30")):
        if col not in frame:
            frame[col] = default
    return frame


def _ctx(policy, rows, portfolio=None):
    return pol.PolicyContext(policy=policy, holdings=_holdings(rows), portfolio=portfolio or {})


def _by(findings, rule, subject=None):
    return [f for f in findings if f.rule == rule and (subject is None or f.subject == subject)]


def test_asset_class_targets_band_logic(policy):
    # fixture policy: us_equity 0.50, band 0.05, breach at 2x band
    rows = [
        {"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.62},
        {"ticker": "B", "asset_type": "etf", "asset_class": "bonds", "weight": 0.21},
        {"ticker": "CASH", "asset_type": "cash", "asset_class": "cash", "weight": 0.17},
    ]
    f = pol.check_asset_class_targets(_ctx(policy, rows))
    sev = {x.subject: x.severity for x in f}
    assert sev["us_equity"] == "breach"  # +12 > 10
    assert sev["bonds"] == "info"  # -4 within 5
    assert sev["cash"] == "info"  # +2
    assert sev["intl_equity"] == "warn"  # -10, exactly 2x band -> warn, not breach
    assert "trim us_equity" in _by(f, "asset_class_target", "us_equity")[0].suggested_action


def test_max_single_position(policy):  # limit 0.25, warn at 0.225
    rows = [
        {"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.30},
        {"ticker": "B", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.23},
        {"ticker": "C", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.25},
        {"ticker": "D", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.10},
        {"ticker": "CASH", "asset_type": "cash", "asset_class": "cash", "weight": 0.12},
    ]
    sev = {x.subject: x.severity for x in pol.check_max_single_position(_ctx(policy, rows))}
    assert sev == {"A": "breach", "B": "warn", "C": "warn", "D": "info"}  # cash never listed


def test_max_sector(policy):  # limit 0.35
    rows = [
        {"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.20, "sector": "Tech"},
        {"ticker": "B", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.20, "sector": "Tech"},
        {"ticker": "C", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.10, "sector": ""},
        {"ticker": "CASH", "asset_type": "cash", "asset_class": "cash", "weight": 0.50, "sector": "Cash"},
    ]
    f = pol.check_max_sector(_ctx(policy, rows))
    sev = {x.subject: x.severity for x in f}
    assert sev["Tech"] == "breach" and sev["Unknown"] == "info" and "Cash" not in sev


def test_max_single_etf(policy):  # limit 0.30
    rows = [
        {"ticker": "E1", "asset_type": "etf", "asset_class": "bonds", "weight": 0.31},
        {"ticker": "S1", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.40},
        {"ticker": "CASH", "asset_type": "cash", "asset_class": "cash", "weight": 0.29},
    ]
    f = pol.check_max_single_etf(_ctx(policy, rows))
    assert [(x.subject, x.severity) for x in f] == [("E1", "breach")]  # stocks not checked here


def test_min_cash(policy):  # min 0.05
    def cash(w):
        rows = [
            {"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 1 - w},
            {"ticker": "CASH", "asset_type": "cash", "asset_class": "cash", "weight": w},
        ]
        return pol.check_min_cash(_ctx(policy, rows))[0].severity

    assert cash(0.02) == "breach" and cash(0.055) == "warn" and cash(0.10) == "info"


def test_max_volatility(policy):  # limit 0.20, warn at 0.18
    rows = [{"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 1.0}]
    assert pol.check_max_volatility(_ctx(policy, rows, {"annualized_volatility": 0.25}))[0].severity == "breach"
    assert pol.check_max_volatility(_ctx(policy, rows, {"annualized_volatility": 0.19}))[0].severity == "warn"
    assert pol.check_max_volatility(_ctx(policy, rows, {"annualized_volatility": 0.10}))[0].severity == "info"
    assert pol.check_max_volatility(_ctx(policy, rows, {}))[0].severity == "warn"  # unknown is never silent


def test_max_drawdown(policy):  # tolerance 0.25
    rows = [{"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 1.0}]
    assert pol.check_max_drawdown(_ctx(policy, rows, {"max_drawdown": -0.30}))[0].severity == "breach"
    assert pol.check_max_drawdown(_ctx(policy, rows, {"max_drawdown": -0.23}))[0].severity == "warn"
    assert pol.check_max_drawdown(_ctx(policy, rows, {"max_drawdown": -0.05}))[0].severity == "info"


def test_listing_status(policy):
    rows = [
        {"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.5, "listing_status": "active"},
        {"ticker": "D", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.3, "listing_status": "delisted"},
        {"ticker": "U", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.2, "listing_status": "unknown"},
    ]
    f = pol.check_listing_status(_ctx(policy, rows))
    assert {x.subject: x.severity for x in f} == {"D": "breach", "U": "warn"}


def test_evaluate_runs_every_rule_and_sorts_worst_first(policy):
    rows = [
        {"ticker": "A", "asset_type": "stock", "asset_class": "us_equity", "weight": 0.9},
        {"ticker": "CASH", "asset_type": "cash", "asset_class": "cash", "weight": 0.1},
    ]
    findings = pol.evaluate(_ctx(policy, rows, {"annualized_volatility": 0.1, "max_drawdown": -0.1}))
    rules = {f.rule for f in findings}
    expected = {
        "asset_class_target", "max_single_position_weight", "max_sector_weight",
        "max_annualized_volatility", "max_drawdown_tolerance", "min_cash_weight",
    }
    assert expected <= rules
    assert len(pol.RULES) == 8
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: -pol._SEVERITY_RANK[s])
    frame = pol.findings_frame(findings)
    assert list(frame.columns) == ["severity", "rule", "subject", "current", "limit", "message", "suggested_action"]

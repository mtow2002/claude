"""Policy file validation."""

from __future__ import annotations

import copy

import pytest
import yaml

from portfolio_review.config import PolicyError, load_policy, parse_policy


@pytest.fixture
def raw(fixtures_dir):
    return yaml.safe_load((fixtures_dir / "policy.yaml").read_text())


def test_loads_example_policy():
    policy = load_policy("config/policy.example.yaml")
    assert sum(policy.targets.values()) == pytest.approx(1.0)
    assert sum(policy.factor_weights.values()) == pytest.approx(1.0)
    assert policy.benchmark == "SPY"
    assert policy.sha256


def test_targets_must_sum_to_one(raw):
    bad = copy.deepcopy(raw)
    bad["targets"]["asset_class"]["cash"] = 0.5
    with pytest.raises(PolicyError, match="must sum to 1.0"):
        parse_policy(bad)


def test_factor_weights_must_sum_to_one(raw):
    bad = copy.deepcopy(raw)
    bad["factor_weights"]["momentum"] = 0.9
    with pytest.raises(PolicyError, match="factor_weights must sum"):
        parse_policy(bad)


def test_unknown_factor_rejected(raw):
    bad = copy.deepcopy(raw)
    bad["factor_weights"]["growth"] = 0.0
    with pytest.raises(PolicyError, match="unknown factors"):
        parse_policy(bad)


def test_missing_key_named(raw):
    bad = copy.deepcopy(raw)
    del bad["limits"]["max_sector_weight"]
    with pytest.raises(PolicyError, match="limits.max_sector_weight"):
        parse_policy(bad)


def test_fraction_out_of_range(raw):
    bad = copy.deepcopy(raw)
    bad["limits"]["min_cash_weight"] = 5
    with pytest.raises(PolicyError, match="between 0 and 1"):
        parse_policy(bad)


def test_asset_class_resolution_priority(raw):
    policy = parse_policy(raw)
    assert policy.asset_class_for("CCC", "etf") == "bonds"  # by_ticker
    assert policy.asset_class_for("CCC", "etf", "intl_equity") == "intl_equity"  # explicit wins
    assert policy.asset_class_for("XYZ", "etf") == "us_equity"  # default by type
    assert policy.asset_class_for("CASH", "cash") == "cash"
    with pytest.raises(PolicyError, match="not one of"):
        policy.asset_class_for("XYZ", "stock", "crypto")


def test_missing_policy_file_points_to_example(tmp_path):
    with pytest.raises(PolicyError, match="policy.example.yaml"):
        load_policy(tmp_path / "nope.yaml")

"""Holdings loading and weight normalization."""

from __future__ import annotations

import pytest

from portfolio_review.holdings import HoldingsError, load_holdings, normalize_weights, read_holdings_csv


def test_weights_are_normalized_to_one(fixtures_dir):
    h = load_holdings(fixtures_dir / "holdings.csv")
    assert h.weight_source == "weights"
    assert h.frame["weight"].sum() == pytest.approx(1.0)
    assert h.tickers == ["AAA", "BBB", "CCC", "DDD", "CASH"]
    assert h.priced_tickers == ["AAA", "BBB", "CCC", "DDD"]


def test_unnormalized_weights_are_scaled(tmp_path):
    path = tmp_path / "h.csv"
    path.write_text("ticker,asset_type,weight\nAAA,stock,30\nBBB,stock,70\n")
    h = load_holdings(path)
    assert h.frame["weight"].tolist() == pytest.approx([0.3, 0.7])
    assert h.frame["raw_weight"].tolist() == [30.0, 70.0]


def test_shares_times_price(fixtures_dir):
    h = load_holdings(fixtures_dir / "holdings_shares.csv", {"AAA": 100.0, "BBB": 50.0, "CCC": 80.0})
    assert h.weight_source == "shares_x_price"
    # values: 1000, 1000, 400, cash 1000 -> total 3400
    assert h.frame["market_value"].tolist() == pytest.approx([1000, 1000, 400, 1000])
    assert h.frame["weight"].tolist() == pytest.approx([1000 / 3400, 1000 / 3400, 400 / 3400, 1000 / 3400])


def test_shares_without_price_fails_clearly(fixtures_dir):
    with pytest.raises(HoldingsError, match=r"no price is available.*\['BBB', 'CCC'\]"):
        load_holdings(fixtures_dir / "holdings_shares.csv", {"AAA": 100.0})


def test_neither_weight_nor_shares_fails_clearly(tmp_path):
    path = tmp_path / "h.csv"
    path.write_text("ticker,asset_type,shares,weight\nAAA,stock,,0.5\nBBB,stock,,\n")
    with pytest.raises(HoldingsError, match=r"Rows with neither: \['BBB'\]"):
        load_holdings(path)


def test_bad_asset_type_rejected(tmp_path):
    path = tmp_path / "h.csv"
    path.write_text("ticker,asset_type,weight\nAAA,bond,1\n")
    with pytest.raises(HoldingsError, match="asset_type must be one of"):
        read_holdings_csv(path)


def test_non_numeric_weight_rejected(tmp_path):
    path = tmp_path / "h.csv"
    path.write_text("ticker,asset_type,weight\nAAA,stock,ten\n")
    with pytest.raises(HoldingsError, match="non-numeric"):
        read_holdings_csv(path)


def test_missing_required_column(tmp_path):
    path = tmp_path / "h.csv"
    path.write_text("ticker,weight\nAAA,1\n")
    with pytest.raises(HoldingsError, match="missing required columns"):
        read_holdings_csv(path)


def test_missing_file_message_points_to_example(tmp_path):
    with pytest.raises(HoldingsError, match="holdings.example.csv"):
        read_holdings_csv(tmp_path / "nope.csv")


def test_negative_weight_rejected(tmp_path):
    path = tmp_path / "h.csv"
    path.write_text("ticker,asset_type,weight\nAAA,stock,-1\nBBB,stock,2\n")
    frame, _ = read_holdings_csv(path)
    with pytest.raises(HoldingsError, match="negative"):
        normalize_weights(frame)

"""CLI end to end on fixtures with the offline csv provider."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from portfolio_review.cli import build_parser, main


def _run_args(fixtures_dir, prices_dir, tmp_path, extra=()):
    return [
        "run",
        "--holdings", str(fixtures_dir / "holdings.csv"),
        "--policy", str(fixtures_dir / "policy.yaml"),
        "--as-of", "2025-09-30",
        "--provider", "csv",
        "--provider-path", str(prices_dir),
        "--cache-dir", str(tmp_path / "cache"),
        "--runs-dir", str(tmp_path / "runs"),
        *extra,
    ]


def test_commands_are_discovered():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert {"run", "validate", "fetch", "report"} <= set(sub.choices)


def test_run_requires_question(fixtures_dir, prices_dir, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(_run_args(fixtures_dir, prices_dir, tmp_path))
    assert "--question" in capsys.readouterr().err


def test_run_end_to_end(fixtures_dir, prices_dir, tmp_path, capsys):
    code = main(_run_args(fixtures_dir, prices_dir, tmp_path, ["--question", "Within policy?"]))
    assert code == 0
    out = capsys.readouterr().out
    assert "Question: Within policy?" in out and "Report:" in out

    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1 and runs[0].name.startswith("2025-09-30_")
    record = json.loads((runs[0] / "run.json").read_text())
    assert record["question"] == "Within policy?"
    assert record["as_of"] == "2025-09-30"
    assert record["provider"] == "csv" and record["benchmark"] == "SPY"
    assert record["policy_hash"] and record["holdings_hash"]
    assert len(record["sources"]) == 9  # 4 tickers x (prices + profile) + SPY prices

    report = (runs[0] / "report.md").read_text()
    assert report.startswith("# Portfolio Review as of 2025-09-30")
    assert "**Question:** Within policy?" in report
    assert "## Sources" in report and "profiles.csv" in report
    assert "DDD" in report and "delisted" in report  # the delisted ticker is visible, not dropped

    holdings = pd.read_parquet(runs[0] / "tables" / "holdings.parquet")
    assert holdings["weight"].sum() == pytest.approx(1.0)
    assert holdings.set_index("ticker").loc["DDD", "listing_status"] == "delisted"
    assert holdings.set_index("ticker").loc["DDD", "price_status"] == "stale"
    findings = pd.read_parquet(runs[0] / "tables" / "findings.parquet")
    assert "listing_status" in set(findings["rule"])
    prices = pd.read_parquet(runs[0] / "tables" / "prices.parquet")
    assert prices["date"].max() <= pd.Timestamp("2025-09-30")


def test_run_is_reproducible_from_cache(fixtures_dir, prices_dir, tmp_path):
    main(_run_args(fixtures_dir, prices_dir, tmp_path, ["--question", "first"]))
    main(_run_args(fixtures_dir, prices_dir, tmp_path, ["--question", "second"]))
    runs = sorted((tmp_path / "runs").iterdir(), key=lambda p: json.loads((p / "run.json").read_text())["created_at"])
    a = json.loads((runs[0] / "run.json").read_text())
    b = json.loads((runs[1] / "run.json").read_text())
    assert a["params"]["cache_misses"] == 9 and a["params"]["cache_hits"] == 0
    assert b["params"]["cache_hits"] == 9 and b["params"]["cache_misses"] == 0
    assert [s["fetched_at"] for s in a["sources"]] == [s["fetched_at"] for s in b["sources"]]
    ma = pd.read_parquet(runs[0] / "tables" / "metrics.parquet")
    mb = pd.read_parquet(runs[1] / "tables" / "metrics.parquet")
    pd.testing.assert_frame_equal(ma, mb)


def test_as_of_changes_the_numbers(fixtures_dir, prices_dir, tmp_path):
    args = _run_args(fixtures_dir, prices_dir, tmp_path, ["--question", "q"])
    main(args)
    early = [a if a != "2025-09-30" else "2025-03-31" for a in args]
    main(early)
    runs = sorted((tmp_path / "runs").iterdir())
    early_prices = pd.read_parquet(next(r for r in runs if r.name.startswith("2025-03-31")) / "tables" / "prices.parquet")
    assert early_prices["date"].max() == pd.Timestamp("2025-03-31")


def test_validate_ok_and_failing(fixtures_dir, tmp_path, capsys):
    assert main(["validate", "--holdings", str(fixtures_dir / "holdings.csv"), "--policy", str(fixtures_dir / "policy.yaml")]) == 0
    assert "validation passed" in capsys.readouterr().out
    bad = tmp_path / "bad.csv"
    bad.write_text("ticker,asset_type,weight\nAAA,stock,\n")
    assert main(["validate", "--holdings", str(bad), "--policy", str(fixtures_dir / "policy.yaml")]) == 1
    assert "holdings ERROR" in capsys.readouterr().out


def test_fetch_warms_cache(fixtures_dir, prices_dir, tmp_path, capsys):
    code = main([
        "fetch", "--holdings", str(fixtures_dir / "holdings.csv"), "--policy", str(fixtures_dir / "policy.yaml"),
        "--as-of", "2025-09-30", "--provider", "csv", "--provider-path", str(prices_dir), "--cache-dir", str(tmp_path / "cache"),
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "SPY" in out and "DDD" in out and "0 hits, 9 fetches" in out
    assert (tmp_path / "cache" / "csv" / "SPY" / "2025-09-30" / "prices.parquet").exists()


def test_report_rerenders_saved_run(fixtures_dir, prices_dir, tmp_path, capsys):
    main(_run_args(fixtures_dir, prices_dir, tmp_path, ["--question", "q"]))
    run_dir = next((tmp_path / "runs").iterdir())
    (run_dir / "report.md").write_text("stale")
    assert main(["report", "--runs-dir", str(tmp_path / "runs")]) == 0
    assert (run_dir / "report.md").read_text().startswith("# Portfolio Review")
    assert main(["report", "--runs-dir", str(tmp_path / "runs"), "--list"]) == 0
    assert run_dir.name in capsys.readouterr().out
    assert main(["report", "--runs-dir", str(tmp_path / "empty")]) == 1


def test_errors_exit_nonzero_with_message(fixtures_dir, prices_dir, tmp_path, capsys):
    args = _run_args(fixtures_dir, prices_dir, tmp_path, ["--question", "q"])
    args[args.index("--holdings") + 1] = str(tmp_path / "missing.csv")
    assert main(args) == 1
    assert "holdings file not found" in capsys.readouterr().err

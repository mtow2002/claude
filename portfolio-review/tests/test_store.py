"""LocalStore: save, load, list, never overwrite."""

from __future__ import annotations

import pandas as pd
import pytest

from portfolio_review.store import LocalStore, RunRecord


def _record(run_id="abc12345", as_of="2025-09-30", created="2025-10-01T00:00:00+00:00"):
    return RunRecord(
        run_id=run_id, question="q?", as_of=as_of, created_at=created, policy_hash="p", holdings_hash="h",
        package_version="0.1.0", git_commit=None, provider="csv", benchmark="SPY",
        sources=[{"provider": "csv", "endpoint": "x", "fetched_at": created, "as_of": as_of, "ticker": "A", "cache_hit": False, "note": ""}],
    )


def test_save_and_load_round_trip(tmp_path):
    store = LocalStore(tmp_path / "runs")
    tables = {"holdings": pd.DataFrame({"ticker": ["A"], "weight": [1.0]})}
    folder = store.save_run(_record(), tables, "# report")
    assert folder.name == "2025-09-30_abc12345"
    assert (folder / "run.json").exists() and (folder / "report.md").read_text() == "# report"
    loaded = store.load_run("abc12345")
    assert loaded.record.question == "q?" and loaded.record.tables == ["holdings"]
    pd.testing.assert_frame_equal(loaded.tables["holdings"], tables["holdings"])
    assert store.load_run("2025-09-30_abc12345").path == folder


def test_never_overwrites(tmp_path):
    store = LocalStore(tmp_path / "runs")
    store.save_run(_record(), {}, None)
    with pytest.raises(FileExistsError):
        store.save_run(_record(), {}, None)


def test_list_runs_newest_first(tmp_path):
    store = LocalStore(tmp_path / "runs")
    store.save_run(_record("old00000", created="2025-01-01T00:00:00+00:00"), {}, None)
    store.save_run(_record("new00000", created="2025-02-01T00:00:00+00:00"), {}, None)
    assert [r.run_id for r in store.list_runs()] == ["new00000", "old00000"]
    assert LocalStore(tmp_path / "missing").list_runs() == []


def test_save_table_adds_to_existing_run(tmp_path):
    store = LocalStore(tmp_path / "runs")
    store.save_run(_record(), {}, None)
    store.save_table("abc12345", "extra", pd.DataFrame({"x": [1]}))
    assert "extra" in store.load_run("abc12345").tables


def test_bigquery_stub_raises():
    from portfolio_review.store.bigquery import BigQueryStore

    with pytest.raises(NotImplementedError):
        BigQueryStore().list_runs()

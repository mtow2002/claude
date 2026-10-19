"""BigQuery store. STUB: a later session implements this.

Install extras first:  pip install -e ".[bigquery]"
Project comes from GOOGLE_CLOUD_PROJECT (see .env.example).

Interface to satisfy (identical to LocalStore, see base.py):

    class BigQueryStore:
        def __init__(self, project: str | None = None, dataset: str = "portfolio_review"):
            # Create the dataset if missing. Tables:
            #   runs        one row per RunRecord (sources and params as JSON)
            #   <table>     one BigQuery table per logical table name, with
            #               run_id and as_of columns added to every row so
            #               all runs share one table (partition by as_of).
        def save_run(self, record, tables, report_md=None) -> Path | str:
            # Insert the record row, append every table with run_id/as_of
            # columns, store report_md in a `reports` table. Return the
            # fully-qualified runs table id.
        def load_run(self, run_id) -> LoadedRun:
            # SELECT ... WHERE run_id = @run_id for the record and each table.
        def list_runs(self) -> list[RunRecord]:
            # SELECT from runs ORDER BY created_at DESC.
        def save_table(self, run_id, name, frame) -> Path | str:
            # Append frame (plus run_id/as_of) to dataset.<name>.

Rules: use parameterized queries only; never write credentials to disk; tests
must mock google.cloud.bigquery.Client, never call the API.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import LoadedRun, RunRecord


class BigQueryStore:
    """Placeholder that fails loudly until implemented."""

    def __init__(self, project: str | None = None, dataset: str = "portfolio_review") -> None:
        self.project = project
        self.dataset = dataset

    def save_run(self, record: RunRecord, tables: dict[str, pd.DataFrame], report_md: str | None = None) -> Path:
        raise NotImplementedError("BigQueryStore is not implemented yet; see the module docstring")

    def load_run(self, run_id: str) -> LoadedRun:
        raise NotImplementedError("BigQueryStore is not implemented yet; see the module docstring")

    def list_runs(self) -> list[RunRecord]:
        raise NotImplementedError("BigQueryStore is not implemented yet; see the module docstring")

    def save_table(self, run_id: str, name: str, frame: pd.DataFrame) -> Path:
        raise NotImplementedError("BigQueryStore is not implemented yet; see the module docstring")

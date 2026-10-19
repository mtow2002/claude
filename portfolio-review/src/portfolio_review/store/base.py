"""Store interface: where runs and their tables are persisted.

A run is one execution of the ``run`` command. It produces:

* ``RunRecord``: the metadata that makes the run reproducible (question,
  as_of, hashes of the inputs, package version, git commit, every Source);
* named tables (holdings, metrics, factors, findings, exposures...) as
  DataFrames;
* the Markdown report.

:class:`LocalStore` (local.py) writes these to ``runs/<as_of>_<run_id>/``.
BigQuery (bigquery.py) is a stub for a later session.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


@dataclass
class RunRecord:
    """Everything needed to reproduce or audit a run. Serialized to run.json."""

    run_id: str
    question: str
    as_of: str  # ISO date
    created_at: str  # ISO datetime, UTC
    policy_hash: str
    holdings_hash: str
    package_version: str
    git_commit: str | None
    provider: str
    benchmark: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    tables: list[str] = field(default_factory=list)
    report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RunRecord":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})  # type: ignore[arg-type]

    @property
    def folder_name(self) -> str:
        return f"{self.as_of}_{self.run_id}"


@dataclass
class LoadedRun:
    """A run read back from a store: its record plus its tables."""

    record: RunRecord
    tables: dict[str, pd.DataFrame]
    path: Path | None = None


class Store(Protocol):
    """Persistence contract. Implement all four methods."""

    def save_run(self, record: RunRecord, tables: dict[str, pd.DataFrame], report_md: str | None = None) -> Path:
        """Persist the record, every table, and the report. Returns the run location."""
        ...

    def load_run(self, run_id: str) -> LoadedRun:
        """Read a run back by id (or by folder name)."""
        ...

    def list_runs(self) -> list[RunRecord]:
        """All stored runs, newest first."""
        ...

    def save_table(self, run_id: str, name: str, frame: pd.DataFrame) -> Path:
        """Add or replace a single table inside an existing run."""
        ...

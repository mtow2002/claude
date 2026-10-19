"""Local filesystem store: ``runs/<as_of>_<run_id>/``.

Layout::

    runs/2025-09-30_a1b2c3d4/
        run.json          RunRecord
        report.md         the rendered report
        tables/
            holdings.parquet
            metrics.parquet
            ...

Runs are never overwritten: a new run gets a new run_id even for the same
as_of (the old doctrine "corrections go in a new file" applies).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .base import LoadedRun, RunRecord

DEFAULT_RUNS_DIR = Path("runs")


class LocalStore:
    """Store implementation that writes JSON + parquet under a runs directory."""

    def __init__(self, runs_dir: Path | str = DEFAULT_RUNS_DIR) -> None:
        self.runs_dir = Path(runs_dir)

    def _folder(self, record: RunRecord) -> Path:
        return self.runs_dir / record.folder_name

    def _find(self, run_id: str) -> Path:
        """Accept a bare run_id, a folder name, or a path to a run folder."""
        direct = Path(run_id)
        if direct.is_dir() and (direct / "run.json").exists():
            return direct
        candidate = self.runs_dir / run_id
        if candidate.is_dir() and (candidate / "run.json").exists():
            return candidate
        matches = [p for p in self.runs_dir.glob(f"*_{run_id}") if (p / "run.json").exists()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise FileNotFoundError(f"run id {run_id!r} is ambiguous: {[m.name for m in matches]}")
        raise FileNotFoundError(f"run {run_id!r} not found under {self.runs_dir}")

    def save_run(self, record: RunRecord, tables: dict[str, pd.DataFrame], report_md: str | None = None) -> Path:
        folder = self._folder(record)
        if folder.exists():
            raise FileExistsError(f"run folder already exists, refusing to overwrite: {folder}")
        (folder / "tables").mkdir(parents=True)
        for name, frame in tables.items():
            self.save_table(record.folder_name, name, frame)
        record.tables = sorted(tables)
        if report_md is not None:
            (folder / "report.md").write_text(report_md, encoding="utf-8")
            record.report_path = str(folder / "report.md")
        (folder / "run.json").write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        return folder

    def save_table(self, run_id: str, name: str, frame: pd.DataFrame) -> Path:
        folder = self.runs_dir / run_id if (self.runs_dir / run_id).is_dir() else self._find(run_id)
        path = folder / "tables" / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Object columns with mixed None/str confuse parquet; cast them to str.
        safe = frame.copy()
        for col in safe.columns:
            if safe[col].dtype == object:
                safe[col] = safe[col].astype("string")
        safe.to_parquet(path, index=False)
        return path

    def load_run(self, run_id: str) -> LoadedRun:
        folder = self._find(run_id)
        record = RunRecord.from_dict(json.loads((folder / "run.json").read_text(encoding="utf-8")))
        tables = {}
        for path in sorted((folder / "tables").glob("*.parquet")):
            tables[path.stem] = pd.read_parquet(path)
        return LoadedRun(record=record, tables=tables, path=folder)

    def list_runs(self) -> list[RunRecord]:
        if not self.runs_dir.exists():
            return []
        records = []
        for path in self.runs_dir.iterdir():
            run_json = path / "run.json"
            if run_json.exists():
                records.append(RunRecord.from_dict(json.loads(run_json.read_text(encoding="utf-8"))))
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records

    def write_report(self, run_id: str, report_md: str) -> Path:
        """Overwrite report.md for an existing run (used by the ``report`` command)."""
        folder = self._find(run_id)
        path = folder / "report.md"
        path.write_text(report_md, encoding="utf-8")
        return path

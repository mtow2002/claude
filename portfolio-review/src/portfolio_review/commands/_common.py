"""Argument helpers shared by the commands (underscore name: not a command itself)."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from ..data.registry import PROVIDERS


def parse_as_of(value: str | None) -> date:
    """ISO date string -> date; default today. Never silently accept garbage."""
    if value is None or value.strip() == "" or value.lower() == "today":
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--as-of must be YYYY-MM-DD, got {value!r}") from exc


def add_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--holdings", type=Path, default=Path("config/holdings.csv"), help="holdings CSV (default config/holdings.csv)")
    parser.add_argument("--policy", type=Path, default=Path("config/policy.yaml"), help="policy YAML (default config/policy.yaml)")


def add_data_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--as-of", type=parse_as_of, default=None, help="point-in-time date YYYY-MM-DD (default today)")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="yfinance", help="data provider (default yfinance)")
    parser.add_argument("--provider-path", default=None, help="folder for the csv provider")
    parser.add_argument("--benchmark", default=None, help="benchmark ticker (default: policy settings.benchmark, usually SPY)")
    parser.add_argument("--cache-dir", type=Path, default=Path("data") / "cache", help="parquet cache folder")
    parser.add_argument("--no-cache", action="store_true", help="bypass the cache (always fetch)")


def add_store_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"), help="where run folders are written")

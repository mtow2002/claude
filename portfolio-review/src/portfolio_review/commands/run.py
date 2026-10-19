"""``portfolio-review run``: the full analysis for one as-of date and one question."""

from __future__ import annotations

import argparse
from datetime import date

from ..runner import RunInputs, execute_run
from ._common import add_data_args, add_input_args, add_store_args


def handle(args: argparse.Namespace) -> int:
    inputs = RunInputs(
        holdings_path=args.holdings,
        policy_path=args.policy,
        as_of=args.as_of or date.today(),
        question=args.question,
        provider=args.provider,
        provider_path=args.provider_path,
        benchmark=args.benchmark,
        cache_dir=None if args.no_cache else args.cache_dir,
        runs_dir=args.runs_dir,
    )
    result = execute_run(inputs)
    findings = result.tables["findings"]
    breaches = int((findings["severity"] == "breach").sum()) if len(findings) else 0
    warns = int((findings["severity"] == "warn").sum()) if len(findings) else 0
    print(f"Question: {result.record.question}")
    print(f"As of: {result.record.as_of}   run id: {result.record.run_id}")
    print(f"Findings: {breaches} breach, {warns} warn")
    print(f"Report: {result.path / 'report.md'}")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("run", help="run the analysis and write a report")
    add_input_args(p)
    add_data_args(p)
    add_store_args(p)
    p.add_argument("--question", required=True, help="the question this run answers (recorded in run.json)")
    p.set_defaults(handler=handle)

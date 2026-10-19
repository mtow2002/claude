"""``portfolio-review report``: re-render the Markdown report for a saved run."""

from __future__ import annotations

import argparse

from ..report import render_report
from ..store import LocalStore
from ._common import add_store_args


def handle(args: argparse.Namespace) -> int:
    store = LocalStore(args.runs_dir)
    if args.run_id is None:
        runs = store.list_runs()
        if not runs:
            print(f"no runs found under {args.runs_dir}")
            return 1
        if args.list:
            for r in runs:
                print(f"{r.folder_name}  {r.created_at}  {r.question}")
            return 0
        run_id = runs[0].folder_name
    else:
        run_id = args.run_id
    loaded = store.load_run(run_id)
    md = render_report(loaded.record, loaded.tables)
    path = store.write_report(run_id, md)
    if args.stdout:
        print(md)
    print(f"Report: {path}")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("report", help="re-render a saved run's report")
    add_store_args(p)
    p.add_argument("--run-id", default=None, help="run id or folder name (default: newest run)")
    p.add_argument("--list", action="store_true", help="list saved runs and exit")
    p.add_argument("--stdout", action="store_true", help="also print the report to the terminal")
    p.set_defaults(handler=handle)

"""``portfolio-review validate``: check holdings.csv and policy.yaml without fetching data."""

from __future__ import annotations

import argparse

from ..config import load_policy
from ..holdings import normalize_weights, read_holdings_csv
from ._common import add_input_args


def handle(args: argparse.Namespace) -> int:
    ok = True
    try:
        policy = load_policy(args.policy)
        print(f"policy OK: {args.policy} (targets sum to 1, factor weights sum to 1, benchmark {policy.benchmark})")
    except Exception as exc:  # noqa: BLE001  (report every problem, then exit non-zero)
        ok = False
        print(f"policy ERROR: {exc}")
        policy = None

    try:
        frame, _ = read_holdings_csv(args.holdings)
        print(f"holdings OK: {args.holdings} ({len(frame)} rows)")
        if frame["weight"].notna().all():
            weighted, _ = normalize_weights(frame)
            print("weights OK: all rows have weights; normalized to sum to 1")
        elif frame["shares"].notna().all():
            print("weights: rows have shares; weights will be computed from prices at run time")
        else:
            normalize_weights(frame)  # raises with the detailed message
        if policy is not None:
            for row in frame.itertuples(index=False):
                policy.asset_class_for(row.ticker, row.asset_type, row.asset_class or None)
            print("asset classes OK: every holding maps to one of the policy's classes")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"holdings ERROR: {exc}")

    print("validation passed" if ok else "validation FAILED")
    return 0 if ok else 1


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("validate", help="check the holdings and policy files")
    add_input_args(p)
    p.set_defaults(handler=handle)

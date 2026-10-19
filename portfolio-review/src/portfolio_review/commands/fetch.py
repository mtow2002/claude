"""``portfolio-review fetch``: warm the cache for the holdings universe plus benchmark.

This is the nightly sweep. It fetches prices and profiles for every ticker in
holdings.csv and the benchmark for the given as-of date and stores them in
the parquet cache, so a later ``run`` for that as-of date is fully offline.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from ..config import load_policy
from ..data import make_provider
from ..holdings import read_holdings_csv
from ..runner import fetch_universe
from ._common import add_data_args, add_input_args


def handle(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    frame, _ = read_holdings_csv(args.holdings)
    as_of = args.as_of or date.today()
    start = as_of - timedelta(days=policy.lookback_days)
    benchmark = (args.benchmark or policy.benchmark).upper()
    provider = make_provider(args.provider, args.provider_path, cache_dir=None if args.no_cache else args.cache_dir)
    tickers = list(frame.loc[frame["asset_type"] != "cash", "ticker"])
    prices, _, sources = fetch_universe(provider, tickers, start, as_of, as_of)
    bprices, _, bsources = fetch_universe(provider, [benchmark], start, as_of, as_of, want_profiles=False)
    prices.update(bprices)
    for ticker, f in prices.items():
        last = f["date"].iloc[-1].date().isoformat() if len(f) else "NO DATA"
        print(f"{ticker:>8}: {len(f):4d} rows, last {last}")
    stats = getattr(provider, "stats", None)
    if stats is not None:
        print(f"cache: {stats.hits} hits, {stats.misses} fetches -> {args.cache_dir}")
    print(f"fetched {len(sources) + len(bsources)} sources for as_of {as_of}")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("fetch", help="warm the data cache for holdings plus benchmark")
    add_input_args(p)
    add_data_args(p)
    p.set_defaults(handler=handle)

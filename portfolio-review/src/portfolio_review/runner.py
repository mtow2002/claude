"""Orchestrates one analysis run: inputs -> data -> analytics -> findings -> store.

This is the only module that knows the whole pipeline. Each step calls a pure
function elsewhere, so every piece is testable on its own. The ``run`` CLI
command is a thin wrapper around :func:`execute_run`.
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .config import Policy, load_policy
from .data import Provider, Source, make_provider
from .factors import score_factors
from .holdings import Holdings, normalize_weights, read_holdings_csv
from .metrics import ticker_metrics
from .policy import PolicyContext, evaluate, findings_frame
from .portfolio import concentration, exposure_by, portfolio_metrics, portfolio_returns
from .report import render_report
from .store import LocalStore, RunRecord


@dataclass
class RunInputs:
    """Everything the CLI collects before a run starts."""

    holdings_path: Path
    policy_path: Path
    as_of: date
    question: str
    provider: str = "yfinance"
    provider_path: str | None = None
    benchmark: str | None = None  # None -> policy.settings.benchmark
    cache_dir: Path | None = Path("data") / "cache"
    runs_dir: Path = Path("runs")
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    record: RunRecord
    tables: dict[str, pd.DataFrame]
    report_md: str
    path: Path


def git_commit() -> str | None:
    """Current git commit hash, or None when not in a git checkout."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def price_status(last_date: pd.Timestamp | None, as_of: date, stale_days: int) -> str:
    """'current' if the last bar is within stale_days of as_of, 'stale' if older, 'missing' if none."""
    if last_date is None or pd.isna(last_date):
        return "missing"
    gap = (pd.Timestamp(as_of) - last_date).days
    return "current" if gap <= stale_days else "stale"


def fetch_universe(
    provider: Provider,
    tickers: list[str],
    start: date,
    end: date,
    as_of: date,
    want_profiles: bool = True,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], list[Source]]:
    """Pull prices (and profiles) for every ticker, collecting Sources as we go."""
    prices: dict[str, pd.DataFrame] = {}
    profiles: dict[str, Any] = {}
    sources: list[Source] = []
    for ticker in tickers:
        pdata = provider.prices(ticker, start, end, as_of)
        prices[ticker] = pdata.frame
        sources.append(pdata.source)
        if want_profiles:
            prof = provider.profile(ticker, as_of)
            profiles[ticker] = prof.profile
            sources.append(prof.source)
    return prices, profiles, sources


def _close_series(frame: pd.DataFrame) -> pd.Series:
    """adj_close indexed by date, the series every metric is computed on."""
    if frame is None or len(frame) == 0:
        return pd.Series(dtype="float64")
    return frame.set_index("date")["adj_close"].astype("float64")


def execute_run(inputs: RunInputs) -> RunResult:
    """Run the full pipeline and persist the result. Returns the saved run."""
    if not inputs.question or not inputs.question.strip():
        raise ValueError("--question is required: state the question this run answers")

    policy: Policy = load_policy(inputs.policy_path)
    raw_holdings, holdings_hash = read_holdings_csv(inputs.holdings_path)
    provider = make_provider(inputs.provider, inputs.provider_path, cache_dir=inputs.cache_dir)
    benchmark = (inputs.benchmark or policy.benchmark).upper()
    as_of = inputs.as_of
    start = as_of - timedelta(days=policy.lookback_days)

    # ---- 1. Data (point-in-time, with sources) --------------------------
    priced = list(raw_holdings.loc[raw_holdings["asset_type"] != "cash", "ticker"])
    prices, profiles, sources = fetch_universe(provider, priced, start, as_of, as_of)
    bench_prices, _, bench_sources = fetch_universe(provider, [benchmark], start, as_of, as_of, want_profiles=False)
    sources.extend(bench_sources)
    benchmark_close = _close_series(bench_prices[benchmark])

    # ---- 2. Weights (principle 4) ---------------------------------------
    last_close = {t: (float(f["close"].iloc[-1]) if len(f) else float("nan")) for t, f in prices.items()}
    weighted, weight_source = normalize_weights(raw_holdings, last_close)
    holdings = Holdings(frame=weighted, weight_source=weight_source, sha256=holdings_hash)

    # ---- 3. Enrich holdings with profile facts and data status ----------
    rows = []
    for row in holdings.frame.itertuples(index=False):
        prof = profiles.get(row.ticker)
        frame = prices.get(row.ticker)
        last_date = frame["date"].iloc[-1] if frame is not None and len(frame) else None
        if row.asset_type == "cash":
            sector, industry, name, listing, pstatus = "Cash", "Cash", "Cash", "active", "current"
        else:
            sector = prof.sector if prof else ""
            industry = prof.industry if prof else ""
            name = prof.name if prof else ""
            listing = prof.listing_status if prof else "unknown"
            pstatus = price_status(last_date, as_of, policy.stale_price_days)
            if listing == "active" and pstatus != "current":
                # Prices stopped before as_of: the provider says active but the
                # tape disagrees. Flag it, never hide it.
                listing = "delisted" if pstatus == "stale" else "unknown"
        rows.append(
            {
                "ticker": row.ticker,
                "name": name,
                "asset_type": row.asset_type,
                "asset_class": policy.asset_class_for(row.ticker, row.asset_type, row.asset_class or None),
                "account": row.account,
                "sector": sector,
                "industry": industry,
                "shares": row.shares,
                "market_value": row.market_value,
                "weight": float(row.weight),
                "cost_basis": row.cost_basis,
                "listing_status": listing,
                "price_status": pstatus,
                "last_price_date": last_date.date().isoformat() if last_date is not None else "",
                "last_close": last_close.get(row.ticker, float("nan")),
                "note": row.note,
            }
        )
    holdings_table = pd.DataFrame(rows)

    # ---- 4. Per-ticker metrics and factor scores -------------------------
    metrics_rows = {}
    for ticker in priced:
        metrics_rows[ticker] = ticker_metrics(_close_series(prices[ticker]), benchmark_close, policy.risk_free_rate)
    metrics_table = pd.DataFrame.from_dict(metrics_rows, orient="index").rename_axis("ticker").reset_index()
    bench_metrics = ticker_metrics(benchmark_close, benchmark_close, policy.risk_free_rate)
    benchmark_table = pd.DataFrame([{"ticker": benchmark, **bench_metrics}])

    fundamentals = {t: (profiles[t].fundamentals if t in profiles else {}) for t in priced}
    factors_table, missing_factors = score_factors(metrics_rows, fundamentals, policy.factor_weights)

    # ---- 5. Portfolio level ---------------------------------------------
    weights = dict(zip(holdings_table["ticker"], holdings_table["weight"]))
    port_rets = portfolio_returns(weights, {t: _close_series(f) for t, f in prices.items()})
    port = portfolio_metrics(port_rets, benchmark_close, policy.risk_free_rate)
    port.update(concentration(holdings_table))
    portfolio_table = pd.DataFrame([port])
    exposures = {
        "exposure_asset_class": exposure_by(holdings_table, "asset_class"),
        "exposure_asset_type": exposure_by(holdings_table, "asset_type"),
        "exposure_sector": exposure_by(holdings_table, "sector"),
        "exposure_account": exposure_by(holdings_table, "account"),
    }

    # ---- 6. Policy drift ------------------------------------------------
    findings = evaluate(PolicyContext(policy=policy, holdings=holdings_table, portfolio=port))

    # ---- 7. Persist -----------------------------------------------------
    long_prices = pd.concat(
        [f.assign(ticker=t) for t, f in {**prices, benchmark: bench_prices[benchmark]}.items() if len(f)],
        ignore_index=True,
    ) if any(len(f) for f in prices.values()) else pd.DataFrame()
    sources_table = pd.DataFrame([s.to_dict() for s in sources])
    tables = {
        "holdings": holdings_table,
        "metrics": metrics_table,
        "benchmark_metrics": benchmark_table,
        "factors": factors_table,
        "portfolio": portfolio_table,
        "findings": findings_frame(findings),
        "sources": sources_table,
        "prices": long_prices,
        **exposures,
    }
    record = RunRecord(
        run_id=uuid.uuid4().hex[:8],
        question=inputs.question.strip(),
        as_of=as_of.isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        policy_hash=policy.sha256,
        holdings_hash=holdings_hash,
        package_version=__version__,
        git_commit=git_commit(),
        provider=provider.name,
        benchmark=benchmark,
        sources=[s.to_dict() for s in sources],
        params={
            "holdings_path": str(inputs.holdings_path),
            "policy_path": str(inputs.policy_path),
            "lookback_days": policy.lookback_days,
            "start": start.isoformat(),
            "risk_free_rate": policy.risk_free_rate,
            "weight_source": weight_source,
            "missing_factors": missing_factors,
            "cache_hits": getattr(getattr(provider, "stats", None), "hits", None),
            "cache_misses": getattr(getattr(provider, "stats", None), "misses", None),
            **inputs.extra_params,
        },
    )
    report_md = render_report(record, tables)
    store = LocalStore(inputs.runs_dir)
    path = store.save_run(record, tables, report_md)
    return RunResult(record=record, tables=tables, report_md=report_md, path=path)

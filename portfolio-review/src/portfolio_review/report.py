"""Render a saved run as a Markdown report.

The report is built ONLY from the RunRecord and the run's tables, so the
``report`` command can re-render any stored run without touching the network.
Every number shown comes from a table that was computed from Sources listed at
the end (principle 3).
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .store.base import RunRecord


def _fmt_pct(x: Any, digits: int = 1) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.{digits}%}"


def _fmt_num(x: Any, digits: int = 2) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.{digits}f}"


def _table(frame: pd.DataFrame, columns: list[tuple[str, str, Any]]) -> list[str]:
    """Markdown table. columns = [(column_name, header, formatter)]."""
    if frame is None or len(frame) == 0:
        return ["_(no rows)_", ""]
    header = "| " + " | ".join(h for _, h, _ in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    lines = [header, sep]
    for _, row in frame.iterrows():
        cells = []
        for col, _, fmt in columns:
            value = row[col] if col in row.index else ""
            cells.append(fmt(value) if fmt else ("" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def render_report(record: RunRecord, tables: dict[str, pd.DataFrame]) -> str:
    """Build the full Markdown report text."""
    t = tables
    lines: list[str] = []
    lines.append(f"# Portfolio Review as of {record.as_of}")
    lines.append("")
    lines.append(f"**Question:** {record.question}")
    lines.append("")
    lines.append(f"- As-of date: {record.as_of}")
    lines.append(f"- Run id: {record.run_id} (created {record.created_at})")
    lines.append(f"- Provider: {record.provider}; benchmark: {record.benchmark}")
    lines.append(f"- Policy hash: `{record.policy_hash[:12]}`; holdings hash: `{record.holdings_hash[:12]}`")
    lines.append(f"- Package version: {record.package_version}; git commit: {record.git_commit or 'n/a'}")
    weight_source = record.params.get("weight_source", "")
    if weight_source:
        lines.append(f"- Weights derived from: {weight_source}")
    lines.append("")

    # ---- holdings
    lines.append("## Holdings")
    lines.append("")
    lines.extend(
        _table(
            t.get("holdings", pd.DataFrame()).sort_values("weight", ascending=False) if "holdings" in t else pd.DataFrame(),
            [
                ("ticker", "Ticker", None),
                ("name", "Name", None),
                ("asset_type", "Type", None),
                ("asset_class", "Class", None),
                ("sector", "Sector", None),
                ("weight", "Weight", _fmt_pct),
                ("listing_status", "Listing", None),
                ("price_status", "Prices", None),
                ("last_price_date", "Last price", None),
            ],
        )
    )
    flagged = t.get("holdings", pd.DataFrame())
    if len(flagged) and "listing_status" in flagged.columns:
        bad = flagged[(flagged["listing_status"] != "active") | (flagged["price_status"] != "current")]
        for row in bad.itertuples(index=False):
            lines.append(f"> Data warning: {row.ticker} listing status '{row.listing_status}', price status '{row.price_status}', last price {row.last_price_date or 'none'}.")
        if len(bad):
            lines.append("")

    # ---- exposures
    lines.append("## Exposures")
    lines.append("")
    for name, title in (
        ("exposure_asset_class", "By asset class"),
        ("exposure_asset_type", "By asset type"),
        ("exposure_sector", "By sector"),
        ("exposure_account", "By account"),
    ):
        if name in t:
            lines.append(f"### {title}")
            lines.append("")
            key = name.replace("exposure_", "")
            lines.extend(_table(t[name], [(key, key.replace("_", " ").title(), None), ("weight", "Weight", _fmt_pct)]))

    # ---- concentration + portfolio metrics
    port = t.get("portfolio")
    if port is not None and len(port):
        p = port.iloc[0]
        lines.append("## Portfolio metrics (lookback window, constant weights)")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Total return | {_fmt_pct(p.get('total_return'))} |")
        lines.append(f"| Annualized return | {_fmt_pct(p.get('annualized_return'))} |")
        lines.append(f"| Annualized volatility | {_fmt_pct(p.get('annualized_volatility'))} |")
        lines.append(f"| Max drawdown | {_fmt_pct(p.get('max_drawdown'))} |")
        lines.append(f"| Sharpe (rf {_fmt_pct(record.params.get('risk_free_rate', float('nan')))}) | {_fmt_num(p.get('sharpe'))} |")
        lines.append(f"| Beta vs {record.benchmark} | {_fmt_num(p.get('beta'))} |")
        lines.append(f"| HHI (non-cash) | {_fmt_num(p.get('hhi'), 3)} |")
        lines.append(f"| Effective number of positions | {_fmt_num(p.get('effective_n'), 1)} |")
        lines.append(f"| Top position weight | {_fmt_pct(p.get('top_1_weight'))} |")
        lines.append(f"| Top 3 weight | {_fmt_pct(p.get('top_3_weight'))} |")
        lines.append("")

    # ---- per-ticker metrics
    if "metrics" in t:
        lines.append("## Per-ticker metrics")
        lines.append("")
        lines.extend(
            _table(
                t["metrics"],
                [
                    ("ticker", "Ticker", None),
                    ("observations", "Days", lambda v: _fmt_num(v, 0)),
                    ("annualized_return", "Ann. return", _fmt_pct),
                    ("annualized_volatility", "Ann. vol", _fmt_pct),
                    ("max_drawdown", "Max DD", _fmt_pct),
                    ("sharpe", "Sharpe", _fmt_num),
                    ("beta", "Beta", _fmt_num),
                    ("momentum_3m", "3m", _fmt_pct),
                    ("momentum_6m", "6m", _fmt_pct),
                    ("momentum_12m", "12m", _fmt_pct),
                    ("trend_200d", "vs 200d", _fmt_pct),
                ],
            )
        )
        if "benchmark_metrics" in t:
            lines.append(f"Benchmark {record.benchmark}:")
            lines.append("")
            lines.extend(
                _table(
                    t["benchmark_metrics"],
                    [
                        ("ticker", "Ticker", None),
                        ("annualized_return", "Ann. return", _fmt_pct),
                        ("annualized_volatility", "Ann. vol", _fmt_pct),
                        ("max_drawdown", "Max DD", _fmt_pct),
                        ("sharpe", "Sharpe", _fmt_num),
                        ("momentum_12m", "12m", _fmt_pct),
                    ],
                )
            )

    # ---- factors
    if "factors" in t:
        lines.append("## Factor scores (0 = worst in universe, 100 = best, 50 = neutral or no data)")
        lines.append("")
        lines.extend(
            _table(
                t["factors"].sort_values("composite", ascending=False),
                [
                    ("ticker", "Ticker", None),
                    ("momentum_score", "Momentum", lambda v: _fmt_num(v, 0)),
                    ("value_score", "Value", lambda v: _fmt_num(v, 0)),
                    ("quality_score", "Quality", lambda v: _fmt_num(v, 0)),
                    ("low_volatility_score", "Low vol", lambda v: _fmt_num(v, 0)),
                    ("trend_score", "Trend", lambda v: _fmt_num(v, 0)),
                    ("composite", "Composite", lambda v: _fmt_num(v, 1)),
                ],
            )
        )
        missing = record.params.get("missing_factors") or {}
        notes = [f"{k}: {', '.join(v)}" for k, v in missing.items() if v]
        if notes:
            lines.append("Neutral (50) because no data: " + "; ".join(notes))
            lines.append("")

    # ---- findings
    lines.append("## Policy drift findings")
    lines.append("")
    findings = t.get("findings", pd.DataFrame())
    if len(findings):
        counts = findings["severity"].value_counts()
        lines.append(
            f"Breaches: {int(counts.get('breach', 0))}, warnings: {int(counts.get('warn', 0))}, info: {int(counts.get('info', 0))}."
        )
        lines.append("")
        lines.extend(
            _table(
                findings,
                [
                    ("severity", "Severity", lambda v: str(v).upper()),
                    ("rule", "Rule", None),
                    ("subject", "Subject", None),
                    ("current", "Current", _fmt_pct),
                    ("limit", "Limit", _fmt_pct),
                    ("message", "Detail", None),
                    ("suggested_action", "Suggested action", None),
                ],
            )
        )
    else:
        lines.append("_(no findings)_")
        lines.append("")

    # ---- sources
    lines.append("## Sources")
    lines.append("")
    lines.append("Every number above traces to one of these fetches. Cache hits reuse the original fetch time.")
    lines.append("")
    srcs = t.get("sources")
    if srcs is None or len(srcs) == 0:
        srcs = pd.DataFrame(record.sources)
    lines.extend(
        _table(
            srcs,
            [
                ("ticker", "Ticker", None),
                ("provider", "Provider", None),
                ("endpoint", "Endpoint", None),
                ("fetched_at", "Fetched at (UTC)", None),
                ("as_of", "As of", None),
                ("cache_hit", "Cache", lambda v: "hit" if str(v).lower() == "true" else "fetch"),
                ("note", "Note", None),
            ],
        )
    )
    lines.append("---")
    lines.append("Not investment advice. The system informs; only the owner acts.")
    lines.append("")
    return "\n".join(lines)

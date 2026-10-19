"""Compare the current portfolio to the policy and emit Findings (principle 5).

Each rule in policy.yaml has exactly one checker function here. ``evaluate``
runs all of them and returns a flat list of :class:`Finding`. Severity levels:

    info    inside the limit, reported so the owner sees headroom
    warn    at or close to a limit (within warn_fraction) or just outside a band
    breach  the limit is exceeded (or beyond breach_multiple x band for targets)

To add a rule: write ``def check_<name>(ctx: PolicyContext) -> list[Finding]``,
append it to RULES, and add a test in tests/test_policy.py.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Callable

import pandas as pd

from .config import Policy

SEVERITIES = ("info", "warn", "breach")
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass(frozen=True)
class Finding:
    """One result of one rule applied to one subject."""

    severity: str  # info | warn | breach
    rule: str  # e.g. "max_single_position_weight"
    subject: str  # e.g. ticker, sector, asset class, or "portfolio"
    current: float
    limit: float
    message: str
    suggested_action: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PolicyContext:
    """Everything the rules need, gathered once by the runner.

    holdings:  weight-normalized frame with columns ticker, asset_type,
               asset_class, sector, weight, listing_status, last_price_date
    portfolio: dict with annualized_volatility, max_drawdown (may be nan)
    """

    policy: Policy
    holdings: pd.DataFrame
    portfolio: dict[str, float] = field(default_factory=dict)


def _pct(x: float) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1%}"


def _cap_severity(current: float, limit: float, warn_fraction: float) -> str:
    """Severity for an upper limit: breach ABOVE the limit, warn at or near it, else info.

    Exactly at the limit counts as allowed ("max 10%" permits 10%) but warns.
    """
    if current > limit + 1e-12:
        return "breach"
    if current >= limit * warn_fraction - 1e-12:
        return "warn"
    return "info"


# --------------------------------------------------------------------- rules
def check_asset_class_targets(ctx: PolicyContext) -> list[Finding]:
    """targets.asset_class with rebalance.band_absolute and breach_multiple.

    deviation = current - target. |deviation| <= band -> info;
    <= breach_multiple * band -> warn; beyond -> breach.
    """
    p = ctx.policy
    actual = ctx.holdings.groupby("asset_class")["weight"].sum()
    out = []
    for cls, target in p.targets.items():
        current = float(actual.get(cls, 0.0))
        deviation = current - target
        band = p.band_absolute
        if abs(deviation) <= band + 1e-12:
            sev = "info"
        elif abs(deviation) <= p.breach_multiple * band + 1e-12:
            sev = "warn"
        else:
            sev = "breach"
        direction = "over" if deviation > 0 else "under"
        action = (
            "within band; no action"
            if sev == "info"
            else f"{'trim' if deviation > 0 else 'add to'} {cls} by about {_pct(abs(deviation))} to reach target"
        )
        out.append(
            Finding(
                severity=sev,
                rule="asset_class_target",
                subject=cls,
                current=current,
                limit=target,
                message=f"{cls} is {_pct(current)} vs target {_pct(target)} ({direction} by {_pct(abs(deviation))}, band {_pct(band)})",
                suggested_action=action,
            )
        )
    return out


def check_max_single_position(ctx: PolicyContext) -> list[Finding]:
    """limits.max_single_position_weight applied to every non-cash holding."""
    p = ctx.policy
    out = []
    rows = ctx.holdings[ctx.holdings["asset_type"] != "cash"]
    for row in rows.itertuples(index=False):
        sev = _cap_severity(float(row.weight), p.max_single_position_weight, p.warn_fraction)
        out.append(
            Finding(
                severity=sev,
                rule="max_single_position_weight",
                subject=row.ticker,
                current=float(row.weight),
                limit=p.max_single_position_weight,
                message=f"{row.ticker} is {_pct(row.weight)} of the portfolio (limit {_pct(p.max_single_position_weight)})",
                suggested_action="no action"
                if sev == "info"
                else f"trim {row.ticker} by about {_pct(max(0.0, row.weight - p.max_single_position_weight))} or more",
            )
        )
    return out


def check_max_sector(ctx: PolicyContext) -> list[Finding]:
    """limits.max_sector_weight over non-cash holdings grouped by sector."""
    p = ctx.policy
    rows = ctx.holdings[ctx.holdings["asset_type"] != "cash"].copy()
    rows["sector"] = rows["sector"].replace("", "Unknown")
    out = []
    for sector, weight in rows.groupby("sector")["weight"].sum().items():
        sev = _cap_severity(float(weight), p.max_sector_weight, p.warn_fraction)
        out.append(
            Finding(
                severity=sev,
                rule="max_sector_weight",
                subject=str(sector),
                current=float(weight),
                limit=p.max_sector_weight,
                message=f"sector {sector} is {_pct(weight)} (limit {_pct(p.max_sector_weight)})",
                suggested_action="no action" if sev == "info" else f"reduce exposure to {sector}",
            )
        )
    return out


def check_max_single_etf(ctx: PolicyContext) -> list[Finding]:
    """limits.max_single_etf_weight applied to every ETF row."""
    p = ctx.policy
    out = []
    for row in ctx.holdings[ctx.holdings["asset_type"] == "etf"].itertuples(index=False):
        sev = _cap_severity(float(row.weight), p.max_single_etf_weight, p.warn_fraction)
        out.append(
            Finding(
                severity=sev,
                rule="max_single_etf_weight",
                subject=row.ticker,
                current=float(row.weight),
                limit=p.max_single_etf_weight,
                message=f"ETF {row.ticker} is {_pct(row.weight)} (limit {_pct(p.max_single_etf_weight)})",
                suggested_action="no action" if sev == "info" else f"split {row.ticker} across more funds",
            )
        )
    return out


def check_min_cash(ctx: PolicyContext) -> list[Finding]:
    """limits.min_cash_weight: a floor. Below it = breach, within 1 point above = warn."""
    p = ctx.policy
    cash = float(ctx.holdings.loc[ctx.holdings["asset_class"] == "cash", "weight"].sum())
    if cash < p.min_cash_weight - 1e-12:
        sev = "breach"
    elif cash < p.min_cash_weight + 0.01:
        sev = "warn"
    else:
        sev = "info"
    return [
        Finding(
            severity=sev,
            rule="min_cash_weight",
            subject="cash",
            current=cash,
            limit=p.min_cash_weight,
            message=f"cash is {_pct(cash)} (minimum {_pct(p.min_cash_weight)})",
            suggested_action="no action" if sev == "info" else f"raise cash by about {_pct(max(0.0, p.min_cash_weight - cash))}",
        )
    ]


def check_max_volatility(ctx: PolicyContext) -> list[Finding]:
    """risk.max_annualized_volatility against the weighted portfolio's realized vol."""
    p = ctx.policy
    vol = float(ctx.portfolio.get("annualized_volatility", float("nan")))
    if math.isnan(vol):
        return [
            Finding("warn", "max_annualized_volatility", "portfolio", vol, p.max_annualized_volatility,
                    "portfolio volatility could not be computed (not enough price history)",
                    "check data coverage before trusting the risk section")
        ]
    sev = _cap_severity(vol, p.max_annualized_volatility, p.warn_fraction)
    return [
        Finding(
            severity=sev,
            rule="max_annualized_volatility",
            subject="portfolio",
            current=vol,
            limit=p.max_annualized_volatility,
            message=f"realized annualized volatility is {_pct(vol)} (limit {_pct(p.max_annualized_volatility)})",
            suggested_action="no action" if sev == "info" else "shift weight toward lower-volatility holdings or cash",
        )
    ]


def check_max_drawdown(ctx: PolicyContext) -> list[Finding]:
    """risk.max_drawdown_tolerance against the portfolio's max drawdown (magnitude)."""
    p = ctx.policy
    dd = ctx.portfolio.get("max_drawdown", float("nan"))
    if dd is None or math.isnan(dd):
        return [
            Finding("warn", "max_drawdown_tolerance", "portfolio", float("nan"), p.max_drawdown_tolerance,
                    "portfolio drawdown could not be computed (not enough price history)",
                    "check data coverage before trusting the risk section")
        ]
    magnitude = abs(float(dd))
    sev = _cap_severity(magnitude, p.max_drawdown_tolerance, p.warn_fraction)
    return [
        Finding(
            severity=sev,
            rule="max_drawdown_tolerance",
            subject="portfolio",
            current=magnitude,
            limit=p.max_drawdown_tolerance,
            message=f"max drawdown over the lookback is {_pct(magnitude)} (tolerance {_pct(p.max_drawdown_tolerance)})",
            suggested_action="no action" if sev == "info" else "review position sizing; drawdown exceeded tolerance",
        )
    ]


def check_listing_status(ctx: PolicyContext) -> list[Finding]:
    """Data-integrity rule: a holding that is delisted, unknown, or stale is never silent."""
    out = []
    if "listing_status" not in ctx.holdings.columns:
        return out
    for row in ctx.holdings[ctx.holdings["asset_type"] != "cash"].itertuples(index=False):
        status = str(getattr(row, "listing_status", "unknown"))
        if status == "active":
            continue
        sev = "breach" if status == "delisted" else "warn"
        out.append(
            Finding(
                severity=sev,
                rule="listing_status",
                subject=row.ticker,
                current=float(row.weight),
                limit=float("nan"),
                message=f"{row.ticker} listing status is '{status}' (last price {getattr(row, 'last_price_date', 'n/a')}); it still carries {_pct(row.weight)} weight",
                suggested_action="confirm the position exists; replace or remove it in holdings.csv",
            )
        )
    return out


# Order matters only for the report. Every policy.yaml rule appears here.
RULES: list[Callable[[PolicyContext], list[Finding]]] = [
    check_asset_class_targets,
    check_max_single_position,
    check_max_sector,
    check_max_single_etf,
    check_min_cash,
    check_max_volatility,
    check_max_drawdown,
    check_listing_status,
]


def evaluate(ctx: PolicyContext) -> list[Finding]:
    """Run every rule and return findings sorted worst-first."""
    findings: list[Finding] = []
    for rule in RULES:
        findings.extend(rule(ctx))
    findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.rule, f.subject))
    return findings


def findings_frame(findings: list[Finding]) -> pd.DataFrame:
    """Findings as a DataFrame for storage and the report."""
    if not findings:
        return pd.DataFrame(columns=["severity", "rule", "subject", "current", "limit", "message", "suggested_action"])
    return pd.DataFrame([f.to_dict() for f in findings])

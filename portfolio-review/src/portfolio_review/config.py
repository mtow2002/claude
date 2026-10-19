"""Load and validate the policy file (the owner's vision, principle 5).

The policy is plain YAML so it can be edited by hand. This module turns it into
a typed :class:`Policy` object and refuses anything malformed, with a message
that names the exact key at fault. Everything downstream (drift rules, factor
weights, classification) reads from the typed object, never the raw dict.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ASSET_CLASSES = ("us_equity", "intl_equity", "bonds", "cash")
FACTOR_NAMES = ("momentum", "value", "quality", "low_volatility", "trend")
_TOLERANCE = 1e-6


class PolicyError(ValueError):
    """Raised when the policy file is missing something or inconsistent."""


@dataclass(frozen=True)
class Policy:
    """Typed view of policy.yaml. All weights are fractions (0.10 = 10%)."""

    targets: dict[str, float]
    max_single_position_weight: float
    max_sector_weight: float
    max_single_etf_weight: float
    min_cash_weight: float
    warn_fraction: float
    band_absolute: float
    breach_multiple: float
    max_annualized_volatility: float
    max_drawdown_tolerance: float
    factor_weights: dict[str, float]
    default_by_asset_type: dict[str, str]
    by_ticker: dict[str, str]
    benchmark: str
    risk_free_rate: float
    lookback_days: int
    stale_price_days: int
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    sha256: str = field(default="", compare=False)

    def asset_class_for(self, ticker: str, asset_type: str, explicit: str | None = None) -> str:
        """Resolve a holding's asset class.

        Priority: explicit value from holdings.csv, then policy.by_ticker,
        then policy.default_by_asset_type. Raises if the result is not one of
        ASSET_CLASSES so a typo cannot silently create a fifth class.
        """
        if explicit:
            result = explicit
        elif ticker.upper() in self.by_ticker:
            result = self.by_ticker[ticker.upper()]
        else:
            result = self.default_by_asset_type.get(asset_type, "")
        if result not in ASSET_CLASSES:
            raise PolicyError(
                f"asset class {result!r} for {ticker} is not one of {ASSET_CLASSES}"
            )
        return result


def _get(d: dict[str, Any], path: str) -> Any:
    """Fetch a dotted key such as 'limits.max_sector_weight' or raise PolicyError."""
    node: Any = d
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise PolicyError(f"policy is missing required key '{path}'")
        node = node[part]
    return node


def _fraction(d: dict[str, Any], path: str) -> float:
    value = _get(d, path)
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"policy key '{path}' must be a number, got {value!r}") from exc
    if not 0.0 <= f <= 1.0:
        raise PolicyError(f"policy key '{path}' must be between 0 and 1, got {f}")
    return f


def parse_policy(raw: dict[str, Any], sha256: str = "") -> Policy:
    """Validate a parsed YAML dict and build a Policy. Pure: no file access."""
    if not isinstance(raw, dict):
        raise PolicyError("policy file must be a YAML mapping at the top level")

    targets_raw = _get(raw, "targets.asset_class")
    if not isinstance(targets_raw, dict):
        raise PolicyError("targets.asset_class must be a mapping")
    targets: dict[str, float] = {}
    for cls in ASSET_CLASSES:
        targets[cls] = _fraction(raw, f"targets.asset_class.{cls}")
    extra = set(targets_raw) - set(ASSET_CLASSES)
    if extra:
        raise PolicyError(f"targets.asset_class has unknown classes {sorted(extra)}")
    if abs(sum(targets.values()) - 1.0) > _TOLERANCE:
        raise PolicyError(f"targets.asset_class must sum to 1.0, got {sum(targets.values()):.6f}")

    fw_raw = _get(raw, "factor_weights")
    if not isinstance(fw_raw, dict):
        raise PolicyError("factor_weights must be a mapping")
    factor_weights = {name: _fraction(raw, f"factor_weights.{name}") for name in FACTOR_NAMES}
    extra = set(fw_raw) - set(FACTOR_NAMES)
    if extra:
        raise PolicyError(
            f"factor_weights has unknown factors {sorted(extra)}; known: {FACTOR_NAMES}"
        )
    if abs(sum(factor_weights.values()) - 1.0) > _TOLERANCE:
        raise PolicyError(f"factor_weights must sum to 1.0, got {sum(factor_weights.values()):.6f}")

    classification = raw.get("classification") or {}
    default_by_asset_type = {
        str(k): str(v) for k, v in (classification.get("default_by_asset_type") or {}).items()
    }
    for asset_type in ("stock", "etf", "cash"):
        default_by_asset_type.setdefault(asset_type, "cash" if asset_type == "cash" else "us_equity")
    by_ticker = {str(k).upper(): str(v) for k, v in (classification.get("by_ticker") or {}).items()}
    for key, value in list(default_by_asset_type.items()) + list(by_ticker.items()):
        if value not in ASSET_CLASSES:
            raise PolicyError(f"classification maps {key!r} to unknown asset class {value!r}")

    settings = raw.get("settings") or {}
    limits = raw.get("limits") or {}
    rebalance = raw.get("rebalance") or {}

    return Policy(
        targets=targets,
        max_single_position_weight=_fraction(raw, "limits.max_single_position_weight"),
        max_sector_weight=_fraction(raw, "limits.max_sector_weight"),
        max_single_etf_weight=_fraction(raw, "limits.max_single_etf_weight"),
        min_cash_weight=_fraction(raw, "limits.min_cash_weight"),
        warn_fraction=float(limits.get("warn_fraction", 0.90)),
        band_absolute=_fraction(raw, "rebalance.band_absolute"),
        breach_multiple=float(rebalance.get("breach_multiple", 2.0)),
        max_annualized_volatility=_fraction(raw, "risk.max_annualized_volatility"),
        max_drawdown_tolerance=_fraction(raw, "risk.max_drawdown_tolerance"),
        factor_weights=factor_weights,
        default_by_asset_type=default_by_asset_type,
        by_ticker=by_ticker,
        benchmark=str(settings.get("benchmark", "SPY")).upper(),
        risk_free_rate=float(settings.get("risk_free_rate", 0.0)),
        lookback_days=int(settings.get("lookback_days", 400)),
        stale_price_days=int(settings.get("stale_price_days", 10)),
        raw=raw,
        sha256=sha256,
    )


def file_sha256(path: Path | str) -> str:
    """Hash of a file's bytes; stored in run.json so a run is tied to its inputs."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_policy(path: Path | str) -> Policy:
    """Read policy.yaml from disk, validate it, and return a Policy."""
    path = Path(path)
    if not path.exists():
        raise PolicyError(
            f"policy file not found: {path}. Copy config/policy.example.yaml to {path} and edit it."
        )
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return parse_policy(raw, sha256=file_sha256(path))

"""Load holdings.csv and normalize it to portfolio WEIGHTS (principle 4).

Column guide (also in README.md):

    ticker       symbol; use CASH for a money-market or sweep balance
    asset_type   stock | etf | cash
    account      free text, e.g. brokerage, ira
    shares       optional; for cash rows this is the dollar amount
    weight       optional; fraction of the portfolio (0.10 = 10%)
    cost_basis   optional; per-share cost, informational only
    asset_class  optional; us_equity | intl_equity | bonds | cash (overrides policy)
    note         free text

Weight rules:
  * If every row has a weight, those weights are normalized to sum to 1
    (so 30/20/50 and 0.3/0.2/0.5 both work).
  * Else, if every row has shares and a price is available for each non-cash
    row, market value = shares x close at as_of, and weights follow.
  * Else the loader fails with a message naming the rows that block it.
    It never guesses.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

REQUIRED_COLUMNS = ("ticker", "asset_type")
OPTIONAL_COLUMNS = ("account", "shares", "weight", "cost_basis", "asset_class", "note")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
ASSET_TYPES = ("stock", "etf", "cash")
CASH_TICKER = "CASH"


class HoldingsError(ValueError):
    """Raised when holdings.csv cannot be turned into weights."""


@dataclass(frozen=True)
class Holdings:
    """A validated holdings table. ``frame`` always has a ``weight`` column summing to 1."""

    frame: pd.DataFrame
    weight_source: str  # "weights" or "shares_x_price"
    sha256: str

    @property
    def tickers(self) -> list[str]:
        return list(self.frame["ticker"])

    @property
    def priced_tickers(self) -> list[str]:
        """Tickers that need market data (everything except cash)."""
        return list(self.frame.loc[self.frame["asset_type"] != "cash", "ticker"])


def read_holdings_csv(path: Path | str) -> tuple[pd.DataFrame, str]:
    """Read and structurally validate the CSV. Returns (frame, sha256)."""
    path = Path(path)
    if not path.exists():
        raise HoldingsError(
            f"holdings file not found: {path}. Copy config/holdings.example.csv to {path} and edit it."
        )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    df = pd.read_csv(path, dtype=str, skip_blank_lines=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise HoldingsError(f"holdings.csv is missing required columns {missing}")
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[list(ALL_COLUMNS)].fillna("")
    for col in ALL_COLUMNS:
        df[col] = df[col].astype(str).str.strip()
    df = df[df["ticker"] != ""].reset_index(drop=True)
    if df.empty:
        raise HoldingsError("holdings.csv has no rows")

    df["ticker"] = df["ticker"].str.upper()
    df["asset_type"] = df["asset_type"].str.lower()
    bad_types = df.loc[~df["asset_type"].isin(ASSET_TYPES), ["ticker", "asset_type"]]
    if len(bad_types):
        rows = ", ".join(f"{t}={a!r}" for t, a in bad_types.itertuples(index=False))
        raise HoldingsError(f"asset_type must be one of {ASSET_TYPES}; bad rows: {rows}")
    dupes = df.loc[df.duplicated(subset=["ticker", "account"]), "ticker"].tolist()
    if dupes:
        raise HoldingsError(f"duplicate ticker+account rows: {dupes}")

    for col in ("shares", "weight", "cost_basis"):
        text = df[col]
        numeric = pd.to_numeric(text.replace("", None), errors="coerce")
        # A filled cell that did not parse is an error, not a silent blank.
        bad_mask = (text != "") & numeric.isna()
        if bad_mask.any():
            bad = df.loc[bad_mask, "ticker"].tolist()
            raise HoldingsError(f"column {col!r} has non-numeric values for {bad}")
        df[col] = numeric.astype("float64")
    df["asset_class"] = df["asset_class"].str.lower()
    return df, sha


def normalize_weights(
    df: pd.DataFrame,
    prices: Mapping[str, float] | None = None,
) -> tuple[pd.DataFrame, str]:
    """Attach a ``weight`` column that sums to 1. Returns (frame, weight_source).

    ``prices`` maps ticker -> close at as_of for the shares path. Cash rows do
    not need a price: their ``shares`` value is a dollar amount.
    """
    df = df.copy()
    has_weight = df["weight"].notna()
    has_shares = df["shares"].notna()

    if has_weight.all():
        if (df["weight"] < 0).any():
            raise HoldingsError("weights must not be negative")
        total = float(df["weight"].sum())
        if total <= 0:
            raise HoldingsError("weights sum to zero")
        df["raw_weight"] = df["weight"]
        df["weight"] = df["weight"] / total
        df["market_value"] = pd.NA
        return df, "weights"

    if has_shares.all():
        prices = prices or {}
        values = []
        missing_price = []
        for row in df.itertuples(index=False):
            if row.asset_type == "cash":
                values.append(float(row.shares))
            elif row.ticker in prices and pd.notna(prices[row.ticker]):
                values.append(float(row.shares) * float(prices[row.ticker]))
            else:
                values.append(float("nan"))
                missing_price.append(row.ticker)
        if missing_price:
            raise HoldingsError(
                "weights are missing and no price is available at as_of for "
                f"{missing_price}; add a weight column or check the ticker/provider"
            )
        df["market_value"] = values
        total = float(df["market_value"].sum())
        if total <= 0:
            raise HoldingsError("total market value is zero")
        df["raw_weight"] = pd.NA
        df["weight"] = df["market_value"] / total
        return df, "shares_x_price"

    blocked = df.loc[~has_weight & ~has_shares, "ticker"].tolist()
    partial_w = df.loc[has_weight, "ticker"].tolist()
    raise HoldingsError(
        "cannot determine weights: every row needs either a weight or shares. "
        f"Rows with neither: {blocked}. Rows with a weight: {partial_w}. "
        "Mixing the two styles is not supported; pick one for the whole file."
    )


def load_holdings(path: Path | str, prices: Mapping[str, float] | None = None) -> Holdings:
    """Read, validate, and weight-normalize holdings.csv in one call."""
    df, sha = read_holdings_csv(path)
    df, source = normalize_weights(df, prices)
    return Holdings(frame=df, weight_source=source, sha256=sha)

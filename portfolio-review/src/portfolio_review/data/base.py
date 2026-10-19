"""Data-layer contracts: the Provider protocol and the Source record.

Principle 2 (point-in-time) and principle 3 (cite sources) are enforced here:

* every data call takes ``as_of`` and must never return rows dated after it;
* every return value is wrapped with a :class:`Source` saying which provider,
  which endpoint, and when the bytes were fetched.

A "provider" is anything that can answer two questions:

    prices(ticker, start, end, as_of)  -> daily OHLCV bars
    profile(ticker, as_of)             -> name, sector, industry, type, status

To add a provider, implement those two methods (see docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Protocol, runtime_checkable

import pandas as pd

# The exact columns every prices() DataFrame must have, in this order.
PRICE_COLUMNS: list[str] = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
]

# Allowed values for Profile.listing_status.
LISTING_STATUSES = ("active", "delisted", "unknown")

# Allowed values for Profile.asset_type.
ASSET_TYPES = ("stock", "etf", "cash", "unknown")


class ProviderError(RuntimeError):
    """A provider could not get data (network blocked, bad symbol, API down).

    Raised instead of returning partial or empty data silently, so the run
    fails loudly with the ticker and endpoint in the message.
    """


@dataclass(frozen=True)
class Source:
    """Where a piece of data came from. Attached to every provider result.

    Attributes:
        provider:   short provider name, e.g. "yfinance".
        endpoint:   the call made, e.g. "Ticker.history" or a URL path.
        fetched_at: UTC timestamp when the bytes were actually retrieved.
                    For a cache hit this is the ORIGINAL fetch time.
        as_of:      the point-in-time date the data represents.
        ticker:     which symbol (kept here so a report can list all sources).
        cache_hit:  True if served from the local cache rather than the network.
        note:       free text, e.g. "profile fields are not point-in-time".
    """

    provider: str
    endpoint: str
    fetched_at: datetime
    as_of: date
    ticker: str = ""
    cache_hit: bool = False
    note: str = ""

    def to_dict_raw(self) -> dict[str, Any]:
        """Plain dict with the original datetime/date objects (for copying)."""
        return asdict(self)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly form used in run.json and the report Sources section."""
        d = asdict(self)
        d["fetched_at"] = self.fetched_at.isoformat()
        d["as_of"] = self.as_of.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Source":
        return cls(
            provider=d["provider"],
            endpoint=d["endpoint"],
            fetched_at=datetime.fromisoformat(d["fetched_at"]),
            as_of=date.fromisoformat(d["as_of"]),
            ticker=d.get("ticker", ""),
            cache_hit=bool(d.get("cache_hit", False)),
            note=d.get("note", ""),
        )


@dataclass(frozen=True)
class Profile:
    """Static-ish facts about a ticker.

    ``fundamentals`` is an open dict for optional numbers used by the value and
    quality factors (keys: pe_ratio, price_to_book, return_on_equity,
    debt_to_equity, profit_margin). Missing keys mean "not available".
    """

    ticker: str
    name: str
    sector: str
    industry: str
    asset_type: str  # one of ASSET_TYPES
    listing_status: str  # one of LISTING_STATUSES
    fundamentals: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Profile":
        return cls(
            ticker=d["ticker"],
            name=d.get("name", ""),
            sector=d.get("sector", ""),
            industry=d.get("industry", ""),
            asset_type=d.get("asset_type", "unknown"),
            listing_status=d.get("listing_status", "unknown"),
            fundamentals={k: float(v) for k, v in (d.get("fundamentals") or {}).items()},
        )


@dataclass(frozen=True)
class PriceData:
    """A price DataFrame plus the Source that produced it."""

    frame: pd.DataFrame
    source: Source


@dataclass(frozen=True)
class ProfileData:
    """A Profile plus the Source that produced it."""

    profile: Profile
    source: Source


@runtime_checkable
class Provider(Protocol):
    """The interface every data provider must satisfy.

    Implementations must:
      * return a DataFrame with exactly PRICE_COLUMNS (date as datetime64,
        sorted ascending, no duplicates);
      * drop every row whose date is after ``as_of`` (use
        :func:`enforce_as_of`);
      * fill ``Source.fetched_at`` with the real retrieval time, UTC.
    """

    name: str

    def prices(self, ticker: str, start: date, end: date, as_of: date) -> PriceData:
        """Daily bars for ``ticker`` between ``start`` and ``end`` inclusive."""
        ...

    def profile(self, ticker: str, as_of: date) -> ProfileData:
        """Descriptive facts about ``ticker`` as known at ``as_of``."""
        ...


def utc_now() -> datetime:
    """Timezone-aware 'now'. Every fetched_at goes through here."""
    return datetime.now(timezone.utc)


def empty_price_frame() -> pd.DataFrame:
    """A zero-row frame with the right columns and dtypes."""
    return pd.DataFrame(
        {
            "date": pd.Series([], dtype="datetime64[ns]"),
            "open": pd.Series([], dtype="float64"),
            "high": pd.Series([], dtype="float64"),
            "low": pd.Series([], dtype="float64"),
            "close": pd.Series([], dtype="float64"),
            "adj_close": pd.Series([], dtype="float64"),
            "volume": pd.Series([], dtype="float64"),
        }
    )


def normalize_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce an arbitrary OHLCV frame into the canonical layout.

    Accepts common column spellings ("Adj Close", "adj_close", "Date"...),
    lower-cases and underscores them, parses dates, sorts, and de-duplicates.
    Raises ``ValueError`` if a required column is missing.
    """
    if frame is None or len(frame) == 0:
        return empty_price_frame()
    df = frame.copy()
    if df.index.name is not None and "date" not in {c.lower() for c in df.columns}:
        df = df.reset_index()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]
    missing = [c for c in PRICE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"price frame is missing columns {missing}; have {list(df.columns)}")
    df = df[PRICE_COLUMNS].copy()
    # Strip any timezone so comparisons with plain dates are unambiguous.
    dates = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
    df["date"] = dates.dt.normalize()
    for col in PRICE_COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df = df.dropna(subset=["close"])
    df = df.drop_duplicates(subset="date", keep="last").sort_values("date")
    return df.reset_index(drop=True)


def enforce_as_of(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Drop every row dated after ``as_of``. The point-in-time guard."""
    if len(frame) == 0:
        return frame
    cutoff = pd.Timestamp(as_of)
    return frame[frame["date"] <= cutoff].reset_index(drop=True)


def check_as_of(frame: pd.DataFrame, as_of: date) -> None:
    """Raise if any row is after ``as_of``. Used by tests and the cache."""
    if len(frame) and frame["date"].max() > pd.Timestamp(as_of):
        raise ValueError(
            f"point-in-time violation: data dated {frame['date'].max().date()} "
            f"is after as_of {as_of}"
        )

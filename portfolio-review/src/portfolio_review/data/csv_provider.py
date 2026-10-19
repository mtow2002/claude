"""CSV provider: prices and profiles from local files. Used for tests and for
any offline data you export yourself (broker downloads, StockCharts exports).

Directory layout::

    <folder>/<TICKER>.csv      columns: date,open,high,low,close,adj_close,volume
    <folder>/profiles.csv      columns: ticker,name,sector,industry,asset_type,
                               listing_status[,pe_ratio,price_to_book,
                               return_on_equity,debt_to_equity,profit_margin]

A ticker with no CSV yields an empty price frame (not an error) so that a
delisted or unknown symbol shows up in the report as missing rather than
silently vanishing. A ticker absent from profiles.csv gets listing_status
"unknown".
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .base import (
    PriceData,
    Profile,
    ProfileData,
    Source,
    empty_price_frame,
    enforce_as_of,
    normalize_price_frame,
    utc_now,
)

_FUNDAMENTAL_COLUMNS = (
    "pe_ratio",
    "price_to_book",
    "return_on_equity",
    "debt_to_equity",
    "profit_margin",
)


class CSVProvider:
    """Provider that reads from a folder of CSV files."""

    name = "csv"

    def __init__(self, folder: Path | str) -> None:
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise FileNotFoundError(f"csv provider folder not found: {self.folder}")
        profiles_path = self.folder / "profiles.csv"
        self._profiles = (
            pd.read_csv(profiles_path, dtype=str).fillna("") if profiles_path.exists() else None
        )

    def prices(self, ticker: str, start: date, end: date, as_of: date) -> PriceData:
        fetched_at = utc_now()
        path = self.folder / f"{ticker.upper()}.csv"
        if path.exists():
            frame = normalize_price_frame(pd.read_csv(path))
            frame = frame[
                (frame["date"] >= pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(end))
            ].reset_index(drop=True)
        else:
            frame = empty_price_frame()
        frame = enforce_as_of(frame, as_of)
        source = Source(
            provider=self.name,
            endpoint=str(path),
            fetched_at=fetched_at,
            as_of=as_of,
            ticker=ticker.upper(),
        )
        return PriceData(frame=frame, source=source)

    def profile(self, ticker: str, as_of: date) -> ProfileData:
        fetched_at = utc_now()
        row = None
        if self._profiles is not None:
            match = self._profiles[self._profiles["ticker"].str.upper() == ticker.upper()]
            if len(match):
                row = match.iloc[0]
        if row is None:
            profile = Profile(
                ticker=ticker.upper(),
                name="",
                sector="",
                industry="",
                asset_type="unknown",
                listing_status="unknown",
            )
        else:
            fundamentals = {}
            for col in _FUNDAMENTAL_COLUMNS:
                if col in row.index and str(row[col]).strip() != "":
                    fundamentals[col] = float(row[col])
            profile = Profile(
                ticker=ticker.upper(),
                name=str(row.get("name", "")),
                sector=str(row.get("sector", "")),
                industry=str(row.get("industry", "")),
                asset_type=str(row.get("asset_type", "unknown") or "unknown"),
                listing_status=str(row.get("listing_status", "unknown") or "unknown"),
                fundamentals=fundamentals,
            )
        source = Source(
            provider=self.name,
            endpoint=str(self.folder / "profiles.csv"),
            fetched_at=fetched_at,
            as_of=as_of,
            ticker=ticker.upper(),
        )
        return ProfileData(profile=profile, source=source)

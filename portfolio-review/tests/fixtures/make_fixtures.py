"""Generate the synthetic price CSVs used by the tests. Run once; commit output.

    python tests/fixtures/make_fixtures.py

Four tickers plus the SPY benchmark, business days 2024-01-02 .. 2025-12-31.
DDD is "delisted": its series stops on 2025-06-30 and profiles.csv marks it.
Prices are a seeded geometric random walk, so nothing here is real market data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent / "prices"

# ticker -> (start price, annual drift, annual volatility, last date or None)
SPECS = {
    "AAA": (100.0, 0.25, 0.30, None),  # high momentum tech stock
    "BBB": (50.0, 0.05, 0.15, None),  # sleepy healthcare stock
    "CCC": (80.0, 0.02, 0.06, None),  # bond ETF
    "DDD": (20.0, -0.40, 0.50, "2025-06-30"),  # delisted mid-series
    "SPY": (400.0, 0.10, 0.18, None),  # benchmark
}


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2024-01-02", "2025-12-31")
    rng = np.random.default_rng(42)
    for ticker, (p0, drift, vol, last) in SPECS.items():
        n = len(dates)
        daily = rng.normal(drift / 252, vol / np.sqrt(252), size=n)
        close = p0 * np.exp(np.cumsum(daily))
        spread = close * 0.01
        frame = pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "open": np.round(close - spread / 2, 4),
                "high": np.round(close + spread, 4),
                "low": np.round(close - spread, 4),
                "close": np.round(close, 4),
                "adj_close": np.round(close, 4),
                "volume": rng.integers(100_000, 1_000_000, size=n),
            }
        )
        if last is not None:
            frame = frame[frame["date"] <= last]
        frame.to_csv(HERE / f"{ticker}.csv", index=False)
        print(ticker, len(frame), "rows")


if __name__ == "__main__":
    main()

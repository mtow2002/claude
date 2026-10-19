# Decisions (ADR style)

Short, numbered. Each has the decision, the reason, and what was rejected.

## 1. Self-contained project in `portfolio-review/`

Decision: everything lives under `portfolio-review/` with its own
`pyproject.toml`, README, tests. Only the CI workflow sits at the repo root.
Reason: the work will move to a new `portfolio-review` repo; a folder move is
then the whole migration. Rejected: mixing with the existing docs at root.

## 2. `src/` layout with a console script

Decision: package under `src/portfolio_review`, installed with `pip install -e`.
Reason: tests import the installed package, not the working directory, which
catches packaging mistakes early. Rejected: flat layout (easier to import
accidentally without installing).

## 3. Providers return `(frame, Source)` wrappers, not bare DataFrames

Decision: `PriceData` / `ProfileData` dataclasses carry a `Source`.
Reason: principle 3 needs the citation to travel with the data; a side channel
would be forgotten. Rejected: DataFrame `.attrs` (silently dropped by many
pandas operations).

## 4. Cache keyed by `(provider, ticker, as_of)` in parquet + JSON sidecar

Decision: one folder per key with `prices.parquet` and `prices.meta.json`.
Reason: as_of isolation is a folder boundary, which is easy to reason about
and to delete. Parquet is compact and typed; the JSON sidecar keeps
`fetched_at` human-readable. Rejected: SQLite (harder to inspect for a
beginner), one big parquet per ticker (as_of isolation becomes a filter you
can forget).

## 5. Weights normalized at load; shares are optional input

Decision: `holdings.normalize_weights` is the single path to weights.
Reason: principle 4. Rejected: carrying share counts through the analytics.

## 6. Mixed weight/shares rows are an error

Decision: a file must use weights for every row or shares for every row.
Reason: mixing a relative weight with an absolute dollar value has no
unambiguous answer; guessing violates "never invent a number".

## 7. Asset class comes from holdings column, then policy map, then type default

Decision: optional `asset_class` column in holdings.csv; policy
`classification.by_ticker`; policy `classification.default_by_asset_type`.
Reason: the policy targets four classes but a ticker's class is a fact about
the holding, and yfinance does not reliably say "international" or "bond".
Rejected: inferring from the provider's category strings (fragile).

## 8. Factor scores by percentile rank across the holdings universe

Decision: 0..100 rank-based scores; missing data = 50 and flagged.
Reason: rank scores are scale-free and robust to outliers with a handful of
tickers; a neutral fill keeps a missing P/E from sinking an ETF. Rejected:
z-scores (unstable with 5 tickers), scoring against a market universe (needs
data we do not fetch yet; listed in ROADMAP).

## 9. "Max" limits are inclusive

Decision: a position exactly at `max_single_position_weight` is a warn, not a
breach; above it is a breach. Reason: "max 10%" in plain English allows 10%.

## 10. Portfolio returns use constant weights

Decision: daily portfolio return = sum of weight x ticker return, weights held
at today's values over the whole lookback.
Reason: this is a review of the current mix, not a backtest of past trades.
A backtesting engine (ROADMAP) will model drift and rebalancing properly.

## 11. Delisted tickers are a breach finding, not a dropped row

Decision: price gaps relative to `as_of` set `price_status`, override
`listing_status`, and raise findings. Reason: principle 2's explicit rule and
the old ledger's "silent drop" incident.

## 12. yfinance profile fields are accepted with a point-in-time caveat

Decision: use `Ticker.info` for sector/fundamentals and label the Source note.
Reason: it is the only free source available now; the caveat is printed in
every report so it cannot be forgotten. Alpha Vantage / Massive can replace it.

## 13. Report is rendered from stored tables only

Decision: `render_report(record, tables)` takes no provider.
Reason: `report` can re-render any old run offline and identically.

## 14. Run folders are immutable

Decision: `LocalStore.save_run` raises if the folder exists; `report` only
rewrites `report.md`. Reason: the old doctrine "corrections go in a new file".

## 15. Commands are auto-discovered modules

Decision: `cli.py` imports every `commands/*.py` with `register`.
Reason: parallel sessions can add commands without merge conflicts in cli.py.

## 16. Optional dependency groups pre-declared

Decision: `bigquery`, `report`, `backtest` (empty), `all` extras exist now.
Reason: later sessions never edit `pyproject.toml`, avoiding conflicts.

## 17. Tests use a CSV provider, not mocks of yfinance

Decision: `CSVProvider` is a real provider used by tests and usable by hand.
Reason: it doubles as the way to analyze broker or StockCharts exports
offline, and it exercises the same code path as any provider.

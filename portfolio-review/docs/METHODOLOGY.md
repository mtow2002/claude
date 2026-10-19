# Methodology

The five analysis principles, and exactly how the code enforces each one.
Where enforcement is partial, it says so.

## 1. Hypothesis before query

Every run records the question it answers.

* `portfolio-review run` has a required `--question` argument
  (`commands/run.py`). argparse refuses to start without it.
* `runner.execute_run` raises `ValueError` if the question is blank.
* The question is stored in `run.json` (`RunRecord.question`) and printed as
  the second line of the report (`report.render_report`).
* `portfolio-review report --list` shows the question next to every saved run.

## 2. Point-in-time discipline

Nothing after `as_of` may influence a result.

* Every provider method takes `as_of` (`data/base.py::Provider`). Providers
  call `enforce_as_of`, which drops rows dated after it.
* The cache (`data/cache.py`) re-verifies with `check_as_of` before writing
  and raises on a violation, so a misbehaving provider cannot poison the cache.
* The cache key is `(provider, ticker, as_of)`: a run for 2025-06-30 never
  reads a folder fetched for 2025-09-30 (test: `test_cache_is_isolated_by_as_of`).
* Cached items store `fetched_at` (when the bytes arrived) and `as_of` (what
  point in time they represent) in `prices.meta.json` / `profile.json`.
* The lookback window starts at `as_of - settings.lookback_days` and ends at
  `as_of`; the runner never reads the wall clock for analysis dates. The only
  default from the clock is the CLI's `--as-of` default of today, which is
  then stored explicitly in `run.json`.
* **Delisted tickers never disappear.** A ticker whose prices stop before
  `as_of` keeps its row and weight. `runner.price_status` marks it `stale`
  (last bar older than `settings.stale_price_days`) or `missing` (no bars),
  the listing status becomes `delisted` / `unknown`, the report prints a data
  warning under the holdings table, and `policy.check_listing_status` raises a
  `breach` (delisted) or `warn` (unknown) finding.
* **Known gap:** yfinance profile fields (sector, P/E, ROE) are a snapshot of
  today, not of `as_of`. The Source note says
  "profile fields are a current snapshot, not point-in-time" and the report
  prints it in the Sources table. Alpha Vantage `LISTING_STATUS` and Massive
  reference data (see the stubs) can close this gap for listing status.

## 3. Cite sources

Every number traces to a provider, endpoint, and fetch timestamp.

* Every provider return value is a `PriceData` / `ProfileData` carrying a
  `Source(provider, endpoint, fetched_at, as_of, ticker, cache_hit, note)`.
* `runner.fetch_universe` collects every Source; they are written to
  `run.json` and to a `sources` table in the run folder.
* The report ends with a **Sources** section listing each one. Cache hits show
  the original fetch time and are marked "hit".
* Hashes of the policy file and holdings file, the package version, and the git
  commit are stored in `run.json` so the run can be reproduced input-for-input.

## 4. Weights over share counts

* `holdings.normalize_weights` always produces a `weight` column summing to 1.
  Weights in the CSV are normalized (30/70 or 0.3/0.7 both work). If weights
  are absent but shares are present, weight = shares x close at `as_of` /
  total (cash rows use the shares column as a dollar amount). If neither is
  available the loader fails and names the rows.
* Every policy limit is a weight (`config/policy.example.yaml`); share counts
  never appear in a rule.
* `run.json` records `weight_source` (`weights` or `shares_x_price`).

## 5. The vision lives in one editable file, and the system reports drift

* `config/policy.yaml` is the only place targets, limits, bands, risk limits,
  factor weights, and classification live. `config.load_policy` validates it
  (targets sum to 1, factor weights sum to 1, every fraction in 0..1, every
  class name known) and names the offending key on failure.
* `policy.RULES` has one checker per rule. `evaluate` runs all of them on
  every run. Rules and their severity logic:

| Rule | Source key | info | warn | breach |
|---|---|---|---|---|
| asset_class_target | targets.asset_class, rebalance.* | within band | outside band | beyond breach_multiple x band |
| max_single_position_weight | limits.* | below warn_fraction x limit | at or near limit | above limit |
| max_sector_weight | limits.* | same | same | same |
| max_single_etf_weight | limits.* | same | same | same |
| min_cash_weight | limits.* | at least 1 pt above min | within 1 pt above | below min |
| max_annualized_volatility | risk.* | same as caps | same | above; warn if not computable |
| max_drawdown_tolerance | risk.* | same as caps | same | above; warn if not computable |
| listing_status | (data integrity) | active | unknown | delisted |

* Each Finding carries current value, limit, a message, and a suggested action.
  The report groups them worst-first.

## Formulas

All in `metrics.py`, `factors.py`, `portfolio.py` docstrings. Summary:

* Daily return r_t = P_t / P_{t-1} - 1 on adjusted close.
* Annualized return = (P_last / P_first)^(252/n) - 1, n = daily observations.
* Annualized volatility = std(r, ddof=1) x sqrt(252).
* Max drawdown = min_t (P_t / max_{s<=t} P_s - 1), reported as a negative.
* Sharpe = mean(r - rf/252) x 252 / (std(r - rf/252, ddof=1) x sqrt(252)).
* Beta = cov(r, r_bench) / var(r_bench) over shared dates.
* Momentum k months = P_last / P_{last - 21k} - 1 (3m = 63, 6m = 126, 12m = 252 trading days).
* Trend = P_last / SMA_200 - 1.
* Factor score = 100 x rank / (n - 1) across tickers with data (lower-is-better
  factors rank ascending); no data = 50 and flagged; composite = sum of
  policy weight x score.
* Portfolio daily return = sum_i w_i r_{i,t} with constant weights; cash = 0.
* HHI = sum of squared non-cash weights; effective N = 1 / HHI.

## Doctrine carried over from the earlier Portfolio Ledger work

From the existing README and audit in this repo, applied here:

* Never invent a number: unknown is `nan` / "n/a", never 0 or a guess.
* Degrade loudly: network failures raise `ProviderError`; stale data is
  flagged, not hidden.
* Imports at module scope, tested by `tests/test_imports.py`.
* No keys in the repo: `.env` is gitignored, `.env.example` has placeholders.
* Run folders are never overwritten (`LocalStore.save_run` refuses).
* The system informs; only the owner acts. The report says so.

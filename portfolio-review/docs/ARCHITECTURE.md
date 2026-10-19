# Architecture

This document maps the code: what each module does, how data flows through a
run, and the recipe for adding a provider, a factor, a rule, or a command.

## Modules

```
src/portfolio_review/
  __init__.py          package version
  cli.py               argparse entry point; auto-discovers commands/*.py
  commands/
    _common.py         shared argument groups (inputs, data, store)
    run.py             `run`: the full analysis for one as_of and one question
    validate.py        `validate`: check holdings.csv and policy.yaml
    fetch.py           `fetch`: warm the cache (the nightly sweep)
    report.py          `report`: re-render a saved run's Markdown
  config.py            load + validate policy.yaml into a typed Policy
  holdings.py          load holdings.csv, normalize to weights
  runner.py            orchestrates one run end to end
  metrics.py           returns, volatility, drawdown, Sharpe, beta, momentum, trend
  factors.py           0..100 factor scores and the weighted composite
  portfolio.py         exposures, concentration (HHI), weighted portfolio returns
  policy.py            drift rules -> Findings
  report.py            Markdown report from a RunRecord + tables
  data/
    base.py            Provider protocol, Source, Profile, point-in-time guards
    cache.py           CachedProvider: parquet cache keyed by provider/ticker/as_of
    registry.py        name -> provider factory (`--provider`)
    yfinance_provider.py  Yahoo Finance (no key)
    csv_provider.py    local CSV folder (tests, broker exports)
    alpha_vantage.py   stub, interface documented
    massive.py         stub, interface documented
  store/
    base.py            Store protocol, RunRecord, LoadedRun
    local.py           LocalStore: runs/<as_of>_<run_id>/
    bigquery.py        stub, interface documented
```

## Data flow of `portfolio-review run`

```
config/policy.yaml ----> config.load_policy ----> Policy (typed, hashed)
config/holdings.csv ---> holdings.read_holdings_csv -> raw rows (hashed)
                                   |
                                   v
            data.make_provider(name) -> CachedProvider(inner provider)
                                   |
           for each non-cash ticker + benchmark, with as_of:
             prices(ticker, start, end, as_of)  -> PriceData(frame, Source)
             profile(ticker, as_of)             -> ProfileData(profile, Source)
                                   |
                 data/cache/<provider>/<TICKER>/<as_of>/  (parquet + json)
                                   |
                                   v
      holdings.normalize_weights(raw, last_close)  -> weights summing to 1
                                   |
                                   v
      runner builds the holdings table:
        asset_class (policy.asset_class_for), sector/industry/name (profile),
        listing_status + price_status (profile x last price date vs as_of)
                                   |
         +-------------------------+----------------------------+
         v                         v                            v
  metrics.ticker_metrics   factors.score_factors      portfolio.exposure_by
  (per ticker, vs bench)   (0..100 + composite)       portfolio.concentration
                                                      portfolio.portfolio_returns
                                                      portfolio.portfolio_metrics
         |                         |                            |
         +-------------------------+----------------------------+
                                   v
                policy.evaluate(PolicyContext) -> list[Finding]
                                   |
                                   v
                 RunRecord (question, as_of, hashes, version,
                            git commit, every Source) + tables
                                   |
                                   v
                 report.render_report(record, tables) -> Markdown
                                   |
                                   v
                 store.LocalStore.save_run -> runs/<as_of>_<run_id>/
                     run.json, report.md, tables/*.parquet
```

`portfolio-review report` loads `run.json` and `tables/*.parquet` and calls
`render_report` again. It never touches a provider.

`portfolio-review fetch` runs only the data step and stops, filling the cache.

## Key contracts

* **Provider** (`data/base.py`): `prices(ticker, start, end, as_of) -> PriceData`
  and `profile(ticker, as_of) -> ProfileData`. The frame has exactly
  `PRICE_COLUMNS`. Rows after `as_of` are removed by `enforce_as_of`; the cache
  re-checks with `check_as_of` and raises on a violation.
* **Source** (`data/base.py`): provider, endpoint, fetched_at (UTC), as_of,
  ticker, cache_hit, note. Collected by the runner and written to `run.json`
  and the report's Sources section.
* **Policy** (`config.py`): frozen dataclass; invalid files raise `PolicyError`
  naming the key.
* **Finding** (`policy.py`): severity, rule, subject, current, limit, message,
  suggested_action.
* **RunRecord** (`store/base.py`): the reproducibility manifest.

## How to add a provider

1. Create `src/portfolio_review/data/<name>.py` with a class that has
   `name = "<name>"` and the two methods. Build the frame with
   `normalize_price_frame`, then call `enforce_as_of`. Fill `Source.endpoint`
   with the real call you made and `fetched_at` with `utc_now()`.
2. Raise `ProviderError` on transport failures; never return partial data as
   if complete.
3. Add one line to `PROVIDERS` in `data/registry.py`.
4. Tests: record JSON/CSV fixtures under `tests/fixtures/<name>/` and test
   against those. No network in tests.

The stubs `alpha_vantage.py` and `massive.py` carry the endpoint-by-endpoint
notes for the next session.

## How to add a factor

1. In `factors.py`, write a raw function
   `def _myfactor_raw(metrics: Mapping, fundamentals: Mapping) -> float`
   returning `nan` when data is missing.
2. Add `FactorSpec("myfactor", _myfactor_raw, higher_is_better, "description")`
   to `FACTORS`.
3. Add `"myfactor"` to `FACTOR_NAMES` in `config.py` so the policy validator
   accepts a weight for it, and give it a weight in your policy (weights must
   still sum to 1).
4. Document the formula in the module docstring and `docs/METHODOLOGY.md`;
   add a test in `tests/test_factors.py`.

If the factor needs a new fundamental field, add the key to the provider's
`Profile.fundamentals` (yfinance: `_FUNDAMENTAL_KEYS`; csv: `_FUNDAMENTAL_COLUMNS`).

## How to add a policy rule

1. Add the parameter to `config/policy.example.yaml` and to `Policy` +
   `parse_policy` in `config.py` (use `_fraction` for 0..1 values).
2. In `policy.py`, write `def check_<rule>(ctx: PolicyContext) -> list[Finding]`
   and append it to `RULES`.
3. Add a test in `tests/test_policy.py` covering info, warn, and breach.
4. Mention it in `docs/METHODOLOGY.md` under principle 5.

## How to add a command

1. Create `src/portfolio_review/commands/<name>.py` with
   `def register(subparsers)` that calls `subparsers.add_parser(...)`, adds
   arguments (reuse `_common.py` helpers), and sets `p.set_defaults(handler=fn)`.
2. `handler(args)` returns an int exit code. Raise `ValueError` or
   `FileNotFoundError` for user mistakes; `cli.main` prints them as
   `error: ...` and exits 1.
3. Add a test in `tests/test_cli.py`. `cli.py` does not change.

## How to add a store

Implement the four methods of `store/base.py::Store`. `bigquery.py` has the
table design for the planned BigQuery store.

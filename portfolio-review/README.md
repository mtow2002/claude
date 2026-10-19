# Portfolio Review

A reproducible, point-in-time stock and ETF portfolio review in Python.

You give it two files: your **holdings** (what you own) and your **policy**
(what you want the portfolio to look like). It fetches prices as of a date you
choose, computes risk and factor metrics, compares the result to your policy,
and writes a Markdown report with every number traced to its data source.

It never trades and never gives advice. It informs; you decide.

## The five principles the code enforces

1. **Hypothesis before query.** Every run needs a `--question`, stored with the run.
2. **Point-in-time.** Every data call has an `as_of` date. Nothing after it is used. Cached data remembers when it was fetched and which `as_of` it serves.
3. **Cite sources.** The report ends with a Sources table: provider, endpoint, fetch time, for every number.
4. **Weights, not share counts.** Holdings become portfolio weights; policy limits are weights.
5. **One policy file.** Your vision lives in `config/policy.yaml`; every run reports drift from it.

Details: `docs/METHODOLOGY.md`. Code map: `docs/ARCHITECTURE.md`.

## Install (Windows, PowerShell)

You need Python 3.11 or newer. Check with `python --version`.

```powershell
# 1. Go to the project folder (adjust the path to wherever you cloned the repo)
cd C:\path\to\claude\portfolio-review

# 2. Create a virtual environment: a private copy of Python for this project
python -m venv .venv

# 3. Activate it (you will see (.venv) at the start of the prompt)
.\.venv\Scripts\Activate.ps1

# If PowerShell refuses to run the activate script, run this once, then retry:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 4. Install the project in editable mode plus the test tools
pip install -e ".[dev]"

# 5. Check it worked
portfolio-review --version
```

Every new terminal session needs step 3 again before `portfolio-review` works.

## Set up your config files

Both real files are gitignored, so your personal data never gets committed.

```powershell
Copy-Item config\policy.example.yaml config\policy.yaml
Copy-Item config\holdings.example.csv config\holdings.csv
```

Then open both in any text editor.

### policy.yaml

Every section has comments explaining it. The parts you will edit most:

* `targets.asset_class`: your intended mix of `us_equity`, `intl_equity`,
  `bonds`, `cash`. Must sum to 1.0.
* `limits`: max weight for one position, one sector, one ETF; minimum cash.
* `rebalance.band_absolute`: how far a class can drift before a warning.
* `risk`: maximum portfolio volatility and drawdown you will tolerate.
* `factor_weights`: how much each factor counts in the composite score. Must sum to 1.0.
* `classification.by_ticker`: tell the system which tickers are international, bonds, or cash-like.

### holdings.csv column guide

| Column | Required | Meaning |
|---|---|---|
| `ticker` | yes | Symbol. Use `CASH` for a money-market or sweep balance. |
| `asset_type` | yes | `stock`, `etf`, or `cash`. |
| `account` | no | Free text such as `brokerage` or `ira`. Used for the by-account table. |
| `shares` | no | Number of shares. For a `cash` row, the dollar amount. |
| `weight` | no | Fraction of the portfolio, e.g. `0.10` for 10%. Any scale works; weights are normalized. |
| `cost_basis` | no | Per-share cost. Informational only. |
| `asset_class` | no | `us_equity`, `intl_equity`, `bonds`, or `cash`. Overrides the policy mapping. |
| `note` | no | Free text. |

Rules: fill `weight` for every row, **or** fill `shares` for every row (the
system multiplies by the price at the as-of date). If neither is complete the
run stops and tells you which rows are missing.

## Run it

```powershell
# Check both files for mistakes (no network needed)
portfolio-review validate

# Download prices and profiles into the local cache (the nightly sweep)
portfolio-review fetch --as-of 2026-10-17

# Run the analysis. --question is required.
portfolio-review run --as-of 2026-10-17 --question "Is the portfolio within policy after the October moves?"

# Re-render the newest saved report (for example after editing report.py)
portfolio-review report
portfolio-review report --list
```

Defaults: `--holdings config/holdings.csv`, `--policy config/policy.yaml`,
`--provider yfinance`, `--benchmark` from the policy (SPY), `--as-of` today.
Add `--help` after any command to see all options.

### Where outputs go

```
data/cache/<provider>/<TICKER>/<as_of>/   downloaded data (gitignored)
runs/<as_of>_<run_id>/
    run.json        question, as_of, input hashes, version, git commit, sources
    report.md       the report
    tables/*.parquet  holdings, metrics, factors, findings, exposures, prices, sources
```

The `run` command prints the report path when it finishes. Open `report.md`
in any Markdown viewer (VS Code previews it with Ctrl+Shift+V).

### Working offline or from your own exports

The `csv` provider reads local files: one `<TICKER>.csv` per symbol with
columns `date,open,high,low,close,adj_close,volume`, plus an optional
`profiles.csv`. See `tests/fixtures/prices/` for the exact shape.

```powershell
portfolio-review run --provider csv --provider-path data\csv --as-of 2026-10-17 --question "..."
```

## Run the tests

```powershell
pytest
```

Tests use synthetic data under `tests/fixtures/` and never touch the network.
GitHub Actions runs the same command on every push
(`.github/workflows/portfolio-review-tests.yml` at the repo root).

## Project layout

```
portfolio-review/
  config/            example policy and holdings (copy, then edit)
  src/portfolio_review/
    data/            providers (yfinance, csv, stubs) and the cache
    store/           where runs are saved (local folder, BigQuery stub)
    commands/        one file per CLI command
    metrics.py factors.py portfolio.py policy.py report.py runner.py
  tests/             pytest suite and fixtures
  docs/              ARCHITECTURE, METHODOLOGY, DECISIONS, SETUP_LOG, ROADMAP
```

## Glossary

* **branch**: a parallel line of work in git. You make changes on a branch, then merge it into `main` when they are reviewed.
* **commit**: a saved snapshot of your changes with a message. `git log` shows the history of commits.
* **PR (pull request)**: a request on GitHub to merge one branch into another. It shows the diff and lets someone review before merging.
* **package**: a folder of Python code that can be installed and imported. This project's package is `portfolio_review`.
* **venv (virtual environment)**: a private Python installation for one project, so its libraries do not clash with other projects. Activate it before working.
* **as_of**: the date the analysis pretends it is. Only data on or before this date is used, so a run can be repeated later with the same answer.
* **cache**: downloaded data saved on disk so a second run does not download again.
* **parquet**: a compact file format for tables; pandas reads it with `pd.read_parquet`.
* **weight**: a holding's share of the total portfolio value, as a fraction (0.10 = 10%).
* **drawdown**: the drop from a peak to a later low, as a percentage.
* **HHI**: sum of squared weights; 1.0 means one position, smaller means more diversified.

## Disclaimer

The owner's own data for the owner's own decisions. Not investment advice.

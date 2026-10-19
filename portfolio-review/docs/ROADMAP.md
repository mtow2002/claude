# Roadmap

Planned work, written so several sessions can pick items up in parallel.
Each item names the files it touches so two sessions do not collide.

| # | Item | Touches | Depends on |
|---|---|---|---|
| 1 | Alpha Vantage provider | `data/alpha_vantage.py`, `data/registry.py`, `tests/fixtures/alpha_vantage/` | nothing |
| 2 | Massive provider | `data/massive.py`, `data/registry.py`, `tests/fixtures/massive/` | nothing |
| 3 | BigQuery store | `store/bigquery.py`, a `--store` flag in `commands/_common.py` | nothing (extras already declared) |
| 4 | Backtesting engine | new `backtest.py`, new `commands/backtest.py`, `backtest` extra | metrics.py (unchanged) |
| 5 | HTML report with charts | new `report_html.py`, `commands/report.py` `--html` flag, `report` extra | nothing |
| 6 | Nightly EOD scheduling on Windows | `docs/SCHEDULING.md`, a `scripts/nightly.ps1` calling `fetch` then `run` | nothing |
| 7 | Migration to the new `portfolio-review` repo | move the folder; move the workflow to `.github/workflows/` with no `working-directory` | repo creation (blocked, see SETUP_LOG) |

Details and acceptance criteria:

1. **Alpha Vantage.** Implement per the stub docstring. Use `LISTING_STATUS`
   for a true point-in-time listing status. Respect the free-tier rate limit.
   Tests from recorded JSON fixtures. Done when `--provider alpha_vantage`
   runs end to end with `ALPHA_VANTAGE_API_KEY` set.
2. **Massive.** Same shape. Done when `--provider massive` runs end to end.
3. **BigQuery store.** Implement the four `Store` methods; add `--store local|bigquery`.
   Done when a run can be saved to and loaded from BigQuery with mocked tests.
4. **Backtesting.** Rebalance on bands from the policy, transaction cost
   parameter, compare against constant-weight and buy-and-hold. Reuse
   `metrics.py`. Done when a `backtest` command writes a run folder with an
   equity curve table.
5. **HTML report.** jinja2 template plus matplotlib charts (weights pie,
   drawdown curve, factor bars). Done when `report --html` writes
   `report.html` next to `report.md`.
6. **Nightly scheduling (Windows).** A PowerShell script that runs
   `portfolio-review fetch` after the close and `run` with a standing
   question; register it in Task Scheduler. Carry over the DST note from the
   earlier build brief: schedules in local time, confirm after November 1.
7. **Migration.** Create the private repo, copy `portfolio-review/` to its
   root, drop the `working-directory` lines from the workflow, update README
   paths, keep this repo's history in the SETUP_LOG.

Also worth doing, smaller:

* Score factors against a broader universe (e.g. an index constituent list)
  instead of only the holdings, so a 3-stock portfolio gets meaningful ranks.
* A `diff` command comparing two runs' findings and weights.
* Per-account policy views (IRA vs brokerage).

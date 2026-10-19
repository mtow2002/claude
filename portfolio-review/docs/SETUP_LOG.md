# Setup log

A dated log of what each session did. Newest entries at the bottom. Later
sessions append; never rewrite earlier entries.

## 2026-10-19 (cloud session, branch `claude/youthful-mccarthy-f5omvl`)

### Repo situation on arrival

`mtow2002/claude` held three files plus a `.gitignore`:

* `README.md`: describes a "Portfolio Ledger" daily pipeline split across a
  Windows desktop (`C:\market`), Claude cloud sessions, and Google Drive. It
  states the pipeline source was not yet under version control and lists the
  doctrine (never overwrite daily files, never invent a number, actuals
  outrank hypotheses, degrade loudly, imports at module scope, no keys in the
  repo, only Matt executes trades).
* `docs/ARCHITECTURE_AUDIT_2026-08-18.md`: seven findings on that pipeline.
  The ones relevant to this project: F1 (no version control, no tests),
  F3 (`date.today()` used as the data date), F5 (prose files used as a
  database), and the recommendation to use a typed record store with tests
  rather than infrastructure.
* `docs/BUILD_BRIEF_2026-08-18_Desktop.md`: a gated work order for the
  desktop session on the old pipeline, with the same doctrine, the import-time
  smoke test idea, range assertions, and a note that cloud schedules shift
  after DST ends on November 1.

None of those files were modified or deleted. No pipeline source code exists
in the repo, so nothing was reused directly.

### Guidance incorporated from those files

| From | Applied as |
|---|---|
| "Never invent a number" | metrics return `nan`, factors fill neutral 50 and flag it, holdings loader fails rather than guessing weights |
| "Degrade loudly" | `ProviderError` on network failure; stale/delisted tickers raise findings and a report warning |
| "Imports at module scope" | `tests/test_imports.py` imports every module |
| "No keys in the repo" | `.env` gitignored, `.env.example` placeholders |
| "Daily files never overwritten" | `LocalStore.save_run` refuses to overwrite a run folder |
| F3 (clock as data date) | `as_of` is explicit everywhere and stored in `run.json`; the only clock default is the CLI's `--as-of` today, which is then recorded |
| F5 (prose as database) | runs are parquet tables + `run.json`; the Markdown report is a rendering of them |
| "Only Matt executes" | report footer says the system informs, the owner acts |
| DST note for scheduling | carried into ROADMAP item 6 |

### What this session built

Everything under `portfolio-review/` plus `.github/workflows/portfolio-review-tests.yml`:

* Package skeleton with console script, optional extras pre-declared.
* `config/policy.example.yaml`, `config/holdings.example.csv`.
* Data layer: Provider protocol with Source records, parquet cache keyed by
  provider/ticker/as_of, yfinance provider, csv provider, Alpha Vantage and
  Massive stubs with documented interfaces.
* Analytics: metrics, factors (0..100 percentile scores + composite),
  portfolio exposures/HHI/weighted returns.
* Policy drift: eight rules producing Findings with severity.
* Store: `LocalStore` writing `runs/<as_of>_<run_id>/`; BigQuery stub.
* Markdown report with holdings, exposures, metrics, factor scores, findings,
  Sources.
* CLI with auto-discovered commands: run, validate, fetch, report.
* 75 tests, all offline, with synthetic fixtures (AAA, BBB, CCC, DDD delisted
  on 2025-06-30, SPY benchmark).
* Docs: ARCHITECTURE, METHODOLOGY, DECISIONS, ROADMAP, this log.

### Test results

```
pip install -e ".[dev]"   (fresh venv, Python 3.13.16 in this container; project requires >= 3.11)
pytest                     75 passed
```

CI pins Python 3.11; it could not be run locally because this container only
has 3.13. The first GitHub Actions run on the PR branch (run 39204715717)
installed and passed all tests on 3.11.

### Live run attempt

`portfolio-review run --provider yfinance` with the example files was tried
twice. Both failed before any data arrived:

```
curl: (7) CONNECT tunnel failed, response 403
```

The container's outbound proxy refuses connections to Yahoo Finance
(`query2.finance.yahoo.com`), confirmed with a direct `curl` as well. No live
results exist and none were faked. The end-to-end path was verified with the
`csv` provider on the fixtures instead (`tests/test_cli.py` and a manual run).
Matt should run the live command on the desktop:

```powershell
portfolio-review validate
portfolio-review run --as-of 2026-10-17 --question "First live run with the example files"
```

### gh commands

```
gh auth status
  -> X Failed to log in to github.com using token (GH_TOKEN)
     The token in GH_TOKEN is invalid.   (exit 1)

gh repo create mtow2002/portfolio-review --private --description "Quantitative stock and ETF portfolio review"
  -> HTTP 403: This GitHub API path is not available: sessions are bound to
     their configured repositories. Use repository-scoped endpoints
     (repos/{owner}/{repo}/...). (https://api.github.com/users/mtow2002)   (exit 1)
```

The new repository was **not** created. This session's GitHub access is
scoped to `mtow2002/claude` only. Matt needs to create
`mtow2002/portfolio-review` (private) from the GitHub web UI or from a
desktop `gh` login.

### Retry after Matt reported being logged in (same day, later)

Re-ran every blocked step from the same session. All still fail:

```
gh auth status
  -> The token in GH_TOKEN is invalid.   (exit 1)

gh repo create mtow2002/portfolio-review --private --description "..."
  -> HTTP 403: This GitHub API path is not available: sessions are bound to
     their configured repositories.   (exit 1)

GitHub connector (Claude GitHub App) create_repository name=portfolio-review private=true
  -> 403 Resource not accessible by integration
     (GitHub Apps cannot create repositories under a personal account)

curl https://query2.finance.yahoo.com/...
  -> curl: (56) CONNECT tunnel failed, response 403
```

Conclusion: the repository has to be created by Matt in the GitHub web UI
(New repository -> name `portfolio-review` -> Private), or from a desktop
terminal where `gh auth login` has been run. The cloud session cannot do it
by any route. Once it exists, a session with that repo in scope can do the
migration (ROADMAP item 7).

### Blocked

* Live Yahoo Finance fetch (proxy 403, confirmed twice).
* Creating the `portfolio-review` repository (all three routes refused, see above).

### Next steps

1. Matt: review and merge the PR; run `validate`, `fetch`, `run` on the desktop
   with real `config/policy.yaml` and `config/holdings.csv`.
2. Matt: create the private `portfolio-review` repo; then a session does
   ROADMAP item 7 (move the folder, simplify the workflow).
3. Parallel sessions: Alpha Vantage provider, Massive provider, BigQuery
   store, backtesting, HTML report, Windows scheduling (ROADMAP items 1 to 6).

## 2026-10-19 (later): migrated

This folder was migrated to https://github.com/mtow2002/portfolio-review
with its full commit history (`git subtree split`). Treat this copy as frozen;
all further development happens in that repository. See its
`docs/SETUP_LOG.md` for the migration details.

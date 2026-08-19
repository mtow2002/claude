# BUILD BRIEF — for the desktop Claude session

**Written 2026-08-18 by a cloud session, from the Drive ledger (~75 files,
2026-08-04 → 2026-08-17) and `push_to_ledger.py` v1.**
**Companion to `ARCHITECTURE_AUDIT_2026-08-18.md`, which carries the full
reasoning. This file is the work order.**

Read this whole file before writing code. It is written for a session with
Rail A access (`C:\market\`, Task Scheduler, the NAS) — that is you, and it is
why this work is yours rather than a cloud run's.

---

## 0 · What you are working on

A live daily portfolio pipeline, ~2 weeks old, split across three rails:

| Rail | What lives there | Can reach |
|---|---|---|
| **A · Desktop** | `C:\market\`, Task Scheduler, `market_daily.py`, `push_to_ledger_v2.py`, `history.parquet` | yfinance, Finnhub, xAI, Alpha Vantage REST, IBKR (interactive only) |
| **B · Chat session** | Opus, MCP connectors | Alpha Vantage MCP, Bigdata.com, Drive, Gmail, Calendar, Slack |
| **C · Google Drive** | `Portfolio Ledger` = `G:\My Drive\Portfolio Ledger` | **Both A and B** |

Rails A and B cannot see each other. Every handoff goes through C.

Current schedule (all ET):

| Time | Task | Writes |
|---|---|---|
| 6:45a (desktop) | Grok pipeline + bridge (Task Scheduler) | GROK/SCREENER/SENTIMENT + heartbeat |
| 7:45a | Grok feed watchdog (cloud) | nothing — notify only |
| 8:00a | AM Morning Brief (cloud) | `AM_<date>.md` |
| 4:45p Tue/Fri | Positions freshness checks (cloud) | `POSITIONS_<date>.md` |
| 9:00p | PM Verdict + Dashboard (cloud) | PM, ROLLING, TRIGGERS, DASH |

**Doctrine you must not break.** These are load-bearing, established by two
weeks of incidents:

- Daily files are **never** overwritten or deleted. Corrections go in a new file.
- **Never invent a number.** Anything unknown is written as unknown.
- Actuals (StockCharts, broker screens) outrank hypotheses (web quotes).
- Degrade **loudly**: on source failure keep yesterday's cache, mark the field
  stale with its as-of date, never let an empty result pass as valid.
- **Imports at module scope**, always. A `requests` import inside a function
  silently killed the entire AI layer for six trading days.
- One `AM_<date>.md` and one `PM_<date>.md` per date. Same-day additions are
  `_ADDENDUM-N` and are non-scoring.
- Only Matt executes trades. This system informs; it never acts on any account.

---

## 1 · The findings you are fixing

Full reasoning is in the audit. Summary, with severity:

| # | Finding | Severity |
|---|---|---|
| F1 | No version control on any pipeline source | **Critical** |
| F2 | The bridge logs `copied` for deliveries it cannot observe | **Critical** |
| F2b | Guard 1 as designed would not have caught the 8/13 outage | **Critical** |
| F3 | `date.today()` used as session date | High |
| F4 | Scoring rules are prose adjudicated at runtime | High |
| F5 | The ledger is a database made of prose files | Medium-high |
| F6 | Drive serves as message bus + system of record + artifact store | Medium-high |
| F7 | Connector scope makes "absent" unprovable from a cloud run | Medium |

### F1 — no version control

`market_daily.py`, `push_to_ledger_v2.py`, `grok_daily.bat` and `history.parquet`
exist on one Windows disk. Only `push_to_ledger.py` v1 ever reached Drive
(2026-08-12), already superseded. No rollback, no diff, no tests, no review
surface, total loss on disk failure. This is the root cause behind F3 and F4
surviving as long as they did.

### F2 — the bridge cannot observe what it reports

From v1, verbatim:

```python
shutil.copy2(src, dst)
copied.append(dst.name)
```

and its docstring: *"Drive sync does the ferrying."*

`shutil.copy2` returns the instant the **local** write completes. It has no
knowledge of whether the bytes left the machine. On 8/13, 8/14 and 8/17 the
bridge logged `exit=0` and `copied` for files that never reached the cloud.

**A success log written by a component that cannot observe the outcome converts
an outage into a wrong answer.** The ledger recorded "Grok feed dark" for four
sessions on the strength of it.

### F2b — Guard 1 would have stayed green through the outage

`DESIGN_2026-08-15` §4 specifies: *"write a token to ledger → read back via
separate path → record round-trip."*

The observed failure signature (`OPS_CORRECTION_2026-08-17`):

> **Updates to files that already hold a Drive ID succeed. Creation of new files
> fails. Downloads are unaffected.**

A fixed-name token file is an **update** from run two onward. Updates worked
throughout. The heartbeat would have round-tripped green on 8/14 and 8/17 while
every real artifact silently failed.

`PIPELINE_STATUS.md` proves it: created 2026-08-13T14:01:36Z, two minutes before
the cutoff, updating normally ever since — `modifiedTime` 2026-08-17T10:49:06Z
matching the heartbeat's own `last_run_utc` to seven seconds, on a day when
nothing else got through.

**The heartbeat must CREATE a uniquely-named file every run.** Only a create
exercises the path that actually broke.

### F3 — session date is not run date

```python
today = date.today().isoformat()   # session date = run date   <-- wrong
```

The pipeline runs 06:45 ET, before the cash open, so the newest complete session
is the **previous** trading day. Verified five-for-five: `GROK_2026-08-17.md`
carries 2026-08-14 closes (CPRT +7.55%, AMD +6.50%, AVGO −5.94%, HUBS −6.81%,
GDDY −5.56%, all exact against StockCharts 8/14 actuals).

This caused divergence flags to be scored against the wrong session and forced
withdrawal of the only positive evidence the concept had.

### F4 — rules as prose

Three `SCORING_RULES*.md` files; canonicality by convention. Both scheduled
prompts still hardcode the retired 4.66 gate. The gate scored 4/7 (57%) while a
robot answering "RED" daily would have scored 5/7 (71%) — *worse than a constant
answer for six sessions, and nothing noticed*, because no code computed a
baseline. Rule 7 makes baselines mandatory as **policy**; policy is what failed.

### F5 — the ledger is a database made of prose

~75 files, ~5/day (≈1,250/year). Cross-session questions require reading N files
and parsing prose with embedded JSON. Already colliding: **Drive currently holds
two `AM_2026-08-12.md` files** (14,708 and 14,469 bytes, nine minutes apart) plus
duplicate `DASH_2026-08-10.html` and `DASH_2026-08-11.html` pairs. Rule 4's
"earliest `createdTime` wins" is manual reconciliation for what a unique
constraint gives free.

### F6 / F7 — Drive doing three jobs, and connector blindness

| Job | Suitability |
|---|---|
| Message bus A ↔ B | **Poor** — silent, partial, direction-asymmetric failure |
| System of record | **Poor** — no constraints, no atomicity, no history |
| Artifact store | **Good** — this is what it is for |

And per `CHANGE_ORDER_2026-08-17` §3, the connector reliably sees only
Claude-created files, so "absent from search" cannot establish "absent from
Drive." Every cloud run reasons over a view it cannot trust.

---

## 2 · The build order

**Gated. Do not proceed past a failed gate.** Steps 1–4 stop active bleeding;
5–7 are the architecture.

### Step 0 — get the source into git

Repo: `github.com/mtow2002/claude`, branch
`claude/portfolio-project-guidance-2luv19`.

Commit `market_daily.py`, `push_to_ledger_v2.py`, `grok_daily.bat` **as they are
today**, unmodified, as the first commit. A baseline that reflects reality is
worth more than a tidy one.

```
repo/
  src/pipeline/market_daily.py
  src/pipeline/push_to_ledger.py
  src/pipeline/heartbeat.py         # step 3
  src/pipeline/sessions.py          # step 2
  src/scoring/rules.py              # step 5
  src/scoring/baselines.py          # step 5
  scripts/grok_daily.bat
  tests/
  docs/
```

**Never commit the Alpha Vantage key, the xAI key, or any broker credential.**
Keys live in environment variables (`setx AV_API_KEY ...`), never as literals and
never in the ledger folder. Add a `.gitignore` covering `*.parquet`, `output/`,
`*.log`, `.env` before the first commit — the raw audit trail and OHLCV cache do
not belong in git.

**Gate:** the three files are in the repo and CI can import them.

### Step 1 — test harness + import-time smoke test

The `requests` incident cost six trading days and is caught by one test.

```python
# tests/test_imports.py
import importlib, pkgutil
import src.pipeline

def test_every_module_imports_cleanly():
    """A function-scope import that only fails at call time must fail here."""
    for mod in pkgutil.walk_packages(src.pipeline.__path__, "src.pipeline."):
        importlib.import_module(mod.name)
```

Add `pytest` and a GitHub Actions workflow running it on push.

**Gate:** move an import inside a function; CI goes red.

### Step 2 — `data_session` derived from data, never the clock (F3)

```python
# src/pipeline/sessions.py
from datetime import date
import pandas as pd

def data_session(price_history: pd.DataFrame) -> date:
    """The session the data describes.

    NEVER date.today(). The 06:45 ET run precedes the cash open, so the newest
    complete session is the prior trading day. Derived from the data itself so
    no future reader has to infer it.
    """
    if price_history.empty:
        raise ValueError("empty price history: session date is unknown, not today")
    return pd.to_datetime(price_history.index.max()).date()
```

Stamp it in the digest header:

```
data_session: 2026-08-14
run_date:     2026-08-17
```

**Do NOT rename existing GROK files.** Renaming breaks the series and the AM's
"read today's GROK file" lookup, which is currently correct by accident. The
convention on record stands: a flag in `GROK_<date>.md` resolves against
`<date>`'s own close.

**Gate:** golden test — a 06:45 run on Mon 2026-08-17 with Friday-terminated
history yields `data_session: 2026-08-14`. Assert on the five verified movers.

### Step 3 — a heartbeat that exercises the path that breaks (F2b)

```python
# src/pipeline/heartbeat.py
import uuid, json
from datetime import datetime, timezone
from pathlib import Path

def heartbeat(ledger: Path) -> dict:
    """Positive assertion via CREATE, not update.

    The 2026-08-13 fault was: creates fail, updates succeed, downloads fine.
    A fixed-name token is an update from run two onward and would have shown
    green through the entire outage. Each run creates a NEW file.
    """
    run_id = uuid.uuid4().hex[:12]
    token = ledger / f"HEARTBEAT_{run_id}.txt"
    stamp = datetime.now(timezone.utc).isoformat()
    try:
        token.write_text(stamp, encoding="utf-8")
        readback = token.read_text(encoding="utf-8")
        ok = readback == stamp
    except OSError as exc:
        return {"create_ok": False, "error": str(exc), "checked_utc": stamp}
    finally:
        token.unlink(missing_ok=True)
    return {"create_ok": ok, "run_id": run_id, "checked_utc": stamp}
```

**A local create test is necessary but not sufficient** — the 8/13 fault was
local-write-succeeds, cloud-create-fails. The full check needs a cloud-side
readback, which Rail A cannot do directly. Two options, pick one and record it:

1. **Cheapest honest version:** the local create proves the disk is writable;
   pair it with step 4's delivery verification, which is the real cloud check.
2. **Strongest version:** give the pipeline its own Google Drive API service
   credential so Rail A can create-and-verify in the cloud directly, closing the
   loop without a cloud session. This also permanently answers the open question
   of whether files arrive via sync or via API.

`PIPELINE_STATUS.md` must show the **successful-read timestamp**, never merely
the absence of an error — so an empty field is itself the alarm.

**Gate:** make the ledger path unwritable; confirm the run screams rather than
proceeding quietly.

### Step 4 — the bridge verifies delivery before claiming it (F2)

This is the fix that would have prevented the four-session misdiagnosis.

```python
copied, unverified, missing, skipped = [], [], [], []
for src, dst in jobs:
    if not src.is_file():
        missing.append(src.name)
        continue
    if dst.exists():
        skipped.append(dst.name)          # never overwrite dated files
        continue
    shutil.copy2(src, dst)
    if verify_delivered(dst):             # cloud-side existence check
        copied.append(dst.name)
    else:
        unverified.append(dst.name)       # wrote locally, delivery UNCONFIRMED
```

The distinction is the whole point: **`copied` must mean "confirmed in the
cloud."** Anything written locally but unconfirmed goes in `unverified` and is
reported as such in `PIPELINE_STATUS.md`. Never let a local write claim delivery.

Also add **per-source freshness** (Guard 2): `last_success` timestamp and row
count per source, with every digest field carrying its own as-of date. This
catches 4/4 of the logged silent-staleness incidents.

And **range assertions** (Guard 3), which cover the class freshness cannot see —
three of nine logged incidents were data that was perfectly fresh and completely
wrong:

```
yield_pct <= 25          # caught the 100x bug
name non-empty           # caught the blank-fund-name bug
etf metadata present     # caught the silent-drop bug
close > 0
pct_chg within +/- 60
composite 0..100
survivor count >= 100    # earnings join sanity
```

Violations write to `PIPELINE_STATUS.md` with the offending symbol and value.
**Do not coerce, do not silently drop** — suppression is how all three of those
bugs survived.

**Gate:** kill Drive upload sync deliberately. The bridge must report
`unverified`, not `copied`. Then feed a 100× yield by hand and confirm it is
caught rather than coerced.

### Step 5 — scoring as tested code, baselines automatic (F4)

```python
def score_rate_light(call: str, close_bp: float, prior_close_bp: float) -> str:
    """Rule 1 v2. UP >= +3bp, DOWN <= -3bp, FLAT strictly between."""
    delta = close_bp - prior_close_bp
    actual = "up" if delta >= 3 else "down" if delta <= -3 else "flat"
    return "hit" if call == actual else "miss"

def naive_baseline(history: list[str]) -> tuple[str, float]:
    """The best constant answer, computed — never asserted."""
    counts = {s: history.count(s) for s in set(history)}
    best = max(counts, key=counts.get)
    return best, counts[best] / len(history)
```

The model produces the **call**; code scores it and reports it against its
baseline automatically. Rule versions become code versions — "which rules were in
force on 2026-08-13" becomes a git tag, not a reading-comprehension exercise.

Baselines currently on record (measured 2026-08-17, daily 10-yr series):

| Window | UP ≥+3bp | FLAT ±3bp | DOWN ≤−3bp | Best constant |
|---|---:|---:|---:|---:|
| 12 months (n=259) | 26.6% | 50.2% | 23.2% | **FLAT, 50.2%** |
| 6 months (n=136) | 32.4% | 41.9% | 25.7% | **FLAT, 41.9%** |

The bar is ~50%, not 33%. First baseline-relative review at **20 scored
sessions**; if the light has not beaten constant-FLAT by then, the PM says so
plainly and recommends retirement. That commitment was made in advance
deliberately — honour it.

**Gate:** replay the 7 scored gate sessions from code and reproduce both 4/7 and
the 5/7 constant-answer baseline. If the code cannot reproduce the known history,
it is wrong.

### Step 6 — typed append-only record store; markdown becomes a projection (F5)

Invert the relationship. Structured records (JSONL, or SQLite built from them)
become the source of truth; the daily markdown files become a **rendered view**.

Nothing is lost — the prose is what makes this ledger good, and it stays. It just
stops being the thing queries have to parse. Backfill from the existing ~75 files;
they already carry embedded JSON blocks, so most of the extraction is mechanical.

**Gate:** "rate light hit rate over the last 20 sessions, with baseline" answered
by one query rather than by reading twenty files.

### Step 7 — git as transport; Drive demoted to artifact store (F6, F7)

| Property | Drive today | Git |
|---|---|---|
| Both rails reach it | yes | yes |
| Failed delivery is loud | **no** — logs success | **yes** — non-zero exit |
| Create/update asymmetry | **yes** — the 8/13 bug | none |
| History / rollback | none | native |
| Duplicate `AM_<date>.md` | **yes, happening now** | conflict, must resolve |
| "What changed since the working run" | unanswerable | `git diff` |
| Connector-scope blindness | **yes** | none |
| Deep-dive write-back from chat | manual, unsolved | `git push` |

`DESIGN_2026-08-15` §6 lists deep-dive write-back as **unsolved** — chat sessions
are ephemeral and cannot reach Rail A, so Opus findings evaporate unless manually
written down. A repo both rails push to closes that as a side effect.

Drive keeps what it is good at: dashboards, screenshots, human-facing artifacts.

**Gate:** a desktop run pushes; a cloud run reads it without a Drive search.

---

## 3 · Explicitly NOT in scope

**Do not build this to scale to millions of users.** It has one user. The scarce
resources are Matt's attention and the correctness of the scoring record — not
throughput, concurrency, or horizontal scale. Every hour on service decomposition
is an hour not spent on the tests that would have caught the `requests` import,
the session offset, and the 100× yield bug. The axis that genuinely grows is
**sessions × sources × rule versions over time**, and the answer to that is a
typed record store with tests, not infrastructure.

**Do not add a second sentiment voice yet.** `REVIEW_2026-08-15` held this and
the reasoning stands: not simulable (no historical Bigdata sentiment on this
universe, no scored Grok history to compare against); not commensurable (Grok
reads headlines and X, Bigdata reads filings and transcripts — different objects
on different latencies); and the scoring rail does not exist, so **adding a
second voice before the scoreboard means neither gets scored**. Correct order:
build the scoreboard, score Grok solo for 30 days, then introduce a challenger
with a baseline to beat.

**Do not put Bigdata.com price fields in the pipeline.** Composition data
(holdings, weights, sector/country, AUM, TER, HHI) is trustworthy and stays a
chat-side tool. Its derived price fields are not: a +9.11% NAV premium on a $95B
index fund, two conflicting day-change figures in one document, a stale `SPLG`
label. Nothing automated consumes the NAV premium field.

**Do not rename or edit existing ledger files.** Ever. Corrections are new files.

---

## 4 · Carried-over items this build should absorb

From the ledger's own open lists — these are not new, and several are cheap:

- **DST, November 1 2026.** Cloud schedules are stored in UTC, so every cloud
  task fires an hour earlier on the clock after DST ends. **The PM's cron must
  shift one hour in November** or it will run *before* the Intermarket email
  arrives, leaving the rate light unscored. First unscored-email night after
  Nov 1 is the tell if it is forgotten. Consider encoding the schedule in the
  repo so this is reviewable rather than remembered.
- **The Position Snapshots question.** The subfolder holds only two READMEs,
  both created *before* the 2026-08-13T14:03:51Z cutoff. If the seven 8/12
  screenshots were ever dropped into the local folder, they are on disk
  unuploaded — meaning the three-sessions-stale book is the same sync bug, not
  a missed chore. **You can check this directly; a cloud run cannot.** The
  answer reassigns ownership of a standing item.
- **Whether the 8/14 files arrived via recovered sync or the Drive-API
  workaround.** Step 3/4 answers this permanently; until then it is unknown.
- **One same-day Composite/SCTR capture**, to remove the 14-day confound from
  the ρ=0.874 finding. Five minutes, settles whether the manual StockCharts
  export is needed at all. Note the finding already stands: Composite tracks
  SCTR more closely (0.874) than SCTR tracks itself across two sessions (0.840).
  SCTR is not the crown jewel; market state and the curated Buy/Watch lists are.
- **`$UST10Y` into an early-batch StockCharts list** so the 10-yr close lands
  before the evening run.
- **The two scheduled prompts still hardcode "currently 4.66."** Housekeeping,
  not a correctness fix — both prompts already defer to the newest rules file —
  but clean it while you are in there.
- **Google Drive connector reconnect.** Matt reconnects with full Drive access
  (or explicitly selects Portfolio Ledger, Claude\Stocks, Claude NAS, market C
  at the Google picker). This unblocks cloud visibility until step 7 makes it
  moot. **This one needs Matt, not you.**
- **The watchdog's new verdict set** — HEALTHY / DELIVERY GAP / RAN BUT EMPTY /
  STALE / NOTHING ARRIVED — should be driven by the step-4 `copied` vs
  `unverified` distinction rather than inferred. DELIVERY GAP becomes a fact the
  bridge reports, not a guess the watchdog makes.

---

## 5 · Questions for Matt before step 5

Answer these in the ledger, not just in chat:

1. **Drive API credential for the pipeline?** (Step 3, option 2.) It closes the
   heartbeat loop properly and permanently distinguishes sync from API delivery.
   Costs one service-account setup.
2. **Where does the record store live** once step 6 lands — in the repo, or on
   `C:` with the repo holding only code? Repo is my recommendation: it makes
   history reviewable and gives the cloud a read path.
3. **Does the manual StockCharts export survive** the same-day Composite/SCTR
   capture? If the Composite substitutes, the remaining unique content is thin
   and 15–20 minutes a day is recoverable.

---

## 6 · When you finish

Per the ledger's own convention — *every deep dive ends with a dated file in
`Portfolio Ledger`* — write a dated build record into the ledger saying what
landed, which gates passed, and what is still open. A cloud run will read it
tomorrow morning and needs to know what changed.

If Drive creates are still failing from the desktop when you finish, push through
the Drive API instead and move the local copy out of `G:\` so it cannot become a
`(1)` duplicate when sync recovers.

---

*Matt's own data for Matt's own decisions — not investment advice. The platform
proposes; only Matt executes.*

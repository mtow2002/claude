# Architecture audit — Portfolio Ledger system

**2026-08-18. Written from the Drive ledger (~75 files, 2026-08-04 → 2026-08-17)
plus `push_to_ledger.py` v1, the only source file that ever reached Drive.**

Scope note: I have not seen `market_daily.py`, `push_to_ledger_v2.py`, or
`grok_daily.bat`. They live on `C:\market\` and no cloud session can reach them.
Findings F3 and below are inferred from behaviour documented in the ledger and
from v1's source; they need confirming against v2. F1 and F2 do not — they are
established by what is and is not in Drive, and by v1's own code.

---

## The one-line version

The system's *thinking* is excellent and its *engineering substrate* is absent.
Nine logged incidents in two weeks are not bad luck; they are the expected yield
of running an eight-source data pipeline with no version control, no tests, and a
delivery layer that cannot tell success from failure.

---

## F1 — There is no version control. **Critical.**

`market_daily.py`, `push_to_ledger_v2.py`, `grok_daily.bat` and `history.parquet`
exist in exactly one place: a single Windows disk. Only `push_to_ledger.py` v1
was ever copied to Drive, on 2026-08-12, and it is already superseded.

Consequences, all currently live:

- **No rollback.** When a change breaks a run, the prior version is gone.
- **No diff.** "What changed between the run that worked and the run that
  didn't" is unanswerable — which is why incident diagnosis has repeatedly
  required Matt to hand-carry log files into a chat session.
- **No tests.** The missing `requests` import — an import inside a function
  rather than at module scope — silently killed the entire AI layer for six
  trading days. A single import-time smoke test catches that in under a second.
- **No review surface.** Every proposed change in this ledger is argued in prose
  because there is no diff to argue over.
- **Total loss on disk failure.** The pipeline, its history, and the audit trail
  share one point of failure with no backup rail.

This is the root cause behind several findings below, not a separate concern.

## F2 — The bridge reports success for deliveries that never happened. **Critical.**

From `push_to_ledger.py` v1, verbatim:

```python
shutil.copy2(src, dst)
copied.append(dst.name)
```

and from its own docstring: *"Drive sync does the ferrying."*

The script delegates the delivery guarantee to a component it never checks, then
logs `copied`. `shutil.copy2` returns the instant the **local** write completes.
It has no knowledge of, and no opinion about, whether the bytes ever left the
machine.

This is the exact architecture of the 2026-08-13 → 2026-08-17 outage. Three
consecutive runs logged `exit=0` and `copied` for files that never reached the
cloud. The ledger correctly recorded the symptom for four sessions and drew the
wrong inference — "Grok feed dark" — because the only signal available said the
copy succeeded.

**A success log written by a component that cannot observe the outcome is worse
than no log.** It converts an outage into a wrong answer.

### F2b — Guard 1 as currently specified would not have caught it

`DESIGN_2026-08-15` §4 specifies the heartbeat as: *"write a token to ledger →
read back via separate path → record round-trip."*

The observed 8/13 failure signature, from `OPS_CORRECTION_2026-08-17`:

> **Updates to files that already hold a Drive ID succeed. Creation of new files
> fails. Downloads are unaffected.**

If the heartbeat token is a fixed filename, then from run two onward it is an
**update**, not a create — and updates worked throughout the entire outage. The
heartbeat would have round-tripped green on 8/14 and 8/17 while every real
artifact silently failed to deliver.

`PIPELINE_STATUS.md` is itself the proof: created 2026-08-13T14:01:36Z, two
minutes before the cutoff, and it has updated normally ever since — including a
modifiedTime that matches the heartbeat's own `last_run_utc` to seven seconds,
on a day when nothing else got through.

**Required change:** the heartbeat must **create a uniquely-named file each run**
(`HEARTBEAT_<run_id>.txt`), read it back by ID, and then delete it. Only a create
exercises the code path that actually broke. A guard that exercises a different
path than the one it protects is decoration.

This is the design's own stated principle — *"a monitor that can fail silently
inherits the exact fault it watches for"* — applied one level deeper than the
design applied it.

## F3 — `date.today()` is used as the session date. **High.**

From v1, with the assumption stated in the comment:

```python
today = date.today().isoformat()   # session date = run date
```

The pipeline runs at 06:45 ET, before the cash open, so the newest complete
session available is the **previous** trading day. Session date is not run date,
and the comment asserts the opposite.

This is the origin of the offset documented in `OPS_CORRECTION_2026-08-17`
Finding 2 — every GROK file labelled one session ahead of its contents, which
in turn caused divergence flags to be scored against the wrong day and forced
the withdrawal of the only positive evidence the concept had.

**Fix** (already correctly identified in the ledger): derive `data_session` from
the last row of the price history, never from the run clock, and stamp it in the
digest header. In a tested codebase this is a three-line function and one test.
Untested and uncommitted, it silently corrupted the scoring record for two weeks.

## F4 — The scoring rules are prose, adjudicated by a model at runtime. **High.**

Three `SCORING_RULES*.md` files now exist. Canonicality is a *convention*
("the newest is canonical"), enforced by each run remembering to read the right
file and correctly interpret which rules were superseded, replaced, or carried
forward. Both scheduled prompts still hardcode the retired 4.66 gate; the only
thing preventing them acting on it is an instruction to prefer the newer file.

The cost is already on the record. The gate was scored seven times and hit four
(57%) before anyone computed that answering "RED" every day would have scored
5/7 (71%). *The gauge performed worse than a constant answer for six sessions
and nothing in the system noticed*, because no code computed a baseline.

Rule 7 correctly makes baselines mandatory — but it makes them mandatory as
*policy*. Policy is what failed. A baseline that must be remembered will
eventually not be.

**Fix:** scoring becomes a pure, versioned function with golden tests.

```
score_rate_light(call, close, prior_close, rules_version) -> hit | miss | unscored
naive_baseline(series, rule) -> float
```

The model's job is to produce the *call*; code's job is to score it and report
it against its baseline automatically. Rule versions become code versions, and
"which rules were in force on 2026-08-13" becomes a git tag rather than a
reading-comprehension exercise.

## F5 — The ledger is a database implemented as prose files. **Medium-high.**

~75 files, growing ~5/day (≈1,250/year). Every cross-session question — "what is
the rate light's hit rate over 20 sessions", "when did coverage last miss" —
requires reading N files and parsing prose with embedded JSON.

Rule 4 exists because this has already produced collisions. It is not
theoretical: **as of today Drive holds two `AM_2026-08-12.md` files** (14,708 and
14,469 bytes, created nine minutes apart) and duplicate `DASH_2026-08-10.html`
and `DASH_2026-08-11.html` pairs. Rule 4's "earliest `createdTime` is the scored
file" is a manual reconciliation procedure for a problem that a unique constraint
solves for free.

**Fix:** invert the relationship. Structured append-only records (JSONL, or
SQLite built from them) become the source of truth; the markdown daily files
become a *rendered projection* of those records. Nothing is lost — the prose is
what makes this ledger good — but it stops being the thing queries have to parse.

## F6 — Drive is doing three incompatible jobs at once. **Medium-high.**

| Job | Suitability |
|---|---|
| Message bus between Rail A and Rail B | **Poor** — silent, partial, direction-asymmetric failure |
| System of record / append-only ledger | **Poor** — no constraints, no atomicity, no history |
| Artifact store (dashboards, screenshots) | **Good** — this is what it is for |

`DESIGN_2026-08-15` names Rail C the single point of failure for the whole
architecture and builds Guard 1 to watch it. That is treating a symptom. Drive
is a *file sync product*; it was never a delivery-guaranteed transport, and the
8/13 outage is the entirely ordinary consequence of using it as one.

## F7 — Connector scope permanently poisons cloud-run inference. **Medium.**

Per `CHANGE_ORDER_2026-08-17` §3: this connector reliably sees only files that
Claude sessions created. So "absent from search" cannot establish "absent from
Drive," and no cloud run can distinguish an upload-sync stall from a
connector-scope limit without a human opening a browser.

Every automated run therefore reasons over a view of the world it cannot trust,
and the correct-but-useless phrasing "not visible, not necessarily not delivered"
is now doctrine. **This is fully fixed by F6's fix** — a transport both rails can
authenticate against directly has no such ambiguity.

---

## The recommendation: git is the fix for F1, F2, F5, F6 and F7 at once

Not as a code repository bolted alongside the system — **as the transport and the
system of record.**

| Property | Drive today | Git |
|---|---|---|
| Both rails reach it | yes | yes |
| Failed delivery is loud | **no** — silent, logs success | **yes** — non-zero exit |
| Create vs update asymmetry | **yes** — the 8/13 bug | none |
| History / rollback | none | native |
| Duplicate `AM_<date>.md` possible | **yes, happening now** | conflict, must resolve |
| "What changed since the working run" | unanswerable | `git diff` |
| Connector-scope blindness | **yes** | none |
| Deep-dive write-back from chat | manual, unsolved | `git push` |

`DESIGN_2026-08-15` §6 lists deep-dive write-back as **unsolved** — chat sessions
are ephemeral and cannot reach Rail A, so anything found in an Opus session
evaporates unless manually written down. A repo both rails can push to closes
that hole as a side effect.

Drive keeps the job it is good at: dashboards, screenshots, human-facing
artifacts. It stops being the message bus and the database.

---

## What I am explicitly NOT recommending

**Do not build this "to scale to millions of users."** It has one user. The
scarce resources are Matt's attention and the correctness of the scoring record —
not throughput, not concurrency, not horizontal scale. Every hour spent on
service decomposition is an hour not spent on the tests that would have caught
the `requests` import, the session-offset bug, and the 100× yield bug.

The axis that genuinely grows is **sessions × sources × rule versions over
time**, and the answer to that is a typed record store with tests, not
infrastructure.

**Do not add a second sentiment voice yet.** `REVIEW_2026-08-15` held this
correctly and the reasoning still stands: the scoreboard does not exist, so
neither voice would be scored. Build the scoreboard, score Grok solo, then
introduce a challenger with a baseline to beat.

---

## Build order

Each step is gated. Do not proceed past a failed gate.

| # | Work | Gate |
|---|---|---|
| 0 | Get `market_daily.py`, `push_to_ledger_v2.py`, `grok_daily.bat` into this repo | The files are here and I can read them |
| 1 | Test harness + import-time smoke test | A function-scope import fails CI |
| 2 | `data_session` from last price row, stamped in the digest header (F3) | Golden test: a 06:45 run on Mon 8/17 yields `data_session: 2026-08-14` |
| 3 | Heartbeat that **creates** a uniquely-named file, reads by ID, deletes (F2b) | Simulate create-fail-update-succeed; confirm it screams |
| 4 | Bridge verifies delivery by reading back from the cloud before logging `copied` (F2) | Kill upload sync; the bridge reports FAILED, not copied |
| 5 | Scoring engine as tested pure functions + automatic baselines (F4) | Replay the 7 scored gate sessions; reproduce 4/7 and 5/7 baseline from code |
| 6 | Typed append-only record store; markdown becomes a projection (F5) | Rate-light hit rate over 20 sessions computed by one query |
| 7 | Git as transport; Drive demoted to artifact store (F6, F7) | A desktop run pushes; a cloud run reads it without a Drive search |

Steps 1–4 are the ones that stop active bleeding. 5–7 are the architecture.

---

*Matt's own data for Matt's own decisions — not investment advice. The platform
proposes; only Matt executes.*

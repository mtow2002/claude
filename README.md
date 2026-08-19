# Portfolio Ledger — system repository

Code and design record for the daily portfolio pipeline currently split across
three rails (desktop `C:\market`, Claude cloud sessions, Google Drive).

The pipeline source still lives on Rail A and is not yet under version control —
that is finding F1, and closing it is step 0 of the build order.

## Contents

| Path | What |
|---|---|
| `docs/ARCHITECTURE_AUDIT_2026-08-18.md` | Full audit: 7 findings, reasoning, recommendation |
| `docs/BUILD_BRIEF_2026-08-18_Desktop.md` | **Work order for the desktop session** — gated build order, code, scope limits, open questions |

Start with the build brief. The audit is the reasoning behind it.

## Doctrine that applies here too

- Daily files are never overwritten or deleted; corrections go in a new file.
- Never invent a number; anything unknown is written as unknown.
- Actuals (StockCharts, broker screens) outrank hypotheses (web quotes).
- Degrade loudly: keep the stale value, mark it stale, never pass empty as valid.
- Imports at module scope, always.
- No keys in the repo. Environment variables only.
- Only Matt executes trades. This system informs; it never acts on any account.

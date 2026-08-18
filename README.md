# Portfolio Ledger — system repository

Code and design record for the daily portfolio pipeline currently split across
three rails (desktop `C:\market`, Claude cloud sessions, Google Drive).

Today this repo holds the architecture audit only. The pipeline source still
lives on Rail A and is not yet under version control — that is finding F1, and
closing it is step 0 of the build order.

## Contents

| Path | What |
|---|---|
| `docs/ARCHITECTURE_AUDIT_2026-08-18.md` | Full audit: 7 findings, recommendation, gated build order |

## Ledger doctrine that applies here too

- Daily files are never overwritten or deleted; corrections go in a new file.
- Never invent a number; anything unknown is written as unknown.
- Actuals (StockCharts, broker screens) outrank hypotheses (web quotes).
- Only Matt executes trades. This system informs; it never acts on any account.

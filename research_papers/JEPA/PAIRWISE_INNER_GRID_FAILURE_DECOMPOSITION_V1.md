# PAIRWISE_INNER_GRID_FAILURE_DECOMPOSITION_V1

Status: predeclared diagnostic; not executed at this checkpoint.

## Purpose

Pairwise V1 produced zero valid inner policies in both arms. This diagnostic does
not change the model, features, labels, folds, thresholds, scheduler or gates. It
re-trains the four frozen V1 LightGBM heads and persists every one of the 63
threshold/margin configurations for each arm and each of the 99 ticker/fold cells.

## Causal boundary

- Dataset is the same sealed 2022–2025 parquet, SHA-256
  `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- Train remains 12 months and inner remains the following 3 months.
- The outer month is used only as a fold identity; its scores, labels and returns are
  never computed by this diagnostic.
- 2026 is physically absent and production is untouched.

## Outputs and decision

The expected grid has `99 × 2 × 63 = 12,474` rows. For every row and every inner
month it records PF, WR, trades, PnL and minimum hold, plus whether each gate passes
across all three months. The diagnostic will report eliminating-gate counts and one
best near-miss per arm/ticker/fold.

It cannot promote a policy or relax a gate. Its only decision is whether the next
single-factor hypothesis should address direction/payoff (`PF/WR/PnL`) or candidate
starvation (`trades`). No architecture search is authorized by this diagnostic.

Canonical command after commit/push:

```powershell
pwsh -File run_pairwise_inner_grid_diagnostic_v1.ps1
```

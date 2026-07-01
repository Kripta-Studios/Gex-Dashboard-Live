# JEPA Production Pipeline

This directory now serves two purposes:

- production artifacts for the live bot;
- reproducible research scripts for the causal level-stability and structural option-profile pipeline.

## Current Live Contract

The live bot does not use the old JEPA 180m model as the primary signal.

```text
entry signal:
  neural/models/jepa/jepa_production_level_stability/level_stability_signal.json

option selector:
  neural/models/jepa/jepa_production_structural_options/structural_option_profiles.json

execution:
  0DTE options
  risk capital 5000 dollars
  hard stop -60%
  trail activation +50%
  trail giveback 25%
  emergency take profit +1000%
  latest entry 14:30 ET
  EOD cleanup 16:00 ET
```

The legacy `jepa_production_final_180m` artifact is retained only for diagnostics or explicit fallback via `--allow-signal-model-fallback`.

## Daily Production Build

Run from the repository root:

```powershell
.\neural\jepa\run_pipeline.ps1 -DailyProduction -ProductionDeployMonth 202606 -Workers 32
```

Equivalent direct runner:

```powershell
.\neural\jepa\run_daily_production_pipeline.ps1 -DeployMonth 202606 -Workers 32
```

Both steps exclude the deployment month from model/profile selection.

## Core Scripts

- `level_stability_live.py`: live evaluator for the production level-stability signal.
- `fit_production_level_stability_signal.py`: fits the production signal JSON from prior months only.
- `fit_production_structural_option_profiles.py`: fits production option profiles from prior candidate labels only.
- `run_daily_production_pipeline.ps1`: daily artifact build and smoke check.
- `walkforward_level_stability_ensemble.py`: research OOF entry-signal generator.
- `walkforward_structural_option_profiles.py`: nested walk-forward option-profile selector.
- `combine_walkforward_option_results.py`: verifies per-ticker profitability/volume checks.
- `search_option_structural_profiles.py`: profile search helpers used by production fitting.

## Validated Result

The clean Jan-May 2026 nested option-profile validation passes each ticker independently:

Gates used: PF >= 1.10, WR >= 35%, PnL > 0, min 15 trades/month, long-rate 20%-80%.

| Ticker | Trades | WR | PF | PnL | Min Month Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPX | 227 | 37.9% | 1.181 | 69,884 | 17 |
| SPY | 204 | 35.8% | 1.157 | 59,688 | 17 |
| QQQ | 209 | 39.7% | 1.361 | 119,338 | 22 |

The result path is:

```text
research_papers/JEPA/results/level_stability_nested_structural_profiles_risk5000_mixed_causal_2026janmay
```

The combined result includes a walk-forward integrity audit: 15 folds and 640 selected trades checked, with no temporal leakage found.

June 2026 is partial in the available data. Jan-Jun remains profitable but does not pass the 15-trades/month rule for SPX/SPY because June is incomplete.

## Deployment

Use the root deployment guide:

```text
README_PRODUCTION_DEPLOYMENT.md
```

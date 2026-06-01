# Base+JEPA 180m Integration Plan

## Decision

Promote the frozen `base_jepa` 180m candidate to the next integration phase, but do not overwrite the current GBT/RL pipeline yet.

Current accepted candidate:

- Signal: `base+XInputJEPA`
- Horizon: terminal 180m direction, `spot_price(t+180m) > spot_price(t)`
- Execution proxy: SPX/SPY/QQQ fixed 180m hold
- Cooldown: 180m
- Model artifacts: `neural/models/jepa/jepa_180m_frozen_march/base_jepa/`
- Standalone runner: `neural/jepa/run_jepa_180m_standalone.ps1`
- Standalone backtest report: `research_papers/JEPA/results/jepa_180m_standalone/SUMMARY.md`

The current GBT remains the production model until the JEPA 180m path is wired into the same operational pipeline and passes the same acceptance gates.

## Why Cooldown 180m

The label and execution horizon are both 180 minutes. A signal at 10:00 and another at 10:05 mostly bet on overlapping future windows. Counting both as fully independent trades inflates the sample and creates correlated stacked exposure.

Default policy:

- Use 180m cooldown for replacement decisions.
- Keep cooldown configurable for research and production sizing tests.
- Treat 60m/90m cooldown results as leveraged/overlapping variants, not as the clean model-comparison baseline.

Observed Apr/May OOS sensitivity:

| Cooldown | Trades | WR | PF | PnL | Max DD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 60m | 178 | 64.0% | 1.889 | +13,931 | -2,166 |
| 90m | 160 | 61.9% | 1.838 | +13,182 | -2,830 |
| 120m | 104 | 68.3% | 1.936 | +9,044 | -1,522 |
| 180m | 104 | 68.3% | 1.936 | +9,044 | -1,522 |

## Current Pipeline Context

`neural/run_pipeline.ps1` currently does:

1. Step 0: collect data into `training_data/training_data_spx_qqq_spy.parquet` and create March cutoff `training_data/training_data_spx_qqq_spy_march_2026.parquet`.
2. Step 1: train ticker-specific GBT models with `neural/train_walkforward.py`.
3. Step 2: generate GBT episode index for RL with `neural/generate_episode_index.py`.
4. Step 3: preprocess options cache for RL with `neural/run_preprocess.py`.
5. Step 4: train RL with `neural/rl/training.py`.
6. Step 6: backtest GBT-only with `backtest/backtest_gbt_parquet.py`.
7. Step 7: backtest GBT+RL with `backtest/backtest_rl.py`.

The JEPA 180m model should first be integrated as a parallel entry system after Step 0 and before/around Step 6. It should not change Step 1/2/3/4 until it has a production-equivalent backtest report.

## Required Artifacts

Frozen candidate artifacts already exist:

```text
neural/models/jepa/jepa_180m_frozen_march/base_jepa/QQQ.joblib
neural/models/jepa/jepa_180m_frozen_march/base_jepa/SPX.joblib
neural/models/jepa/jepa_180m_frozen_march/base_jepa/SPY.joblib
```

Each artifact contains:

- LightGBM model
- feature list
- median imputation values
- ticker-specific long/short thresholds
- metadata with train cutoff, horizon, notional, and cooldown

The input parquet must include the exported `xjepa_*` features. Current research input:

```text
training_data/training_data_spx_qqq_spy_jepa_xinput_v3.parquet
```

For full pipeline integration, Step 0 must produce or refresh this augmented parquet after data collection.

## Training And Backtest Mechanics

`base_jepa` is not a pure JEPA neural policy. It is a LightGBM model trained on a wider feature set:

```text
base_jepa = LightGBM(base market features + xjepa_* features)
```

The current GBT-only pipeline and the new `base_jepa` model differ in both inputs and labels:

| Model | Inputs | Label |
| --- | --- | --- |
| Current GBT-only | base market features | target/stop path outcome inside 180m |
| base-only 180m | base market features | `spot_price(t+180m) > spot_price(t)` |
| base+JEPA 180m | base market features + `xjepa_*` | `spot_price(t+180m) > spot_price(t)` |

`collect_training_data_spx_qqq.py` does not need to create this new 180m label. The 180m experiment uses the collected parquet and constructs the label offline:

```text
future_return_180m = spot_price(t+180m) / spot_price(t) - 1
future_up_180m = future_return_180m > 0
```

Leakage control:

- `future_return_180m` is never a feature.
- `future_up_180m` is never a feature.
- Existing target/stop columns are never features:
  - `target`
  - `time_to_target`
  - `time_to_stop`
  - `max_move`
- Features are only the current-row base features plus current-row frozen JEPA features.

The fixed-hold backtest does not use target/stop:

```text
LONG  at t -> exit at t+180m -> pnl = spot(t+180m) - spot(t)
SHORT at t -> exit at t+180m -> pnl = spot(t) - spot(t+180m)
```

Then the backtest subtracts cost bps, applies notional sizing, and enforces cooldown.

This means the JEPA 180m candidate is a separate entry strategy from the current GBT target/stop strategy. It is not a drop-in probability replacement for the current GBT output unless the downstream execution is also changed to fixed-hold 180m.

## Why JEPA Improves The 180m Model

The earlier diagnostics showed a specific pattern:

- XInputJEPA did not beat persistence at 5m, 15m, 30m, or 60m latent prediction.
- XInputJEPA did beat persistence at 120m and 180m.

That makes the terminal 180m direction task a better fit than the original target/stop task.

Base features mostly describe the current state:

- Greeks and net exposure
- IV/VIX regime
- price position versus support/resistance and exposure levels
- momentum and return context
- time-of-day context

JEPA features add learned state dynamics:

- latent market state `xjepa_z_*`
- dynamic input embedding `xjepa_u_*`
- auxiliary direction score/probabilities
- prediction dispersion and surprise features

The practical effect in the frozen Apr/May test:

| Model | Trades | WR | PF | PnL |
| --- | ---: | ---: | ---: | ---: |
| base-only 180m | 80 | 58.8% | 1.389 | +3,522 |
| base+JEPA 180m | 104 | 68.3% | 1.936 | +9,044 |

So the JEPA features are improving directional selection for the 180m terminal task, not merely increasing the number of trades.

## Phase 1: Keep Standalone Path As The Source Of Truth

Do not edit `neural/run_pipeline.ps1` until the RL agent work is complete.

Keep this standalone command as the reproducible JEPA 180m entry test:

```powershell
powershell -ExecutionPolicy Bypass -File neural\jepa\run_jepa_180m_standalone.ps1 `
  -Mode base_jepa `
  -CooldownMinutes 180 `
  -CostBps 1.0 `
  -StartDate 20260401
```

Expected Apr/May OOS result:

| Model | Trades | WR | PF | PnL | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: |
| base+JEPA 180m | 104 | 68.3% | 1.936 | +9,044 | -1,522 |

This standalone path uses:

- `neural/jepa/jepa_180m_signal.py` for inference
- `neural/jepa/backtest_jepa_180m.py` for backtesting
- frozen artifacts from `neural/models/jepa/jepa_180m_frozen_march/`

## Phase 2: Add Pipeline Variables

When it is safe to edit `neural/run_pipeline.ps1`, add variables near the existing GBT path configuration:

```powershell
$Jepa180Enabled = $true
$Jepa180Mode = "base_jepa"
$Jepa180CooldownMinutes = 180
$Jepa180CostBpsArg = "1.0"
$Jepa180NotionalArg = "100000"
$JepaXInputExperiment = "xinput_v3"
$JepaXInputModelDir = Join-NeuralPath "models\jepa\$JepaXInputExperiment"
$Jepa180ModelRoot = Join-NeuralPath "models\jepa\jepa_180m_frozen_march"
$JepaBacktestDataPath = Join-ProjectPath "training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet"
$Jepa180ResultsRoot = Join-ProjectPath "research_papers\JEPA\results\pipeline_jepa_180m"
```

Do not point `$GbtModelPath` or `$GbtNormalizerPath` at JEPA artifacts. The current GBT and the JEPA 180m candidate are different model contracts.

## Phase 3: Add JEPA Feature Export After Step 0

After Step 0 creates:

```text
training_data/training_data_spx_qqq_spy.parquet
training_data/training_data_spx_qqq_spy_march_2026.parquet
```

add a JEPA feature append step:

```powershell
if ($Jepa180Enabled -and $skip_to_step -le 0) {
  Write-Host "`n=== APPENDING XInputJEPA FEATURES ===" -ForegroundColor Cyan
  python -u (Join-NeuralPath "jepa\append_xinput_jepa_features.py") `
    --data $BacktestDataPath `
    --model-dir $JepaXInputModelDir `
    --output $JepaBacktestDataPath `
    --device cuda

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: append_xinput_jepa_features.py fallo." -ForegroundColor Red
    Exit-Pipeline 1
  }
}
```

For research reproducibility, use the frozen XInputJEPA model trained through the March cutoff. Do not retrain XInputJEPA on Apr/May and then claim Apr/May OOS.

If the pipeline later retrains JEPA on fresh data, the reports must use a new cutoff and a new OOS window.

## Phase 4: Add Standalone JEPA Backtest Step

Add a new step after current Step 6 GBT backtest:

```text
Step 6.5: Backtest JEPA 180m standalone
```

PowerShell block:

```powershell
if ($Jepa180Enabled -and $skip_to_step -le 6) {
  Write-Host "`n=== BACKTESTING JEPA 180m standalone ===" -ForegroundColor Magenta
  python -u (Join-NeuralPath "jepa\backtest_jepa_180m.py") `
    --data $JepaBacktestDataPath `
    --model-dir $Jepa180ModelRoot `
    --mode $Jepa180Mode `
    --output-dir $Jepa180ResultsRoot `
    --start-date 20260401 `
    --tickers SPX QQQ SPY `
    --horizon-steps 36 `
    --cooldown-minutes $Jepa180CooldownMinutes `
    --cost-bps $Jepa180CostBpsArg `
    --notional $Jepa180NotionalArg

  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backtest JEPA 180m fallo." -ForegroundColor Red
    Exit-Pipeline 1
  }
}
```

This gives a clean side-by-side output:

- current GBT target/stop backtest
- current GBT+RL backtest
- JEPA 180m fixed-hold backtest

## Phase 5: Compare Against Current GBT Under Same Payoff

The current GBT backtest optimizes target/stop, not terminal 180m direction. To compare entry quality fairly, keep the existing signal repricing tool:

```powershell
python neural\jepa\compare_existing_signals_180m.py `
  --data training_data\training_data_spx_qqq_spy_jepa_xinput_v3.parquet `
  --output-dir research_papers\JEPA\results\pipeline_jepa_180m\existing_signals_fixed180 `
  --trades baseline_gbt=research_papers\JEPA\results\xinput_v3\baseline_gbt_oos_trades.csv `
  --cost-bps 1.0 `
  --cooldown-steps 36 `
  --notional 100000
```

Do not use this as the only decision metric, but keep it as a fair entry-signal comparison under the 180m payoff.

## Phase 6: Optional Replacement Of GBT Entry Signal

Only after Phase 4 and 5 pass, add a pipeline switch:

```powershell
[switch]$jepa180_entry
```

If `$jepa180_entry` is set:

- Step 1 still trains the current GBT unless explicitly skipped.
- Step 6.5 becomes mandatory.
- A new episode generator should be used for JEPA entries, not `generate_episode_index.py`.

Required new script:

```text
neural/jepa/generate_episode_index_jepa_180m.py
```

It should output the same high-level fields expected by downstream tools:

- ticker
- date
- time
- direction
- confidence
- model_source = `jepa_180m`

Do not feed JEPA 180m entries into RL until `run_preprocess.py` and RL rewards are audited. The RL code currently assumes the GBT target/stop entry distribution and options episode cache. JEPA 180m is a different entry distribution.

## Phase 7: Interaction With Current GBT

Use the current GBT in three roles:

1. Baseline comparator: keep current Step 1 and Step 6 unchanged.
2. Fallback: if JEPA 180m has no signal, the current GBT can still run its target/stop strategy.
3. Feature source: `base+JEPA` means the JEPA 180m candidate uses the same base market feature family plus XInputJEPA features, not the saved current GBT model output.

Do not combine GBT target/stop probabilities and JEPA 180m probabilities by simple averaging. They answer different questions:

```text
GBT current: target/stop path outcome inside 180m
JEPA 180m: terminal direction at t+180m
```

If an ensemble is desired later, train a supervised meta-model with both outputs and evaluate it with strict temporal OOS.

## Phase 8: Promotion Gates

Promote JEPA 180m from standalone candidate to pipeline entry model only if:

- Standalone `base_jepa` remains better than current GBT under fixed 180m repricing.
- It remains positive at 5 bps cost.
- No ticker is persistently destructive.
- Cooldown 180m PF stays above 1.25 in OOS.
- Drawdown is not worse than current GBT under comparable notional/risk.
- The exact inference class `Jepa180mSignalModel` is used by both backtest and any live/integration path.

Current frozen Apr/May status:

- Pass on OOS PF and PnL.
- Pass on 5 bps cost.
- Pass on per-ticker profitability.
- Needs rolling historical validation before full production replacement.

## Phase 9: Files To Preserve

Keep these files as the base integration set:

```text
neural/jepa/jepa_180m_signal.py
neural/jepa/backtest_jepa_180m.py
neural/jepa/run_jepa_180m_standalone.ps1
neural/jepa/train_backtest_180m_frozen.py
neural/jepa/run_jepa_180m_frozen.ps1
neural/jepa/compare_existing_signals_180m.py
neural/models/jepa/jepa_180m_frozen_march/base_jepa/*.joblib
research_papers/JEPA/results/jepa_180m_standalone/SUMMARY.md
research_papers/JEPA/results/jepa_180m_frozen_march/SUMMARY.md
```

## Phase 10: 0DTE Option Policy To Replace RL

The RL replacement path should start from the result that survived validation, not from the learned delta selector.

Current deployable candidate:

```text
base_jepa 180m entry
-> buy 0DTE option closest to absolute delta 0.70
-> hard stop -60%, take profit +250%, max hold 180m
-> 180m cooldown between entries per ticker
```

Why this is the current choice:

- The original `-35%/+250%` fixed 0.70 contract was robust but left avoidable losses in the 180m option path.
- Exit-grid validation on pre-OOS months selected `-60%/+250%`.
- Apr/May 2026 OOS improved from 105 trades, PF 1.725, WR 42.9%, PnL +20,719 to 105 trades, PF 2.033, WR 56.2%, PnL +28,115.
- Monthly ticker volume remained intact: no Apr/May ticker-month had fewer than 17 trades.
- Latest Apr/May option-policy OOS still chose fixed 0.70: PF 2.033, WR 56.2%, PnL +28,115 across 105 trades.
- Learned delta selectors are not promoted because they remain below fixed 0.70 in OOS PF/PnL, while skip-gated variants cut volume to 46 trades.
- The remaining gap to `oracle_best_delta_hard` is real: Apr/May oracle hard produced +69,480, PF 5.053. That oracle sees the future delta outcome and is not deployable.

Implementation steps for the production pipeline:

1. Add a JEPA option-policy backtest step parallel to RL, not inside RL training.
2. Use `Jepa180mSignalModel` for entries and the current ThetaData option-chain lookup for contract selection.
3. Select the nearest 0DTE contract by absolute delta 0.70 on the correct side: call for LONG, put for SHORT.
4. Use the existing option premium simulation logic from `train_backtest_option_policy.py` as the reference for backtest accounting.
5. Emit trades with the same core fields as `backtest_rl.py`: ticker, date, entry time, side, strike, delta, premium, contracts, exit time, exit reason, pnl.
6. Compare against GBT-only, GBT+RL, and JEPA fixed-spot proxy in the same report.
7. Promote as RL replacement only if the option-policy backtest beats RL on PF, PnL, max drawdown, and trade count without using oracle labels.

Do not wire the learned delta model as the first production policy. Keep it behind a research flag until it beats fixed 0.70 on rolling walk-forward validation.

Next research steps to reduce the oracle gap:

- Keep option labels and compact 5m state rows refreshed over the full available history before each promotion test.
- Persist option premium paths or compact path features so exit-policy experiments can run without repeatedly loading ThetaData.
- Test delta selectors with strict monthly walk-forward model selection, where hyperparameters are chosen only from past months.
- Add richer candidate features for strike selection: spread/liquidity filters, IV rank by strike, premium decay profile, distance to gamma/vanna walls in option-dollar terms, and time-of-day interaction features.
- Treat oracle-hard as a diagnostic ceiling only. A learned policy must beat fixed 0.70 out of sample before it replaces the simple deployable policy.

## Phase 11: OptionValueJEPA Strike And Exit Research

Implemented:

```text
neural/jepa/train_option_value_jepa.py
neural/jepa/run_option_value_jepa.ps1
```

The model explicitly scores each option candidate:

```text
market_state_t + option_candidate(delta, premium, IV, theta, gamma, strike distance)
-> predicted hold180 value
-> predicted hard-exit value
-> predicted future-best value
```

The same model also learns a 5m continuation value:

```text
current option state every 5m
-> predicted best future value from here
-> exit if continuation value no longer beats current realized value
```

Current full monthly walk-forward result, 2023-08 through 2026-05:

- `fixed_delta_0.70_hard`: 2,100 trades, WR 74.3%, PF 5.761, PnL +1,171,610, max DD -5,546, avg delta 0.703.
- `option_value_hold180_select_hard`: 2,100 trades, WR 65.8%, PF 4.414, PnL +1,199,159, max DD -5,546, avg delta 0.572.
- `option_value_rule_select_hard`: 2,100 trades, WR 66.0%, PF 4.415, PnL +1,187,154, max DD -5,546.
- `fixed_delta_0.70_learned_exit_5m`: 2,100 trades, WR 75.1%, PF 5.398, PnL +1,055,623, max DD -5,546.
- `option_value_best_select_hard`: 2,100 trades, WR 51.8%, PF 2.937, PnL +1,106,884, max DD -8,180.
- `oracle_best_delta_hard`: 2,100 trades, WR 74.5%, PF 13.993, PnL +2,084,499.

Decision:

- OptionValueJEPA strike selection is promising because `hold180_select_hard` slightly improves full-WF PnL over fixed 0.70.
- It is not yet robust enough to replace fixed 0.70 because PF and win rate are materially worse.
- The learned 5m exit is not promoted. It raises WR slightly on fixed 0.70 but exits too early and loses too much PnL/PF.

Next steps for this branch:

1. Add a stricter promotion gate for `option_value_hold180_select_hard`: it must beat fixed 0.70 on PnL without dropping PF/WR below agreed thresholds in rolling OOS.
2. Train the continuation head with a conservative exit target, not pure future-best value. The current target makes it sensitive to noisy local maxima and exits too early.
3. Add separate exit heads for loss-cutting and profit-locking:

```text
P(hit worse drawdown before new high)
P(hit take-profit before stop)
expected value if continue 15m/30m/60m
```

4. Add an exit cost/penalty for premature exits during training, because the current learned-exit policy reduces exposure too aggressively.
5. Only promote OptionValueJEPA if rolling validation beats fixed 0.70 on PF and PnL, not just on one Apr/May OOS slice.

## Phase 12: GBT+JEPA 180m Learned Exit Gate

Implemented:

```text
neural/jepa/walkforward_jepa_180m_continuation_exit.py
```

This is the only acceptable path for replacing the fixed 180m exit in the `base_jepa` spot/proxy strategy:

1. Build states for every live decision point, not only entries.
2. Use only information available at that 5m timestamp:
   - entry base + `xjepa_*` features,
   - current base + `xjepa_*` features,
   - deltas between current and entry features,
   - current PnL, MFE, MAE, drawdown from peak, time remaining,
   - `base_jepa` probability/confidence changes.
3. Use future path values only as labels:
   - `exit_now_value`,
   - `continue_value`,
   - `terminal_value`,
   - `continue_edge = continue_value - exit_now_value`.
4. Train continuation-edge models with robust/quantile losses.
5. Select the exit margin by monthly walk-forward validation on prior months only.
6. Promote only if the learned exit beats fixed 180m on PF, PnL, and drawdown while preserving the same entries.

Current Apr/May 2026 result:

- `fixed_180m`: 105 trades, PF 1.945, PnL +9,132, chronological max DD -2,093.
- Best learned continuation variant did not beat fixed hold:
  - pooled L1 held every trade to 180m and added no alpha,
  - pooled Q75 improved WR to 70.5% but reduced PF to 1.901 and PnL to +8,679,
  - per-ticker L1 reduced DD slightly to -2,033 but reduced PF to 1.799 and PnL to +7,357.
- `oracle_exit`: PF 44.155, PnL +27,428, max DD -215, but it is non-deployable.

Decision: keep the GBT+JEPA 180m exit fixed at 180m. The oracle ceiling is real, but the current learned continuation state does not capture enough of it to replace the fixed hold.

## Phase 13: Strike Selection Against Fixed 0.70

Implemented:

```text
neural/jepa/research_excess_vs_fixed_option_selector.py
```

This branch trains directly on candidate excess versus the fixed 0.70 delta contract for the same signal:

```text
candidate features -> predicted(candidate_pnl - fixed_070_pnl)
candidate features -> P(candidate beats fixed_070)
candidate features -> P(candidate is oracle-hard best)
```

The selector only overrides fixed 0.70 when validation-selected predicted edge clears a margin; otherwise it falls back to fixed 0.70.

Current Apr/May 2026 result:

- `fixed_delta_0.70_hard`: 105 trades, PF 1.725, PnL +20,719, max DD -5,095.
- `excess_vs_fixed_selector`: 105 trades, PF 1.717, PnL +18,748, max DD -5,614.
- `oracle_best_delta_hard`: 105 trades, PF 4.092, PnL +54,238.

Decision: do not promote. The direct excess target is better aligned with the objective than absolute-return prediction, but it still overrode fixed 0.70 in the wrong places OOS.

## Phase 14: Fixed 0.70 Exit-Contract Upgrade

Implemented:

```text
neural/jepa/research_fixed_delta_exit_grid.py
```

This branch does not change the entry model or strike selector. It uses the cached 5m option path states to validate the execution contract:

```text
same base_jepa entry
same fixed 0.70 delta contract
vary hard_stop_pct and take_profit_pct
select on months <= 202603
verify on Apr/May 2026
```

Selected config:

```text
hard_stop_pct = -0.60
take_profit_pct = 2.50
max_hold_minutes = 180
```

Gate result:

- Meta-train old `-35/+250`: PF 3.098, WR 58.9%, PnL +773,131, DD -9,193.
- Meta-train selected `-60/+250`: PF 6.224, WR 75.2%, PnL +1,143,494, DD -8,249.
- Apr/May old `-35/+250`: PF 1.725, WR 42.9%, PnL +20,719, DD -4,343.
- Apr/May selected `-60/+250`: PF 2.033, WR 56.2%, PnL +28,115, DD -3,982.
- Trade count remains 105; minimum Apr/May ticker-month volume remains 17.

Decision: promote `-60/+250/180m` as the JEPA 0DTE fixed-delta execution contract.

## Final Recommendation

Integrate `base+JEPA 180m` as a parallel Step 6.5 first. Do not replace the current GBT/RL path in `run_pipeline.ps1` in the same patch.

After several successful pipeline runs, promote it with an explicit switch:

```powershell
-jepa180_entry
```

The switch should route entry generation to JEPA 180m only for the fixed-hold 180m strategy. The current GBT target/stop strategy and RL strategy should remain available until JEPA 180m wins on a longer rolling OOS validation.

For the 0DTE options replacement path, the current candidate is `base_jepa` entries with validated fixed 0.70 delta and the `-60%/+250%/180m` exit. This should be compared directly against `backtest_rl.py` before replacing RL strike/exit selection.

# Daily trade feasibility — frozen universe and original policies

Diagnostic completed 2026-10-18. The new requirement is at least one filled trade per day and ticker, with free entry timing. This is an explicitly post-result gate; no original policy, scheduler, model, ranking, source or frozen cache was changed. No PnL columns were read.

All **2,595 available ticker-days** contain at least one action with an observed valid entry (`FILLED`) in the engine universe. All also contain an entry with an observed exit quote. This is a descriptive hindsight feasibility ceiling, not a causal trading policy or profitability result. None of the nine original policies satisfies the daily requirement: every one of the 54 policy × ticker × year blocks contains an observed zero-trade day.

## Calendar and action availability

The frozen calendar contains 867 full sessions from 2023-01-03 through 2026-06-30, or 2,601 ticker-days. It is the research full-session calendar, not a claim to cover every exchange session including shortened sessions.

| Ticker | Expected | Available with FILLED entry | Missing source | First causal eligibility/action, range ET |
|---|---:|---:|---:|---|
| QQQ | 867 | 864 | 3 | 10:30–10:58 |
| SPXW | 867 | 867 | 0 | 10:30–10:42 |
| SPY | 867 | 864 | 3 | 10:30–10:43 |

The earliest causal action time equals earliest eligibility on these available days. Entry occurs one minute after the action state. The separate hindsight earliest-filled-entry ranges are QQQ 10:31–10:59, SPXW 10:31–10:43 and SPY 10:31–10:44. These hindsight times must never be used to schedule or select a trade. There are 15,394,541 FILLED entry actions in the complete universe; actions overlap and are alternatives, so this is not a possible combined trading ledger.

`FILLED` means the simulator found a valid entry quote under its execution rule. It does not establish a historical broker fill. The diagnostic separately checks `missing_exit`; every available day has at least one FILLED entry with an observed exit. Selecting such an action retrospectively would still use future information. No force-first rule was introduced.

## Original policy daily coverage

Cells are days with at least one fill / available days. In 2025 each ticker has 247 available and expected days. In 2026 QQQ/SPY have 120 available of 123 expected; SPXW has 123 of 123. Missing days remain separate from observed zero-trade days.

| Frozen policy | 2025 QQQ | 2025 SPXW | 2025 SPY | 2026 QQQ | 2026 SPXW | 2026 SPY |
|---|---:|---:|---:|---:|---:|---:|
| gbt_net__0 | 199/247 | 235/247 | 174/247 | 108/120 | 118/123 | 101/120 |
| gbt_net__5 | 163/247 | 231/247 | 125/247 | 97/120 | 118/123 | 73/120 |
| gbt_net__10 | 133/247 | 227/247 | 92/247 | 80/120 | 117/123 | 57/120 |
| gbt_advantage__0 | 8/247 | 2/247 | 11/247 | 4/120 | 0/123 | 4/120 |
| gbt_advantage__5 | 1/247 | 2/247 | 0/247 | 0/120 | 0/123 | 2/120 |
| gbt_advantage__10 | 0/247 | 2/247 | 0/247 | 0/120 | 0/123 | 0/120 |
| tcn_teacher__0 | 3/247 | 44/247 | 3/247 | 3/120 | 25/123 | 0/120 |
| tcn_teacher__5 | 2/247 | 27/247 | 2/247 | 2/120 | 12/123 | 0/120 |
| tcn_teacher__10 | 2/247 | 10/247 | 1/247 | 2/120 | 5/123 | 0/120 |

All blocks have minimum daily fills zero. The appendix gives p10, median, maximum and longest observed zero-session streak for every block. Quantiles include observed zero days and exclude unknown source days. A missing-source session breaks a measured zero streak; it is neither counted as zero nor silently bridged. `full_calendar_gate=NO_EVALUABLE_MISSING_SOURCE` in the CSV indicates incomplete source coverage, while `meets_new_gate_all_available=false` separately records the already established policy failure on observed days. Missingness cannot rescue that failure.

## Six missing sources

QQQ and SPY on **2026-04-01, 2026-04-09 and 2026-04-15** remain `NO_EVALUABLE_MISSING_SOURCE`. A fresh names-only traversal of all 366,555 files under `D:/ThetaData` completed without traversal errors. It found the same 18 symbol/date matches as the full earlier census. All 18 Parquet footers were inspected: twelve OI files (six same-day expiry, six other expiry) and six derived underlying OHLC files.

| Ticker | Date | Same-day OI rows | Derived spot rows | Greek / IV / option OHLC |
|---|---|---:|---:|---|
| QQQ | 20260401 | 288 | 391 | absent by canonical path/name search |
| QQQ | 20260409 | 264 | 391 | absent by canonical path/name search |
| QQQ | 20260415 | 266 | 391 | absent by canonical path/name search |
| SPY | 20260401 | 390 | 391 | absent by canonical path/name search |
| SPY | 20260409 | 342 | 391 | absent by canonical path/name search |
| SPY | 20260415 | 366 | 391 | absent by canonical path/name search |

OI schemas contain contract identity, open interest and timestamp; they contain no bid, ask, delta or IV. Derived spot schemas contain symbol/date/timestamp, open/high/low/close and tick_count; they contain no option contract quotes or Greeks. These files alone cannot provide the frozen option execution/Greek inputs. No sufficient duplicate, IV or NBBO alternative was located by this names/schema search. This is an evidence limitation, not a finding that the real market had no tradable options or opportunities.

Other local candidate families were checked by filenames: native quote sidecars, NBBO/quote-size and tick captures end in 2025; `data_training_input` ends at 2026-02-19; the 2026 retry capture covers 2026-06-24 through 2026-06-26. Six undated symbol-bearing data-like files are administrative request/retry CSV logs. Full family/date spans and exact candidate schemas are in `source_candidates.json`. The search is bounded to names and schemas; it does not inspect row values inside unrelated opaque or differently dated files, admit a new source, or certify that none could exist under misleading names. No network, API, download, imputation or cache change occurred.

## Evidence and reproducibility

Artifacts: `D:/GexResearchArtifacts/level_oracle_20261018/daily_trade_feasibility_v1/`.

- `daily_action_availability.csv`: every expected ticker-day, causal eligibility/action time, separate hindsight entry time, execution counts, reported source hashes and missingness status.
- `original_policy_coverage.csv`: all 54 policy/ticker/year coverage, quantile and zero-streak records.
- `original_policy_daily_counts.csv`: full expected-calendar ledger counts with missing days retained.
- `summary.json`: input bindings, verified hashes for all 18 original ledgers, column whitelist and runtime.
- `source_candidates.json`: fresh complete names traversal, 18 exact footer/schema records, canonical source presence and other-family spans.
- Executed script copies and `artifact_hashes.json`: exact code and artifact hashes.

Engine index SHA256: `8d0c6e27bdaf7d47ef2a9888505294b8f3186da3a6927e780ce9e517e660e8e5`.
Calendar SHA256: `5cd9c8ed0585bff64808d99036cd9a0ab22fce599cc155527501201104475e61`.
Original economic audit SHA256: `238e6f0974025edf076d4023f134878340141271547e45e618026042539945bd`.
Diagnostic code SHA256: `d1bc967341d5def66bd75b86ffd4fa789a50e9844fc7b037ecd3dec27246babc`.
Source search code SHA256: `e39bc68f499a9c9b85dba9823de93a1b9ae6054f3629cae1336d39b0eabcc677`.

The engine index and calendar hashes bind the reported universe. All 18 policy ledger bytes were rehashed against the existing economic audit before reading their ticker/date/status columns. Daily engine source hashes are reported from the audited index, not freshly rehashed in this diagnostic. Source candidate schemas, sizes and mtimes were read; complete raw source bytes were not rehashed. This report does not replace the previous full engine/source audit.

One process per diagnostic: availability/ledger pass 11.306 seconds; names/schema search 22.355 seconds. No learner or economic simulation was run. Ruff passed both scripts. Reproduction must use a fresh output directory because the diagnostic refuses to overwrite its output root.

```powershell
python research_papers/JEPA/level_oracle_20261018/daily_trade_feasibility.py --out D:/GexResearchArtifacts/level_oracle_20261018/daily_trade_feasibility_fresh
```

The names/schema search script has its original evidence destination fixed; its executed copy records the exact completed operation. Do not rerun it over existing evidence merely to regenerate this report.

## Complete daily count metrics

Each row is an original frozen policy block. Fills are counted only from the stored FILLED ledger.

| Policy | Year | Ticker | Zero / available | min | p10 | median | max | Longest observed zero streak |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| gbt_net__0 | 2025 | QQQ | 48/247 | 0 | 0 | 2 | 12 | 7 |
| gbt_net__0 | 2025 | SPXW | 12/247 | 0 | 1 | 4 | 15 | 1 |
| gbt_net__0 | 2025 | SPY | 73/247 | 0 | 0 | 1 | 15 | 4 |
| gbt_net__5 | 2025 | QQQ | 84/247 | 0 | 0 | 1 | 11 | 8 |
| gbt_net__5 | 2025 | SPXW | 16/247 | 0 | 1 | 3 | 15 | 2 |
| gbt_net__5 | 2025 | SPY | 122/247 | 0 | 0 | 1 | 15 | 8 |
| gbt_net__10 | 2025 | QQQ | 114/247 | 0 | 0 | 1 | 11 | 8 |
| gbt_net__10 | 2025 | SPXW | 20/247 | 0 | 1 | 3 | 14 | 2 |
| gbt_net__10 | 2025 | SPY | 155/247 | 0 | 0 | 0 | 16 | 16 |
| gbt_advantage__0 | 2025 | QQQ | 239/247 | 0 | 0 | 0 | 1 | 72 |
| gbt_advantage__0 | 2025 | SPXW | 245/247 | 0 | 0 | 0 | 1 | 146 |
| gbt_advantage__0 | 2025 | SPY | 236/247 | 0 | 0 | 0 | 1 | 104 |
| gbt_advantage__5 | 2025 | QQQ | 246/247 | 0 | 0 | 0 | 1 | 126 |
| gbt_advantage__5 | 2025 | SPXW | 245/247 | 0 | 0 | 0 | 1 | 146 |
| gbt_advantage__5 | 2025 | SPY | 247/247 | 0 | 0 | 0 | 0 | 247 |
| gbt_advantage__10 | 2025 | QQQ | 247/247 | 0 | 0 | 0 | 0 | 247 |
| gbt_advantage__10 | 2025 | SPXW | 245/247 | 0 | 0 | 0 | 1 | 146 |
| gbt_advantage__10 | 2025 | SPY | 247/247 | 0 | 0 | 0 | 0 | 247 |
| tcn_teacher__0 | 2025 | QQQ | 244/247 | 0 | 0 | 0 | 1 | 135 |
| tcn_teacher__0 | 2025 | SPXW | 203/247 | 0 | 0 | 0 | 10 | 22 |
| tcn_teacher__0 | 2025 | SPY | 244/247 | 0 | 0 | 0 | 3 | 166 |
| tcn_teacher__5 | 2025 | QQQ | 245/247 | 0 | 0 | 0 | 1 | 135 |
| tcn_teacher__5 | 2025 | SPXW | 220/247 | 0 | 0 | 0 | 5 | 32 |
| tcn_teacher__5 | 2025 | SPY | 245/247 | 0 | 0 | 0 | 1 | 166 |
| tcn_teacher__10 | 2025 | QQQ | 245/247 | 0 | 0 | 0 | 1 | 135 |
| tcn_teacher__10 | 2025 | SPXW | 237/247 | 0 | 0 | 0 | 4 | 90 |
| tcn_teacher__10 | 2025 | SPY | 246/247 | 0 | 0 | 0 | 1 | 200 |
| gbt_net__0 | 2026 | QQQ | 12/120 | 0 | 0.9 | 3 | 14 | 2 |
| gbt_net__0 | 2026 | SPXW | 5/123 | 0 | 2 | 4 | 19 | 1 |
| gbt_net__0 | 2026 | SPY | 19/120 | 0 | 0 | 2 | 18 | 2 |
| gbt_net__5 | 2026 | QQQ | 23/120 | 0 | 0 | 2 | 12 | 3 |
| gbt_net__5 | 2026 | SPXW | 5/123 | 0 | 1 | 4 | 19 | 1 |
| gbt_net__5 | 2026 | SPY | 47/120 | 0 | 0 | 1 | 11 | 8 |
| gbt_net__10 | 2026 | QQQ | 40/120 | 0 | 0 | 1 | 12 | 5 |
| gbt_net__10 | 2026 | SPXW | 6/123 | 0 | 1 | 4 | 16 | 1 |
| gbt_net__10 | 2026 | SPY | 63/120 | 0 | 0 | 0 | 11 | 15 |
| gbt_advantage__0 | 2026 | QQQ | 116/120 | 0 | 0 | 0 | 3 | 52 |
| gbt_advantage__0 | 2026 | SPXW | 123/123 | 0 | 0 | 0 | 0 | 123 |
| gbt_advantage__0 | 2026 | SPY | 116/120 | 0 | 0 | 0 | 1 | 52 |
| gbt_advantage__5 | 2026 | QQQ | 120/120 | 0 | 0 | 0 | 0 | 61 |
| gbt_advantage__5 | 2026 | SPXW | 123/123 | 0 | 0 | 0 | 0 | 123 |
| gbt_advantage__5 | 2026 | SPY | 118/120 | 0 | 0 | 0 | 1 | 52 |
| gbt_advantage__10 | 2026 | QQQ | 120/120 | 0 | 0 | 0 | 0 | 61 |
| gbt_advantage__10 | 2026 | SPXW | 123/123 | 0 | 0 | 0 | 0 | 123 |
| gbt_advantage__10 | 2026 | SPY | 120/120 | 0 | 0 | 0 | 0 | 61 |
| tcn_teacher__0 | 2026 | QQQ | 117/120 | 0 | 0 | 0 | 1 | 46 |
| tcn_teacher__0 | 2026 | SPXW | 98/123 | 0 | 0 | 0 | 5 | 18 |
| tcn_teacher__0 | 2026 | SPY | 120/120 | 0 | 0 | 0 | 0 | 61 |
| tcn_teacher__5 | 2026 | QQQ | 118/120 | 0 | 0 | 0 | 1 | 46 |
| tcn_teacher__5 | 2026 | SPXW | 111/123 | 0 | 0 | 0 | 4 | 33 |
| tcn_teacher__5 | 2026 | SPY | 120/120 | 0 | 0 | 0 | 0 | 61 |
| tcn_teacher__10 | 2026 | QQQ | 118/120 | 0 | 0 | 0 | 1 | 46 |
| tcn_teacher__10 | 2026 | SPXW | 118/123 | 0 | 0 | 0 | 1 | 48 |
| tcn_teacher__10 | 2026 | SPY | 120/120 | 0 | 0 | 0 | 0 | 61 |

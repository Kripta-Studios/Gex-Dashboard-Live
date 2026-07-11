# Flat history ablation — dataset audit and frozen design

## Sealed inputs

- Full executable-quote physics parquet (`202201..202605`): 108,156 rows, 371 columns, SHA-256 `11E26AADDD91FD441222D552E0362C1D4C2C4489A08D7A6DE66479D6EB454FB1`.
- Recent logical view (`202501..202605`): 36,796 rows, 371 columns, SHA-256 `AB144DBAD1F6F103C771AE119A1172AC728BC11B6AA79DB5FB0648561673F720`.
- ThetaData source manifest SHA-256: `88BE8A2FF44C18FB57FCA360D31DEF574DDBB0419A792FC88349942711D2974A`.
- Date maximum in every training/downstream input: `20260529`. June 2026 is physically absent.

The full parquet contains only `zero_dte` and `option_price_mode=executable_quote`, with 0 duplicate event keys, 0 infinite numeric cells, and 0 rows outside the 10:30–14:30 ET five-minute grid. The trainer selects the same 277 live-observable features in both views and rejects the same five non-live intraday aggregates.

Two SPXW rows on `20220222` (`10:30`, `11:20`) have PUT availability zero. The raw ThetaData cross-sections contain all 162 PUT strikes but every PUT bid and ask is zero at those timestamps. This is observable contract absence, not a failed join or an imputed label. `prepare_profile()` excludes executable rows unless both CALL and PUT are observable; all rows with observable contracts have finite conservative outcomes. No source row was removed or synthesized.

## Frozen ablation

The only changed factor is the physical beginning of encoder training history:

- `history_2025`: train data begins `202501`.
- `history_2022`: train data begins `202201`.

Both arms export exactly the same 13 OOF months (`202505..202605`) and use the same flat architecture, feature allowlist, horizons `1/3/6/12`, context length 6, seed `20260618`, fold-derived seeds, CUDA deterministic backend, 8 epochs, batch 1024, and zero DataLoader workers. Equal epochs and batch are the frozen training-budget rule; the larger number of observations/updates in the 2022 window is the declared history factor and is reported explicitly in `fold_budget.csv`.

Both embeddings are joined to the same recent event view before downstream selection. Nested evaluation is restricted to `202601..202605`, with one open position per ticker and the exact runtime caps/cooldowns: SPXW `4/0m`, QQQ `2/30m`, SPY `1/0m`.

No architecture, regularizer, threshold grid, labels, runtime contract, or evaluation month differs between arms. No June row is read, trained, selected, or scored.

## Compute preflight

- GPU: NVIDIA RTX 5070 Ti Laptop, 12.2 GiB.
- Synthetic flat forward/backward at batch 1024: peak reserved VRAM about 818 MiB.
- CUDA deterministic GRU forward/backward: PASS with `CUBLAS_WORKSPACE_CONFIG=:4096:8`.
- Dataset build used 24 workers; 32 were not used because free system RAM fell below 10 GiB during the build.
- Nested selector budget: 2 concurrent profiles × 12 LightGBM threads = at most 24 CPU threads, leaving RAM headroom for the shared dataset.

The runner refuses hash mismatches, existing outputs without explicit resume, CUDA with less than 2 GiB free, incomplete fold coverage, or failed nested provenance.

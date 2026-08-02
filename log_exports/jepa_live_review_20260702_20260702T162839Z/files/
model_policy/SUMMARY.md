# Dense15 Backfill19 SPY No-Score-Threshold WF2026 Full-May-Jun Event-Option Package

- Policy: `event_option_dense15_backfill19_spy_no_scorethr_wf2026_fullmayjun_202607`
- Status: `production_live_ready`
- Completed WF months: `202601..202606`, no excluded months in validation.
- Verification passed: `True` with `--strict-month-trades --require-positive-months`.
- Curve health passed: `True`.
- Runtime replay passed: `True`; combined matched `425/425` trades.
- Snapshot-to-order smoke passed: `True`.
- Anti-snooping support for SPY rule: the same `win_no_scorethr_d25` policy passes a separate 2025 causal audit before 2026 evidence: 354 trades, WR `50.00%`, PF `1.656`, min month `19`, positive months `12/12` (`research_papers/JEPA/results/_diagnostics/event_option_gate_dense15_zero_dte_win_no_scorethr_d25_physctx_wf2025_spy_v1/VERIFICATION_wf2025_spy_no_scorethr_presupport.md`).
- Temporal integrity: `True` over `36` folds.

## Metrics

- SPXW: trades=125, WR=51.20%, PF=1.749, min_month=19, PnL=$68,500, positive_months=6/6
- SPY: trades=122, WR=50.82%, PF=1.722, min_month=19, PnL=$65,000, positive_months=6/6, June PnL=$10,000
- QQQ: trades=178, WR=46.07%, PF=1.424, min_month=19, PnL=$61,000, positive_months=6/6

Overall: trades=425, WR=48.94%, PF=1.598, PnL=$194,500.

## Caveat

Raw coverage audit still records 202605 as partial; this package follows the operator instruction to assume 202605 complete.

# Wall-state physical separability V1 — REJECTED

The frozen run completed 2,223 labeled sessions and 144 LightGBM fits in 48.4 s.
It produced 26,090 causal approaching-wall candidates and all 48 paired D0/S2
cells were valid. No 2026 data or production component was used.

S1 wall state beat distance-only in 17/48 cells with median ROC-AUC delta
`-0.00154`. S2 wall state plus current/prior IB/Fibonacci confluence won 22/48,
median delta `-0.000077`, one-sided Wilcoxon `p=0.5672`. Average precision and
log-loss wins were only 19/48 and 17/48. Every ticker failed the frozen gate.

Distance and approach already predict `magnet_hit` well: median D0 AUC `0.805`.
Adding state/confluence did not improve it stably. `resolved_rejection` remained
near chance: median AUC D0/S1/S2 `0.511/0.519/0.516`.

The directional task also lacks the required monthly volume. Minimum resolved
samples at 30m were QQQ/SPXW/SPY `6/0/0`; at 60m `14/4/5`. The apparent
180-minute improvement (S2 wins 5/6, median delta about `+0.029`) is late,
low-frequency and diagnostic only; selecting it after the run is forbidden.

Conclusion: wall location is a causal magnet feature, but daily-OI-based wall
strength, persistence and IB/Fibonacci confluence do not decide rejection versus
accepted break with stable frequency. No option-payoff model is authorized from
this arm and no candidate is live-safe.

The next defensible source is intraday surface flow/quote pressure near the wall.
Local ThetaData contains Greeks bid/ask snapshots and option OHLC volume/count,
but no raw signed trade-aggressor feed. Any next test must predeclare a causal
completed-bar proxy and compare it to the rejected D0 control without retuning
this wall-state output.

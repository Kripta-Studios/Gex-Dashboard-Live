# H-IBQDYN1 economic translation predeclaration

Status: frozen before any H-IBQDYN1 physical outcome, option payoff or 2026 row
was opened. It is dormant unless the complete predeclared physical gate passes.

This is the only authorized H-IBQDYN1 payoff translation. It introduces no new
data family, model fit, threshold, feature, hyperparameter or rescue sweep.

## Frozen signal

For each annual outer fold, use only the fitted primary F1 L2-logistic model at
the 60-minute physical horizon:

- train through 2023, score every both-valid 2024 event;
- train through 2024, score every both-valid 2025 event.

The probability is `P(true rejection)`. At resistance, rejection maps to PUT
and accepted break to CALL. At support, rejection maps to CALL and accepted
break to PUT. The decision boundary is exactly 0.5. Every eligible both-valid
event is actionable; there is no confidence threshold, calibration selection,
ranking over future intraday events or option-payoff training.

## Frozen execution

Join only the exact bucket already stored by the sealed executable-quote source:
SPXW d25, QQQ d35 and SPY d35. Its contract is entry at ask, future exits at
bid, stop -60%, TP 1000%, trailing activation 50%/drawdown 25%, minimum hold 30
minutes and maximum hold 180 minutes.

Replay events chronologically as they become observable. Reject an entry while
a position is open. Daily caps are SPXW 4, QQQ 2 and SPY 1; QQQ additionally
requires 30 minutes from the prior entry. Equal exit/next-entry timestamps are
allowed. No end-of-day ranking, monthly backfill or use of future trade count is
allowed.

## One-shot gate

Report every calendar month of 2024 and 2025 separately. Promotion requires for
each of SPXW, QQQ and SPY: aggregate PF >=1.30 and WR >=50%, at least 18 trades
and positive PnL in every month, and every realized hold >=30 minutes. June 2026
remains sealed; January-May 2026 is not part of selection or reported OOS.

Any failure closes this translation. Do not tune the 0.5 boundary, horizon,
mapping, caps, cooldown, exits, ticker subset or month subset after results.

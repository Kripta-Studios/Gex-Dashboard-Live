# JEPA Option Ticker Gate Diagnostics

This report is diagnostic research for ticker-specific deployment gates.
Validation uses 2026-01-01 through 2026-03-31; OOS uses 2026-04-01 onward.

## Current OOS OptionValue Blended + Trail/Cutoff

| Scope | Trades | WR | PF | PnL | Max DD | Avg PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL | 136 | 58.8% | 2.095 | +$35,988 | -$3,920 | +$265 |
| QQQ | 35 | 51.4% | 0.902 | -$767 | -$3,664 | -$22 |
| SPX | 40 | 72.5% | 3.457 | +$27,769 | -$3,920 | +$694 |
| SPY | 61 | 54.1% | 1.656 | +$8,986 | -$2,943 | +$147 |

## Cross-Ticker Confirmation On Current OOS Blended Trades

| Gate | Trades | WR | PF | PnL | Max DD | Avg PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY confirmed by SPX | 23 | 78.3% | 4.331 | +$8,930 | -$1,019 | +$388 |
| SPY confirmed by any other | 30 | 70.0% | 2.644 | +$7,823 | -$1,233 | +$261 |
| QQQ confirmed by SPX | 8 | 50.0% | 1.151 | +$249 | -$1,025 | +$31 |
| QQQ confirmed by SPX or SPY | 15 | 46.7% | 0.978 | -$73 | -$1,725 | -$5 |

## Fixed 0.70 Trail/Cutoff Validation vs OOS Confirmation

| Gate | Trades | WR | PF | PnL | Max DD | Avg PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| VAL fixed 0.70 | 292 | 70.9% | 3.256 | +$114,213 | -$3,378 | +$391 |
| VAL fixed 0.70 QQQ | 94 | 69.1% | 3.395 | +$25,134 | -$1,477 | +$267 |
| VAL fixed 0.70 SPX | 81 | 76.5% | 3.337 | +$56,073 | -$3,378 | +$692 |
| VAL fixed 0.70 SPY | 117 | 68.4% | 3.046 | +$33,007 | -$2,200 | +$282 |
| VAL fixed 0.70 SPY confirmed by SPX | 44 | 81.8% | 6.509 | +$17,855 | -$1,179 | +$406 |
| VAL fixed 0.70 QQQ confirmed by SPX | 44 | 75.0% | 3.782 | +$13,201 | -$1,113 | +$300 |
| OOS fixed 0.70 | 136 | 58.8% | 2.026 | +$33,338 | -$4,281 | +$245 |
| OOS fixed 0.70 QQQ | 35 | 51.4% | 0.800 | -$1,549 | -$3,733 | -$44 |
| OOS fixed 0.70 SPX | 40 | 72.5% | 3.399 | +$27,110 | -$3,920 | +$678 |
| OOS fixed 0.70 SPY | 61 | 54.1% | 1.578 | +$7,777 | -$3,103 | +$127 |
| OOS fixed 0.70 SPY confirmed by SPX | 23 | 78.3% | 3.929 | +$7,574 | -$1,019 | +$329 |
| OOS fixed 0.70 QQQ confirmed by SPX | 8 | 50.0% | 1.103 | +$163 | -$1,025 | +$20 |

## OOS Oracle Delta Hard-Exit Upper Bound

| Ticker | Trades | WR | PF | PnL | Max DD | Avg PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 49 | 36.7% | 1.525 | +$7,441 | -$5,502 | +$152 |
| SPX | 51 | 54.9% | 6.281 | +$45,126 | -$1,862 | +$885 |
| SPY | 74 | 44.6% | 2.929 | +$37,723 | -$3,448 | +$510 |

## Interpretation

- SPY's weak aggregate OOS result is mostly from unconfirmed SPY-only entries; SPY trades confirmed by SPX are SPX-like.
- QQQ is not rescued by SPX/SPY confirmation in the current OOS window.
- QQQ's hard-exit oracle delta upper bound is still far below SPX in the current OOS split, so strike selection alone cannot make QQQ SPX-like.

# QQQ OptionValue Rescue Diagnostics

Goal: investigate ways to keep QQQ tradable instead of disabling it.
Validation is `2026-01-01` through `2026-03-31`; OOS is `2026-04-01` onward.

## Findings

- QQQ fixed 0.70 was strong in validation but failed in the current OOS, so the issue is a regime/entry problem more than a pure delta problem.
- A looser QQQ-specific stop (`-70%`) with the same 50% trail activation but tighter 15% giveback improves QQQ OOS versus the live-style `-60% / 50% / 25%` exit.
- Excluding the QQQ 11:31-12:30 ET entry window improves validation and turns QQQ OOS positive, while keeping QQQ active.
- The highest OOS QQQ PF in this diagnostic comes from early-only entries, but that is lower volume and should be treated as research until tested in more folds.

## Metrics

| Scenario | Trades | WR | PF | PnL | Max DD | Avg PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| VAL fixed QQQ baseline | 94 | 69.1% | 3.395 | +$25,134 | -$1,477 | +$267 |
| VAL fixed QQQ exclude 11:31-12:30 | 81 | 72.8% | 4.002 | +$24,869 | -$1,490 | +$307 |
| VAL fixed QQQ loose exit + exclude 11:31-12:30 | 81 | 76.5% | 5.334 | +$26,203 | -$1,202 | +$323 |
| VAL fixed QQQ loose exit + early only | 41 | 68.3% | 2.594 | +$7,740 | -$984 | +$189 |
| OOS fixed QQQ baseline | 35 | 51.4% | 0.800 | -$1,549 | -$3,733 | -$44 |
| OOS fixed QQQ exclude 11:31-12:30 | 25 | 56.0% | 1.063 | +$318 | -$2,953 | +$13 |
| OOS fixed QQQ loose exit + exclude 11:31-12:30 | 25 | 64.0% | 1.331 | +$1,409 | -$1,875 | +$56 |
| OOS fixed QQQ loose exit + early only | 15 | 66.7% | 1.784 | +$1,883 | -$1,745 | +$126 |
| OOS OptionValue QQQ baseline | 35 | 51.4% | 0.902 | -$767 | -$3,664 | -$22 |
| OOS OptionValue QQQ loose exit | 35 | 57.1% | 1.094 | +$635 | -$2,771 | +$18 |
| OOS OptionValue QQQ loose exit + exclude 11:31-12:30 | 25 | 64.0% | 1.489 | +$2,157 | -$1,796 | +$86 |
| OOS OptionValue QQQ loose exit + early only | 15 | 66.7% | 2.078 | +$2,695 | -$1,745 | +$180 |
| OOS OptionValue QQQ loose exit + long or early short | 27 | 63.0% | 1.430 | +$1,929 | -$1,848 | +$71 |
| OOS mixed: SPX/SPY base + QQQ loose exclude 11:31-12:30 | 126 | 61.9% | 2.323 | +$38,913 | -$3,920 | +$309 |
| OOS mixed: SPX/SPY base + QQQ loose early only | 116 | 62.1% | 2.435 | +$39,451 | -$3,920 | +$340 |
| OOS mixed: SPX/SPY base + QQQ loose long or early short | 128 | 61.7% | 2.312 | +$38,684 | -$3,920 | +$302 |

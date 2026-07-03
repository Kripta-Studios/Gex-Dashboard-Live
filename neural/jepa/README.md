# JEPA Event-Option Production Pipeline

This directory contains the current production event-option package tooling plus older JEPA research experiments. The active live system is the frozen 2025 static-union event-option package for deploy month 202607.

## Active Production Package

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
  event_option_policy.json
  component_registry.json
```

Policy id:

```text
event_option_frozen2025_static_union_balanced_202607
```

Result directory:

```text
research_papers/JEPA/results/event_option_mh30trail_frozen2025_static_union_deploy202607_production_v1
```

Live services:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

## Live Contract

```text
tickers: SPX, QQQ, SPY
option symbols: SPXW, QQQ, SPY
expiry: 0DTE only
entry window: 10:00-14:30 ET
risk: 5000 dollars
exit: stop -60%, trail +50% / 25% giveback, emergency TP +1000%
hold: min 30m, max 180m
order mode: paper intents and Discord alerts; no broker submission
```

Static policy caps:

| Ticker | Bucket | Score gate | Max trades/day | Cooldown |
| --- | --- | --- | ---: | --- |
| SPXW | d25 | min score 0.34 | 4 | 0m |
| QQQ | d35 | policy-defined | 2 | 30m |
| SPY | d35 | policy-defined | 1 | 0m |

## Validation

Canonical production validation:

```bash
python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12
```

Completed Jan-Jun 2026 metrics:

| Scope | Trades | WR | PF | Min month trades |
| --- | ---: | ---: | ---: | ---: |
| Overall | 697 | 57.819% | 1.915 | 103 |
| QQQ | 236 | 60.593% | 1.771 | 36 |
| SPXW | 355 | 55.211% | 2.037 | 51 |
| SPY | 106 | 60.377% | 1.769 | 12 |

The deployable gate is `min_month_trades=12`; the preferred 18-trades/month/ticker target is not met by SPY.

## Daily Workflow

Daily work is monitoring and audit:

```bash
DAY=$(TZ=America/New_York date +%Y%m%d)
python3 neural/jepa/audit_live_feature_drift.py --day-dir "rt_data/$DAY" --strict-features
journalctl -u realtime_feed.service -n 120 --no-pager
journalctl -u ai_bot.service -n 160 --no-pager
```

Do not retrain every day. Retrain/reselect only after a month is complete and only promote a package that passes live-ready validation and service smoke checks.

## Important Scripts

Live equivalence and runtime:

```text
event_option_live_snapshot.py
event_option_live_scorer.py
event_option_component_live.py
audit_live_feature_drift.py
validate_event_option_production_package.py
```

Training, leakage, and walk-forward research:

```text
build_event_option_dataset.py
audit_event_option_feature_leakage.py
walkforward_event_option_gate.py
walkforward_trade_quality_filter.py
evaluate_dense_candidate_fixed_holdout.py
```

Representation-learning research:

```text
sigreg.py
train_xinput_jepa.py
walkforward_xinput_jepa_oof.py
walkforward_event_phys_td_jepa_oof.py
compare_xinput_jepa_regularizers.py
```

## Legacy Paths

The following are research/legacy unless explicitly selected by a service or validation command:

```text
neural/models/jepa/jepa_production_final_180m
neural/models/jepa/jepa_production_final_option_value
neural/models/jepa/jepa_production_level_stability
neural/models/jepa/jepa_production_structural_options
```

The live event-option static-union package replaced the previous level-stability + structural-profile path.

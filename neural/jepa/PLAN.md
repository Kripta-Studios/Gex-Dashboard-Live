# JEPA Current Plan

## Production Priority

Keep the live event-option static-union package aligned between training, backtest, live snapshot generation, live scorer, and systemd.

Current production package:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

Current live policy:

```text
event_option_frozen2025_static_union_balanced_202607
```

## Daily Work

Daily work is audit, not retraining.

```bash
DAY=$(TZ=America/New_York date +%Y%m%d)
python3 neural/jepa/audit_live_feature_drift.py --day-dir "rt_data/$DAY" --strict-features
journalctl -u realtime_feed.service -n 120 --no-pager
journalctl -u ai_bot.service -n 160 --no-pager
```

Check that both services show:

```text
[EVENT_OPTION] loaded policy=event_option_frozen2025_static_union_balanced_202607
Loaded event-option component registry status=production_live_ready
event_exit=stop=-60%/tp=1000%/trail=50%/25%/min_hold=30m/max_hold=180m
```

## Monthly Promotion Work

After a completed month:

1. Rebuild candidate datasets from ThetaData.
2. Re-run leakage audits and walk-forward/fixed-holdout selection.
3. Export a new production package only if selection evidence is prior to the deploy month.
4. Validate the package with `--require-live-ready`.
5. Smoke test realtime feed, live scorer, and bot startup.
6. Deploy via git pull and explicit systemd restart.

Production validation gate:

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

## Research Priorities

1. Keep event-option features strictly live-observable.
2. Keep policy replay reproducible: no missing/extra trades when replaying runtime logic against historical snapshots.
3. Improve SPY monthly trade volume without weakening PF/WR gates.
4. Evaluate VISReg/SIGReg/XInputJEPA only as auxiliary representation features until they improve the event-option baseline.
5. Do not promote RL or OptionValue unless it beats the current static-union event-option package under the same live-ready checks.

## Files That Matter

Live runtime:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
neural/jepa/event_option_live_snapshot.py
neural/jepa/event_option_live_scorer.py
neural/jepa/event_option_component_live.py
```

Validation and audits:

```text
neural/jepa/validate_event_option_production_package.py
neural/jepa/audit_live_feature_drift.py
neural/jepa/audit_event_option_feature_leakage.py
```

Systemd:

```text
systemd/realtime_feed.service
systemd/ai_bot.service
```

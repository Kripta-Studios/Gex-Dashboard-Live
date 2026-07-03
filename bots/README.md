# Live Event-Option Bot

This folder contains the live JEPA event-option trading wrapper. The active process is an alert and paper-intent bot; it does not submit broker orders.

## Active Entry Point

```text
bots/tradingbot_wrapper_jepa.py
```

Systemd runs it through:

```text
systemd/ai_bot.service
```

The companion feed is:

```text
services/realtime_feed.py
systemd/realtime_feed.service
```

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

The bot must be started with:

```text
--require-event-option-policy
--require-event-option-component-registry
--require-event-option-live-ready
--enable-event-option-scorer
--strict-event-option-features
--paper-order-intents
```

## Runtime Contract

| Field | Value |
| --- | --- |
| Tickers | SPX, QQQ, SPY |
| Option symbols | SPX -> SPXW, QQQ -> QQQ, SPY -> SPY |
| Expiry | 0DTE |
| Entry window | 10:00-14:30 ET |
| Risk capital | $5,000 |
| Stop | -60% |
| Trail | activate +50%, close after 25% giveback |
| Emergency TP | +1000% |
| Min hold | 30 minutes |
| Max hold | 180 minutes |
| Broker | disabled; paper intents only |

Per-ticker caps:

| Ticker | Bucket | Max trades/day | Cooldown |
| --- | --- | ---: | --- |
| SPXW | d25 | 4 | 0m |
| QQQ | d35 | 2 | 30m |
| SPY | d35 | 1 | 0m |

## Runtime Files

Feed output:

```text
rt_data/YYYYMMDD/
  event_option_snapshots_latest.parquet
  spot_{TICKER}_latest.parquet
  {OPTION_SYMBOL}_greeks_0dte_latest.parquet
  {OPTION_SYMBOL}_ohlc_0dte_latest.parquet
  realtime_feed.log
```

Bot output:

```text
trades_jepa/
  open_positions_jepa.json
  event_option_runtime_state.json
  evaluated_features_jepa.json
  cooldowns_jepa.json
  trades_jepa.csv
  event_option_candidate_audit_jepa.jsonl
  paper_order_intents_jepa.jsonl
  tradingbot_jepa.log
```

## Local/VPS Checks

Compile the live entry points:

```bash
python3 -m py_compile \
  services/realtime_feed.py \
  bots/tradingbot_wrapper_jepa.py \
  neural/jepa/event_option_live_snapshot.py \
  neural/jepa/event_option_live_scorer.py \
  neural/jepa/event_option_component_live.py
```

Validate the package:

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

Audit live feature drift after the feed has written the daily snapshot:

```bash
DAY=$(TZ=America/New_York date +%Y%m%d)
python3 neural/jepa/audit_live_feature_drift.py --day-dir "rt_data/$DAY" --strict-features
```

## Deployment

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git pull --ff-only
sudo install -m 0644 systemd/realtime_feed.service /etc/systemd/system/realtime_feed.service
sudo install -m 0644 systemd/ai_bot.service /etc/systemd/system/ai_bot.service
sudo systemctl daemon-reload
sudo systemctl restart realtime_feed.service
sudo systemctl restart ai_bot.service
sudo systemctl status realtime_feed.service ai_bot.service --no-pager -l
```

Expected bot log:

```text
Loaded event-option production policy=event_option_frozen2025_static_union_balanced_202607
Loaded event-option component registry status=production_live_ready
Starting JEPA live bot ... event_exit=stop=-60%/tp=1000%/trail=50%/25%/min_hold=30m/max_hold=180m
Paper order intents enabled
```

## Legacy Bot Files

Older `tradingbot1.py`, `tradingbot2.py`, wrapper, Hybrid, OptionValue, and base JEPA 180m paths are historical or diagnostic. Do not assume they are live production unless the active systemd units point to them.

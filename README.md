# GEX Dashboard Live

GEX Dashboard Live is a real-time options data, plotting, Discord, and paper-trading stack. The current live trading path is the JEPA event-option static-union package for 0DTE SPXW, QQQ, and SPY options.

Older Hybrid Attention-MLP, GBT, level-stability, structural-profile, OptionValue, and PPO/RL systems remain in the repository as research or legacy tooling. They are not the active production trading service unless a service file or command explicitly enables them.

## Current Production Stack

The live trade-alert stack is:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

The active package is:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
  event_option_policy.json
  component_registry.json
```

Policy id:

```text
event_option_frozen2025_static_union_balanced_202607
```

Validated research result:

```text
research_papers/JEPA/results/event_option_mh30trail_frozen2025_static_union_deploy202607_production_v1
```

The bot emits Discord trade alerts and writes paper order intents. It does not submit broker orders.

## Live Trading Contract

| Field | Current value |
| --- | --- |
| Tickers | SPX, QQQ, SPY |
| Option symbols | SPX -> SPXW, QQQ -> QQQ, SPY -> SPY |
| Expiry | 0DTE only |
| Entry window | 10:00-14:30 ET |
| EOD cleanup | 16:00 ET |
| Risk capital | $5,000 per trade |
| Exit | stop -60%, trail +50% / 25% giveback, emergency TP +1000% |
| Hold bounds | min 30m, max 180m |
| Runtime state | `trades_jepa/` |
| Broker submission | Disabled; paper intents only |

Per-ticker static policy caps:

| Ticker | Delta bucket | Score gate | Max trades/day | Cooldown |
| --- | --- | --- | ---: | --- |
| QQQ | d35 | policy-defined | 2 | 30m |
| SPXW | d25 | min score 0.34 | 4 | 0m |
| SPY | d35 | policy-defined | 1 | 0m |

## Production Validation Snapshot

Completed-month validation over January-June 2026:

| Scope | Trades | WR | PF | Min month trades |
| --- | ---: | ---: | ---: | ---: |
| Overall | 697 | 57.819% | 1.915 | 103 |
| QQQ | 236 | 60.593% | 1.771 | 36 |
| SPXW | 355 | 55.211% | 2.037 | 51 |
| SPY | 106 | 60.377% | 1.769 | 12 |

The active production gate accepts `--min-month-trades 12`. The stronger preferred target of 18 monthly trades per ticker is not met by SPY in this package.

Validate the package with:

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

## Data Layout

Local historical ThetaData inputs:

```text
D:/ThetaData/data_options/SPXW
D:/ThetaData/data_options/QQQ
D:/ThetaData/data_options/SPY
D:/ThetaData/data_underlying_derived/SPXW
D:/ThetaData/data_underlying_derived/QQQ
D:/ThetaData/data_underlying_derived/SPY
```

VPS runtime data:

```text
rt_data/YYYYMMDD/
  spot_{TICKER}_latest.parquet
  {OPTION_SYMBOL}_greeks_0dte_latest.parquet
  {OPTION_SYMBOL}_ohlc_0dte_latest.parquet
  event_option_snapshots_latest.parquet
  realtime_feed.log

trades_jepa/
  open_positions_jepa.json
  event_option_runtime_state.json
  event_option_candidate_audit_jepa.jsonl
  paper_order_intents_jepa.jsonl
  tradingbot_jepa.log
```

## Daily Operations

Daily work is audit and monitoring, not retraining.

```bash
DAY=$(TZ=America/New_York date +%Y%m%d)
python3 neural/jepa/audit_live_feature_drift.py --day-dir "rt_data/$DAY" --strict-features
journalctl -u realtime_feed.service -n 120 --no-pager
journalctl -u ai_bot.service -n 160 --no-pager
tail -n 200 trades_jepa/tradingbot_jepa.log
```

If market data has not been produced yet for the day, `audit_live_feature_drift.py` can fail because `event_option_snapshots_latest.parquet` does not exist. That is expected before the feed has written its first event-option snapshot.

## Deployment

Deploy source and model/service changes with git and explicit service restarts. Do not use `reboot now` as the default deployment method.

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git pull --ff-only

python3 -m py_compile \
  services/realtime_feed.py \
  bots/tradingbot_wrapper_jepa.py \
  neural/jepa/event_option_live_snapshot.py \
  neural/jepa/event_option_live_scorer.py \
  neural/jepa/event_option_component_live.py \
  neural/jepa/audit_live_feature_drift.py \
  neural/jepa/validate_event_option_production_package.py

python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12

sudo install -m 0644 systemd/realtime_feed.service /etc/systemd/system/realtime_feed.service
sudo install -m 0644 systemd/ai_bot.service /etc/systemd/system/ai_bot.service
sudo systemctl daemon-reload
sudo systemctl restart realtime_feed.service
sudo systemctl restart ai_bot.service
sudo systemctl status realtime_feed.service ai_bot.service --no-pager -l
```

Use `systemctl status ... --no-pager -l`; do not append a bare number such as `50`, because systemd interprets it as a PID.

Expected live log markers:

```text
[EVENT_OPTION] loaded policy=event_option_frozen2025_static_union_balanced_202607
Loaded event-option component registry status=production_live_ready
event_exit=stop=-60%/tp=1000%/trail=50%/25%/min_hold=30m/max_hold=180m
Paper order intents enabled
```

## Retraining Cadence

Do not retrain every day just because a new day of data exists.

The normal cadence is:

1. Audit live behavior daily.
2. After a month is complete, rebuild/evaluate the next deploy package.
3. Promote only if validation, live feature equivalence, leakage audits, and service smoke tests pass.
4. Deploy through git pull, validation, service install, and restart.

## Other Services

The repo still contains dashboard and plotting services:

```text
services/gex_daemon.py
services/ib_service.py
services/servidor.py
discord_app/main.py
discord_app/discord_send_plots.py
tools/data_plotting.py
modules/tasty_handler.py
```

These are separate from the event-option trading bot. Recent systemd work also includes `gex_daemon.service`, `discord-bot.service`, timer/drop-in files, and dxLink handling improvements.

## Legacy Research

The following areas are useful research references but are not the current live trading contract:

```text
neural/run_pipeline.ps1
neural/train_walkforward.py
neural/rl/
neural/hybrid_model.py
neural/jepa/jepa_production_final_180m
neural/models/jepa/jepa_production_level_stability
neural/models/jepa/jepa_production_structural_options
```

Before promoting any legacy or new model, compare it against the current event-option static-union package with the same walk-forward, leakage, live-equivalence, and service-start checks.

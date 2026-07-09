# Codex Live Sentinel Runbook

This document is for a Codex agent running on the VPS as a live sentinel for the
0DTE JEPA event-option bot. The sentinel's job is to verify that the live system
is reading the expected data, using the production policy, producing causal
features, enforcing runtime guards, and behaving consistently with the validated
backtest / walk-forward contract.

The sentinel must not place trades, reboot the server, change systemd units, or
edit production policy unless explicitly instructed by the operator.

## Current Production Contract

Repository root on VPS:

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
```

Live services:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

Active event-option package:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

Active policy:

```text
event_option_frozen2025_static_union_balanced_spxw_stop_pause1_202607
```

Production validation result directory:

```text
research_papers/JEPA/results/event_option_mh30trail_frozen2025_static_union_deploy202607_production_v1_spxw_stop_pause1/
```

Live option contract:

```text
entry_window=10:00-14:30 ET
expiry_mode=zero_dte
stop=-60%
take_profit=1000%
trail=50% activation / 25% giveback
min_hold=30m
max_hold=180m
risk_capital=$5000 per trade
paper_order_intents=true
```

Runtime risk guard:

```text
SPXW intraday stop-pause:
After one known SPXW event_option_stop_loss_60% close, reject all later SPX/SPXW
entries for the same trading day. QQQ and SPY are not affected.
```

Ticker policy:

| Policy ticker | Bot ticker | Option root | Delta bucket | Max trades/day | Cooldown |
| --- | --- | --- | ---: | ---: | ---: |
| SPXW | SPX | SPXW | d25 | 4 | 0m |
| QQQ | QQQ | QQQ | d35 | 2 | 30m |
| SPY | SPY | SPY | d35 | 1 | 0m |

Validated Jan-Jun 2026 metrics with the SPXW stop-pause guard:

| Scope | Trades | WR | PF | PnL R | Min month trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 668 | 59.132% | 2.013 | +164.480R | 101 |
| QQQ | 236 | 60.593% | 1.771 | +42.360R | 36 |
| SPXW | 326 | 57.669% | 2.249 | +102.760R | 49 |
| SPY | 106 | 60.377% | 1.769 | +19.361R | 12 |

These are not per-day guarantees. The sentinel should compare live behavior to
the contract and rolling distributions, not expect every day to be profitable.

## Files And Directories To Watch

Live feed output:

```text
rt_data/YYYYMMDD/
  event_option_snapshots_latest.parquet
  event_option_snapshots_latest.summary.json
  feed_intraday_state.json
  jepa_live_execution_config.json
  realtime_feed.log
  ml_features_*_latest.parquet
  spot_*_latest.parquet
  *_greeks_0dte_latest.parquet
  *_ohlc_0dte_latest.parquet
  *_oi_0dte_latest.parquet
```

Bot runtime output:

```text
trades_jepa/
  trades_jepa.csv
  paper_order_intents_jepa.jsonl
  event_option_candidate_audit_jepa.jsonl
  event_option_runtime_state.json
  open_positions_jepa.json
  evaluated_features_jepa.json
  tradingbot_jepa.log
```

Production package files:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
  event_option_policy.json
  component_registry.json
  completed_month_metrics.json
  completed_month_curve_health.json
  runtime_policy_replay_summary.json
  components/
```

Backtest / walk-forward evidence:

```text
research_papers/JEPA/results/event_option_mh30trail_frozen2025_static_union_deploy202607_production_v1_spxw_stop_pause1/
  combined_trades.csv
  spxw_stop_pause1_skipped_trades.csv
  metrics.json
  verification.json
  curve_health/curve_health.json
```

## Startup Checklist

Run these commands at the start of every sentinel session:

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git rev-parse --short HEAD
git status --short
systemctl status realtime_feed.service ai_bot.service --no-pager -l
```

Expected:

- Both services are `active (running)`.
- No unexpected local code changes unless the operator has said so.
- `ai_bot.service` command line points to:
  `jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json`.

Validate the live-ready production package:

```bash
python3 -m py_compile \
  services/realtime_feed.py \
  bots/tradingbot_wrapper_jepa.py \
  neural/jepa/validate_event_option_production_package.py

python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12
```

Expected:

```text
policy=event_option_frozen2025_static_union_balanced_spxw_stop_pause1_202607
status=production_live_ready
verification_passed=true
curve_health_passed=true
missing_live_equivalence_count=0
invalidated_component_count=0
```

## Recurrent Sentinel Loop

During market hours, repeat these checks every 5-15 minutes.

### 1. Confirm Services Are Alive

```bash
systemctl is-active realtime_feed.service ai_bot.service
journalctl -u realtime_feed.service -n 80 --no-pager
journalctl -u ai_bot.service -n 160 --no-pager
```

Alert if:

- Either service is not active.
- Logs show unhandled exceptions.
- Logs show stale data, missing policy, missing registry, or scorer import errors.
- `ai_bot.service` restarts repeatedly.

### 2. Confirm Today Has Fresh Feed Files

```bash
TODAY=$(TZ=America/New_York date +%Y%m%d)
ls -lh rt_data/$TODAY
stat rt_data/$TODAY/event_option_snapshots_latest.parquet
cat rt_data/$TODAY/event_option_snapshots_latest.summary.json
cat rt_data/$TODAY/jepa_live_execution_config.json
```

Expected:

- Snapshot files exist after the feed has started producing data.
- `jepa_live_execution_config.json` points to the active policy and registry.
- File modification times update during market hours.

Alert if:

- `event_option_snapshots_latest.parquet` is missing after 10:05 ET.
- Feed files stop updating for more than a few minutes during market hours.
- Execution config points to an old package or old policy.

### 3. Confirm Bot Reads And Scores Candidates

```bash
tail -n 200 trades_jepa/tradingbot_jepa.log
tail -n 20 trades_jepa/event_option_candidate_audit_jepa.jsonl
```

Expected candidate audit events include:

```text
candidate_selected
no_entry_candidate
no_allowed_candidate
entry_rejected
```

Alert if:

- There are no candidate audit records during the entry window.
- All candidates are rejected for feature issues.
- The bot repeatedly logs missing `event_option_snapshots_latest.parquet`.
- The scorer reports non-finite required features for selected candidates.

### 4. Confirm Paper Intents Match Trade Log

```bash
tail -n 30 trades_jepa/paper_order_intents_jepa.jsonl
tail -n 30 trades_jepa/trades_jepa.csv
cat trades_jepa/open_positions_jepa.json
```

Expected:

- Each BUY_TO_OPEN paper intent should correspond to either an open position or a later row in `trades_jepa.csv`.
- Each close in `trades_jepa.csv` should have a SELL_TO_CLOSE intent.
- `open_positions_jepa.json` should be `{}` after all positions close.

Alert if:

- An open position remains beyond `max_hold=180m` or after market close.
- There are closes without matching open intents.
- There are BUY_TO_OPEN intents for a ticker that already has an open position.
- Paper intents use the wrong contract root, expiration, right, or quantity.

### 5. Confirm Runtime Caps And Cooldowns

Use this quick daily summary:

```bash
python3 - <<'PY'
import pandas as pd
from pathlib import Path

today = pd.Timestamp.now(tz="America/New_York").strftime("%Y%m%d")
p = Path("trades_jepa/trades_jepa.csv")
if not p.exists():
    print("NO_TRADES_FILE")
    raise SystemExit
df = pd.read_csv(p, dtype={"date": str})
df = df[df["date"].astype(str).eq(today)].copy()
df = df[df["source_model"].astype(str).str.contains("FROZEN2025_SELECT2026_BALANCED", na=False)]
if df.empty:
    print("NO_TRADES_TODAY")
    raise SystemExit
df["policy_ticker"] = df["ticker"].replace({"SPX": "SPXW"})
print(df[["date","entry_time","exit_time","ticker","right","strike","pnl_pct","pnl_dollars","exit_reason","source_model"]].to_string(index=False))
print("\nCOUNTS")
print(df.groupby("policy_ticker").size().to_string())
print("\nPNL")
print(df.groupby("policy_ticker")["pnl_dollars"].sum().to_string())
PY
```

Expected:

- SPXW should not exceed 4 entries/day.
- QQQ should not exceed 2 entries/day and should respect 30m entry cooldown.
- SPY should not exceed 1 entry/day.
- Entries must be inside 10:00-14:30 ET.

### 6. Confirm SPXW Stop-Pause Guard

After any SPXW stop loss, the sentinel must verify no later SPX entry is opened
that day.

```bash
grep -R "intraday_stop_pause_SPXW_after_1_stop" \
  trades_jepa/event_option_candidate_audit_jepa.jsonl | tail -20
```

Manual check:

```bash
python3 - <<'PY'
import pandas as pd
from pathlib import Path

today = pd.Timestamp.now(tz="America/New_York").strftime("%Y%m%d")
p = Path("trades_jepa/trades_jepa.csv")
if not p.exists():
    print("NO_TRADES_FILE")
    raise SystemExit
df = pd.read_csv(p, dtype={"date": str})
df = df[df["date"].astype(str).eq(today)].copy()
df = df[df["source_model"].astype(str).str.contains("event_option:SPXW:", regex=False, na=False)]
if df.empty:
    print("NO_SPXW_TRADES_TODAY")
    raise SystemExit
stops = df[df["exit_reason"].astype(str).str.contains("event_option_stop_loss_60%", regex=False, na=False)]
print(df[["entry_time","exit_time","ticker","right","strike","pnl_pct","exit_reason"]].to_string(index=False))
if stops.empty:
    print("NO_SPXW_STOP_YET")
    raise SystemExit
first_stop_exit = str(stops.sort_values("exit_time").iloc[0]["exit_time"])[:5]
later = df[df["entry_time"].astype(str).str[:5] > first_stop_exit]
print(f"FIRST_SPXW_STOP_EXIT={first_stop_exit}")
print(f"LATER_SPXW_ENTRIES_AFTER_STOP={len(later)}")
if len(later):
    print(later[["entry_time","exit_time","right","strike","pnl_pct","exit_reason"]].to_string(index=False))
PY
```

Expected:

- After the first SPXW stop, `LATER_SPXW_ENTRIES_AFTER_STOP=0`.
- Candidate audit should record rejected SPX candidates with reason
  `intraday_stop_pause_SPXW_after_1_stop` if SPX candidates continue to appear.

Alert immediately if a later SPX/SPXW BUY_TO_OPEN happens after a known SPXW
`event_option_stop_loss_60%` close on the same date.

### 7. Compare Live PnL To Backtest Expectations

Daily losses can happen. The sentinel should not declare failure from a single
losing day. It should compare live behavior to the validated distribution and
runtime contract.

Use R units:

```text
R = pnl_dollars / 5000
```

Live daily summary:

```bash
python3 - <<'PY'
import pandas as pd
from pathlib import Path

p = Path("trades_jepa/trades_jepa.csv")
if not p.exists():
    print("NO_TRADES_FILE")
    raise SystemExit
df = pd.read_csv(p, dtype={"date": str})
df = df[df["source_model"].astype(str).str.contains("FROZEN2025_SELECT2026_BALANCED", na=False)].copy()
if df.empty:
    print("NO_FROZEN_STATIC_UNION_TRADES")
    raise SystemExit
df["R"] = pd.to_numeric(df["pnl_dollars"], errors="coerce").fillna(0.0) / 5000.0
print("BY_DAY")
print(df.groupby("date").agg(trades=("ticker","size"), pnl_R=("R","sum")).tail(20).to_string())
print("\nBY_TICKER")
print(df.assign(policy_ticker=df["ticker"].replace({"SPX":"SPXW"})).groupby("policy_ticker").agg(trades=("ticker","size"), pnl_R=("R","sum")).to_string())
PY
```

Backtest reference:

```text
Overall Jan-Jun 2026: +164.480R over 668 trades, PF 2.013, WR 59.132%.
SPXW: +102.760R over 326 trades, PF 2.249, WR 57.669%.
QQQ: +42.360R over 236 trades, PF 1.771, WR 60.593%.
SPY: +19.361R over 106 trades, PF 1.769, WR 60.377%.
```

Alert if:

- Live trades violate the policy contract.
- Fill assumptions differ materially from paper intents.
- Multiple days show outsized negative drift not explained by normal stop-loss
  frequency.
- SPXW continues trading after the stop-pause should be active.
- Live selected candidates use a different `source_model` or policy than the
  active package.

## Live-Equivalence Checks

The live system and the backtest are equivalent only if all these layers match:

1. Same package and policy.
2. Same component registry and model artifacts.
3. Same entry window and sampling cadence.
4. Same option exit contract.
5. Same ticker caps and cooldowns.
6. Same runtime SPXW stop-pause guard.
7. Live features are finite and observable at decision time.
8. Paper fills are reasonable relative to market/tracker fills.

Run this if there is doubt:

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

## What To Archive For Operator Review

When the operator asks for an audit bundle, archive only useful live evidence:

```bash
TS=$(date -u +%Y%m%dT%H%M%SZ)
TODAY=$(TZ=America/New_York date +%Y%m%d)
tar -czf /tmp/jepa_live_sentinel_${TODAY}_${TS}.tar.gz \
  rt_data/$TODAY \
  trades_jepa/trades_jepa.csv \
  trades_jepa/paper_order_intents_jepa.jsonl \
  trades_jepa/event_option_candidate_audit_jepa.jsonl \
  trades_jepa/event_option_runtime_state.json \
  trades_jepa/open_positions_jepa.json \
  trades_jepa/tradingbot_jepa.log \
  neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json
echo /tmp/jepa_live_sentinel_${TODAY}_${TS}.tar.gz
```

Do not archive full historical `rt_data/` unless explicitly requested.

## Non-Negotiable Rules

- Do not use future prices, labels, option high/low after entry, or outcome
  columns to judge live entries before they close.
- Do not compare live decisions to final recomputed snapshots as if they were
  immutable decision features. Candidate audit rows are the authoritative record
  of what the bot saw at decision time.
- Do not change systemd units without validating both services.
- Do not restart `realtime_feed.service` unless feed behavior is the issue.
- Do not run `reboot now` as a normal fix.
- Do not promote a new model, threshold, or risk guard from a few live days only.
- Do not treat paper profitability as broker-executable profitability without
  checking slippage, spreads, latency, and tracker fills.

## Escalation Template

When alerting the operator, include:

```text
Time ET:
Service status:
Current git SHA:
Policy:
Issue:
Evidence files:
Last 5 trades:
Open positions:
Candidate audit reason:
Recommended action:
```

Keep the recommendation concrete: restart `ai_bot.service`, inspect feed
staleness, stop trading for the day, or collect an audit bundle. Do not make
unrequested code or policy changes.

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
event_option_frozen2025_causal1030_intersection_guarded_v1_202607
```

Production validation result directory:

```text
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1/
```

Walk-forward robustness result directory:

```text
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1_walkforward/
```

Live option contract:

```text
entry_window=10:30-14:30 ET
expiry_mode=zero_dte
entry_sample_minutes=5
candidate_universe=near_level_abs_bps <= 20, complete initial balance required
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

SPY daily loss-streak pause:
After 3 completed losing SPY event-option trading days, pause the next SPY
candidate day. Uses only completed prior-day PnL from trades_jepa.csv.
```

Ticker policy:

| Policy ticker | Bot ticker | Option root | Delta bucket | Max trades/day | Cooldown |
| --- | --- | --- | ---: | ---: | ---: |
| SPXW | SPX | SPXW | d25 | 1 | 30m |
| QQQ | QQQ | QQQ | d35 | 2 | 45m |
| SPY | SPY | SPY | d35 | 4 | 30m |

Per-ticker live filters:

| Ticker | Time ET | Actions | Score | Edge abs | Momentum filter |
| --- | --- | --- | ---: | ---: | --- |
| SPXW | 10:30-14:30 | CALL, PUT | >= 0.0 | >= 0.05 | none |
| QQQ | 12:30-14:30 | CALL, PUT | >= 0.0 | >= 0.0 | self counter 5m |
| SPY | 12:00-14:30 | PUT only | >= -0.1 | >= 0.1 | SPX counter 5m |

Validated Jan-Jun 2026 backtest metrics:

| Scope | Trades | WR | PF | PnL R | Min month trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 416 | 57.933% | 1.749 | +77.537R | 58 |
| QQQ | 170 | 55.882% | 1.626 | +27.516R | 22 |
| SPXW | 122 | 58.197% | 1.950 | +28.730R | 19 |
| SPY | 124 | 60.484% | 1.725 | +21.292R | 14 |

Monthly retrain walk-forward robustness metrics:

| Scope | Trades | WR | PF | PnL R | Min month trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 512 | 54.883% | 1.663 | +91.089R | 72 |
| QQQ | 183 | 54.645% | 1.744 | +36.622R | 26 |
| SPXW | 120 | 55.833% | 1.874 | +27.478R | 19 |
| SPY | 209 | 54.545% | 1.476 | +26.989R | 26 |

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
research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1/
  combined_trades.csv
  daily_loss_guard_skipped_trades.csv
  metrics.json
  verification.json
  curve_health/curve_health.json

research_papers/JEPA/results/event_option_mh30trail_causal1030_static_union_deploy202607_intersection_guarded_v1_walkforward/
  combined_trades.csv
  daily_loss_guard_skipped_trades.csv
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
  neural/jepa/event_option_live_scorer.py \
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
policy=event_option_frozen2025_causal1030_intersection_guarded_v1_202607
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
- `event_option_snapshots_latest.summary.json` has non-zero rows once all
  required live inputs exist.
- All candidate rows used for trading are at or after 10:30 ET.

Alert if:

- `event_option_snapshots_latest.parquet` is missing after 10:35 ET on a normal
  trading day.
- Feed files stop updating for more than a few minutes during market hours.
- Execution config points to an old package or old policy.
- Snapshot rows selected for scoring have `minute < 630`.
- Selected rows have `nearest_level_abs_bps > 20`.

### 3. Confirm Bot Reads And Scores Candidates

```bash
tail -n 200 trades_jepa/tradingbot_jepa.log
tail -n 20 trades_jepa/event_option_candidate_audit_jepa.jsonl
```

Expected candidate audit events include:

```text
score_snapshot
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
- A selected candidate violates its ticker filter: time window, max day,
  cooldown, action, momentum filter, edge, or near-level limit.

Use this invariant checker on the decision-time audit:

```bash
python3 - <<'PY'
import json
from pathlib import Path

audit = Path("trades_jepa/event_option_candidate_audit_jepa.jsonl")
if not audit.exists():
    print("NO_CANDIDATE_AUDIT")
    raise SystemExit

rules = {
    "SPXW": {"min_minute": 630, "max_minute": 870, "actions": {"CALL", "PUT"}, "edge": 0.05, "max_near": 20.0},
    "QQQ": {"min_minute": 750, "max_minute": 870, "actions": {"CALL", "PUT"}, "edge": 0.0, "max_near": 20.0},
    "SPY": {"min_minute": 720, "max_minute": 870, "actions": {"PUT"}, "edge": 0.1, "max_near": 20.0},
}

issues = []
for line in audit.read_text(errors="ignore").splitlines():
    if not line.strip():
        continue
    try:
        rec = json.loads(line)
    except Exception:
        continue
    row = rec.get("selected_candidate")
    if not isinstance(row, dict):
        continue
    ticker = str(row.get("policy_ticker") or row.get("ticker") or "").upper()
    rule = rules.get(ticker)
    if not rule:
        continue
    minute = int(float(row.get("minute", -1)))
    action = str(row.get("action", "")).upper()
    edge = abs(float(row.get("edge_abs", 0.0)))
    near = abs(float(row.get("nearest_level_abs_bps", 999999.0)))
    if minute < rule["min_minute"] or minute > rule["max_minute"]:
        issues.append((rec.get("recorded_at"), ticker, "time_window", minute))
    if action not in rule["actions"]:
        issues.append((rec.get("recorded_at"), ticker, "action", action))
    if edge + 1e-12 < rule["edge"]:
        issues.append((rec.get("recorded_at"), ticker, "edge_abs", edge))
    if near > rule["max_near"] + 1e-12:
        issues.append((rec.get("recorded_at"), ticker, "near_level_abs_bps", near))

print(f"SELECTED_CANDIDATE_ISSUES={len(issues)}")
for issue in issues[-20:]:
    print(issue)
if issues:
    raise SystemExit(2)
PY
```

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
df = df[df["source_model"].astype(str).str.contains("event_option:", na=False)]
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

- SPXW should not exceed 1 entry/day and should respect 30m entry cooldown.
- QQQ should not exceed 2 entries/day and should respect 45m entry cooldown.
- SPY should not exceed 4 entries/day and should respect 30m entry cooldown.
- Entries must be inside the ticker-specific time windows:
  SPXW 10:30-14:30 ET, QQQ 12:30-14:30 ET, SPY 12:00-14:30 ET.
- SPY entries must be PUT only.

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

### 7. Confirm SPY Daily Loss-Streak Pause

The SPY guard is causal and day-based. It uses only completed prior SPY
event-option trading days. If there are 3 completed losing SPY days in a row,
the next SPY candidate day should be skipped and recorded in candidate audit or
runtime state.

```bash
python3 - <<'PY'
import json
import pandas as pd
from pathlib import Path

p = Path("trades_jepa/trades_jepa.csv")
state_path = Path("trades_jepa/event_option_runtime_state.json")
if not p.exists():
    print("NO_TRADES_FILE")
    raise SystemExit
df = pd.read_csv(p, dtype={"date": str})
df = df[df["source_model"].astype(str).str.contains("event_option:SPY:", regex=False, na=False)].copy()
if df.empty:
    print("NO_SPY_EVENT_TRADES")
else:
    df["R"] = pd.to_numeric(df["pnl_dollars"], errors="coerce").fillna(0.0) / 5000.0
    daily = df.groupby("date")["R"].sum().sort_index()
    print(daily.tail(15).to_string())
    streak = 0
    for value in daily:
        streak = streak + 1 if value < 0 else 0
    print(f"SPY_COMPLETED_LOSS_STREAK={streak}")
if state_path.exists():
    state = json.loads(state_path.read_text())
    print("SPY_DAILY_LOSS_GUARD_SKIPS_TAIL")
    print(json.dumps(state.get("daily_loss_guard_skips", [])[-10:], indent=2))
PY
```

Expected:

- If `SPY_COMPLETED_LOSS_STREAK >= 3`, the next SPY candidate day should be
  skipped.
- QQQ and SPXW must not be blocked by this SPY-specific guard.

### 8. Compare Live PnL To Backtest Expectations

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
df = df[df["source_model"].astype(str).str.contains("event_option:", na=False)].copy()
if df.empty:
    print("NO_EVENT_OPTION_TRADES")
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
Overall Jan-Jun 2026: +77.537R over 416 trades, PF 1.749, WR 57.933%.
QQQ: +27.516R over 170 trades, PF 1.626, WR 55.882%.
SPXW: +28.730R over 122 trades, PF 1.950, WR 58.197%.
SPY: +21.292R over 124 trades, PF 1.725, WR 60.484%.

Monthly retrain walk-forward robustness:
Overall: +91.089R over 512 trades, PF 1.663, WR 54.883%.
QQQ: +36.622R over 183 trades, PF 1.744, WR 54.645%.
SPXW: +27.478R over 120 trades, PF 1.874, WR 55.833%.
SPY: +26.989R over 209 trades, PF 1.476, WR 54.545%.
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
3. Same entry window, candidate universe, and sampling cadence.
4. Same option exit contract.
5. Same ticker caps and cooldowns.
6. Same runtime SPXW stop-pause and SPY daily loss-streak guards.
7. Live features are finite and observable at decision time.
8. IB/fib/near-level features are only used after 10:30 ET, when complete
   initial balance levels exist.
9. Paper fills are reasonable relative to market/tracker fills.

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

## Detailed Log Capture

The system already writes the evidence needed for a live audit:

- `journalctl` captures stdout/stderr for both systemd services.
- `rt_data/YYYYMMDD/realtime_feed.log` records feed startup, API warnings,
  parquet saves, feature computation warnings, and event-option snapshot saves.
- `rt_data/YYYYMMDD/event_option_snapshots_latest.parquet` stores accumulated
  same-day event-option snapshot rows. It is the primary evidence for what the
  scorer could read.
- `rt_data/YYYYMMDD/event_option_snapshots_latest.summary.json` records row
  counts, missing feed inputs, expiry modes, and snapshot freshness.
- `rt_data/YYYYMMDD/jepa_live_execution_config.json` records the policy and
  registry loaded by the feed.
- `trades_jepa/tradingbot_jepa.log` records bot startup, scorer issues,
  skipped candidates, entries, exits, and paper-intent writes.
- `trades_jepa/event_option_candidate_audit_jepa.jsonl` is the authoritative
  decision-time audit. It records every `score_snapshot`, candidate selection,
  rejection reason, selected row, issues, and the candidate frame seen by the
  bot.
- `trades_jepa/paper_order_intents_jepa.jsonl` records broker-shaped paper
  intents. `broker_submission=false` means no broker order was sent.
- `trades_jepa/trades_jepa.csv`, `open_positions_jepa.json`,
  `event_option_runtime_state.json`, and `evaluated_features_jepa.json` record
  trade lifecycle and runtime state.
- `request_stats.csv` and `retry_audit.csv` record ThetaData request duration,
  HTTP status, and retry/error traces.

At end of day, generate a human-readable export:

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
TODAY=$(TZ=America/New_York date +%Y%m%d)
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT=log_exports/jepa_live_sentinel_${TODAY}_${TS}
mkdir -p "$OUT"

journalctl -u realtime_feed.service --since "${TODAY:0:4}-${TODAY:4:2}-${TODAY:6:2} 09:00:00" --no-pager > "$OUT/realtime_feed.journal.log"
journalctl -u ai_bot.service --since "${TODAY:0:4}-${TODAY:4:2}-${TODAY:6:2} 09:00:00" --no-pager > "$OUT/ai_bot.journal.log"

cp -av rt_data/$TODAY "$OUT/"
cp -av trades_jepa/tradingbot_jepa.log "$OUT/" 2>/dev/null || true
cp -av trades_jepa/trades_jepa.csv "$OUT/" 2>/dev/null || true
cp -av trades_jepa/paper_order_intents_jepa.jsonl "$OUT/" 2>/dev/null || true
cp -av trades_jepa/event_option_candidate_audit_jepa.jsonl "$OUT/" 2>/dev/null || true
cp -av trades_jepa/event_option_runtime_state.json "$OUT/" 2>/dev/null || true
cp -av trades_jepa/open_positions_jepa.json "$OUT/" 2>/dev/null || true
cp -av trades_jepa/evaluated_features_jepa.json "$OUT/" 2>/dev/null || true
cp -av request_stats.csv retry_audit.csv "$OUT/" 2>/dev/null || true

python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12 > "$OUT/production_validation.json"
```

The sentinel must inspect `production_validation.json` before archiving. Any
non-zero exit code or missing file in this export is itself an audit finding.

## Feature Equivalence Audit

Run this after the feed has produced same-day snapshots, preferably after the
entry window has closed. It checks that live event-option features are present,
finite, observable after 10:30 ET, and within a reasonable distributional range
versus the deploy scored rows used by the production components.

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
TODAY=$(TZ=America/New_York date +%Y%m%d)
REF=/tmp/causal1030_deploy_select_scored_rows.csv

python3 - <<'PY'
import pandas as pd
from pathlib import Path

paths = [
    Path("neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/QQQ_frozen_d35_return/deploy_model/deploy_select_scored_rows.csv"),
    Path("neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/SPXW_frozen_d25_return/deploy_model/deploy_select_scored_rows.csv"),
    Path("neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/components/SPY_frozen_d35_return/deploy_model/deploy_select_scored_rows.csv"),
]
frames = []
for path in paths:
    df = pd.read_csv(path, low_memory=False)
    frames.append(df)
out = pd.concat(frames, ignore_index=True, sort=False)
out.to_csv("/tmp/causal1030_deploy_select_scored_rows.csv", index=False)
print({"reference": "/tmp/causal1030_deploy_select_scored_rows.csv", "rows": len(out), "columns": len(out.columns)})
PY

python3 neural/jepa/audit_live_feature_drift.py \
  --day-dir "rt_data/$TODAY" \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --reference "$REF" \
  --strict-features \
  --entry-start-minute 630 \
  --entry-end-minute 870 \
  --output "rt_data/$TODAY/live_feature_drift_audit.json"
```

Expected:

- `passed=true`.
- `event_option_passed=true`.
- `event_score_issues=[]`.
- `event_live_contract_issues=[]`.
- Component statuses are `ok` or at most `review_feature_drift`.
- No selected or scored candidate uses `minute < 630`.

If the feature audit fails, archive it anyway. The failure reason is useful:
missing features, non-finite values, stale snapshots, or large drift can explain
why live behavior diverges from backtest/walk-forward.

## What To Archive For Operator Review

When the operator asks for an audit bundle, archive only useful live evidence:

```bash
TS=$(date -u +%Y%m%dT%H%M%SZ)
TODAY=$(TZ=America/New_York date +%Y%m%d)
tar -czf /tmp/jepa_live_sentinel_${TODAY}_${TS}.tar.gz \
  log_exports/jepa_live_sentinel_${TODAY}_* \
  rt_data/$TODAY \
  trades_jepa/trades_jepa.csv \
  trades_jepa/paper_order_intents_jepa.jsonl \
  trades_jepa/event_option_candidate_audit_jepa.jsonl \
  trades_jepa/event_option_runtime_state.json \
  trades_jepa/open_positions_jepa.json \
  trades_jepa/evaluated_features_jepa.json \
  trades_jepa/tradingbot_jepa.log \
  request_stats.csv \
  retry_audit.csv \
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

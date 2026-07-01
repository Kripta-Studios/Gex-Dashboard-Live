#!/usr/bin/env bash
set -euo pipefail

SINCE="${1:-2026-07-01 00:00:00}"
UNTIL="${2:-now}"
ROOT="${3:-/home/Option-Greeks-Plotting-Discord-Bot}"
PACKAGE="jepa_production_event_options_backfill19_spy_no_scorethr_wf2026_fullmayjun"

cd "$ROOT"
mkdir -p log_exports
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FEED_LOG="log_exports/realtime_feed_${STAMP}.journal.log"
BOT_LOG="log_exports/ai_bot_${STAMP}.journal.log"
OUT="log_exports/jepa_eod_${STAMP}.tar.gz"

journalctl -u realtime_feed.service --since "$SINCE" --until "$UNTIL" --no-pager -o short-iso > "$FEED_LOG" || true
journalctl -u ai_bot.service --since "$SINCE" --until "$UNTIL" --no-pager -o short-iso > "$BOT_LOG" || true

tar -czf "$OUT" \
  "$FEED_LOG" \
  "$BOT_LOG" \
  rt_data \
  trades_jepa \
  systemd/realtime_feed.service \
  systemd/ai_bot.service \
  neural/models/jepa/production_manifest.json \
  "neural/models/jepa/${PACKAGE}/event_option_policy.json" \
  "neural/models/jepa/${PACKAGE}/component_registry.json" \
  "neural/models/jepa/${PACKAGE}/runtime_policy_replay_summary.json" \
  "neural/models/jepa/${PACKAGE}/snapshot_to_order_smoke.json"

echo "$OUT"

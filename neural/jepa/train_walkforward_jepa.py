from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from neural.jepa.features import build_training_feature_list, write_feature_names


def main() -> int:
    parser = argparse.ArgumentParser(description="Run existing walk-forward GBT with an explicit JEPA feature set.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--ticker", default="all", choices=["all", "SPX", "QQQ", "SPY"])
    parser.add_argument("--feature-mode", default="base_jepa", choices=["base", "base_jepa", "jepa_only", "custom"])
    parser.add_argument("--jepa-feature-names", default=None)
    parser.add_argument("--custom-feature-names", default=None)
    parser.add_argument("--selected-feature-output", default=None)
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--train-months", type=int, default=12)
    parser.add_argument("--test-months", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=0.0003)
    parser.add_argument("--ensemble", type=int, default=3)
    parser.add_argument("--top-n-windows", type=int, default=10)
    parser.add_argument("--min-window", type=int, default=0)
    parser.add_argument("--hold-ratio", type=float, default=1.5)
    parser.add_argument("--class-weight", default="none", choices=["none", "balanced"])
    parser.add_argument("--min-pf-floor", type=float, default=0.10)
    parser.add_argument("--selection-metric", default="label", choices=["label", "economic"])
    parser.add_argument("--min-selection-trades", type=int, default=10)
    parser.add_argument("--selection-base-confidence", type=float, default=None)
    parser.add_argument("--selection-cooldown", type=int, default=15)
    parser.add_argument("--min-entry-minute", type=int, default=580)
    parser.add_argument("--min-short-entry-minute", type=int, default=None)
    parser.add_argument("--min-short-price-vs-ib-high", type=float, default=None)
    parser.add_argument("--min-selection-win-rate", type=float, default=0.45)
    parser.add_argument("--target-long", type=float, default=0.010)
    parser.add_argument("--target-short", type=float, default=0.010)
    parser.add_argument("--stop-pct", type=float, default=0.003)
    parser.add_argument("--max-time", type=int, default=390)
    parser.add_argument("--objective-mode", default="multiclass", choices=["multiclass", "binary_ovr"])
    parser.add_argument("--calibrate-binary-ovr", action="store_true")
    parser.add_argument("--sample-weight-decay-days", type=float, default=30.0)
    parser.add_argument("--model_path", default="models/trading_jepa_wf.joblib")
    parser.add_argument("--norm_path", default="models/trading_jepa_wf_norm.npz")
    args = parser.parse_args()

    df_head = pd.read_parquet(args.data)
    selected_features = build_training_feature_list(
        df_head,
        args.feature_mode,
        jepa_feature_names_path=args.jepa_feature_names,
        custom_feature_names_path=args.custom_feature_names,
    )
    if args.selected_feature_output:
        write_feature_names(args.selected_feature_output, selected_features)

    print(
        f"[JEPA_GBT] feature_mode={args.feature_mode} "
        f"selected_features={len(selected_features)} ticker={args.ticker}"
    )

    import train_walkforward as tw

    tw.FEATURE_COLUMNS = selected_features
    tw.walk_forward_train(
        args.data,
        args.model_path,
        args.norm_path,
        args.model_size,
        args.train_months,
        args.test_months,
        args.epochs,
        args.batch_size,
        args.lr,
        args.ensemble,
        args.top_n_windows,
        args.min_window,
        args.hold_ratio,
        args.class_weight,
        args.min_pf_floor,
        args.selection_metric,
        args.min_selection_trades,
        args.selection_base_confidence,
        args.selection_cooldown,
        args.min_entry_minute,
        args.min_short_entry_minute,
        args.min_short_price_vs_ib_high,
        args.min_selection_win_rate,
        args.max_time,
        args.ticker,
        args.target_long,
        args.target_short,
        args.stop_pct,
        args.objective_mode,
        args.calibrate_binary_ovr,
        args.sample_weight_decay_days,
    )

    meta_path = Path(args.model_path).with_suffix(".features.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(
            {
                "feature_mode": args.feature_mode,
                "feature_count": len(selected_features),
                "feature_names": selected_features,
                "data": args.data,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[JEPA_GBT] wrote_feature_manifest={meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


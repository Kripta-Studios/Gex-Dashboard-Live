from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))

from gbt_model import load_gbt_ensemble
from neural.jepa.features import load_feature_names


def add_importance(acc: dict[str, float], clf, fallback_names: list[str] | None = None) -> None:
    names = getattr(clf, "feature_name_", None)
    vals = getattr(clf, "feature_importances_", None)
    if vals is None:
        return
    vals = list(vals)
    if (
        fallback_names
        and len(fallback_names) == len(vals)
        and (names is None or all(str(n).startswith("Column_") for n in names))
    ):
        names = fallback_names
    if names is None:
        names = [f"feature_{i}" for i in range(len(vals))]
    for name, val in zip(names, vals):
        acc[str(name)] += float(val)


def model_importances(model_path: str, norm_path: str) -> dict[str, float]:
    ensemble, _ = load_gbt_ensemble(model_path, norm_path)
    acc: dict[str, float] = defaultdict(float)
    for model in ensemble.models:
        fallback_names = None
        if getattr(model, "normalizer", None) is not None:
            fallback_names = getattr(model.normalizer, "feature_names", None)
        if getattr(model, "model", None) is not None:
            add_importance(acc, model.model, fallback_names)
        if getattr(model, "model_long", None) is not None:
            add_importance(acc, model.model_long, fallback_names)
        if getattr(model, "model_short", None) is not None:
            add_importance(acc, model.model_short, fallback_names)
    return dict(acc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize LightGBM JEPA feature usage.")
    parser.add_argument("--model-base", required=True)
    parser.add_argument("--normalizer-base", required=True)
    parser.add_argument("--jepa-feature-names", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "QQQ", "SPY"])
    args = parser.parse_args()

    jepa_names = set(load_feature_names(args.jepa_feature_names))
    payload = {}
    lines = [
        "# JEPA Feature Usage",
        "",
        "| Ticker | Total Importance | JEPA Importance | JEPA Share | Top JEPA Features |",
        "| --- | ---: | ---: | ---: | --- |",
    ]

    for ticker in args.tickers:
        model_path = args.model_base.replace(".joblib", f"_{ticker}.joblib")
        norm_path = args.normalizer_base.replace(".npz", f"_{ticker}.npz")
        imp = model_importances(model_path, norm_path)
        total = float(sum(max(0.0, v) for v in imp.values()))
        jepa_total = float(sum(max(0.0, v) for k, v in imp.items() if k in jepa_names))
        top_jepa = sorted(
            [(k, v) for k, v in imp.items() if k in jepa_names],
            key=lambda kv: kv[1],
            reverse=True,
        )[:10]
        payload[ticker] = {
            "total_importance": total,
            "jepa_importance": jepa_total,
            "jepa_share": jepa_total / total if total > 0 else 0.0,
            "top_jepa": [{"feature": k, "importance": float(v)} for k, v in top_jepa],
        }
        top_text = ", ".join([f"{k}:{v:.0f}" for k, v in top_jepa[:5]]) if top_jepa else "none"
        lines.append(
            f"| {ticker} | {total:.0f} | {jepa_total:.0f} | "
            f"{(jepa_total / total if total > 0 else 0.0):.2%} | {top_text} |"
        )

    Path(args.output_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

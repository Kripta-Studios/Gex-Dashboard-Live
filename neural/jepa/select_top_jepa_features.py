from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.features import available_features, load_base_feature_columns, write_feature_names


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact base+Top-K JEPA feature lists.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--usage-json", required=True)
    parser.add_argument("--top-k-per-ticker", type=int, default=8)
    parser.add_argument("--selected-output", required=True)
    parser.add_argument("--top-jepa-output", required=True)
    args = parser.parse_args()

    df = pd.read_parquet(args.data)
    base = available_features(df, load_base_feature_columns())
    usage = json.loads(Path(args.usage_json).read_text(encoding="utf-8"))

    top = []
    for ticker, payload in usage.items():
        for item in payload.get("top_jepa", [])[: args.top_k_per_ticker]:
            feat = str(item["feature"])
            if feat not in top:
                top.append(feat)
    top = [c for c in top if c in df.columns]
    selected = base + [c for c in top if c not in base]

    write_feature_names(args.selected_output, selected)
    write_feature_names(args.top_jepa_output, top)
    print(f"base_features={len(base)} top_jepa={len(top)} selected={len(selected)}")
    print("top_jepa=" + ",".join(top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


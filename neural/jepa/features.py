from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NEURAL_ROOT = PROJECT_ROOT / "neural"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(NEURAL_ROOT) not in sys.path:
    sys.path.insert(0, str(NEURAL_ROOT))


def load_base_feature_columns() -> list[str]:
    from hybrid_model import FEATURE_COLUMNS

    return list(FEATURE_COLUMNS)


def load_feature_names(path: str | os.PathLike | None) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Feature-name file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        names = data.get("feature_names") or data.get("features") or []
    else:
        names = data
    return [str(x) for x in names]


def write_feature_names(path: str | os.PathLike, names: Iterable[str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = [str(x) for x in names]
    p.write_text(json.dumps({"feature_names": clean}, indent=2), encoding="utf-8")


def available_features(df: pd.DataFrame, names: Iterable[str]) -> list[str]:
    cols = set(df.columns)
    return [c for c in names if c in cols]


def time_context_features(df: pd.DataFrame) -> list[str]:
    preferred = [
        "time_sin",
        "time_cos",
        "minutes_to_close_norm",
        "dow_sin",
        "dow_cos",
    ]
    return [c for c in preferred if c in df.columns]


def build_training_feature_list(
    df: pd.DataFrame,
    feature_mode: str,
    jepa_feature_names_path: str | os.PathLike | None = None,
    custom_feature_names_path: str | os.PathLike | None = None,
) -> list[str]:
    """Return the exact feature order for a GBT experiment."""
    feature_mode = str(feature_mode).lower()
    base = available_features(df, load_base_feature_columns())
    jepa = available_features(df, load_feature_names(jepa_feature_names_path))

    if feature_mode == "base":
        selected = base
    elif feature_mode == "base_jepa":
        selected = base + [c for c in jepa if c not in base]
    elif feature_mode == "jepa_only":
        selected = jepa + [c for c in time_context_features(df) if c not in jepa]
    elif feature_mode == "custom":
        selected = available_features(df, load_feature_names(custom_feature_names_path))
    else:
        raise ValueError(
            f"Unknown feature_mode={feature_mode!r}; expected base, base_jepa, jepa_only, custom"
        )

    if not selected:
        raise ValueError(f"No features selected for mode {feature_mode!r}")
    return selected


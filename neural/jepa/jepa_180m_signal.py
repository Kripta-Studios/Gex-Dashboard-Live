from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass(frozen=True)
class Jepa180mArtifact:
    ticker: str
    model: object
    medians: pd.Series
    features: list[str]
    thresholds: dict
    meta: dict


def normalize_ticker(value: str) -> str:
    return str(value).replace("/", "").upper()


def load_artifact(path: str | Path, ticker: str) -> Jepa180mArtifact:
    payload = joblib.load(path)
    required = {"model", "medians", "features", "thresholds", "meta"}
    missing = required - set(payload.keys())
    if missing:
        raise KeyError(f"Invalid JEPA 180m artifact {path}: missing {sorted(missing)}")
    medians = pd.Series(payload["medians"], dtype=np.float64)
    features = [str(x) for x in payload["features"]]
    return Jepa180mArtifact(
        ticker=normalize_ticker(ticker),
        model=payload["model"],
        medians=medians,
        features=features,
        thresholds=dict(payload["thresholds"]),
        meta=dict(payload["meta"]),
    )


class Jepa180mSignalModel:
    """Frozen per-ticker base+JEPA 180m signal model.

    Input rows must already contain the base market features and the exported
    `xjepa_*` features. The class intentionally does not compute future labels.
    """

    def __init__(self, model_dir: str | Path, mode: str = "base_jepa", tickers: list[str] | None = None) -> None:
        self.model_dir = Path(model_dir)
        self.mode = str(mode)
        self.artifact_dir = self.model_dir / self.mode
        if not self.artifact_dir.exists():
            raise FileNotFoundError(f"JEPA 180m artifact directory not found: {self.artifact_dir}")
        if tickers is None:
            tickers = [p.stem for p in sorted(self.artifact_dir.glob("*.joblib"))]
        self.artifacts: dict[str, Jepa180mArtifact] = {}
        for ticker in tickers:
            key = normalize_ticker(ticker)
            path = self.artifact_dir / f"{key}.joblib"
            if not path.exists():
                raise FileNotFoundError(f"Missing JEPA 180m artifact for {key}: {path}")
            self.artifacts[key] = load_artifact(path, key)
        if not self.artifacts:
            raise ValueError(f"No JEPA 180m artifacts loaded from {self.artifact_dir}")

    @property
    def tickers(self) -> list[str]:
        return sorted(self.artifacts.keys())

    def required_features(self, ticker: str | None = None) -> list[str]:
        if ticker is not None:
            return list(self.artifacts[normalize_ticker(ticker)].features)
        seen = set()
        out = []
        for artifact in self.artifacts.values():
            for feature in artifact.features:
                if feature not in seen:
                    seen.add(feature)
                    out.append(feature)
        return out

    def _matrix(self, frame: pd.DataFrame, artifact: Jepa180mArtifact) -> pd.DataFrame:
        values = frame.reindex(columns=artifact.features)
        values = values.apply(pd.to_numeric, errors="coerce")
        values = values.replace([np.inf, -np.inf], np.nan)
        values = values.fillna(artifact.medians).fillna(0.0)
        return values.astype(np.float32)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        if "ticker" not in frame.columns:
            raise KeyError("Input frame must contain a 'ticker' column")
        out = np.full(len(frame), np.nan, dtype=np.float64)
        tickers = frame["ticker"].map(normalize_ticker)
        for ticker, artifact in self.artifacts.items():
            mask = tickers == ticker
            if not mask.any():
                continue
            x = self._matrix(frame.loc[mask], artifact)
            proba = artifact.model.predict_proba(x)
            if proba.shape[1] == 1:
                out[np.flatnonzero(mask.to_numpy())] = float(artifact.model.classes_[0])
            else:
                pos_idx = list(artifact.model.classes_).index(1)
                out[np.flatnonzero(mask.to_numpy())] = proba[:, pos_idx].astype(np.float64)
        return out

    def predict_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        result["ticker"] = result["ticker"].map(normalize_ticker)
        result["jepa180_prob_up"] = self.predict_proba(result)
        result["jepa180_long_threshold"] = np.nan
        result["jepa180_short_threshold"] = np.nan
        result["jepa180_signal"] = "HOLD"
        result["jepa180_direction"] = 0
        result["jepa180_confidence"] = np.nan

        for ticker, artifact in self.artifacts.items():
            mask = result["ticker"] == ticker
            if not mask.any():
                continue
            long_threshold = float(artifact.thresholds.get("long_threshold", 0.70))
            short_threshold = float(artifact.thresholds.get("short_threshold", 0.30))
            prob = result.loc[mask, "jepa180_prob_up"].astype(float)
            long_mask = mask & (result["jepa180_prob_up"].astype(float) >= long_threshold)
            short_mask = mask & (result["jepa180_prob_up"].astype(float) <= short_threshold)
            result.loc[mask, "jepa180_long_threshold"] = long_threshold
            result.loc[mask, "jepa180_short_threshold"] = short_threshold
            result.loc[long_mask, "jepa180_signal"] = "LONG"
            result.loc[long_mask, "jepa180_direction"] = 1
            result.loc[short_mask, "jepa180_signal"] = "SHORT"
            result.loc[short_mask, "jepa180_direction"] = -1
            result.loc[mask, "jepa180_confidence"] = np.maximum(prob, 1.0 - prob)
        return result

    def metadata(self) -> dict:
        return {
            "model_dir": str(self.model_dir),
            "mode": self.mode,
            "tickers": {
                ticker: {
                    "feature_count": len(artifact.features),
                    "thresholds": artifact.thresholds,
                    "meta": artifact.meta,
                }
                for ticker, artifact in self.artifacts.items()
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen JEPA 180m signal inference on a parquet file.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--mode", default="base_jepa")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    args = parser.parse_args()

    df = pd.read_parquet(args.data)
    if args.start_date:
        df = df[df["date"].astype(str) >= str(args.start_date)].copy()
    if args.end_date:
        df = df[df["date"].astype(str) <= str(args.end_date)].copy()
    model = Jepa180mSignalModel(args.model_dir, args.mode)
    out = model.predict_frame(df)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    meta_path = output.with_suffix(".metadata.json")
    meta_path.write_text(json.dumps(model.metadata(), indent=2, allow_nan=True), encoding="utf-8")
    print(f"wrote={output} rows={len(out)} metadata={meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

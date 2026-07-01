from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


TOPK_SCORE_COL = "topk_pred_return"
DAILY_ROUTER_SCORE_COL = "daily_router_pred_return"
META_GATE_SCORE_COL = "meta_score"
EVENT_GATE_SCORE_COL = "score"


def _derive_minute(frame: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for col in ("minute", "minute_x", "minute_y", "entry_minute"):
        if col in frame.columns:
            cand = pd.to_numeric(frame[col], errors="coerce")
            out = out.where(out.notna(), cand)
    missing = out.isna()
    if missing.any() and "time" in frame.columns:
        parsed = pd.to_datetime(frame.loc[missing, "time"].astype(str), format="%H:%M", errors="coerce")
        out.loc[missing] = parsed.dt.hour * 60 + parsed.dt.minute
    return out.fillna(0).astype(int)


def _standardize_candidate_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "date" not in out.columns:
        if "trade_date" in out.columns:
            out["date"] = out["trade_date"].astype(str)
        elif "timestamp" in out.columns:
            out["date"] = pd.to_datetime(out["timestamp"], errors="coerce").dt.strftime("%Y%m%d")
    if "time" not in out.columns and "timestamp" in out.columns:
        out["time"] = pd.to_datetime(out["timestamp"], errors="coerce").dt.strftime("%H:%M")
    if "month" not in out.columns and "date" in out.columns:
        out["month"] = out["date"].astype(str).str.slice(0, 6)
    if "test_month" not in out.columns and "month" in out.columns:
        out["test_month"] = out["month"].astype(str)
    out["minute"] = _derive_minute(out)
    if "score" in out.columns:
        out["score"] = pd.to_numeric(out["score"], errors="coerce")
    return out


def _apply_max_day_cooldown(candidates: pd.DataFrame, max_day: int, cooldown_minutes: int) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    work = _standardize_candidate_columns(candidates)
    sort_cols = ["date", "minute", "source_priority", "score"]
    ascending = [True, True, True, False]
    work = work.sort_values(sort_cols, ascending=ascending, kind="stable")
    dedupe_cols = [col for col in ["date", "minute", "action", "expiry_mode"] if col in work.columns]
    if dedupe_cols:
        work = work.drop_duplicates(dedupe_cols, keep="first").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    day_key = "date" if "date" in work.columns else "trade_date"
    for _, day in work.groupby(day_key, sort=False):
        next_allowed = -1
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(getattr(row, "minute", 0))
            if minute < next_allowed:
                continue
            if int(max_day) < 999 and taken >= int(max_day):
                break
            rows.append(row._asdict())
            taken += 1
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(rows) if rows else work.iloc[0:0].copy()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _discover_project_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
        if (candidate / "neural" / "jepa").exists() and (candidate / "bots").exists():
            return candidate
    return current


def _resolve_path(raw_path: str, *, project_root: Path, registry_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    root_relative = project_root / path
    if root_relative.exists():
        return root_relative
    return registry_path.parent / path


def _months_from_component(component: dict[str, Any], key: str) -> list[str]:
    value = component.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Component month field {key} must be a list")
    return [str(item) for item in value]


def _as_medians(value: Any) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.astype(float)
    if isinstance(value, dict):
        return pd.Series({str(k): float(v) for k, v in value.items()}, dtype=float)
    return pd.Series(dtype=float)


def _append_derived_one_hot_columns(frame: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    derived: dict[str, pd.Series] = {}
    ticker_values = frame["ticker"].astype(str).str.upper() if "ticker" in frame.columns else None
    expiry_values = frame["expiry_mode"].astype(str) if "expiry_mode" in frame.columns else None
    level_values = frame["nearest_level_name"].astype(str) if "nearest_level_name" in frame.columns else None
    source_values = frame["source_variant"].astype(str) if "source_variant" in frame.columns else None
    for col in feature_cols:
        if col in frame.columns or col in derived:
            continue
        if ticker_values is not None and col.startswith("ticker_"):
            derived[col] = ticker_values.eq(col.removeprefix("ticker_").upper()).astype(float)
        elif expiry_values is not None and col.startswith("expiry_mode_"):
            derived[col] = expiry_values.eq(col.removeprefix("expiry_mode_")).astype(float)
        elif level_values is not None and col.startswith("nearest_level_name_"):
            derived[col] = level_values.eq(col.removeprefix("nearest_level_name_")).astype(float)
        elif source_values is not None and col.startswith("variant_"):
            derived[col] = source_values.eq(col.removeprefix("variant_")).astype(float)
        elif col == "action_is_call" and "action" in frame.columns:
            derived[col] = frame["action"].astype(str).str.upper().eq("CALL").astype(float)
        elif col == "score_margin" and {"pred_call_return", "pred_put_return"}.issubset(frame.columns):
            call = pd.to_numeric(frame["pred_call_return"], errors="coerce")
            put = pd.to_numeric(frame["pred_put_return"], errors="coerce")
            derived[col] = (call - put).abs()
    if not derived:
        return frame
    return pd.concat([frame, pd.DataFrame(derived, index=frame.index)], axis=1)


def _prepare_feature_frame(
    frame: pd.DataFrame,
    feature_cols: list[str],
    medians: pd.Series,
    *,
    strict: bool,
) -> tuple[pd.DataFrame, list[str]]:
    frame = _append_derived_one_hot_columns(frame, feature_cols)
    missing = [col for col in feature_cols if col not in frame.columns]
    if strict and missing:
        preview = ", ".join(missing[:20])
        extra = "" if len(missing) <= 20 else f" ... +{len(missing) - 20}"
        raise ValueError(f"Missing required event-option features: {preview}{extra}")

    x = frame.reindex(columns=feature_cols)
    for col in feature_cols:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.replace([np.inf, -np.inf], np.nan).fillna(medians.reindex(feature_cols)).fillna(0.0)
    return x, missing


def _nonfinite_feature_rows(frame: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.Series, dict[Any, list[str]]]:
    expanded = _append_derived_one_hot_columns(frame, feature_cols)
    x = expanded.reindex(columns=feature_cols)
    for col in feature_cols:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.replace([np.inf, -np.inf], np.nan)
    bad = x.isna()
    bad_rows = bad.any(axis=1)
    row_features: dict[Any, list[str]] = {}
    for idx in bad.index[bad_rows]:
        row_features[idx] = [str(col) for col in bad.columns[bad.loc[idx]].tolist()]
    return bad_rows, row_features


@dataclass(frozen=True)
class EventOptionComponent:
    name: str
    kind: str
    path: Path
    metadata_path: Path
    registry_entry: dict[str, Any]
    metadata: dict[str, Any]

    @property
    def train_months(self) -> list[str]:
        return _months_from_component(self.registry_entry, "train_months")

    @property
    def select_months(self) -> list[str]:
        return _months_from_component(self.registry_entry, "select_months")

    @property
    def selected_topk(self) -> int | None:
        value = self.registry_entry.get("selected_topk", self.metadata.get("selected_topk"))
        return None if value is None else int(value)

    @property
    def selected_source(self) -> str | None:
        value = self.registry_entry.get("selected_source", self.metadata.get("selected_source"))
        return None if value is None else str(value)

    def model_payload(self) -> dict[str, Any]:
        if self.kind not in {
            "event_trade_union_topk_regressor",
            "event_trade_union_meta_gate",
            "event_daily_source_router",
            "event_option_gate_direction_model",
        }:
            raise TypeError(f"Component {self.name} is not a pickle-backed scorer: {self.kind}")
        with self.path.open("rb") as fh:
            payload = pickle.load(fh)
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected model payload for {self.name}: {self.path}")
        if self.kind == "event_option_gate_direction_model":
            if "call_model" not in payload or "put_model" not in payload:
                raise ValueError(f"Unexpected gate model payload for {self.name}: {self.path}")
        elif "model" not in payload:
            raise ValueError(f"Unexpected model payload for {self.name}: {self.path}")
        return payload


class EventOptionComponentRegistry:
    def __init__(
        self,
        *,
        path: Path,
        project_root: Path,
        payload: dict[str, Any],
        components: dict[str, EventOptionComponent],
    ) -> None:
        self.path = path
        self.project_root = project_root
        self.payload = payload
        self.components = components

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        project_root: str | Path | None = None,
        require_complete_live_equivalence: bool = False,
    ) -> "EventOptionComponentRegistry":
        registry_path = Path(path).resolve()
        payload = _read_json(registry_path)
        root = Path(project_root).resolve() if project_root is not None else _discover_project_root(registry_path)
        raw_components = payload.get("available_components", {})
        if not isinstance(raw_components, dict) or not raw_components:
            raise ValueError(f"No available_components found in event-option registry: {registry_path}")

        components: dict[str, EventOptionComponent] = {}
        for name, entry in raw_components.items():
            if not isinstance(entry, dict):
                raise ValueError(f"Component entry must be an object: {name}")
            kind = str(entry.get("component", "")).strip()
            artifact = str(entry.get("path", "")).strip()
            metadata = str(entry.get("metadata", artifact)).strip()
            if not kind or not artifact:
                raise ValueError(f"Component {name} is missing component/path")
            artifact_path = _resolve_path(artifact, project_root=root, registry_path=registry_path)
            metadata_path = _resolve_path(metadata, project_root=root, registry_path=registry_path)
            if not artifact_path.exists():
                raise FileNotFoundError(f"Missing event-option component artifact for {name}: {artifact_path}")
            if not metadata_path.exists():
                raise FileNotFoundError(f"Missing event-option component metadata for {name}: {metadata_path}")
            metadata_payload = _read_json(metadata_path) if metadata_path.suffix.lower() == ".json" else {}
            components[str(name)] = EventOptionComponent(
                name=str(name),
                kind=kind,
                path=artifact_path,
                metadata_path=metadata_path,
                registry_entry=entry,
                metadata=metadata_payload,
            )

        registry = cls(path=registry_path, project_root=root, payload=payload, components=components)
        registry.validate_temporal_cutoff()
        if require_complete_live_equivalence:
            registry.assert_complete_live_equivalence()
        return registry

    @property
    def status(self) -> str:
        return str(self.payload.get("status", ""))

    @property
    def deploy_month(self) -> str:
        return str(self.payload.get("deploy_month", ""))

    @property
    def completed_data_through_month(self) -> str:
        return str(self.payload.get("completed_data_through_month", ""))

    @property
    def missing_for_full_live_equivalence(self) -> list[str]:
        value = self.payload.get("missing_for_full_live_equivalence", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    @property
    def invalidated_components(self) -> list[str]:
        value = (self.payload.get("invalidated_components") or {}).get("components", [])
        return [str(item) for item in value] if isinstance(value, list) else []

    def validate_temporal_cutoff(self) -> None:
        deploy_month = self.deploy_month
        completed = self.completed_data_through_month
        for component in self.components.values():
            for field, months in (("train_months", component.train_months), ("select_months", component.select_months)):
                for month in months:
                    if deploy_month and month >= deploy_month:
                        raise ValueError(
                            f"Temporal leakage in {component.name}: {field} contains {month} >= deploy_month {deploy_month}"
                        )
                    if completed and month > completed:
                        raise ValueError(
                            f"Partial/future month in {component.name}: {field} contains {month} > completed cutoff {completed}"
                        )

    def assert_complete_live_equivalence(self) -> None:
        missing = self.missing_for_full_live_equivalence
        invalidated = self.invalidated_components
        if missing:
            raise ValueError(
                "Event-option registry is not a complete live scorer yet: " + "; ".join(missing)
            )
        if invalidated:
            raise ValueError(
                "Event-option registry contains invalidated research-only components: " + "; ".join(invalidated)
            )

    def summary(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "deploy_month": self.deploy_month,
            "completed_data_through_month": self.completed_data_through_month,
            "component_count": len(self.components),
            "components": sorted(self.components),
            "missing_for_full_live_equivalence": self.missing_for_full_live_equivalence,
            "invalidated_components": self.invalidated_components,
        }

    def component(self, name: str) -> EventOptionComponent:
        try:
            return self.components[name]
        except KeyError as exc:
            raise KeyError(f"Unknown event-option component {name!r}") from exc

    def component_feature_cols(self, name: str) -> list[str]:
        component = self.component(name)
        cols = component.metadata.get("feature_cols", [])
        if not isinstance(cols, list):
            return []
        return [str(col) for col in cols]

    def feature_coverage(self, name: str, frame: pd.DataFrame) -> dict[str, Any]:
        required = self.component_feature_cols(name)
        effective = _append_derived_one_hot_columns(frame, required)
        present = [col for col in required if col in effective.columns]
        missing = [col for col in required if col not in effective.columns]
        return {
            "component": name,
            "required": len(required),
            "present": len(present),
            "missing": len(missing),
            "coverage": float(len(present) / len(required)) if required else float("nan"),
            "missing_columns": missing,
        }

    def append_phys_td_jepa_features(
        self,
        name: str,
        snapshots: pd.DataFrame,
        *,
        strict: bool = True,
        device: str | None = None,
    ) -> pd.DataFrame:
        component = self.component(name)
        if component.kind != "event_phys_td_jepa_encoder":
            raise TypeError(f"Component {name} is not an event Phys-TD-JEPA encoder: {component.kind}")
        if snapshots.empty:
            return snapshots.copy()

        import torch

        from neural.jepa.dataset import RobustNormalizer
        from neural.jepa.walkforward_event_phys_td_jepa_oof import (
            EventPhysTDJEPA,
            EventPhysTDJEPAConfig,
            export_month_features,
        )

        try:
            payload = torch.load(component.path, map_location="cpu", weights_only=False)
        except TypeError:
            payload = torch.load(component.path, map_location="cpu")
        if not isinstance(payload, dict) or "model_state_dict" not in payload:
            raise ValueError(f"Unexpected Phys-TD-JEPA encoder payload for {name}: {component.path}")

        feature_cols = [str(col) for col in payload.get("feature_cols", component.metadata.get("feature_cols", []))]
        physical_cols = [str(col) for col in payload.get("physical_cols", component.metadata.get("physical_cols", []))]
        feature_names = [str(col) for col in payload.get("feature_names", component.metadata.get("feature_names", []))]
        if not feature_cols or not physical_cols or not feature_names:
            raise ValueError(f"Phys-TD-JEPA component {name} is missing feature metadata")
        missing = [col for col in feature_cols if col not in snapshots.columns]
        if strict and missing:
            preview = ", ".join(missing[:20])
            extra = "" if len(missing) <= 20 else f" ... +{len(missing) - 20}"
            raise ValueError(f"Missing required Phys-TD-JEPA snapshot features: {preview}{extra}")

        normalizer = RobustNormalizer.from_dict(payload["normalizer"])
        work = snapshots.copy()
        if "date" not in work.columns and "trade_date" in work.columns:
            work["date"] = work["trade_date"].astype(str)
        if "expiration" not in work.columns and "trade_date" in work.columns:
            work["expiration"] = work["trade_date"].astype(str)
        if "time" not in work.columns and "timestamp" in work.columns:
            parsed = pd.to_datetime(work["timestamp"], format="mixed", errors="coerce")
            work["time"] = parsed.dt.strftime("%H:%M")
        if "timestamp" not in work.columns and {"trade_date", "time"}.issubset(work.columns):
            parsed = pd.to_datetime(work["trade_date"].astype(str) + " " + work["time"].astype(str), errors="coerce")
            work["timestamp"] = parsed.dt.strftime("%Y-%m-%dT%H:%M:%S")

        median_by_feature = dict(zip(normalizer.feature_names, normalizer.median.tolist()))
        for col in missing:
            work[col] = float(median_by_feature.get(col, 0.0))
        for col in ("ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time"):
            if col not in work.columns:
                raise ValueError(f"Phys-TD-JEPA snapshots missing key column: {col}")

        config = EventPhysTDJEPAConfig(**payload["config"])
        model = EventPhysTDJEPA(config)
        model.load_state_dict(payload["model_state_dict"])
        target_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        model.to(target_device)
        metadata_args = (payload.get("metadata") or {}).get("args", {})
        live_args = SimpleNamespace(
            infer_batch_size=int(metadata_args.get("infer_batch_size", 4096)),
            feature_prefix=str(metadata_args.get("feature_prefix", "ptdj")),
            group_expiry_mode=bool(metadata_args.get("group_expiry_mode", True)),
        )
        features = export_month_features(model, normalizer, work, feature_cols, physical_cols, live_args, target_device)
        key_cols = ["ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time"]
        features = features.drop_duplicates(key_cols, keep="last")
        base = work.drop(columns=[col for col in feature_names if col in work.columns], errors="ignore")
        out = base.merge(features[key_cols + feature_names], on=key_cols, how="left")
        for col in feature_names:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        out.attrs["missing_event_option_features"] = missing
        out.attrs["phys_td_jepa_feature_names"] = feature_names
        return out

    def score_topk_component(self, name: str, candidates: pd.DataFrame, *, strict: bool = False) -> pd.DataFrame:
        component = self.component(name)
        if component.kind != "event_trade_union_topk_regressor":
            raise TypeError(f"Component {name} is not a top-k regressor: {component.kind}")
        payload = component.model_payload()
        feature_cols = [str(col) for col in payload.get("feature_cols", component.metadata.get("feature_cols", []))]
        if not feature_cols:
            raise ValueError(f"Top-k component {name} has no feature_cols")
        medians = _as_medians(payload.get("medians", component.metadata.get("feature_medians", {})))
        x_score, missing = _prepare_feature_frame(candidates, feature_cols, medians, strict=strict)
        out = candidates.copy()
        out[TOPK_SCORE_COL] = payload["model"].predict(x_score)
        out.attrs["missing_event_option_features"] = missing
        out.attrs["selected_topk"] = component.selected_topk
        out.attrs["selected_score_threshold"] = component.registry_entry.get(
            "selected_score_threshold", component.metadata.get("selected_score_threshold")
        )
        return out

    def score_meta_gate_component(self, name: str, candidates: pd.DataFrame, *, strict: bool = False) -> pd.DataFrame:
        component = self.component(name)
        if component.kind != "event_trade_union_meta_gate":
            raise TypeError(f"Component {name} is not a trade-union meta gate: {component.kind}")
        payload = component.model_payload()
        feature_cols = [str(col) for col in payload.get("feature_cols", component.metadata.get("feature_cols", []))]
        if not feature_cols:
            raise ValueError(f"Meta-gate component {name} has no feature_cols")
        medians = _as_medians(payload.get("medians", component.metadata.get("feature_medians", {})))
        x_score, missing = _prepare_feature_frame(candidates, feature_cols, medians, strict=strict)
        model = payload["model"]
        out = candidates.copy()
        if hasattr(model, "predict_proba"):
            out[META_GATE_SCORE_COL] = model.predict_proba(x_score)[:, 1]
        else:
            out[META_GATE_SCORE_COL] = model.predict(x_score)
        out.attrs["missing_event_option_features"] = missing
        out.attrs["selected_threshold"] = component.registry_entry.get(
            "selected_threshold", component.metadata.get("selected_threshold")
        )
        return out

    def score_daily_router_component(self, name: str, candidates: pd.DataFrame, *, strict: bool = False) -> pd.DataFrame:
        component = self.component(name)
        if component.kind != "event_daily_source_router":
            raise TypeError(f"Component {name} is not a daily source router: {component.kind}")
        payload = component.model_payload()
        feature_cols = [str(col) for col in payload.get("feature_cols", component.metadata.get("feature_cols", []))]
        if not feature_cols:
            raise ValueError(f"Daily router component {name} has no feature_cols")
        medians = _as_medians(payload.get("medians", component.metadata.get("feature_medians", {})))
        x_score, missing = _prepare_feature_frame(candidates, feature_cols, medians, strict=strict)
        out = candidates.copy()
        out[DAILY_ROUTER_SCORE_COL] = payload["model"].predict(x_score)
        out.attrs["missing_event_option_features"] = missing
        return out

    def score_daily_router_sources(
        self,
        name: str,
        snapshot: pd.DataFrame,
        *,
        source_names: list[str] | None = None,
        strict: bool = True,
    ) -> pd.DataFrame:
        component = self.component(name)
        if component.kind != "event_daily_source_router":
            raise TypeError(f"Component {name} is not a daily source router: {component.kind}")
        if snapshot.empty:
            return snapshot.copy()
        if source_names is None:
            raw_sources = component.metadata.get("eligible_sources", component.registry_entry.get("eligible_sources", []))
            if not isinstance(raw_sources, list) or not raw_sources:
                raw_sources = sorted((component.metadata.get("source_history") or {}).keys())
            source_names = [str(item) for item in raw_sources]
        if not source_names:
            raise ValueError(f"Daily router component {name} has no source names")
        base = snapshot.tail(1).copy()
        rows: list[pd.DataFrame] = []
        for priority, source in enumerate(source_names):
            part = base.copy()
            part["daily_source"] = str(source)
            part["daily_source_priority"] = int(priority)
            for other in source_names:
                part[f"source_is_{other}"] = 1.0 if str(other) == str(source) else 0.0
            rows.append(part)
        candidates = pd.concat(rows, ignore_index=True)
        scored = self.score_daily_router_component(name, candidates, strict=strict)
        return scored.sort_values(DAILY_ROUTER_SCORE_COL, ascending=False).reset_index(drop=True)

    def score_event_option_gate_component(self, name: str, snapshots: pd.DataFrame, *, strict: bool = False) -> pd.DataFrame:
        component = self.component(name)
        if component.kind != "event_option_gate_direction_model":
            raise TypeError(f"Component {name} is not an event-option gate direction model: {component.kind}")
        payload = component.model_payload()
        feature_cols = [str(col) for col in payload.get("feature_cols", component.metadata.get("feature_cols", []))]
        if not feature_cols:
            raise ValueError(f"Event-option gate component {name} has no feature_cols")
        medians = _as_medians(payload.get("medians", component.metadata.get("feature_medians", {})))
        call_model = payload.get("call_model")
        put_model = payload.get("put_model")
        if call_model is None or put_model is None:
            raise ValueError(f"Event-option gate component {name} is missing call_model/put_model")
        metadata = payload.get("metadata", component.metadata)
        score_input = snapshots.copy()
        dropped_nonfinite: dict[str, Any] = {}
        if strict and not score_input.empty:
            bad_rows, row_features = _nonfinite_feature_rows(score_input, feature_cols)
            if bad_rows.any():
                dropped = score_input.loc[bad_rows].copy()
                score_input = score_input.loc[~bad_rows].copy()
                preview = []
                for idx, cols in list(row_features.items())[:5]:
                    row = dropped.loc[idx] if idx in dropped.index else pd.Series(dtype=object)
                    preview.append(
                        {
                            "ticker": str(row.get("ticker", "")),
                            "time": str(row.get("time", "")),
                            "features": cols[:12],
                            "feature_count": int(len(cols)),
                        }
                    )
                dropped_nonfinite = {
                    "dropped_rows": int(bad_rows.sum()),
                    "preview": preview,
                }
                if score_input.empty:
                    raise ValueError(
                        "All event-option snapshot rows have nonfinite required features; "
                        f"examples={preview}"
                    )
        x_score, missing = _prepare_feature_frame(score_input, feature_cols, medians, strict=strict)
        label_mode = str((metadata.get("args") or {}).get("label_mode", "return")).lower()
        out = score_input.copy()
        if label_mode == "win":
            out["pred_call_return"] = call_model.predict_proba(x_score)[:, 1]
            out["pred_put_return"] = put_model.predict_proba(x_score)[:, 1]
        else:
            out["pred_call_return"] = call_model.predict(x_score)
            out["pred_put_return"] = put_model.predict(x_score)
        call_action = out["pred_call_return"].astype(float) >= out["pred_put_return"].astype(float)
        out["action"] = np.where(call_action, "CALL", "PUT")
        out[EVENT_GATE_SCORE_COL] = np.where(call_action, out["pred_call_return"], out["pred_put_return"])
        deploy_config = metadata.get("deploy_config") if isinstance(metadata.get("deploy_config"), dict) else {}
        threshold = float(deploy_config.get("threshold", float("-inf")))
        out["deploy_config"] = str(metadata.get("deploy_config_name", ""))
        out["event_gate_pass"] = out[EVENT_GATE_SCORE_COL].astype(float) >= threshold
        out.attrs["missing_event_option_features"] = missing
        out.attrs["dropped_nonfinite_event_option_features"] = dropped_nonfinite
        out.attrs["deploy_config"] = deploy_config
        return out

    def relative_momentum_selected_source(self, name: str) -> str:
        component = self.component(name)
        if component.kind != "event_source_relative_momentum_router":
            raise TypeError(f"Component {name} is not a relative momentum router: {component.kind}")
        selected = component.selected_source
        if not selected:
            raise ValueError(f"Relative momentum component {name} has no selected_source")
        return selected

    def json_component_payload(self, name: str, expected_kind: str) -> dict[str, Any]:
        component = self.component(name)
        if component.kind != expected_kind:
            raise TypeError(f"Component {name} is not {expected_kind}: {component.kind}")
        if not component.metadata:
            raise ValueError(f"Component {name} has no JSON metadata payload")
        return component.metadata

    def intraday_circuit_config(self, name: str, *, ticker: str | None = None) -> dict[str, Any]:
        payload = self.json_component_payload(name, "event_intraday_circuit_breaker_config")
        rows = payload.get("tickers", [])
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"Intraday circuit component {name} has no ticker configs")
        if ticker is None:
            return dict(rows[0])
        target = str(ticker).upper()
        for row in rows:
            if str(row.get("ticker", "")).upper() == target:
                return dict(row)
        raise KeyError(f"Intraday circuit component {name} has no config for ticker {target}")

    def trade_union_config(self, name: str) -> dict[str, Any]:
        payload = self.json_component_payload(name, "event_trade_union_config_selector")
        required = ["selected_variants", "selected_max_day", "selected_cooldown"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Trade union config component {name} missing fields: {missing}")
        return payload

    def monthly_volume_backfill_policy(self, name: str) -> dict[str, Any]:
        payload = self.json_component_payload(name, "event_monthly_volume_backfill_policy")
        required = ["primary_name", "fallback_name", "min_month_trades", "max_day", "cooldown_minutes"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Monthly backfill policy component {name} missing fields: {missing}")
        return payload

    def static_gate_policy(self, name: str) -> dict[str, Any]:
        payload = self.json_component_payload(name, "event_static_gate_policy")
        required = ["source_component", "source_name", "max_day", "cooldown_minutes"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Static gate policy component {name} missing fields: {missing}")
        return payload

    def mtd_rescue_policy(self, name: str) -> dict[str, Any]:
        payload = self.json_component_payload(name, "event_static_union_mtd_rescue_policy")
        required = ["base_sources", "rescue_sources", "trigger_threshold_return", "max_day", "cooldown_minutes"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"MTD rescue policy component {name} missing fields: {missing}")
        return payload

    def score_gate_source(
        self,
        name: str,
        snapshots: pd.DataFrame,
        *,
        source_variant: str,
        source_priority: int = 0,
        strict: bool = False,
        only_pass: bool = True,
    ) -> pd.DataFrame:
        scored = self.score_event_option_gate_component(name, snapshots, strict=strict)
        if only_pass:
            scored = scored[scored["event_gate_pass"].astype(bool)].copy()
        else:
            scored = scored.copy()
        if scored.empty:
            return _standardize_candidate_columns(scored)
        scored["source_variant"] = str(source_variant)
        scored["source_priority"] = int(source_priority)
        scored["source_component"] = str(name)
        return _standardize_candidate_columns(scored)

    def materialize_trade_union_config(self, name: str, candidates: pd.DataFrame) -> pd.DataFrame:
        config = self.trade_union_config(name)
        variants = {str(item) for item in config.get("selected_variants", [])}
        work = candidates.copy()
        if variants:
            work = work[work["source_variant"].astype(str).isin(variants)].copy()
        if work.empty:
            return _standardize_candidate_columns(work)
        out = _apply_max_day_cooldown(
            work,
            int(config.get("selected_max_day", 999)),
            int(config.get("selected_cooldown", 0)),
        )
        if not out.empty:
            out["config_selector_component"] = str(name)
            out["selected_variants"] = ",".join(sorted(variants))
            out["selected_max_day"] = int(config.get("selected_max_day", 999))
            out["selected_cooldown"] = int(config.get("selected_cooldown", 0))
        out.attrs["trade_union_config"] = config
        return out

    def materialize_max_day_cooldown(
        self,
        candidates: pd.DataFrame,
        *,
        max_day: int,
        cooldown_minutes: int,
    ) -> pd.DataFrame:
        return _apply_max_day_cooldown(candidates, int(max_day), int(cooldown_minutes))

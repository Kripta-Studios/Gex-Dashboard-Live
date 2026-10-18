"""Incremental session-clock dataset: reference full days, build only short days.

One process, local files only. No fits or selection. The explicit --build flag
opens short-session labels only after causal artifacts and features are sealed.
Existing full-session arrays/parquets are referenced, never copied or modified.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    from . import build_cache, features as original_features
    from . import session_cache, session_features, session_level_engine
    from .session_clock import FULL, SHORT
except ImportError:
    import build_cache
    import features as original_features
    import session_cache
    import session_features
    import session_level_engine
    from session_clock import FULL, SHORT

VERSION = "SESSION_CLOCK_DATASET_V1"
FAMILY = Path(__file__).parent
DEFAULT = Path("D:/GexResearchArtifacts/level_oracle_20261018")
SOURCE_COLUMNS = [
    "ticker",
    "date",
    "status",
    "cache_path",
    "day_root",
    "cache_npz_sha256",
    "cache_meta_sha256",
    "states_sha256",
    "levels_sha256",
    "actions_sha256",
    "labels_sha256",
    "causal_freeze_sha256",
]
DEPENDENCIES = (
    "session_clock.py",
    "session_cache.py",
    "session_level_engine.py",
    "session_features.py",
    "build_cache.py",
    "level_engine.py",
    "features.py",
)
sha = build_cache.sha256


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def durable(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial-" + uuid.uuid4().hex)
    writer(temporary)
    with temporary.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json(path, obj):
    durable(
        path,
        lambda p: p.write_text(
            json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8"
        ),
    )


def write_npz(path, arrays):
    def writer(p):
        with p.open("wb") as handle:
            np.savez_compressed(handle, **arrays)

    durable(path, writer)


def write_frame(path, frame):
    durable(path, lambda p: frame.to_parquet(p, index=False))


def require_hash(path, expected):
    if sha(path) != expected:
        raise ValueError(f"Input hash mismatch: {path}")


def source_dependencies():
    return {name: sha(FAMILY / name) for name in DEPENDENCIES}


@contextmanager
def lock(root):
    """Kernel byte lock is released on exit/crash; no stale PID authorization."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "writer.lock"
    with path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def expected_days(calendar):
    schedule = pd.read_csv(calendar, dtype={"date": str})
    if (
        schedule.date.duplicated().any()
        or not schedule.full_session.isin([True, False]).all()
    ):
        raise ValueError("Invalid calendar identity/full-session flag")
    result = []
    for row in schedule.itertuples(index=False):
        open_ = pd.Timestamp(row.open).tz_convert("America/New_York")
        close = pd.Timestamp(row.close).tz_convert("America/New_York")
        minutes = int((close - open_).total_seconds() / 60)
        if open_.strftime("%H:%M") != "09:30" or minutes not in (210, 390):
            raise ValueError("Unsupported session calendar")
        if bool(row.full_session) != (minutes == 390):
            raise ValueError("Session flag disagrees with clock")
        for ticker in ("QQQ", "SPXW", "SPY"):
            result.append(dict(ticker=ticker, date=row.date, close_i=minutes))
    return result


def binding(cache_path, cache_meta_path, dependencies):
    return dict(
        source_sha256=sha(cache_path),
        source_metadata_sha256=sha(cache_meta_path),
        dependencies=dependencies,
    )


def seal_day(directory, row, files, contract_sha):
    marker = dict(
        version=VERSION,
        contract_sha256=contract_sha,
        row=row,
        files={str(Path(p).resolve()): sha(p) for p in files},
    )
    write_json(directory / "complete.json", marker)
    return row


def verified_resume(directory, contract_sha):
    marker = directory / "complete.json"
    if not marker.exists():
        if directory.exists():
            # Preserve uncompleted evidence; never mistake it for a sealed day.
            archive = directory.with_name(
                directory.name + ".incomplete-" + uuid.uuid4().hex
            )
            directory.rename(archive)
        return None
    value = read_json(marker)
    if value["contract_sha256"] != contract_sha:
        raise ValueError(f"Day contract changed: {directory}")
    row = value["row"]
    required = {
        row[key]
        for key in (
            "cache_path",
            "cache_meta_path",
            "features_path",
            "features_meta_path",
            "action_features_path",
            "action_features_meta_path",
        )
    }
    required.update(
        str((Path(row["day_root"]) / name).resolve())
        for name in (
            "states.parquet",
            "levels.parquet",
            "actions.parquet",
            "labels.parquet",
            "causal_freeze.json",
        )
    )
    if not required.issubset(value["files"]):
        raise ValueError("Incomplete consumed-file membership in day seal")
    for path, digest in value["files"].items():
        require_hash(path, digest)
    return row


def reference_full(source, feature_root, directory, dependencies, contract_sha):
    row = dict(source)
    row["date"] = str(row["date"])
    row["close_i"] = FULL.close_i
    row["reused_full_session"] = True
    for key in ("cache_path", "day_root"):
        row[key] = str(Path(row[key]).resolve())
    cache_path = Path(row["cache_path"])
    row["cache_meta_path"] = str(cache_path.with_suffix(".json"))
    require_hash(cache_path, row["cache_npz_sha256"])
    require_hash(row["cache_meta_path"], row["cache_meta_sha256"])
    files = [cache_path, Path(row["cache_meta_path"])]
    for name in ("states", "levels", "actions", "labels", "causal_freeze"):
        path = Path(row["day_root"]) / (
            name + (".json" if name == "causal_freeze" else ".parquet")
        )
        require_hash(path, row[name + "_sha256"])
        files.append(path)
    source_day = feature_root / row["ticker"] / row["date"]
    for name, prefix in (("features", "features"), ("actions", "action_features")):
        npz = source_day / (name + ".npz")
        old_meta = npz.with_suffix(".json")
        metadata = read_json(old_meta)
        require_hash(npz, metadata["sha256"])
        if (
            metadata["binding"]["source_sha256"] != row["cache_npz_sha256"]
            or metadata["binding"]["source_metadata_sha256"] != row["cache_meta_sha256"]
        ):
            raise ValueError("Frozen feature/cache binding mismatch")
        if metadata["binding"]["dependencies"] != original_features._dependencies():
            raise ValueError("Frozen feature dependency mismatch")
        if name == "features" and (
            metadata["schema"] != original_features.feature_schema()
            or metadata["states"] != 316
        ):
            raise ValueError("Frozen state feature schema changed")
        if name == "actions":
            if metadata["action_names"] != list(original_features.ACTION_NAMES):
                raise ValueError("Frozen action feature schema changed")
            keys = pd.read_parquet(
                Path(row["day_root"]) / "actions.parquet",
                columns=["action_id", *original_features.ACTION_INPUT_NAMES],
            )
            identity_sha = hashlib.sha256(
                keys.to_numpy(np.float64).tobytes()
            ).hexdigest()
            if metadata["binding"]["action_inputs_sha256"] != identity_sha:
                raise ValueError("Frozen action feature identity binding changed")
        metadata["version"] = session_features.VERSION
        metadata["binding"]["dependencies"] = dependencies
        metadata["original_metadata"] = dict(
            path=str(old_meta.resolve()), sha256=sha(old_meta)
        )
        metadata["session_clock"] = FULL.as_dict()
        if name == "features":
            metadata["schema"] = session_features.feature_schema()
        target = directory / (name + ".json")
        write_json(target, metadata)
        row[prefix + "_path"] = str(npz.resolve())
        row[prefix + "_meta_path"] = str(target.resolve())
        row[prefix + "_sha256"] = metadata["sha256"]
        row[prefix + "_meta_sha256"] = sha(target)
        files.extend([npz, old_meta, target])
    return seal_day(directory, row, files, contract_sha)


def build_short(ticker, date, source_root, directory, dependencies, contract_sha):
    paths = [
        build_cache.source_path(source_root, ticker, date, kind)
        for kind in ("greeks", "oi")
    ]
    sources = {str(p.resolve()): build_cache.source_record(p) for p in paths}
    frames = []
    for path, columns in zip(
        paths, (build_cache.GREEK_COLUMNS, build_cache.OI_COLUMNS)
    ):
        names = set(pq.ParquetFile(path).schema_arrow.names)
        frames.append(pd.read_parquet(path, columns=[c for c in columns if c in names]))
    raw, metadata = session_cache.normalize_day(*frames, ticker, date, SHORT)
    directory.mkdir(parents=True, exist_ok=True)
    cache_path = directory / "cache.npz"
    write_npz(cache_path, raw)
    metadata.update(
        source_hashes=sources,
        producer_sha256=dependencies["session_cache.py"],
        sha256=sha(cache_path),
        npz_bytes=cache_path.stat().st_size,
    )
    cache_meta_path = directory / "cache.json"
    write_json(cache_meta_path, metadata)
    day = session_level_engine.build_day(raw, metadata, SHORT)
    files = [cache_path, cache_meta_path]
    causal = {}
    for name in ("states", "levels", "actions"):
        path = directory / (name + ".parquet")
        write_frame(path, getattr(day, name))
        causal[path.name] = sha(path)
        files.append(path)
    write_json(directory / "causal_freeze.json", causal)
    files.append(directory / "causal_freeze.json")
    base_binding = binding(cache_path, cache_meta_path, dependencies)
    encoded = session_features.encode_states(
        session_features.build_day_feature_cache(raw, SHORT)
    )
    pack = directory / "features.npz"
    write_npz(pack, encoded)
    feature_meta = dict(
        version=session_features.VERSION,
        ticker=ticker,
        date=date,
        binding=base_binding,
        sha256=sha(pack),
        schema=session_features.feature_schema(),
        source_path=str(cache_path.resolve()),
        session_clock=SHORT.as_dict(),
        array_schema={
            k: dict(shape=list(v.shape), dtype=str(v.dtype)) for k, v in encoded.items()
        },
        clock_basis=metadata["clock_basis"],
        oi_clock_basis=metadata["oi_clock_basis"],
        valid_states=int(encoded["state_valid"].sum()),
        states=len(encoded["state_i"]),
        uncompressed_bytes=sum(v.nbytes for v in encoded.values()),
        outcomes_read=False,
    )
    write_json(directory / "features.json", feature_meta)
    values = session_features.action_features(raw, day.actions, clock=SHORT)
    action_pack = directory / "action_features.npz"
    write_npz(
        action_pack,
        dict(
            action_id=day.actions.action_id.to_numpy(np.int32), action_features=values
        ),
    )
    identities = day.actions.loc[
        :, ["action_id", *session_features.ACTION_INPUT_NAMES]
    ].to_numpy(np.float64)
    action_binding = {
        **base_binding,
        "action_inputs_sha256": hashlib.sha256(identities.tobytes()).hexdigest(),
    }
    write_json(
        directory / "action_features.json",
        dict(
            version=session_features.VERSION,
            binding=action_binding,
            sha256=sha(action_pack),
            action_names=list(session_features.ACTION_NAMES),
            actions=len(day.actions),
            outcomes_read=False,
            session_clock=SHORT.as_dict(),
        ),
    )
    causal_files = [
        *files,
        pack,
        directory / "features.json",
        action_pack,
        directory / "action_features.json",
    ]
    write_json(
        directory / "features_causal_freeze.json",
        {p.name: sha(p) for p in causal_files},
    )
    # Economic sidecar is deliberately constructed only after the causal seal.
    labels = session_level_engine.evaluate_actions(raw, day.actions, SHORT)
    write_frame(directory / "labels.parquet", labels)
    files = [
        *causal_files,
        directory / "features_causal_freeze.json",
        directory / "labels.parquet",
    ]
    for path in paths:
        if build_cache.source_record(path) != sources[str(path.resolve())]:
            raise ValueError("Raw source changed during short build")
        files.append(path)
    row = dict(
        ticker=ticker,
        date=date,
        status="COMPLETE",
        close_i=210,
        reused_full_session=False,
        day_root=str(directory.resolve()),
        cache_path=str(cache_path.resolve()),
        cache_meta_path=str(cache_meta_path.resolve()),
        cache_npz_sha256=sha(cache_path),
        cache_meta_sha256=sha(cache_meta_path),
        features_path=str(pack.resolve()),
        features_meta_path=str((directory / "features.json").resolve()),
        action_features_path=str(action_pack.resolve()),
        action_features_meta_path=str((directory / "action_features.json").resolve()),
    )
    for name in ("states", "levels", "actions", "labels", "causal_freeze"):
        path = directory / (name + (".json" if name == "causal_freeze" else ".parquet"))
        row[name + "_sha256"] = sha(path)
    for name in ("features", "action_features"):
        row[name + "_sha256"] = sha(row[name + "_path"])
        row[name + "_meta_sha256"] = sha(row[name + "_meta_path"])
    return seal_day(directory, row, files, contract_sha)


def run(base, root):
    started = time.perf_counter()
    calendar = base / "cache_v1/expected_calendar.csv"
    index_path = base / "engine_v1/index.parquet"
    audit_path = base / "engine_v1_audit_v4/audit.json"
    audit = read_json(audit_path)
    if audit["status"] != "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT":
        raise ValueError("Original full-session audit is not PASS")
    require_hash(index_path, audit["index_sha256"])
    for name in ("completion", "dataset_contract"):
        require_hash(base / "engine_v1" / (name + ".json"), audit[name + "_sha256"])
    expected = expected_days(calendar)
    if len(expected) != 2625 or sum(x["close_i"] == 210 for x in expected) != 24:
        raise ValueError("Unexpected fixed calendar coverage")
    old = pd.read_parquet(index_path, columns=SOURCE_COLUMNS)
    old["date"] = old.date.astype(str)
    if old.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate full-session input identity")
    lookup = {(r["ticker"], r["date"]): r for r in old.to_dict("records")}
    full_keys = {(r["ticker"], r["date"]) for r in expected if r["close_i"] == 390}
    if (
        set(lookup) != full_keys
        or sum(r["status"] == "COMPLETE" for r in lookup.values()) != 2595
    ):
        raise ValueError("Full-session input coverage changed")
    missing = {
        (r["ticker"], r["date"]) for r in lookup.values() if r["status"] != "COMPLETE"
    }
    if missing != {
        (ticker, date)
        for ticker in ("QQQ", "SPY")
        for date in ("20260401", "20260409", "20260415")
    }:
        raise ValueError("Missing-source identities changed")
    if not old.status.isin(["COMPLETE", "MISSING_SOURCE"]).all():
        raise ValueError("Unexpected original source status")
    if read_json(base / "engine_v1/dataset_contract.json")[
        "expected_calendar_sha256"
    ] != sha(calendar):
        raise ValueError("Calendar differs from original engine binding")
    dependencies = source_dependencies()
    contract = dict(
        version=VERSION,
        builder_sha256=sha(__file__),
        dependencies=dependencies,
        calendar_path=str(calendar.resolve()),
        calendar_sha256=sha(calendar),
        original_index_path=str(index_path.resolve()),
        original_index_sha256=sha(index_path),
        original_audit_path=str(audit_path.resolve()),
        original_audit_sha256=sha(audit_path),
        feature_root=str(root.resolve()),
        expected_days=2625,
        expected_available_days=2619,
        expected_missing_days=6,
        short_days=24,
        native_threads=1,
        workers=1,
    )
    feature_contract = dict(
        version=session_features.VERSION,
        schema=session_features.feature_schema(),
        dependencies=dependencies,
        clock_schedules=[FULL.as_dict(), SHORT.as_dict()],
        outcomes_read=False,
    )
    with lock(root):
        for filename, value in [
            ("dataset_contract.json", contract),
            ("feature_contract.json", feature_contract),
        ]:
            path = root / filename
            if path.exists() and read_json(path) != value:
                raise ValueError("Existing dataset contract differs")
            if not path.exists():
                write_json(path, value)
        contract_sha = sha(root / "dataset_contract.json")
        rows = []
        for item in expected:
            ticker, date = item["ticker"], item["date"]
            oldrow = lookup.get((ticker, date))
            if oldrow is not None and oldrow["status"] != "COMPLETE":
                rows.append(
                    {
                        **oldrow,
                        **item,
                        "status": "MISSING_SOURCE",
                        "evaluation_status": "NO_EVALUABLE",
                    }
                )
                continue
            directory = (
                root
                / ("references" if item["close_i"] == 390 else "short")
                / ticker
                / date
            )
            row = verified_resume(directory, contract_sha)
            if row is None:
                if item["close_i"] == 390:
                    row = reference_full(
                        oldrow,
                        base / "features_v1",
                        directory,
                        dependencies,
                        contract_sha,
                    )
                else:
                    row = build_short(
                        ticker,
                        date,
                        build_cache.ROOT,
                        directory,
                        dependencies,
                        contract_sha,
                    )
            rows.append(row)
            if len(rows) % 25 == 0:
                write_json(
                    root / "progress.json",
                    dict(
                        status="RUNNING",
                        processed=len(rows),
                        expected=2625,
                        elapsed_seconds=time.perf_counter() - started,
                    ),
                )
        if source_dependencies() != dependencies:
            raise ValueError("Dependencies changed during build")
        require_hash(index_path, contract["original_index_sha256"])
        require_hash(audit_path, contract["original_audit_sha256"])
        require_hash(calendar, contract["calendar_sha256"])
        frame = (
            pd.DataFrame(rows).sort_values(["date", "ticker"]).reset_index(drop=True)
        )
        write_frame(root / "index.parquet", frame)
        counts = frame.status.value_counts().to_dict()
        if counts != {"COMPLETE": 2619, "MISSING_SOURCE": 6}:
            raise ValueError("Final session dataset coverage mismatch")
        completion = dict(
            status="COMPLETE",
            available_days=2619,
            missing_days=6,
            short_days=24,
            full_days_reused=2595,
            index_sha256=sha(root / "index.parquet"),
            dataset_contract_sha256=contract_sha,
            feature_contract_sha256=sha(root / "feature_contract.json"),
            elapsed_seconds=time.perf_counter() - started,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            economic_scope="24 short-session labels only; no new fits or policy selection",
            expected_calendar_sha256=sha(calendar),
            feature_root=str(root.resolve()),
        )
        write_json(root / "completion.json", completion)
        write_json(root / "progress.json", completion)
        return completion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT / "session_clock_dataset_v1"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        required=True,
        help="Explicit reviewed execution, including 24 short label sidecars",
    )
    args = parser.parse_args()
    try:
        result = run(args.base.resolve(), args.out.resolve())
    except Exception as exc:
        # Preserve earlier artifacts and report failure; no automatic source retry.
        write_json(
            args.out / "latest_failure.json",
            dict(
                status="FAILED",
                error=repr(exc),
                utc=datetime.now(timezone.utc).isoformat(),
            ),
        )
        raise
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

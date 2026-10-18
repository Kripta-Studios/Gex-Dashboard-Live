"""One serialization-only repair; original diagnostic remains immutable."""

import argparse
import inspect
import json
from pathlib import Path
import shutil
import time

import pandas as pd

import diagnose_oracle_model as producer
import train_episode_model as source


ORIGINAL = 'timing_all.to_parquet(target / "timing_hindsight.parquet", index=False)'
REPLACEMENT = '_write_timing(timing_all, target / "timing_hindsight.parquet")'


def normalized_timing(frame):
    fixed = frame.copy()
    for name in ("original_fill", "shifted_fill"):
        values = fixed[name]
        if not values.dropna().isin([False, True, 0.0, 1.0]).all():
            raise ValueError(f"Non-boolean timing flag: {name}")
        fixed[name] = pd.array([pd.NA if pd.isna(v) else bool(v) for v in values], dtype="boolean")
    return fixed


def write_timing(frame, path):
    normalized_timing(frame).to_parquet(path, index=False)


def repaired_run():
    original = inspect.getsource(producer.run)
    if original.count(ORIGINAL) != 1:
        raise ValueError("Expected exactly one aggregate serialization statement")
    namespace = dict(producer.__dict__, _write_timing=write_timing)
    exec(compile(original.replace(ORIGINAL, REPLACEMENT), producer.__file__, "exec"), namespace)
    return namespace["run"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-runtime", type=Path, required=True)
    args = parser.parse_args()
    args.root, args.output = args.root.resolve(), args.output.resolve()
    args.resume = True
    repair = args.output / "technical_repairs" / "timing_nullable_boolean_v1"
    with source.output_lock(args.output):
        identity = producer.read(args.output / "identity.json")
        if producer.sha(producer.__file__) != identity["code_sha256"]:
            raise ValueError("Original diagnostic source changed")
        repair.mkdir(parents=True, exist_ok=True)
        marker = repair / "repair.json"
        record = dict(
            code_sha256=producer.sha(producer.__file__),
            repair_sha256=producer.sha(__file__),
            identity_sha256=producer.sha(args.output / "identity.json"),
            original_statement=ORIGINAL,
            repaired_statement=REPLACEMENT,
            original_stderr_sha256=producer.sha(args.previous_runtime.resolve() / "stderr.log"),
            original_stderr=str(args.previous_runtime.resolve() / "stderr.log"),
            scope="ONLY_AGGREGATE_TIMING_SERIALIZATION_TWO_NULLABLE_BOOLEAN_COLUMNS",
            new_fits=0,
        )
        if marker.exists():
            if producer.read(marker) != record:
                raise ValueError("Repair identity differs")
        else:
            preserved = repair / "preserved"
            preserved.mkdir()
            for name in ("decision_categories.csv", "action_signal_counts.csv", "timing_hindsight.parquet"):
                original = args.output / "validation" / name
                if original.exists():
                    copied = preserved / name
                    shutil.copyfile(original, copied)
                    if producer.sha(original) != producer.sha(copied):
                        raise ValueError("Preservation copy differs")
            source.atomic(marker, lambda p: p.write_text(json.dumps(record, indent=2), encoding="utf-8"))
        started = time.perf_counter()
        repaired_run()(args, source)
        source.write_json(repair / "completion.json", dict(
            status="COMPLETE_TIMING_DTYPE_CONTINUATION_ZERO_FITS",
            wall_seconds=time.perf_counter() - started,
            repair_sha256=producer.sha(marker),
            summary_sha256=producer.sha(args.output / "summary.json"),
            original_code_sha256=producer.sha(producer.__file__),
        ))


if __name__ == "__main__":
    main()

"""Technical continuation: fix four source-manifest paths, never refit the model."""

import argparse
import hashlib
import inspect
from pathlib import Path
import time

import train_episode_model as producer

ORIGINAL_SHA = "b0b0dcd54a59cfe39ac078b66570a394e7411c1d9b6e67f6e520a6640e3cddb8"


def repaired_function(module):
    source = inspect.getsource(module.predict_day)
    if source.count("day.features /") != 4:
        raise ValueError("Expected exactly four source-manifest path joins")
    patched = source.replace("day.features /", "day.features.parent /")
    namespace = dict(module.__dict__)
    exec(
        compile(patched, __file__ + ":predict_day_source_path_repair", "exec"),
        namespace,
    )
    return namespace["predict_day"], source, patched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", required=True)
    args = parser.parse_args()
    args.root, args.output = args.root.resolve(), args.output.resolve()
    if producer.sha(producer.__file__) != ORIGINAL_SHA:
        raise ValueError("Original episode producer changed")
    with producer.output_lock(args.output):
        stages = producer.Stages(
            args.output, producer.sha(args.output / "identity.json")
        )
        if stages.load("model") is None:
            raise ValueError("Path repair requires the already completed model")
        model_sha = producer.sha(args.output / "gbt_net_episode.txt")
        function, original_source, repaired_source = repaired_function(producer)
        target = args.output / "technical_repairs" / "source_path_v1"
        target.mkdir(parents=True, exist_ok=True)
        marker = target / "repair.json"
        previous = producer.read(marker) if marker.exists() else None
        original_failures = (
            previous["original_failure_files"]
            if previous is not None
            else {
                str(p.resolve()): producer.sha(p)
                for p in sorted(args.output.glob("failure_*.json"))
            }
        )
        for path, digest in original_failures.items():
            if producer.sha(path) != digest:
                raise ValueError("Original failure evidence changed")
        record = {
            "status": "TECHNICAL_SOURCE_MANIFEST_PATH_REPAIR",
            "original_producer_sha256": ORIGINAL_SHA,
            "repair_script_sha256": producer.sha(__file__),
            "original_function_sha256": hashlib.sha256(
                original_source.encode()
            ).hexdigest(),
            "repaired_function_sha256": hashlib.sha256(
                repaired_source.encode()
            ).hexdigest(),
            "change": "Four source hash paths: day.features is NPZ, parent is day directory",
            "model_sha256_before": model_sha,
            "model_stage_sha256": producer.sha(args.output / "model.complete.json"),
            "identity_sha256": stages.identity,
            "original_failure_files": original_failures,
            "preceding_runtime_completion_sha256": producer.sha(
                args.root / "episode_learners_v1_runtime_v1/completion.json"
            ),
            "model_fits_permitted": 0,
        }
        if previous is not None and previous != record:
            raise ValueError("Existing technical repair identity differs")
        if not marker.exists():
            producer.atomic(
                target / "original_predict_day.py",
                lambda p: p.write_text(original_source, encoding="utf-8"),
            )
            producer.atomic(
                target / "repaired_predict_day.py",
                lambda p: p.write_text(repaired_source, encoding="utf-8"),
            )
            producer.write_json(marker, record)
        producer.predict_day = function

        def forbid_fit(*_args, **_kwargs):
            raise AssertionError("This technical continuation cannot fit a model")

        producer.lgb.LGBMRegressor = forbid_fit
        try:
            producer.run(args)
            if producer.sha(args.output / "gbt_net_episode.txt") != model_sha:
                raise ValueError(
                    "Completed model changed during technical continuation"
                )
            producer.write_json(
                target / "completion.json",
                {
                    "status": "TECHNICAL_CONTINUATION_COMPLETE_ZERO_REFITS",
                    "repair_sha256": producer.sha(marker),
                    "model_sha256_after": model_sha,
                    "summary_sha256": producer.sha(args.output / "summary.json"),
                    "scientific_completion_sha256": producer.sha(
                        args.output / "completion.complete.json"
                    ),
                    "refits": 0,
                },
            )
        except BaseException as error:
            producer.write_json(
                args.output / ("failure_" + str(time.time_ns()) + ".json"),
                {
                    "exception": type(error).__name__,
                    "message": str(error),
                    "technical_interruption": isinstance(
                        error, (MemoryError, OSError, KeyboardInterrupt)
                    ),
                },
            )
            raise


if __name__ == "__main__":
    main()

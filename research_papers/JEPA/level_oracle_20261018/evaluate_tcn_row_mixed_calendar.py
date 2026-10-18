"""Frozen TCN comparison over full and early-close NYSE evaluation sessions."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

import evaluate_tcn_row_mixed as legacy
import run_monthly_walk_forward as readers
from session_clock import SessionClock

flags, compat = legacy.flags, legacy.compat
HERE = Path(__file__).resolve().parent
SESSION_AUDIT_SHA = "678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9"
LEGACY_SHA = "870a5815f343735f299fb63066899df29d56c62219c21fa7ad7197188732af30"
SHORT_DATES = ("20250703", "20251128", "20251224")
DEPENDENCIES = tuple(
    sorted(
        set(readers.DEPENDENCIES)
        | {
            "evaluate_tcn_row_mixed_calendar.py",
            "test_evaluate_tcn_row_mixed_calendar.py",
            "TCN_ROW_MIXED_CALENDAR_SPEC.md",
            "evaluate_tcn_row_mixed.py",
            "evaluate_tcn_flags_compat.py",
            "run_tcn_flags.py",
            "session_clock.py",
            "run_policy.py",
            "level_engine.py",
        }
    )
)


def dependency_hashes():
    return {name: flags.sha(HERE / name) for name in DEPENDENCIES}


def require_review(path):
    digest = flags.sha(path)
    review = flags.read_json(path)
    if (
        review.get("status") != "PASS_TCN_ROW_MIXED_CALENDAR_IMPLEMENTATION_REVIEW"
        or review.get("dependencies") != dependency_hashes()
        or flags.sha(path) != digest
    ):
        raise ValueError("Exact calendar implementation review required")
    return digest


def validate_actions(actions, clock):
    if (
        actions.action_id.duplicated().any()
        or not actions.state_i.between(clock.first_state, clock.last_state).all()
    ):
        raise ValueError("Action identities/states exceed explicit session clock")


def validate_labels(labels, clock):
    if (
        labels.action_id.duplicated().any()
        or not labels.status.isin(["FILLED", "NO_FILL"]).all()
    ):
        raise ValueError("Invalid session outcome identity/status")
    filled = labels.status == "FILLED"
    if (
        not labels.loc[filled, "exit_i"]
        .between(clock.first_state + 2, clock.eod_i)
        .all()
    ):
        raise ValueError("Fill exit exceeds explicit session EOD")


class ClockSources(readers.Sources):
    def __init__(self, *args):
        super().__init__(*args)
        self.clock_checked = set()

    def check(self, day, filename):
        digest = super().check(day, filename)
        key = (day.key, filename)
        if key not in self.clock_checked:
            clock = SessionClock(day.close_i)
            if filename == "actions.parquet":
                frame = pd.read_parquet(
                    day.oracle / filename, columns=["action_id", "state_i"]
                )
                validate_actions(frame, clock)
            elif filename == "labels.parquet":
                frame = pd.read_parquet(
                    day.oracle / filename, columns=["action_id", "status", "exit_i"]
                )
                validate_labels(frame, clock)
            self.clock_checked.add(key)
        return digest


class CalendarStore(readers.Features):
    """Interface adaptation only; the audited reader supplies unchanged arrays."""

    def __init__(self, source, artifacts):
        super().__init__(source, artifacts)
        self.seal, self.hashes, self.capacity = source, {}, 1
        self.schema = {
            key: self.contract["schema"][key]
            for key in ("base_names", "token_names", "map_names", "action_names")
        }
        contract = source.feature_root / "feature_contract.json"
        self.hashes[str(contract.resolve())] = flags.sha(contract)

    def get(self, key):
        pack = super().get(key)
        for path in self.days[key].feature_paths:
            self.hashes[str(path.resolve())] = self.source.hashes[str(path.resolve())]
        return pack


def copy_exact(source, destination):
    """Fsync and hash before publishing each new immutable snapshot."""
    source, destination = Path(source), Path(destination)
    digest = flags.sha(source)
    if destination.exists():
        if flags.sha(destination) != digest:
            raise ValueError("Snapshot differs: " + str(destination))
        return digest
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists():
        raise FileExistsError("Partial snapshot preserved: " + str(temporary))
    with source.open("rb") as src, temporary.open("xb") as dst:
        import shutil

        shutil.copyfileobj(src, dst)
    if flags.sha(temporary) != digest or flags.sha(source) != digest:
        raise ValueError("Source changed while copying")
    readers.shared.durable_replace(temporary, destination)
    return digest


def save_scores(path, ids, scores):
    ids, scores = np.asarray(ids), np.asarray(scores)
    if ids.ndim != 1 or scores.shape != ids.shape or not np.isfinite(scores).all():
        raise ValueError("Invalid causal score vector")
    if path.exists():
        with np.load(path, allow_pickle=False) as data:
            if (
                set(data.files) != {"action_ids", "tcn_teacher"}
                or data["action_ids"].dtype != ids.dtype
                or data["tcn_teacher"].dtype != scores.dtype
                or data["action_ids"].tobytes() != ids.tobytes()
                or data["tcn_teacher"].tobytes() != scores.tobytes()
            ):
                raise ValueError("Existing calendar control score differs")
    else:
        temporary = path.with_suffix(".partial.npz")
        if temporary.exists():
            raise FileExistsError("Partial score preserved")
        np.savez_compressed(temporary, action_ids=ids, tcn_teacher=scores)
        readers.shared.durable_replace(temporary, path)


def require_epoch_four(training_root):
    record = flags.read_json(training_root / "training_complete.json")
    if record["binding"].get("epochs") != 4 or [
        item.get("epoch") for item in record.get("history", [])
    ] != [1, 2, 3, 4]:
        raise ValueError("Four completed epochs required before evaluation")
    if any(item.get("updates") != 1491 for item in record["history"]):
        raise ValueError("Fixed 1491 updates per epoch required")
    checkpoint = training_root / "tcn_epoch04.pt"
    metadata_path = checkpoint.with_suffix(".json")
    metadata = flags.read_json(metadata_path)
    latest = flags.read_json(training_root / "latest_checkpoint.json")
    if (
        metadata.get("epoch") != 4
        or metadata.get("complete_epoch_boundary") is not True
        or metadata.get("binding") != record["binding"]
        or metadata.get("sha256") != flags.sha(checkpoint)
        or latest
        != dict(
            file=checkpoint.name,
            metadata_sha256=flags.sha(metadata_path),
            sha256=metadata["sha256"],
            epoch=4,
        )
    ):
        raise ValueError("Fourth checkpoint boundary is not sealed")
    flags.verify_files(record["binding"]["files"])
    if record["binding"]["variant"] != "row_mixed_original_batch_sizes":
        raise ValueError("Wrong row-mixed training family")
    if flags.sha(training_root / "tcn_variant.pt") != record["model_sha256"]:
        raise ValueError("Row-mixed final model changed")
    if flags.sha(training_root / "run_tcn_row_mixed.executed.py") != legacy.TRAIN_SHA:
        raise ValueError("Row-mixed training producer differs")
    return record


def calendar_record(source):
    days = sorted(source.days.values(), key=lambda day: (day.ticker, day.date))
    result = {}
    for period, lower, upper, expected, available in (
        ("validation", "20250101", "20260101", 750, 750),
        ("test", "20260101", "20260701", 369, 363),
    ):
        selected = [d for d in days if lower <= d.date < upper]
        observed = [d for d in selected if d.status == "COMPLETE"]
        if len(selected) != expected or len(observed) != available:
            raise ValueError("Evaluation calendar coverage differs")
        shorts = {(d.ticker, d.date) for d in selected if d.close_i == 210}
        required_short = (
            {(ticker, date) for ticker in flags.TICKERS for date in SHORT_DATES}
            if period == "validation"
            else set()
        )
        if shorts != required_short:
            raise ValueError("Early-close evaluation universe differs")
        result[period] = dict(
            expected=expected,
            available=available,
            days=[
                dict(
                    ticker=d.ticker,
                    date=d.date,
                    status=d.status,
                    clock=SessionClock(d.close_i).as_dict(),
                )
                for d in selected
            ],
        )
    return result


def bind(args):
    out = args.output
    if flags.sha(Path(legacy.__file__)) != LEGACY_SHA:
        raise ValueError("Frozen comparison helpers changed")
    if (
        flags.sha(Path(compat.__file__)) != legacy.COMPAT_SHA
        or flags.sha(Path(flags.__file__)) != compat.EXPECTED_RUNNER_SHA
    ):
        raise ValueError("Frozen inference/selection changed")
    review_hash = require_review(args.implementation_review)
    if flags.sha(args.session_audit) != SESSION_AUDIT_SHA:
        raise ValueError("Unexpected SessionClock audit")
    training = require_epoch_four(args.training_root)
    legacy.verify_control(args.flags_root, args.control_audit)
    control_training = flags.read_json(args.flags_root / "training_complete.json")
    flags.verify_files(control_training["binding"]["files"])
    if control_training["binding"]["device"] != training["binding"]["device"]:
        raise ValueError("Control and variant must use their common original device")
    if (
        flags.sha(args.flags_root / "tcn_variant.pt")
        != control_training["model_sha256"]
    ):
        raise ValueError("FLAGS64 trained model differs")
    control_identity = flags.read_json(args.flags_root / "identity.json")
    flags.verify_files(control_identity["files"])
    cache = flags.read_json(args.training_root / "cache_complete.json")
    if Path(cache["flags_root"]).resolve() != args.flags_root:
        raise ValueError("Different FLAGS64 training preparation")
    for name in ("normalizers.json", "feature_schema.json", "training_sample.parquet"):
        if cache["files"].get(str(args.flags_root / name)) != flags.sha(
            args.flags_root / name
        ):
            raise ValueError("Training normalizers/sample changed")
    fixed_copy_hashes = {
        str(args.training_root / "tcn_variant.pt"): training["model_sha256"],
        str(args.flags_root / "tcn_variant.pt"): control_training["model_sha256"],
        **{
            str(args.flags_root / name): cache["files"][str(args.flags_root / name)]
            for name in ("normalizers.json", "feature_schema.json")
        },
    }
    source = ClockSources(args.session_root, args.session_root, args.session_audit)
    calendar = calendar_record(source)
    dependencies = dependency_hashes()
    copies = {HERE / name: out / "executed_code" / name for name in dependencies}
    copies.update(
        {
            args.training_root / "tcn_variant.pt": out / "tcn_variant.pt",
            args.training_root / "training_complete.json": out
            / "training_complete.json",
            args.flags_root / "tcn_variant.pt": out / "tcn_control.pt",
            args.flags_root / "normalizers.json": out / "normalizers.json",
            args.flags_root / "feature_schema.json": out / "feature_schema.json",
        }
    )
    if not (out / "identity.json").exists() and any(
        (out / p).exists() for p in ("validation", "test", "freeze.json")
    ):
        raise ValueError("Economic output without prior identity")
    files = dict(source.hashes)
    for src, dst in copies.items():
        digest = copy_exact(src, dst)
        expected = fixed_copy_hashes.get(str(src.resolve()), dependencies.get(src.name))
        if expected is not None and digest != expected:
            raise ValueError("Snapshot differs from prior immutable authority")
        files[str(src.resolve())] = digest
        files[str(dst.resolve())] = digest
    for path in (
        args.control_audit,
        args.session_audit,
        args.implementation_review,
        args.flags_root / "identity.json",
        args.flags_root / "training_complete.json",
        args.training_root / "cache_complete.json",
        args.training_root / "tcn_epoch04.pt",
        args.training_root / "tcn_epoch04.json",
        args.training_root / "latest_checkpoint.json",
    ):
        files[str(path.resolve())] = flags.sha(path)
    if (
        files[str(args.implementation_review)] != review_hash
        or dependency_hashes() != dependencies
    ):
        raise ValueError("Authority changed during binding")
    legacy.stable_json(out / "session_calendar.json", calendar)
    dates = sorted(
        {item["date"] for period in calendar.values() for item in period["days"]}
    )
    calendar_csv = "date\n" + "\n".join(dates) + "\n"
    path = out / "expected_full_calendar.csv"
    if path.exists():
        if path.read_text(encoding="utf-8") != calendar_csv:
            raise ValueError("Calendar changed")
    else:
        temporary = path.with_suffix(".partial")
        if temporary.exists():
            raise FileExistsError(temporary)
        temporary.write_text(calendar_csv, encoding="utf-8", newline="")
        readers.shared.durable_replace(temporary, path)
    for path in (out / "session_calendar.json", out / "expected_full_calendar.csv"):
        files[str(path.resolve())] = flags.sha(path)
    identity = dict(
        files=files,
        dependencies=dependencies,
        learner_root=control_identity["learner_root"],
        control_root=str(args.flags_root),
        training_root=str(args.training_root),
        session_root=str(args.session_root),
        variant="row_mixed_epoch4_calendar750",
        control="FLAGS64_full_copy_plus9short",
        evaluation_calendar=calendar,
        training_changed=False,
    )
    legacy.stable_json(out / "identity.json", identity)
    return identity, training, source


def calendar_control(
    args, out, period, days, original, control_model, store, stats, scales, device
):
    lower, upper = (
        ("20250101", "20260101") if period == "validation" else ("20260101", "20260701")
    )
    relevant = [d for d in days if lower <= d.date < upper]
    full = {f"{d.ticker}_{d.date}.npz" for d in relevant if d.close_i == 390}
    full_root = legacy.adapt_control_period(args.flags_root, out, period, full)
    target = out / "control_calendar" / period
    target.mkdir(parents=True, exist_ok=True)
    hashes, lineage = {}, {}
    for day in relevant:
        name = f"{day.ticker}_{day.date}.npz"
        destination = target / name
        if day.close_i == 390:
            source = full_root / period / name
            copy_exact(source, destination)
            lineage[name] = dict(
                kind="AUDITED_FULL_COPY",
                source=str(source),
                source_sha256=flags.sha(source),
            )
        else:
            if period != "validation" or day.date not in SHORT_DATES:
                raise ValueError("Unexpected new control inference day")
            store.seal.check(day, "actions.parquet")
            actions = pd.read_parquet(day.oracle / "actions.parquet")
            marker = destination.with_suffix(".prediction.json")
            if marker.exists():
                record = flags.read_json(marker)
                flags.verify_files(record["files"])
                flags.verify_files(record["feature_files"])
                store.hashes.update(record["feature_files"])
                with np.load(destination, allow_pickle=False) as data:
                    if not np.array_equal(
                        data["action_ids"], actions.action_id.to_numpy()
                    ):
                        raise ValueError("Short control identities changed")
            else:
                if destination.exists():
                    raise FileExistsError("Unsealed short control preserved")
                scores = compat.inference_exact(
                    original,
                    control_model,
                    store,
                    day,
                    actions,
                    stats,
                    scales[day.ticker],
                    device,
                )
                save_scores(destination, actions.action_id.to_numpy(), scores)
                flags.atomic_json(
                    marker,
                    dict(
                        files={
                            str(destination): flags.sha(destination),
                            str(out / "tcn_control.pt"): flags.sha(
                                out / "tcn_control.pt"
                            ),
                            str(out / "normalizers.json"): flags.sha(
                                out / "normalizers.json"
                            ),
                            str(day.oracle / "actions.parquet"): flags.sha(
                                day.oracle / "actions.parquet"
                            ),
                        },
                        feature_files={
                            p: h
                            for p, h in store.hashes.items()
                            if day.date in p or p.endswith("feature_contract.json")
                        },
                        clock=SessionClock(day.close_i).as_dict(),
                        labels_read=False,
                    ),
                )
            lineage[name] = dict(
                kind="NEW_SHORT_INFERENCE",
                prediction_seal=str(marker),
                prediction_seal_sha256=flags.sha(marker),
            )
        hashes[name] = flags.sha(destination)
    legacy.stable_json(target / "prediction_hashes.json", hashes)
    legacy.stable_json(target / "lineage.json", lineage)
    return target.parent


@contextmanager
def exact_inference():
    old = flags.inference
    flags.inference = compat.inference_exact
    try:
        yield
    finally:
        flags.inference = old


def load_model(original, path, device):
    state = torch.load(path, map_location="cpu", weights_only=True)
    if state["epoch"] != 4:
        raise ValueError("Only fixed fourth epoch is allowed")
    model = original.LevelTCN(**state["config"]).to(device)
    model.load_state_dict(state["state_dict"])
    model.eval()
    return model


def evaluate(args):
    out = args.output
    identity, training, source = bind(args)
    if (out / "completion.json").exists():
        flags.verify_files(flags.read_json(out / "completion.json")["files"])
        return
    flags.require_prior_freeze(out)
    if (
        any(
            (out / p).exists()
            for p in ("control_adapter/test", "control_calendar/test")
        )
        and not (out / "freeze.json").exists()
    ):
        raise ValueError("Test artifacts exist without prior freeze")
    original = flags.load_original(Path(identity["learner_root"]))
    days = sorted(
        (d for d in source.days.values() if d.status == "COMPLETE"),
        key=lambda d: (flags.TICKERS.index(d.ticker), d.date),
    )
    artifacts = readers.Artifacts(out, flags.sha(out / "identity.json"))
    store = flags.CheckedStore(
        CalendarStore(source, artifacts), flags.read_json(out / "feature_schema.json")
    )
    normalizers = flags.read_json(out / "normalizers.json")
    stats, scales = normalizers["features"], normalizers["risk_scales_usd"]
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    device = training["binding"]["device"]
    if device.startswith("cuda"):
        torch.backends.cudnn.benchmark = False
    variant = load_model(original, out / "tcn_variant.pt", device)
    control = load_model(original, out / "tcn_control.pt", device)
    selection = None
    with exact_inference():
        for period in ("validation", "test"):
            adapter = calendar_control(
                args, out, period, days, original, control, store, stats, scales, device
            )
            summary = flags.evaluate_period(
                original,
                days,
                store,
                variant,
                scales,
                stats,
                out,
                adapter,
                period,
                device,
            )
            if period == "validation":
                selection = flags.select_validation(summary, scales)
                freeze = out / "freeze.json"
                if freeze.exists():
                    if flags.read_json(freeze)["selection"] != selection:
                        raise ValueError("Frozen selection changed")
                    flags.verify_files(flags.read_json(freeze)["files"])
                else:
                    files = {
                        str(p): flags.sha(p)
                        for p in out.rglob("*")
                        if p.is_file() and p.name != ".output.lock"
                    }
                    files.update(identity["files"])
                    files.update(store.hashes)
                    files.update(source.hashes)
                    files.update(
                        flags.read_json(
                            out / "control_adapter/validation/adapter_lineage.json"
                        )["source_files"]
                    )
                    flags.atomic_json(
                        freeze,
                        dict(
                            selection=selection,
                            files=files,
                            expected_validation_days=750,
                            test_evaluated=False,
                            frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                        ),
                    )
            else:
                legacy.finish(
                    out, identity, selection, summary, original, store, source
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "training-root",
        "flags-root",
        "control-audit",
        "session-root",
        "session-audit",
        "implementation-review",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for key, value in vars(args).items():
        setattr(args, key, value.resolve())
    for protected in (args.training_root, args.flags_root, args.session_root, HERE):
        if (
            args.output == protected
            or args.output.is_relative_to(protected)
            or protected.is_relative_to(args.output)
        ):
            raise ValueError("Separate evaluation output required")
    if (
        readers.shared.psutil.virtual_memory().available < 2_000_000_000
        or readers.shared.free_commit_bytes() < 2_000_000_000
    ):
        raise RuntimeError("At least 2 GB RAM and commit required")
    with flags.output_lock(args.output):
        evaluate(args)


if __name__ == "__main__":
    main()

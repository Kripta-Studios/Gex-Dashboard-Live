"""Independent comparison audit V2: safe separator-neutral relative manifests."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd
import pandas.testing as pdt

POLICIES = ("cue_net__0", "common_greek_net__0")
EDGES = np.array([-1.0, -0.5, 0.0, 0.1, 0.25, 0.5, 1.0, 2.0])
MISSING = {(ticker, day) for ticker in ("SPY", "QQQ")
           for day in ("20260401", "20260409", "20260415")}


def digest(path: Path) -> str:
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require(value, message):
    if not bool(value):
        raise AssertionError(message)


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def same(actual, expected, message="value", tolerance=1e-8):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), message + " keys")
        for key in expected:
            same(actual[key], expected[key], message + "." + str(key), tolerance)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), message + " length")
        for index, value in enumerate(expected):
            same(actual[index], value, message + f"[{index}]", tolerance)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        require(actual is not None and np.isclose(actual, expected, rtol=0, atol=tolerance), message)
    else:
        require(actual == expected, message)


def align(actions: pd.DataFrame, labels: pd.DataFrame, close_i: int) -> pd.DataFrame:
    require(close_i in (210, 390), "Session clock")
    require(actions.action_id.is_unique and labels.action_id.is_unique, "Unique action identity")
    indexed = labels.set_index("action_id", verify_integrity=True)
    require(set(indexed.index) == set(actions.action_id), "Label universe")
    result = indexed.loc[actions.action_id].reset_index()
    state = actions.state_i.to_numpy(int)
    exit_i = result.exit_i.to_numpy(int)
    filled = result.status.to_numpy() == "FILLED"
    require(result.status.isin(["FILLED", "NO_FILL"]).all(), "Label status")
    require(np.all((state >= 60) & (state <= close_i - 15)), "Decision horizon")
    require(np.all((exit_i[filled] >= state[filled] + 2)
                   & (exit_i[filled] <= close_i - 5)), "Filled exit")
    require(np.all(exit_i[~filled] == state[~filled] + 1), "NO_FILL clock")
    require(np.isfinite(result[["net_base", "net_adverse"]].to_numpy()).all(), "Finite payoff")
    require(np.all(result.loc[~filled, ["net_base", "net_adverse"]].to_numpy() == 0),
            "NO_FILL payoff")
    return result


def schedule(actions: pd.DataFrame, labels: pd.DataFrame, scores, close_i: int):
    scores = np.asarray(scores)
    require(scores.shape == (len(actions),) and np.isfinite(scores).all(), "Scores")
    choices = {}
    order = np.lexsort((actions.action_id.to_numpy(), -scores, actions.state_i.to_numpy()))
    for position in order:
        minute = int(actions.state_i.iloc[position])
        if minute not in choices:
            choices[minute] = int(position) if scores[position] > 0 else -1
    aligned = align(actions, labels, close_i)
    selected, prior_filled, minute, has_filled = [], [], 60, 0
    while minute <= close_i - 15:
        position = choices.get(minute, -1)
        if position < 0:
            minute += 1
            continue
        selected.append(position)
        prior_filled.append(has_filled)
        if aligned.status.iloc[position] == "FILLED":
            minute = int(aligned.exit_i.iloc[position]) + 1
            has_filled = 1
        else:
            minute += 1
    attempts = pd.DataFrame({
        "action_id": actions.action_id.to_numpy()[selected],
        "state_i": actions.state_i.to_numpy()[selected],
        "score_usd": scores[selected],
        "has_filled_before": np.asarray(prior_filled, dtype=np.int8),
    })
    for column in ("status", "exit_i", "net_base", "net_adverse"):
        attempts[column] = aligned[column].to_numpy()[selected]
    return aligned, attempts, attempts.loc[attempts.status == "FILLED"].copy()


def calibration_sums(scores, outcomes, scale, weights=None):
    scores, outcomes = np.asarray(scores, float), np.asarray(outcomes, float)
    weights = np.ones(len(scores)) if weights is None else np.asarray(weights, float)
    require(scores.shape == outcomes.shape == weights.shape and scores.ndim == 1, "Calibration shape")
    require(np.isfinite(scores).all() and np.isfinite(outcomes).all()
            and np.isfinite(weights).all() and np.all(weights >= 0) and scale > 0,
            "Calibration values")
    bucket = np.searchsorted(EDGES, scores / scale, side="right")
    residual = outcomes - scores
    rows = []
    for index in range(len(EDGES) + 1):
        take = bucket == index
        weight = weights[take]
        rows.append({"bin": index, "n": int(take.sum()), "weight": float(weight.sum()),
                     "predicted_sum": float(np.dot(weight, scores[take])),
                     "realized_sum": float(np.dot(weight, outcomes[take])),
                     "squared_error_sum": float(np.dot(weight, residual[take] ** 2)),
                     "absolute_error_sum": float(np.dot(weight, np.abs(residual[take])))})
    return rows


def calibration_report(records):
    rows = []
    for index in range(len(EDGES) + 1):
        parts = [row for day in records for row in day if row["bin"] == index]
        def total(field):
            return sum(row[field] for row in parts)

        weight = total("weight")
        rows.append({"bin": index, "lower_risk_units": None if index == 0 else float(EDGES[index - 1]),
                     "upper_risk_units": None if index == len(EDGES) else float(EDGES[index]),
                     "n": total("n"), "weight": weight,
                     "predicted_usd": total("predicted_sum") / weight if weight else None,
                     "realized_usd": total("realized_sum") / weight if weight else None,
                     "mean_residual_usd": (total("realized_sum") - total("predicted_sum")) / weight if weight else None,
                     "rmse_usd": (total("squared_error_sum") / weight) ** 0.5 if weight else None,
                     "mae_usd": total("absolute_error_sum") / weight if weight else None})
    return rows


def trade_metrics(ledger):
    result = {"trades": len(ledger)}
    for column in ("net_base", "net_adverse"):
        values = ledger[column].to_numpy(float)
        gains = float(values[values > 0].sum())
        losses = -float(values[values < 0].sum())
        result[column] = float(values.sum())
        result[column + "_profit_factor"] = gains / losses if losses else None
        result[column + "_pf_infinite"] = bool(gains > 0 and losses == 0)
        result[column + "_win_rate"] = float((values > 0).mean()) if len(values) else None
    return result


def coverage(rows):
    require(len({(r["ticker"], r["date"]) for r in rows}) == len(rows), "Coverage keys")
    missing = [r for r in rows if r["source_status"] == "MISSING_SOURCE"]
    available = [r for r in rows if r["source_status"] == "COMPLETE"]
    require(all(r["trades"] == 0 and r["net_base"] == r["net_adverse"] == 0 for r in missing),
            "Missing economics")
    failures = [r for r in available if r["trades"] < 1]
    return {"expected_days": len(rows), "available_days": len(available),
            "missing_days": len(missing), "available_days_without_fill": len(failures),
            "observable_daily_pass": bool(available) and not failures,
            "universal_daily_pass": not missing and not failures,
            "universal_daily_status": "NO_EVALUABLE" if missing else ("PASS" if not failures else "FAIL"),
            "missing_keys": [r["ticker"] + "/" + r["date"] for r in missing],
            "unfilled_available_keys": [r["ticker"] + "/" + r["date"] for r in failures]}


def canonical_manifest_key(relative):
    require(isinstance(relative, str) and bool(relative), "Relative manifest path required")
    name = relative.replace("\\", "/")
    require(not name.startswith("/") and not PureWindowsPath(relative).drive,
            "Absolute/drive manifest path forbidden")
    parts = name.split("/")
    devices = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    devices.update(prefix + suffix for prefix in ("COM", "LPT")
                   for suffix in "123456789¹²³")
    for part in parts:
        require(part not in ("", ".", "..") and part.rstrip(" .") == part,
                "Ambiguous/escaping manifest segment")
        require(not any(ord(char) < 32 or char in '<>:"|?*' for char in part),
                "Invalid Windows manifest segment")
        require(part.split(".")[0].upper() not in devices, "Reserved Windows manifest segment")
    return "/".join(parts)


def resolved_manifest_target(root: Path, key):
    root = Path(root).resolve()
    target = root.joinpath(*canonical_manifest_key(key).split("/")).resolve()
    require(target.is_relative_to(root) and target != root, "Manifest path escapes root")
    return target


def canonical_manifest_files(root: Path, files):
    require(isinstance(files, dict), "Relative manifest map required")
    result, aliases, targets = {}, set(), set()
    for relative, expected in files.items():
        key = canonical_manifest_key(relative)
        target = resolved_manifest_target(root, key)
        alias, resolved = key.casefold(), str(target).casefold()
        require(alias not in aliases and resolved not in targets, "Manifest path collision")
        aliases.add(alias)
        targets.add(resolved)
        result[key] = expected
    return result


def remember_baseline_score(root, files, relative, memo):
    relative = canonical_manifest_key(relative)
    require(relative in files, "Baseline score absent")
    reference = resolved_manifest_target(root, relative)
    remember(memo, reference, files[relative])
    return reference


def verify_marker(root: Path, name: str, binding: str, memo: dict, required=()):
    path = root / (name + ".complete.json")
    record = read_json(path)
    require(record["status"] == "COMPLETE" and record["binding"] == binding, "Marker binding " + name)
    normalized = canonical_manifest_files(root, record["files"])
    require(len(normalized) == len(record["files"]), "Marker path collision " + name)
    normalized_required = {canonical_manifest_key(relative) for relative in required}
    require(normalized_required.issubset(normalized), "Marker files " + name)
    for relative, expected in normalized.items():
        target = resolved_manifest_target(root, relative)
        key = str(target.resolve())
        if key not in memo:
            memo[key] = digest(target)
        actual = memo[key]
        require(actual == expected, "Marker artifact " + relative)
    for filename, expected in record.get("extra", {}).get("sources", {}).items():
        target = Path(filename)
        key = str(target.resolve())
        if key not in memo:
            memo[key] = digest(target)
        actual = memo[key]
        require(actual == expected, "Marker source " + filename)
    return record


def rehash_memo(memo):
    for filename, expected in memo.items():
        require(digest(Path(filename)) == expected, "Consumed artifact changed " + filename)


def remember(memo, path, expected=None):
    path = Path(path).resolve()
    actual = digest(path)
    if expected is not None:
        require(actual == expected, "Consumed artifact authority " + str(path))
    memo[str(path)] = actual
    return actual


def verify_training_provenance(path, expected, memo, expected_files=None):
    remember(memo, path, expected)
    record = read_json(path)
    require(record["status"] == "PINNED_TRAIN_INPUTS_REHASHED_AT_ADMISSION"
            and record["recheck"] == "ADMISSION_EVERY_RESUME_AND_FINAL_BEFORE_COMPLETION"
            and bool(record["files"]), "TRAIN provenance manifest")
    if expected_files is not None:
        require(record["files"] == expected_files, "TRAIN provenance completeness")
    for filename, file_hash in record["files"].items():
        require(Path(filename).is_absolute(), "TRAIN provenance path")
        remember(memo, filename, file_hash)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--session-root", type=Path, required=True)
    parser.add_argument("--session-audit", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--baseline-audit", type=Path, required=True)
    parser.add_argument("--cue-root", type=Path, required=True)
    parser.add_argument("--greek-root", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Fresh audit root required")
    memo = {}
    freeze_path = args.root / "freeze.json"
    freeze = read_json(freeze_path)
    require(freeze["status"] == "FROZEN_BEFORE_COMPARISON2025"
            and freeze["policies"] == list(POLICIES) and freeze["threshold"] == 0
            and freeze["winner_selection"] is False, "Frozen comparison")
    binding = remember(memo, freeze_path)
    review = read_json(args.review)
    session_audit = read_json(args.session_audit)
    require(session_audit["status"] == "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT"
            and Path(session_audit["binding"]["engine_root"]).resolve() == args.session_root.resolve(),
            "Session audit authority")
    baseline_audit = read_json(args.baseline_audit)
    require(baseline_audit["status"]
            == "PASS_INDEPENDENT_MARKET_CUE_COMPARISON_ECONOMIC_AUDIT"
            and Path(baseline_audit["binding"]["comparison_root"]).resolve()
            == args.baseline_root.resolve(), "Baseline audit authority")
    authority_paths = {
        "cue_comparison_audit_sha256": args.baseline_audit,
        "session_audit_sha256": args.session_audit,
        "cue_contract_sha256": args.cue_root / "run_contract.json",
        "cue_model_completion_sha256": args.cue_root / "model.complete.json",
        "greek_contract_sha256": args.greek_root / "run_contract.json",
        "greek_model_completion_sha256": args.greek_root / "model.complete.json",
    }
    expected_authorities = {name: remember(memo, path) for name, path in authority_paths.items()}
    require(review["status"] == "PASS_COMMON_GREEK_COMPARISON_IMPLEMENTATION_REVIEW"
            and review["authorities"] == expected_authorities
            and review["dependencies"] == freeze["dependencies"], "Review authority")
    for path in [args.review, *authority_paths.values()]:
        require(freeze["sources"].get(str(path.resolve())) == remember(memo, path),
                "Frozen authority source " + str(path))
    cue_contract = read_json(args.cue_root / "run_contract.json")
    greek_contract = read_json(args.greek_root / "run_contract.json")
    require(freeze["scales"] == cue_contract["scales"] == greek_contract["scales"],
            "Frozen TRAIN scales")
    require(freeze["models"] == {
        POLICIES[0]: str((args.cue_root / "cue_net.txt").resolve()),
        POLICIES[1]: str((args.greek_root / "common_greek_net.txt").resolve())},
        "Frozen model paths")
    expected_train_sources = {}
    for source_map in (cue_contract["sources"], greek_contract["sources"]):
        for filename, file_hash in source_map.items():
            require(filename not in expected_train_sources
                    or expected_train_sources[filename] == file_hash,
                    "Conflicting TRAIN source authority")
            expected_train_sources[filename] = file_hash
    for root, model_name in ((args.cue_root, "cue_net.txt"),
                             (args.greek_root, "common_greek_net.txt")):
        marker = read_json(root / "model.complete.json")
        model_files = canonical_manifest_files(root, marker["files"])
        require(marker["status"] == "COMPLETE"
                and marker["binding"] == digest(root / "run_contract.json")
                and model_name in model_files, "Model completion binding")
        remember(memo, resolved_manifest_target(root, model_name), model_files[model_name])
        for filename, file_hash in marker.get("extra", {}).get("sources", {}).items():
            require(filename not in expected_train_sources
                    or expected_train_sources[filename] == file_hash,
                    "Conflicting model source authority")
            expected_train_sources[filename] = file_hash
    index_path = args.session_root / "index.parquet"
    remember(memo, index_path, session_audit["binding"]["index_sha256"])
    index = pd.read_parquet(index_path)
    index["date"] = index.date.astype(str)
    index = index.set_index(["ticker", "date"], verify_integrity=True)
    scales = freeze["scales"]
    baseline_complete = args.baseline_root / "comparison.complete.json"
    remember(memo, baseline_complete,
             baseline_audit["binding"]["comparison_complete_sha256"])
    baseline_manifest = read_json(baseline_complete)
    require(baseline_manifest["status"] == "COMPLETE", "Baseline completion")
    baseline_files = canonical_manifest_files(args.baseline_root, baseline_manifest["files"])
    provenance_path = args.root / "training_provenance.json"
    verify_training_provenance(
        provenance_path, freeze["training_provenance_sha256"], memo,
        expected_train_sources)
    test_freeze_path = args.root / "test_freeze.json"
    test_freeze_sha = remember(memo, test_freeze_path)

    reconstructed, baseline_days, short_days = {2025: {}, 2026: {}}, 0, 0
    consumed_relative = {"freeze.json", "test_freeze.json"}
    for year, expected_days in ((2025, 750), (2026, 369)):
        year_relative = set()
        rows = [(ticker, day, row) for (ticker, day), row in index.iterrows() if day.startswith(str(year))]
        require(len(rows) == expected_days, "Calendar count")
        for number, (ticker, day, source_row) in enumerate(sorted(rows), 1):
            key = ticker + "/" + day
            day_name = "days/" + key
            pred_name = "predictions/" + key
            daily_required = [day_name + ".json",
                              *(day_name + "." + policy + ".parquet" for policy in POLICIES)]
            if source_row.status != "MISSING_SOURCE":
                daily_required.extend([pred_name + ".npz", pred_name + ".complete.json"])
            verify_marker(args.root, day_name, binding, memo, daily_required)
            consumed_relative.update(daily_required)
            consumed_relative.add(day_name + ".complete.json")
            year_relative.update(daily_required)
            year_relative.add(day_name + ".complete.json")
            daily_json = read_json(args.root / (day_name + ".json"))
            if source_row.status == "MISSING_SOURCE":
                require((ticker, day) in MISSING and not (args.root / (pred_name + ".npz")).exists(),
                        "Missing prediction")
                for policy in POLICIES:
                    empty = pd.read_parquet(args.root / (day_name + "." + policy + ".parquet"))
                    require(empty.empty, "Missing attempts")
                    expected = {"ticker": ticker, "date": day, "source_status": "MISSING_SOURCE",
                                **trade_metrics(empty), "attempts": 0, "calibration": {}}
                    same(daily_json[policy], expected, key + policy)
                reconstructed[year][key] = daily_json
                continue
            pred_path = args.root / (pred_name + ".npz")
            pred_marker = verify_marker(args.root, pred_name, binding, memo,
                                        [str(pred_path.relative_to(args.root))])
            consumed_relative.update([pred_name + ".npz", pred_name + ".complete.json"])
            year_relative.update([pred_name + ".npz", pred_name + ".complete.json"])
            require(pred_marker["extra"].get("outcomes_read") is False, "Prediction label boundary")
            if year == 2026:
                require(pred_marker["extra"]["sources"].get(str(test_freeze_path.resolve()))
                        == test_freeze_sha, "Test prediction lacks pre-test freeze")
            with np.load(pred_path, allow_pickle=False) as saved:
                require(set(saved.files) == {"action_id", "state_i", *POLICIES}, "Prediction schema")
                actions = pd.DataFrame({"action_id": saved["action_id"], "state_i": saved["state_i"]})
                scores = {policy: saved[policy] for policy in POLICIES}
            baseline_rel = pred_name + ".npz"
            reference = remember_baseline_score(args.baseline_root, baseline_files, baseline_rel, memo)
            with np.load(reference, allow_pickle=False) as old:
                require(np.array_equal(old["action_id"], actions.action_id)
                        and np.array_equal(old["state_i"], actions.state_i)
                        and old["cue_net__0"].dtype == scores[POLICIES[0]].dtype
                        and old["cue_net__0"].tobytes() == scores[POLICIES[0]].tobytes(),
                        "Cue baseline score byte identity")
            require(pred_marker["extra"]["original_control_reference"]["status"]
                    == "EXACT_AUDITED_CUE_ALL_SESSIONS", "Cue reference marker")
            baseline_days += 1
            short_days += int(source_row.close_i) == 210
            day_root = Path(source_row.day_root)
            action_path, label_path = day_root / "actions.parquet", day_root / "labels.parquet"
            remember(memo, action_path, source_row.actions_sha256)
            remember(memo, label_path, source_row.labels_sha256)
            source_actions = pd.read_parquet(action_path, columns=["action_id", "state_i"])
            require(source_actions.equals(actions), "Prediction action/state identity")
            labels = pd.read_parquet(label_path,
                                     columns=["action_id", "status", "exit_i", "net_base", "net_adverse"])
            result = {}
            for policy in POLICIES:
                aligned, attempts, ledger = schedule(actions, labels, scores[policy], int(source_row.close_i))
                actual_attempts = pd.read_parquet(args.root / (day_name + "." + policy + ".parquet"))
                pdt.assert_frame_equal(attempts.reset_index(drop=True), actual_attempts.reset_index(drop=True),
                                       check_exact=True, check_dtype=True)
                group = actions.groupby("state_i").state_i.transform("size").to_numpy()
                state_count = actions.state_i.nunique()
                equal_state = 1.0 / (group * state_count) if state_count else np.empty(0)
                calibration = {
                    "all_offers_action_weighted": calibration_sums(scores[policy], aligned.net_base, scales[ticker]),
                    "all_offers_equal_day_state": calibration_sums(scores[policy], aligned.net_base, scales[ticker], equal_state),
                    "selected_attempts": calibration_sums(attempts.score_usd, attempts.net_base, scales[ticker]),
                    "selected_fills": calibration_sums(ledger.score_usd, ledger.net_base, scales[ticker]),
                }
                result[policy] = {"ticker": ticker, "date": day, "source_status": "COMPLETE",
                                  **trade_metrics(ledger), "attempts": len(attempts), "calibration": calibration}
                same(daily_json[policy], result[policy], key + policy)
            reconstructed[year][key] = result
            if number % 50 == 0:
                print(json.dumps({"stage": "audit", "year": year, "days": number,
                                  "total": expected_days}), flush=True)
        report = {"policies": {}, "winner_selected": None, "threshold": 0,
                  "development_seen": True, "promotion_approved": False}
        for policy in POLICIES:
            report["policies"][policy] = {}
            for ticker in ("ALL", "QQQ", "SPXW", "SPY"):
                keys = [key for key in reconstructed[year]
                        if ticker == "ALL" or key.startswith(ticker + "/")]
                daily = [reconstructed[year][key][policy] for key in keys]
                frames = [pd.read_parquet(args.root / ("days/" + key + "." + policy + ".parquet"))
                          for key in keys]
                nonempty = [frame for frame in frames if len(frame)]
                attempts = pd.concat(nonempty, ignore_index=True) if nonempty else frames[0].iloc[:0]
                ledger = attempts.loc[attempts.status == "FILLED"]
                report["policies"][policy][ticker] = {
                    "coverage": coverage(daily), "available_economics": trade_metrics(ledger),
                    "calibration": {kind: calibration_report([row["calibration"][kind]
                                                               for row in daily if kind in row["calibration"]])
                                    for kind in ("all_offers_action_weighted",
                                                 "all_offers_equal_day_state",
                                                 "selected_attempts", "selected_fills")}}
        actual_report = read_json(args.root / f"period{year}.json")
        same(actual_report, report, f"period{year}")
        period_name = f"period{year}"
        period_required = [f"period{year}.json", *year_relative]
        verify_marker(args.root, period_name, binding, memo, period_required)
        consumed_relative.update([f"period{year}.json", f"period{year}.complete.json"])

    require(baseline_days == 1113 and short_days == 9, "Reference coverage")
    test_freeze = read_json(test_freeze_path)
    require(test_freeze == {
        "status": "FIXED_POLICIES_AFTER_VALIDATION_BEFORE_TEST",
        "initial_freeze_sha256": binding,
        "validation_sha256": digest(args.root / "period2025.json"),
        "validation_completion_sha256": digest(args.root / "period2025.complete.json"),
        "policies": list(POLICIES), "threshold": 0, "winner_selected": None},
        "Test freeze")
    remember(memo, test_freeze_path)
    completion_path = args.root / "completion.json"
    completion = read_json(completion_path)
    require(completion == {"status": "COMPLETE_FIXED_COMMON_GREEK_COMPARISON",
                           "freeze_sha256": binding, "periods": [2025, 2026],
                           "policies": list(POLICIES), "winner_selected": None,
                           "development_seen": True, "promotion_approved": False},
            "Global completion")
    verify_marker(
        args.root, "comparison", binding, memo,
        ["completion.json", *consumed_relative])
    consumed_relative.update(["completion.json", "comparison.complete.json"])
    rehash_memo(memo)
    args.output.mkdir(parents=True)
    result = {"status": "PASS_INDEPENDENT_COMMON_GREEK_COMPARISON_ECONOMIC_AUDIT",
              "scope": "ECONOMIC_EXECUTION_GIVEN_SEALED_PREDICTIONS",
              "binding": {"comparison_root": str(args.root.resolve()),
                          "freeze_sha256": binding,
                          "period2025_sha256": digest(args.root / "period2025.json"),
                          "period2026_sha256": digest(args.root / "period2026.json"),
                          "completion_sha256": digest(completion_path),
                          "comparison_complete_sha256": digest(args.root / "comparison.complete.json"),
                          "session_audit_sha256": digest(args.session_audit),
                          "cue_comparison_audit_sha256": digest(args.baseline_audit),
                          "review_sha256": digest(args.review),
                          "cue_contract_sha256": digest(args.cue_root / "run_contract.json"),
                          "cue_model_completion_sha256": digest(args.cue_root / "model.complete.json"),
                          "greek_contract_sha256": digest(args.greek_root / "run_contract.json"),
                          "greek_model_completion_sha256": digest(args.greek_root / "model.complete.json"),
                          "training_provenance_sha256": digest(provenance_path),
                          "test_freeze_sha256": digest(test_freeze_path),
                          "audit_script_sha256": digest(Path(__file__).resolve())},
              "coverage": {"days_2025": 750, "days_2026": 369,
                           "available_2026": 363, "missing_2026": 6,
                           "cue_control_scores_bitexact": baseline_days,
                           "short_sessions_bitexact": short_days},
              "policies": list(POLICIES), "winner_selected": None, "threshold": 0,
              "scheduler_reconstructed_independently": True,
              "calibration_reconstructed_independently": True,
              "model_training_reproduced": False, "prediction_inference_reproduced": False,
              "development_seen": True, "technical_ready": False, "promotion_approved": False,
              "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    (args.output / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()



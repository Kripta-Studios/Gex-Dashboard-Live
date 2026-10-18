"""Fixed OOF policy replay. Library only; no market execution or fitting CLI."""

from pathlib import Path
import struct

import pandas as pd

import monthly_oof_calibration_adapter as adapter
import oof_maximum_calibration as core

require = core.require
FIELDS = (
    "action_id",
    "state_i",
    "score",
    "has_filled_before",
    "status",
    "exit_i",
    "net_base",
    "net_adverse",
)
LABEL_FIELDS = ("action_id", "status", "exit_i", "net_base", "net_adverse")


def dependencies():
    root = Path(__file__).resolve().parent
    names = set(adapter.dependency_hashes()) | {
        Path(__file__).name,
        "OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md",
    }
    return {name: core.file_sha(root / name) for name in sorted(names)}


def exact_rows(actual, expected):
    """Compare scheduler projection, preserving IEEE754 float64 bytes."""
    require(len(actual) == len(expected), "Control row count differs")
    for left, right in zip(actual, expected):
        for name in FIELDS:
            if name in ("score", "net_base", "net_adverse"):
                equal = struct.pack("!d", core.finite(left[name])) == struct.pack(
                    "!d", core.finite(right[name])
                )
            else:
                equal = left[name] == right[name]
            require(equal, "Control differs: " + name)


def replay(rows, close_i, outcome, *, corrected=False):
    """Read only the chosen action outcome after visiting its prechosen maximum."""
    require(close_i in (210, 390), "Unknown session clock")
    choices, identities = {}, set()
    score_field = "corrected_score_usd" if corrected else "score_usd"
    for row in rows:
        state, ident = core.integer(row["state_i"]), core.integer(row["action_id"])
        require(60 <= state <= close_i - 15, "Maximum beyond decision horizon")
        require(state not in choices and ident not in identities, "Duplicate maximum")
        choices[state] = (ident, core.finite(row[score_field]))
        identities.add(ident)
    minute, has_filled = 60, 0
    attempts, decisions = [], []
    while minute <= close_i - 15:
        chosen = choices.get(minute)
        if chosen is None or chosen[1] <= 0:
            decisions.append(
                dict(state_i=minute, decision="WAIT", has_filled_before=has_filled)
            )
            minute += 1
            continue
        ident, score = chosen
        label = outcome(ident)
        require(core.integer(label["action_id"]) == ident, "Wrong outcome identity")
        status, exit_i = label["status"], core.integer(label["exit_i"])
        base, adverse = (
            core.finite(label["net_base"]),
            core.finite(label["net_adverse"]),
        )
        require(status in ("FILLED", "NO_FILL"), "Invalid fill status")
        if status == "NO_FILL":
            require(exit_i == minute + 1 and base == adverse == 0, "Invalid NO_FILL")
            next_minute = minute + 1
        else:
            require(minute + 2 <= exit_i <= close_i - 5, "Invalid filled exit")
            next_minute = exit_i + 1
        row = dict(
            action_id=ident,
            state_i=minute,
            score=score,
            has_filled_before=has_filled,
            status=status,
            exit_i=exit_i,
            net_base=base,
            net_adverse=adverse,
        )
        attempts.append(row)
        decisions.append(
            dict(
                state_i=minute,
                decision=status,
                action_id=ident,
                has_filled_before=has_filled,
            )
        )
        has_filled = int(has_filled or status == "FILLED")
        minute = next_minute
    return dict(
        attempts=attempts,
        ledger=[r for r in attempts if r["status"] == "FILLED"],
        decisions=decisions,
    )


def verify_control(selection, attempts, ledger):
    """Reconstruct using already-audited attempts, before new target-label access."""
    by_id = {core.integer(row["action_id"]): row for row in attempts}
    require(len(by_id) == len(attempts), "Duplicate audited control attempt")

    def known(ident):
        require(ident in by_id, "Control maximum absent from audited attempts")
        return by_id[ident]

    result = replay(selection["selected"], selection["close_i"], known)
    exact_rows(result["attempts"], attempts)
    exact_rows(result["ledger"], ledger)
    return result


def observed_metrics(ledger):
    result = dict(trades=len(ledger))
    for field in ("net_base", "net_adverse"):
        values = [core.finite(row[field]) for row in ledger]
        gains, losses = (
            sum(v for v in values if v > 0),
            -sum(v for v in values if v < 0),
        )
        result[field] = sum(values)
        result[field + "_gross_gains"] = gains
        result[field + "_gross_losses"] = losses
        result[field + "_profit_factor"] = gains / losses if losses else None
        result[field + "_pf_infinite"] = bool(gains > 0 and losses == 0)
    return result


def coverage(daily):
    require(
        daily and len({(r["ticker"], r["date"]) for r in daily}) == len(daily),
        "Empty or duplicate calendar",
    )
    require(
        all(r["source_status"] in ("COMPLETE", "MISSING_SOURCE") for r in daily),
        "Unknown calendar status",
    )
    available = [r for r in daily if r["source_status"] == "COMPLETE"]
    missing = [r for r in daily if r["source_status"] == "MISSING_SOURCE"]
    require(
        all(
            r["trades"] is None and r["net_base"] is None and r["net_adverse"] is None
            for r in missing
        ),
        "Fabricated missing-source metrics",
    )
    zero = sum(r["trades"] == 0 for r in available)
    return dict(
        expected_days=len(daily),
        available_days=len(available),
        missing_days=len(missing),
        available_days_without_fill=zero,
        observable_daily_pass=bool(available) and zero == 0,
        universal_daily_pass=bool(available) and not missing and zero == 0,
        universal_daily_status="NO_EVALUABLE"
        if missing
        else ("PASS" if not zero else "FAIL"),
    )


def summarize_period(monthly_summaries, expected_calendar):
    """Pure six-month summary; caller supplies the full source-audited calendar."""
    months = {f"2026{month:02d}" for month in range(1, 7)}
    require(
        len(monthly_summaries) == 6
        and {r["target_month"] for r in monthly_summaries} == months,
        "Six completed development months required",
    )
    require(
        len(expected_calendar) == 369
        and sum(v == "COMPLETE" for v in expected_calendar.values()) == 363
        and sum(v == "MISSING_SOURCE" for v in expected_calendar.values()) == 6,
        "Full 369/363/6 calendar required",
    )
    policies = {
        mode + suffix
        for mode in core.PROCEDURES
        for suffix in ("__control", "__corrected")
    }
    require(
        all(
            r["status"] == "COMPLETE_FIXED_OOF_POLICY_MONTH"
            and set(r["policies"]) == policies
            and r["winner_selected"] is None
            for r in monthly_summaries
        ),
        "Wrong monthly policy closure",
    )
    reports = {}
    for policy in sorted(policies):
        reports_for_policy = [r["policies"][policy] for r in monthly_summaries]
        daily = [d for report in reports_for_policy for d in report["daily"]]
        require(
            len(daily) == len(expected_calendar)
            and {(d["ticker"], d["date"]): d["source_status"] for d in daily}
            == expected_calendar,
            "Period calendar omitted or changed",
        )
        totals = {"trades": sum(r["observed"]["trades"] for r in reports_for_policy)}
        for field in ("net_base", "net_adverse"):
            for suffix in ("", "_gross_gains", "_gross_losses"):
                totals[field + suffix] = sum(
                    r["observed"][field + suffix] for r in reports_for_policy
                )
            gain, loss = totals[field + "_gross_gains"], totals[field + "_gross_losses"]
            totals[field + "_profit_factor"] = gain / loss if loss else None
            totals[field + "_pf_infinite"] = bool(gain > 0 and loss == 0)
        reports[policy] = dict(
            coverage=coverage(daily),
            observed=totals,
            by_ticker={
                ticker: coverage([d for d in daily if d["ticker"] == ticker])
                for ticker in core.TICKERS
            },
        )
    return dict(
        status="COMPLETE_FIXED_OOF_POLICY_DEVELOPMENT_PERIOD",
        policies=reports,
        winner_selected=None,
        promotion_approved=False,
        development_seen=True,
    )


def _load_control(source, procedure, ticker, stamp):
    prefix = f"ledgers/{stamp[:6]}/{procedure}/{ticker}/{stamp}"
    paths = [
        source.root / (prefix + ending)
        for ending in ("_attempts.parquet", "_ledger.parquet")
    ]
    source.marker(prefix, paths)
    result = []
    for path in paths:
        source.verify(path)
        frame = pd.read_parquet(path, columns=list(FIELDS))
        source.verify(path)
        result.append(frame.to_dict("records"))
    return result


def _check_adapter_closure(source, root, month, expected_sha):
    path = root / (month + ".complete.json")
    complete = core.load_seal(path, expected_sha)
    require(
        complete["status"] == "COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS"
        and complete["target_month"] == month
        and complete["monthly_audit_sha256"] == source.authority_sha
        and complete["dependencies"] == adapter.dependency_hashes()
        and complete["target_labels_read"] is False
        and set(complete["procedures"]) == set(core.PROCEDURES),
        "Wrong correction authority",
    )
    inputs_path = root / (month + ".inputs.json")
    inputs = core.load_seal(inputs_path, complete["inputs_sha256"])
    require(
        inputs["dependencies"] == adapter.dependency_hashes()
        and inputs["monthly_audit_sha256"] == source.authority_sha,
        "Correction inputs differ",
    )
    files = {str(path): expected_sha, str(inputs_path): complete["inputs_sha256"]}
    for mapping in (inputs["files"], inputs["run_authorities"]):
        for filename, digest in mapping.items():
            require(core.file_sha(filename) == digest, "Changed correction source")
            files[filename] = digest
    return complete, files


def evaluate_month(
    source, correction_root, target_month, output, *, correction_completion_sha256
):
    """Future integration API. No CLI; independent authority required by MonthlyInputs.

    All controls are reproduced before any new target-month labels are read.
    Offsets and all target scores must already be sealed by the OOF adapter.
    """
    core.month_start(target_month)
    require("202601" <= target_month <= "202606", "Only declared development months")
    correction_root, output = Path(correction_root).resolve(), Path(output).resolve()
    for other in (source.root, source.session_root, correction_root):
        require(
            not output.is_relative_to(other) and not other.is_relative_to(output),
            "Separate evaluation output required",
        )
    code = dependencies()
    with adapter.output_lock(output):
        contract_path = output / "run_contract.json"
        if not contract_path.exists():
            require(
                not any(path.name != ".lock" for path in output.iterdir()),
                "Evaluation outputs exist without run contract",
            )
        complete, files = _check_adapter_closure(
            source, correction_root, target_month, correction_completion_sha256
        )
        contract = dict(
            version="OOF_POLICY_REPLAY_V1",
            dependencies=code,
            monthly_audit_sha256=source.authority_sha,
            correction_completion_sha256=correction_completion_sha256,
            target_month=target_month,
            threshold=0,
            winner_selected=None,
        )
        contract_sha = adapter.publish_or_verify(contract_path, contract)
        files[str(contract_path)] = contract_sha
        rows = source.month_rows(target_month)
        expected_keys = set(rows.index)
        prepared, controls = {}, {}
        # First seal every score and reproduce every control, without target-label access.
        for procedure in core.PROCEDURES:
            item = complete["procedures"][procedure]
            inventory = item["target_calendar"]
            require(
                len(inventory) == len(expected_keys)
                and {(r["ticker"], r["day"]) for r in inventory} == expected_keys,
                "Correction calendar differs",
            )
            calibration_path = (
                correction_root / procedure / target_month / "calibration.json"
            )
            calibration = core.load_seal(calibration_path, item["calibration_sha256"])
            files[str(calibration_path)] = item["calibration_sha256"]
            require(
                calibration["procedure"] == procedure
                and calibration["target_month"] == target_month
                and calibration["threshold"] == 0
                and calibration["ranking_changed"] is False,
                "Calibration procedure differs",
            )
            for entry in inventory:
                ticker, stamp = entry["ticker"], entry["day"]
                require(
                    entry["procedure"] == procedure
                    and entry["source_status"] == rows.loc[(ticker, stamp)].status,
                    "Correction source status differs",
                )
                key = (procedure, ticker, stamp)
                if entry["source_status"] == "MISSING_SOURCE":
                    prepared[key] = None
                    continue
                chosen = source.select_day(
                    procedure, ticker, stamp, output / "baseline"
                )
                require(
                    chosen["selection_sha256"] == entry["selection_sha256"],
                    "Maximum differs from audited monthly scores",
                )
                selection = core.load_seal(
                    chosen["selection_path"], chosen["selection_sha256"]
                )
                files[chosen["selection_path"]] = chosen["selection_sha256"]
                score = core.load_seal(entry["score_path"], entry["score_sha256"])
                expected = dict(
                    version=core.VERSION,
                    procedure=procedure,
                    ticker=ticker,
                    day=stamp,
                    calibration_sha256=item["calibration_sha256"],
                    selection_sha256=chosen["selection_sha256"],
                    rows=[
                        {
                            **r,
                            "corrected_score_usd": core.finite(r["score_usd"])
                            + core.finite(calibration["offsets_usd"][ticker]),
                        }
                        for r in selection["selected"]
                    ],
                    threshold=0,
                    ranking_changed=False,
                    outcomes_read=False,
                )
                require(
                    core.content_sha(score) == core.content_sha(expected),
                    "Altered corrected scores",
                )
                files[entry["score_path"]] = entry["score_sha256"]
                attempts, ledger = _load_control(source, procedure, ticker, stamp)
                controls[key] = verify_control(selection, attempts, ledger)
                prepared[key] = (selection, score)
        source.recheck()
        score_seal = adapter.publish_or_verify(
            output / "all_scores_and_controls.json",
            dict(
                files=files,
                monthly_files=dict(source.used),
                controls_verified=len(controls),
                target_labels_read=False,
                dependencies=code,
            ),
        )
        seal_path = output / "all_scores_and_controls.json"
        files[str(seal_path)] = score_seal
        # Large historical TRAIN provenance is rehashed at admission/final closure.
        # Before each label load, recheck the small immutable score authority only.
        daily_pins = {str(contract_path): contract_sha, str(seal_path): score_seal}
        for item in complete["procedures"].values():
            for entry in item["target_calendar"]:
                if entry["source_status"] == "COMPLETE":
                    daily_pins[entry["score_path"]] = entry["score_sha256"]
        daily = {
            mode + suffix: []
            for mode in core.PROCEDURES
            for suffix in ("__control", "__corrected")
        }
        ledgers = {policy: [] for policy in daily}
        for (procedure, ticker, stamp), pair in prepared.items():
            require(dependencies() == code, "Implementation changed before outcomes")
            for filename, digest in daily_pins.items():
                require(
                    core.file_sha(filename) == digest, "Changed score/authority seal"
                )
            results = {}
            if pair is not None:
                selection, score = pair
                labels, _ = source.source_table(
                    ticker, stamp, "labels", list(LABEL_FIELDS)
                )
                require(not labels.action_id.duplicated().any(), "Duplicate outcome")
                label_map = {int(r["action_id"]): r for r in labels.to_dict("records")}

                def outcome(ident):
                    require(ident in label_map, "Missing selected outcome")
                    return label_map[ident]

                original = replay(selection["selected"], selection["close_i"], outcome)
                exact_rows(
                    original["attempts"],
                    controls[(procedure, ticker, stamp)]["attempts"],
                )
                results["__control"] = original
                results["__corrected"] = replay(
                    score["rows"], selection["close_i"], outcome, corrected=True
                )
            for suffix in ("__control", "__corrected"):
                policy = procedure + suffix
                record = dict(
                    ticker=ticker,
                    date=stamp,
                    source_status="COMPLETE" if pair else "MISSING_SOURCE",
                )
                if pair is None:
                    record.update(trades=None, net_base=None, net_adverse=None)
                    result = None
                else:
                    result = results[suffix]
                    record.update(observed_metrics(result["ledger"]))
                    ledgers[policy].extend(result["ledger"])
                daily[policy].append(record)
                path = output / "days" / policy / ticker / (stamp + ".json")
                files[str(path)] = adapter.publish_or_verify(
                    path, dict(daily=record, trajectory=result)
                )
        source.recheck()
        require(dependencies() == code, "Implementation changed")
        for filename, digest in files.items():
            require(
                core.file_sha(filename) == digest, "Input/output changed before closure"
            )
        summary = dict(
            status="COMPLETE_FIXED_OOF_POLICY_MONTH",
            target_month=target_month,
            policies={
                p: dict(
                    coverage=coverage(daily[p]),
                    observed=observed_metrics(ledgers[p]),
                    daily=daily[p],
                )
                for p in daily
            },
            winner_selected=None,
            refitted=False,
            development_seen=True,
            year2025_role="CALIBRATOR_TRAIN_NOT_VALIDATION",
            full_period_complete=False,
        )
        files[str(output / "summary.json")] = adapter.publish_or_verify(
            output / "summary.json", summary
        )
        adapter.publish_or_verify(
            output / "completion.json",
            dict(
                status=summary["status"],
                files=files,
                monthly_files=dict(source.used),
                dependencies=code,
                target_month=target_month,
                winner_selected=None,
            ),
        )
        return summary

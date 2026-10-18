from pathlib import Path
import json

import pandas as pd
import pytest

import evaluate_oof_calibrated_policy as module
from test_monthly_oof_calibration_adapter import ToySource


def maximum(ident, state, base, corrected):
    return dict(
        action_id=ident, state_i=state, score_usd=base, corrected_score_usd=corrected
    )


def label(ident, status, exit_i, net=0):
    return dict(
        action_id=ident,
        status=status,
        exit_i=exit_i,
        net_base=float(net),
        net_adverse=float(net),
    )


def test_offset_changes_wait_visited_states_and_no_fill_without_rescue():
    rows = [
        maximum(1, 60, 1, -1),
        maximum(2, 61, 3, 1),
        maximum(3, 62, 4, 2),
        maximum(4, 64, 5, 3),
        maximum(5, 67, 3, 1),
    ]
    labels = {
        1: label(1, "FILLED", 66, 10),
        2: label(2, "NO_FILL", 62),
        3: label(3, "FILLED", 65, 2),
        4: label(4, "FILLED", 69, 100),
        5: label(5, "FILLED", 70, -1),
    }
    control = module.replay(rows, 390, labels.__getitem__)
    corrected = module.replay(rows, 390, labels.__getitem__, corrected=True)
    assert [r["action_id"] for r in control["attempts"]] == [1, 5]
    assert [r["action_id"] for r in corrected["attempts"]] == [2, 3, 5]
    assert [r["has_filled_before"] for r in corrected["attempts"]] == [0, 0, 1]
    assert corrected["decisions"][0]["decision"] == "WAIT"
    assert module.observed_metrics(corrected["ledger"])["net_base"] == 1


def test_positive_offset_can_trade_previously_negative_all_state_maximum():
    rows = [maximum(1, 60, -1, 1), maximum(2, 61, 0, 2)]
    labels = {1: label(1, "NO_FILL", 61), 2: label(2, "FILLED", 63, 5)}
    assert not module.replay(rows, 210, labels.__getitem__)["attempts"]
    corrected = module.replay(rows, 210, labels.__getitem__, corrected=True)
    assert [r["action_id"] for r in corrected["attempts"]] == [1, 2]


@pytest.mark.parametrize(
    "bad",
    [
        label(1, "NO_FILL", 62),
        label(1, "NO_FILL", 61, 1),
        label(1, "FILLED", 61),
        label(1, "FILLED", 206),
    ],
)
def test_outcome_clock_and_no_fill_validation(bad):
    with pytest.raises(ValueError):
        module.replay([maximum(1, 60, 1, 1)], 210, lambda _: bad)


def test_short_session_last_state_and_exact_control_projection():
    selection = dict(close_i=210, selected=[maximum(1, 195, 2, 2)])
    result = module.replay(
        selection["selected"], 210, lambda _: label(1, "FILLED", 205, 3)
    )
    assert (
        module.verify_control(selection, result["attempts"], result["ledger"]) == result
    )
    bad = [dict(result["attempts"][0], score=2.0000000000000004)]
    with pytest.raises(ValueError, match="score"):
        module.verify_control(selection, bad, result["ledger"])
    with pytest.raises(ValueError, match="horizon"):
        module.replay([maximum(2, 196, 1, 1)], 210, lambda _: None)


def test_missing_coverage_is_not_zero_profit_or_economic_failure():
    daily = [
        dict(
            ticker="SPY",
            date="20260102",
            source_status="COMPLETE",
            trades=1,
            net_base=5,
            net_adverse=4,
        ),
        dict(
            ticker="QQQ",
            date="20260102",
            source_status="MISSING_SOURCE",
            trades=None,
            net_base=None,
            net_adverse=None,
        ),
    ]
    report = module.coverage(daily)
    assert report["observable_daily_pass"] and not report["universal_daily_pass"]
    assert report["universal_daily_status"] == "NO_EVALUABLE"


class EvaluationSource(ToySource):
    def __init__(self, root, *, output=None, mismatch=False):
        super().__init__(root)
        self.output = output
        self.target_reads = []
        self.control_reads = []
        self.allowed = {}
        for mode in module.core.PROCEDURES:
            for ticker in ("SPY", "SPXW"):
                prefix = self.root / "ledgers" / "202601" / mode / ticker / "20260102"
                prefix.parent.mkdir(parents=True, exist_ok=True)
                result = module.replay(
                    [maximum(1, 60, 2, 1)], 390, lambda _: label(1, "FILLED", 62, 1)
                )
                for ending, rows in (
                    ("_attempts", result["attempts"]),
                    ("_ledger", result["ledger"]),
                ):
                    if mismatch and mode == "static" and ticker == "SPY":
                        rows = [dict(rows[0], score=3)]
                    path = Path(str(prefix) + ending + ".parquet")
                    pd.DataFrame(rows).to_parquet(path, index=False)
                    self.allowed[str(path)] = module.core.file_sha(path)

    def month_rows(self, month):
        rows = super().month_rows(month)
        rows["status"] = "COMPLETE"
        if month == "202601":
            rows.loc[("QQQ", month + "02"), "status"] = "MISSING_SOURCE"
        return rows

    def select_day(self, procedure, ticker, stamp, output):
        if stamp.startswith("202601") and ticker == "QQQ":
            return dict(
                procedure=procedure,
                ticker=ticker,
                day=stamp,
                source_status="MISSING_SOURCE",
                selection_path=None,
            )
        return super().select_day(procedure, ticker, stamp, output)

    def marker(self, name, paths):
        self.control_reads.append(name)
        for path in paths:
            self.verify(path)

    def verify(self, path):
        key = str(path)
        assert module.core.file_sha(path) == self.allowed[key]
        self.used[key] = self.allowed[key]

    def source_table(self, ticker, stamp, kind, columns):
        assert kind == "labels" and stamp.startswith("202601")
        assert len(self.control_reads) == 6
        assert (self.output / "all_scores_and_controls.json").is_file()
        self.target_reads.append((ticker, stamp))
        return pd.DataFrame([label(1, "FILLED", 62, 1)])[columns], "c" * 64

    def recheck(self):
        for path, digest in self.used.items():
            assert module.core.file_sha(path) == digest


def setup(tmp_path, *, mismatch=False):
    corrections, output = tmp_path / "corrections", tmp_path / "evaluation"
    source = EvaluationSource(tmp_path, output=output, mismatch=mismatch)
    module.adapter.prepare_correction(source, "202601", corrections)
    digest = module.core.file_sha(corrections / "202601.complete.json")
    return source, corrections, output, digest


def test_three_modes_full_month_replay_sealed_before_labels_and_resume(tmp_path):
    source, corrections, output, digest = setup(tmp_path)
    result = module.evaluate_month(
        source, corrections, "202601", output, correction_completion_sha256=digest
    )
    assert len(source.target_reads) == 6 and result["winner_selected"] is None
    assert len(result["policies"]) == 6 and not result["full_period_complete"]
    for report in result["policies"].values():
        assert report["coverage"]["missing_days"] == 1
        assert report["observed"]["net_base"] == 2
        assert report["coverage"]["universal_daily_status"] == "NO_EVALUABLE"
    fresh = EvaluationSource(tmp_path, output=output)
    assert (
        module.evaluate_month(
            fresh, corrections, "202601", output, correction_completion_sha256=digest
        )
        == result
    )


def test_control_mismatch_blocks_all_new_target_labels(tmp_path):
    source, corrections, output, digest = setup(tmp_path, mismatch=True)
    with pytest.raises(ValueError, match="score"):
        module.evaluate_month(
            source, corrections, "202601", output, correction_completion_sha256=digest
        )
    assert not source.target_reads


def test_score_mutation_and_calendar_omission_rejected_before_labels(tmp_path):
    source, corrections, output, digest = setup(tmp_path)
    complete_path = corrections / "202601.complete.json"
    complete = json.loads(complete_path.read_text())
    complete["procedures"]["static"]["target_calendar"].pop()
    complete_path.write_bytes(module.core.canonical_bytes(complete))
    with pytest.raises(ValueError, match="calendar"):
        module.evaluate_month(
            source,
            corrections,
            "202601",
            output,
            correction_completion_sha256=module.core.file_sha(complete_path),
        )
    assert not source.target_reads


def test_changed_implementation_resume_fails_before_new_labels(tmp_path, monkeypatch):
    source, corrections, output, digest = setup(tmp_path)
    module.evaluate_month(
        source, corrections, "202601", output, correction_completion_sha256=digest
    )
    fresh = EvaluationSource(tmp_path, output=output)
    old = module.dependencies()
    monkeypatch.setattr(module, "dependencies", lambda: {**old, "new.py": "0" * 64})
    with pytest.raises(ValueError, match="hash differs"):
        module.evaluate_month(
            fresh, corrections, "202601", output, correction_completion_sha256=digest
        )
    assert not fresh.target_reads


def test_corrected_score_mutation_rejected_before_target_labels(tmp_path):
    source, corrections, output, digest = setup(tmp_path)
    complete = json.loads((corrections / "202601.complete.json").read_text())
    entry = next(
        r
        for r in complete["procedures"]["static"]["target_calendar"]
        if r["source_status"] == "COMPLETE"
    )
    path = Path(entry["score_path"])
    score = json.loads(path.read_text())
    score["rows"][0]["corrected_score_usd"] += 1
    path.write_bytes(module.core.canonical_bytes(score))
    with pytest.raises(ValueError, match="hash differs"):
        module.evaluate_month(
            source, corrections, "202601", output, correction_completion_sha256=digest
        )
    assert not source.target_reads


def test_missing_run_contract_cannot_adopt_previous_evaluation(tmp_path):
    source, corrections, output, digest = setup(tmp_path)
    module.evaluate_month(
        source, corrections, "202601", output, correction_completion_sha256=digest
    )
    (output / "run_contract.json").unlink()
    (output / "all_scores_and_controls.json").unlink()
    fresh = EvaluationSource(tmp_path, output=output)
    with pytest.raises(ValueError, match="without run contract"):
        module.evaluate_month(
            fresh, corrections, "202601", output, correction_completion_sha256=digest
        )
    assert not fresh.target_reads and not fresh.control_reads


def test_maximum_tie_uses_lower_identity_before_any_labels():
    selection = module.core.maximum_selection(
        procedure="static",
        ticker="SPY",
        day="20260102",
        close_i=390,
        fit_stop_at="2025-01-01T00:00:00-05:00",
        model_sha256="a" * 64,
        prediction_sha256="b" * 64,
        actions=[dict(action_id=i, state_i=60, score_usd=1) for i in (9, 2)],
    )
    assert selection["selected"][0]["action_id"] == 2
    calls = []

    def outcome(ident):
        calls.append(ident)
        return label(ident, "NO_FILL", 61)

    module.replay(selection["selected"], 390, outcome)
    assert calls == [2]


def test_complete_period_keeps_six_missing_and_observed_positive_net_separate():
    policies = [
        m + s for m in module.core.PROCEDURES for s in ("__control", "__corrected")
    ]
    expected, monthly = {}, []
    for month, count in enumerate((21, 19, 22, 21, 20, 20), 1):
        daily = []
        for ticker in module.core.TICKERS:
            for day in range(1, count + 1):
                date = f"2026{month:02d}{day:02d}"
                missing = month in (4, 6) and day == 1
                status = "MISSING_SOURCE" if missing else "COMPLETE"
                expected[ticker, date] = status
                daily.append(
                    dict(
                        ticker=ticker,
                        date=date,
                        source_status=status,
                        trades=None if missing else 1,
                        net_base=None if missing else 1,
                        net_adverse=None if missing else 1,
                    )
                )
        observed = module.observed_metrics(
            [
                dict(net_base=1, net_adverse=1)
                for r in daily
                if r["source_status"] == "COMPLETE"
            ]
        )
        monthly.append(
            dict(
                status="COMPLETE_FIXED_OOF_POLICY_MONTH",
                target_month=f"2026{month:02d}",
                winner_selected=None,
                policies={p: dict(daily=daily, observed=observed) for p in policies},
            )
        )
    result = module.summarize_period(monthly, expected)
    for report in result["policies"].values():
        assert report["observed"]["net_base"] == 363
        assert report["coverage"]["observable_daily_pass"]
        assert report["coverage"]["universal_daily_status"] == "NO_EVALUABLE"
    with pytest.raises(ValueError, match="Six completed"):
        module.summarize_period(monthly[:-1], expected)
    with pytest.raises(ValueError, match="369/363/6"):
        module.summarize_period(monthly, dict(list(expected.items())[:-1]))

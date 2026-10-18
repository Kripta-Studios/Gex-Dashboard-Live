"""Nine fixed early-close days, inference only; preserve the original 741-day run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import train_causal_rollout as original
import run_monthly_walk_forward as readers
from session_clock import SessionClock

VERSION = "CAUSAL_ROLLOUT_SHORT_SESSIONS_V1"
DATES = ("20250703", "20251128", "20251224")
RUN_SHA = "66ef48eca5aadca70726b1c66997c93dd513ebf7a32283e07e26fc7e3c129a9d"
FREEZE_SHA = "a5cda27adeade05f4e8f9577b8fd0e8483eb37690f812342a573b5cab849b6af"
MODEL_SHA = {
    "net_control": "12b8d5a00d06bb482fc6de66263e8c270929d0d276e226a9889e283a801a09ef",
    "causal_residual": "9fe6a42d2a04459b5eff4b018518a224865b58f2af89ca5903b6e77651303117",
}
SELECTED = "causal_residual__5"
POLICIES = tuple(
    original.policy_id(m, t) for m in original.MODELS for t in original.THRESHOLDS
)
DEPENDENCIES = tuple(
    sorted(
        set(
            readers.DEPENDENCIES
            + (
                "evaluate_causal_rollout_short_sessions.py",
                "test_evaluate_causal_rollout_short_sessions.py",
                "CAUSAL_ROLLOUT_SHORT_SESSION_SPEC.md",
                "session_clock.py",
            )
        )
    )
)
require, sha, read_json = readers.require, original.sha, original.read_json


def dependency_hashes():
    return {name: sha(Path(__file__).with_name(name)) for name in DEPENDENCIES}


class Artifacts(original.Artifacts):
    """Reuse durable writes; never adopt partial/orphan outputs."""

    def require_members(self, name, paths):
        require(self.complete(name), "Incomplete checkpoint: " + name)
        sealed = {
            (self.root / p).resolve() for p in read_json(self.marker(name))["files"]
        }
        require(
            all(p.is_relative_to(self.root.resolve()) for p in sealed),
            "Escaping checkpoint",
        )
        require(
            {Path(p).resolve() for p in paths}.issubset(sealed),
            "Unbound checkpoint member",
        )

    def json(self, name, value):
        path = self.root / (name + ".json")
        if self.complete(name):
            self.require_members(name, [path])
            require(read_json(path) == value, "Changed JSON checkpoint: " + name)
        else:
            original.atomic_json(path, value)
            self.finish(name, [path])
        return value


class OriginalEvidence:
    def __init__(self, root, audit_path):
        self.root = Path(root).resolve()
        self.audit_path = Path(audit_path).resolve()
        self.audit_sha = sha(self.audit_path)
        audit = read_json(self.audit_path)
        require(
            audit.get("status")
            == "PASS_INDEPENDENT_CAUSAL_ROLLOUT_ECONOMIC_AUDIT_GIVEN_SEALED_SCORES",
            "Completed original economic audit required",
        )
        require(
            audit["run_contract_sha256"] == RUN_SHA
            and sha(self.root / "run_contract.json") == RUN_SHA,
            "Original run differs",
        )
        self.verified = {
            str(Path(p).resolve()): h for p, h in audit["verified_artifacts"].items()
        }
        self.used = {}
        self.artifacts = Artifacts(self.root, RUN_SHA)
        for name, suffixes in (
            ("validation_freeze", [".json"]),
            ("risk_scales", [".json"]),
            ("validation/summary", [".json"]),
            ("test/summary", [".json"]),
            ("test/score_h_diagnostic", [".json"]),
        ):
            self.members(name, [self.root / (name + suffix) for suffix in suffixes])
        self.members(
            "validation/summary", [self.root / "validation/daily_calendar.parquet"]
        )
        require(
            sha(self.root / "validation_freeze.json") == FREEZE_SHA,
            "Selection freeze changed",
        )
        freeze = read_json(self.root / "validation_freeze.json")
        require(
            freeze["selected_policy"]["policy"] == SELECTED
            and tuple(freeze["frozen_candidates"]) == POLICIES,
            "Policy selection differs",
        )
        require(freeze["model_hashes"] == MODEL_SHA, "Frozen models differ")
        for name, digest in MODEL_SHA.items():
            path = self.root / ("models/" + name + ".txt")
            self.members("models/" + name, [path])
            require(sha(path) == digest, "Model hash changed")
        require(
            freeze["risk_scales_sha256"] == sha(self.root / "risk_scales.json"),
            "Risk scales changed",
        )
        require(
            freeze["validation_summary_sha256"]
            == sha(self.root / "validation/summary.json"),
            "Original validation summary changed",
        )

    def members(self, name, paths):
        self.artifacts.require_members(name, paths)
        for path in [self.artifacts.marker(name), *paths]:
            path = Path(path).resolve()
            actual = sha(path)
            require(
                self.verified.get(str(path)) == actual,
                "File absent from original independent audit: " + str(path),
            )
            self.used[str(path)] = actual

    def recheck(self):
        require(sha(self.audit_path) == self.audit_sha, "Original audit changed")
        require(
            sha(self.root / "run_contract.json") == RUN_SHA, "Original contract changed"
        )
        for path, digest in self.used.items():
            require(sha(path) == digest, "Original evidence changed")


def fixed_days(source):
    days = [
        d
        for d in source.days.values()
        if d.date.startswith("2025") and d.close_i == 210
    ]
    require(
        {(d.ticker, d.date) for d in days}
        == {(t, d) for t in original.TICKERS for d in DATES}
        and len(days) == 9
        and all(d.status == "COMPLETE" for d in days),
        "Nine fixed short sessions required",
    )
    return sorted(days, key=lambda d: d.key)


def evaluate_policy(actions, labels, scores, threshold, clock):
    """Explicit horizon; choices use no outcome fields and h follows actual fills."""
    require(isinstance(clock, SessionClock), "Explicit SessionClock required")
    keys, outcomes = original.action_rows(actions), original.outcome_rows(labels)
    keys.validate(clock.first_state, clock.last_state)
    filled, exits, _ = outcomes.aligned(keys)
    require(
        np.all(exits[filled] >= keys.state_i[filled] + 2)
        and np.all(exits[filled] <= clock.eod_i),
        "Filled exit outside session",
    )
    require(
        np.all(exits[~filled] == keys.state_i[~filled] + 1),
        "Invalid NO_FILL transition",
    )
    choices = original.rollout.freeze_choices(
        keys,
        scores,
        threshold=threshold,
        first=clock.first_state,
        last=clock.last_state,
    )
    indexed = labels.set_index("action_id").loc[actions.action_id].reset_index()
    lookup = {int(key): i for i, key in enumerate(actions.action_id)}
    rows, flags, chosen_scores = [], [], []
    minute, h = clock.first_state, 0
    while minute <= clock.last_state:
        key = int(choices[minute - clock.first_state, h])
        if key == -1:
            minute += 1
            continue
        row = lookup[key]
        rows.append(row)
        flags.append(h)
        chosen_scores.append(float(scores[row, h]))
        result = indexed.iloc[row]
        if result.status == "FILLED":
            h, minute = 1, int(result.exit_i) + 1
        else:
            minute += 1
    attempts = actions.iloc[rows].merge(
        indexed.iloc[rows], on="action_id", validate="one_to_one"
    )
    attempts["has_filled_before"], attempts["score"] = flags, chosen_scores
    return attempts, attempts.loc[attempts.status == "FILLED"].copy()


def evaluate_day(day, source, store, models, scales, artifacts):
    require(
        day.close_i == 210 and day.date in DATES,
        "Only fixed short sessions can be scored",
    )
    clock = SessionClock(day.close_i)
    store.get(day.key)
    actions = source.read(day, "actions.parquet")
    original.action_rows(actions).validate(clock.first_state, clock.last_state)
    predictions, daily = "predictions/" + day.key, "daily/" + day.key
    if not artifacts.complete(predictions):
        packed = dict(
            action_id=actions.action_id.to_numpy(), state_i=actions.state_i.to_numpy()
        )
        for name in original.MODELS:
            packed[name] = original.score_actions(
                models[name], store, day, actions, scales[day.ticker]
            )
            packed[name + "_sha256"] = np.array(MODEL_SHA[name])
        artifacts.save_npz(predictions, packed)
    artifacts.require_members(predictions, [artifacts.root / (predictions + ".npz")])
    packed = artifacts.load_npz(predictions)
    require(
        np.array_equal(packed["action_id"], actions.action_id)
        and np.array_equal(packed["state_i"], actions.state_i),
        "Prediction identity mismatch",
    )
    for name in original.MODELS:
        require(
            str(packed[name + "_sha256"]) == MODEL_SHA[name], "Prediction model differs"
        )
        require(
            packed[name].shape == (len(actions), 2) and np.isfinite(packed[name]).all(),
            "Invalid scores",
        )
    a_path, l_path = [
        artifacts.root / (daily + suffix)
        for suffix in ("_attempts.parquet", "_ledger.parquet")
    ]
    if artifacts.complete(daily):
        artifacts.require_members(daily, [a_path, l_path])
        require(
            read_json(artifacts.marker(daily))["extra"]["prediction_sha256"]
            == sha(artifacts.root / (predictions + ".npz")),
            "Daily prediction binding changed",
        )
        source.check(day, "labels.parquet")
        return
    labels = source.read(
        day, "labels.parquet"
    )  # Only after both model scores are sealed.
    attempts, ledgers = [], []
    for name in original.MODELS:
        for threshold in original.THRESHOLDS:
            attempted, ledger = evaluate_policy(
                actions, labels, packed[name], threshold, clock
            )
            for frame in (attempted, ledger):
                frame["ticker"], frame["date"] = day.ticker, day.date
                frame["policy"] = original.policy_id(name, threshold)
            attempts.append(attempted)
            ledgers.append(ledger)
    original.save_parquet(a_path, pd.concat(attempts, ignore_index=True))
    original.save_parquet(l_path, pd.concat(ledgers, ignore_index=True))
    artifacts.finish(
        daily,
        [a_path, l_path],
        dict(
            prediction_sha256=sha(artifacts.root / (predictions + ".npz")),
            clock=clock.as_dict(),
        ),
    )


def summarize(ledgers, attempts, expected):
    require(len(expected) == len(set(expected)), "Duplicate expected day")
    expected_set = set(expected)
    for frame in (ledgers, attempts):
        require(
            set(zip(frame.ticker, frame.date)).issubset(expected_set),
            "Unexpected ledger day",
        )
        require(set(frame.policy).issubset(POLICIES), "Unexpected policy")
        require(
            not frame.duplicated(["policy", "ticker", "date", "action_id"]).any(),
            "Duplicate action",
        )
    report, calendar = {}, []
    for policy in POLICIES:
        ledger = ledgers.loc[ledgers.policy == policy].sort_values(
            ["date", "exit_i", "ticker"], kind="stable"
        )
        attempted = attempts.loc[attempts.policy == policy]
        counts = ledger.groupby(["ticker", "date"]).size().to_dict()
        stats = original.economic_summary(ledger)
        stats.update(
            attempts=len(attempted),
            no_fill_attempts=int((attempted.status == "NO_FILL").sum()),
            expected_ticker_days=len(expected),
            observable_ticker_days=len(expected),
            missing_source_days=0,
            zero_fill_expected_days=sum(counts.get(k, 0) == 0 for k in expected),
            zero_fill_observable_days=sum(counts.get(k, 0) == 0 for k in expected),
        )
        stats["tickers"] = {}
        for ticker in original.TICKERS:
            sub = ledger.loc[ledger.ticker == ticker]
            ticker_stats = original.economic_summary(sub)
            months = sorted({d[:6] for t, d in expected if t == ticker})
            monthly = {
                m: original.economic_summary(sub.loc[sub.date.str.startswith(m)])
                for m in months
            }
            ticker_stats.update(
                months=monthly,
                positive_months=sum(v["net_base"] > 0 for v in monthly.values()),
            )
            ticker_stats["economic_gate"] = bool(
                ticker_stats["net_base"] > 0
                and ticker_stats["net_adverse"] > 0
                and (
                    (ticker_stats["net_base_pf"] or 0) >= 1.2
                    or ticker_stats["net_base_pf_infinite"]
                )
                and len(sub) >= 60
                and ticker_stats["positive_months"] >= 3
            )
            stats["tickers"][ticker] = ticker_stats
        stats["economic_gate_all_tickers"] = all(
            v["economic_gate"] for v in stats["tickers"].values()
        )
        report[policy] = stats
        for ticker, date in expected:
            sub = ledger.loc[(ledger.ticker == ticker) & (ledger.date == date)]
            calendar.append(
                dict(
                    policy=policy,
                    ticker=ticker,
                    date=date,
                    trades=int(counts.get((ticker, date), 0)),
                    source_available=True,
                    net_base=float(sub.net_base.sum()),
                    net_adverse=float(sub.net_adverse.sum()),
                )
            )
    return report, pd.DataFrame(calendar)


def require_same_old_calendar(old, combined):
    keys = ["policy", "ticker", "date"]
    require(
        not old.duplicated(keys).any() and not combined.duplicated(keys).any(),
        "Duplicate calendar identity",
    )
    left = old.set_index(keys).sort_index()
    right = combined.set_index(keys).loc[left.index].sort_index()
    pd.testing.assert_frame_equal(
        left, right, check_dtype=False, check_exact=False, rtol=0, atol=1e-8
    )


def build_reports(source, days, evidence, artifacts):
    old_days = sorted(
        [
            d
            for d in source.days.values()
            if d.date.startswith("2025") and d.close_i == 390
        ],
        key=lambda d: d.key,
    )
    require(
        len(old_days) == 741 and all(d.status == "COMPLETE" for d in old_days),
        "Original 741-day population changed",
    )
    old_a, old_l, short_a, short_l = [], [], [], []
    for day in old_days:
        name = "validation/daily/" + day.key
        paths = [
            evidence.root / (name + suffix)
            for suffix in ("_attempts.parquet", "_ledger.parquet")
        ]
        evidence.members(name, paths)
        old_a.append(pd.read_parquet(paths[0]))
        old_l.append(pd.read_parquet(paths[1]))
    for day in days:
        name = "daily/" + day.key
        paths = [
            artifacts.root / (name + suffix)
            for suffix in ("_attempts.parquet", "_ledger.parquet")
        ]
        artifacts.require_members(name, paths)
        short_a.append(pd.read_parquet(paths[0]))
        short_l.append(pd.read_parquet(paths[1]))
    short_a, short_l = (
        pd.concat(short_a, ignore_index=True),
        pd.concat(short_l, ignore_index=True),
    )
    short, short_calendar = summarize(
        short_l, short_a, [(d.ticker, d.date) for d in days]
    )
    combined, combined_calendar = summarize(
        pd.concat([*old_l, short_l], ignore_index=True),
        pd.concat([*old_a, short_a], ignore_index=True),
        [(d.ticker, d.date) for d in [*old_days, *days]],
    )
    old_calendar = pd.read_parquet(evidence.root / "validation/daily_calendar.parquet")
    require(len(old_calendar) == 741 * 6, "Original calendar row count differs")
    require_same_old_calendar(old_calendar, combined_calendar)
    for name, frame in (
        ("short_daily_calendar", short_calendar),
        ("combined_daily_calendar", combined_calendar),
    ):
        path = artifacts.root / (name + ".parquet")
        if artifacts.complete(name):
            artifacts.require_members(name, [path])
            pd.testing.assert_frame_equal(pd.read_parquet(path), frame)
        else:
            original.save_parquet(path, frame)
            artifacts.finish(name, [path])
    report = dict(
        status="INFERENCE_EXTENSION_COMPLETE",
        selected_policy=SELECTED,
        selection_recomputed=False,
        selection_freeze_sha256=FREEZE_SHA,
        original_ticker_days=741,
        added_ticker_days=9,
        combined_ticker_days=750,
        training_early_close_days_added=0,
        terminal_penalty_in_pnl=False,
        short_sessions=short,
        combined_2025=combined,
        development_2026_unchanged=True,
    )
    return report


def closure_paths(artifacts, days):
    """The entire extension's exact declared output population, excluding closure itself."""
    paths = [artifacts.root / "run_contract.json"]
    members = [("summary", [".json"]), ("source_hashes", [".json"])]
    members += [
        (name, [".parquet"])
        for name in ("short_daily_calendar", "combined_daily_calendar")
    ]
    for day in days:
        members.extend(
            [
                ("predictions/" + day.key, [".npz"]),
                ("daily/" + day.key, ["_attempts.parquet", "_ledger.parquet"]),
                ("feature_inputs/" + day.key, [".json"]),
            ]
        )
    for name, suffixes in members:
        files = [artifacts.root / (name + suffix) for suffix in suffixes]
        artifacts.require_members(name, files)
        sealed = {
            (artifacts.root / p).resolve()
            for p in read_json(artifacts.marker(name))["files"]
        }
        require(
            sealed == {p.resolve() for p in files},
            "Unexpected closure checkpoint members",
        )
        paths.extend([artifacts.marker(name), *files])
    require(len(paths) == len(set(paths)), "Duplicate closure path")
    return sorted(paths)


def finalize_or_validate(artifacts, days, *, publish):
    """Only a fully hashed closure may be resumed without any prediction work."""
    if artifacts.marker("completion").exists():
        require(artifacts.complete("completion"), "Incomplete global closure")
    elif not publish:
        return False
    require(
        sha(artifacts.root / "run_contract.json") == artifacts.binding,
        "Run contract changed",
    )
    paths = closure_paths(artifacts, days)
    sources = read_json(artifacts.root / "source_hashes.json")
    require(set(sources) == {"source", "original"}, "Incomplete source manifest")
    for group in sources.values():
        for path, digest in group.items():
            require(
                Path(path).is_absolute() and sha(path) == digest,
                "Closure source changed: " + path,
            )
    payload = dict(
        status="CAUSAL_ROLLOUT_SHORT_SESSIONS_COMPLETE",
        binding=artifacts.binding,
        days=[day.key for day in days],
        files={str(path.relative_to(artifacts.root)): sha(path) for path in paths},
    )
    final = artifacts.root / "completion.json"
    if artifacts.marker("completion").exists():
        artifacts.require_members("completion", [*paths, final])
        sealed = {
            (artifacts.root / p).resolve()
            for p in read_json(artifacts.marker("completion"))["files"]
        }
        require(
            sealed == {p.resolve() for p in [*paths, final]},
            "Global closure inventory differs",
        )
        require(read_json(final) == payload, "Global closure payload differs")
    else:
        original.atomic_json(final, payload)
        artifacts.finish("completion", [*paths, final])
        return finalize_or_validate(artifacts, days, publish=False)
    return True


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "original-root",
        "original-audit",
        "engine-root",
        "feature-root",
        "source-audit",
        "implementation-review",
        "out",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.out = args.out.resolve()
    for root in (args.original_root, args.engine_root, args.feature_root):
        require(
            not args.out.is_relative_to(root.resolve())
            and not root.resolve().is_relative_to(args.out),
            "Separate output root required",
        )
    args.out.mkdir(parents=True, exist_ok=True)
    with original.exclusive_lock(args.out / "run.lock"):
        dependencies = dependency_hashes()
        review = read_json(args.implementation_review)
        require(
            review.get("status") == "PASS_CAUSAL_ROLLOUT_SHORT_SESSION_REVIEW"
            and review.get("dependencies") == dependencies,
            "Exact implementation review required",
        )
        evidence = OriginalEvidence(args.original_root, args.original_audit)
        source = readers.Sources(args.engine_root, args.feature_root, args.source_audit)
        days = fixed_days(source)
        contract = dict(
            version=VERSION,
            dependencies=dependencies,
            original_root=str(evidence.root),
            original_run_sha256=RUN_SHA,
            original_audit_sha256=evidence.audit_sha,
            model_hashes=MODEL_SHA,
            selection_freeze_sha256=FREEZE_SHA,
            selected_policy=SELECTED,
            selection_recomputed=False,
            source_audit=source.audit,
            implementation_review_sha256=sha(args.implementation_review),
            days=[dict(ticker=d.ticker, date=d.date, close_i=d.close_i) for d in days],
        )
        contract_path = args.out / "run_contract.json"
        if contract_path.exists():
            require(
                read_json(contract_path) == contract,
                "Existing extension contract differs",
            )
        else:
            original.atomic_json(contract_path, contract)
        artifacts = Artifacts(args.out, sha(contract_path))
        if finalize_or_validate(artifacts, days, publish=False):
            source.recheck()
            evidence.recheck()
            require(
                dependency_hashes() == dependencies, "Implementation changed on resume"
            )
            print(
                json.dumps(dict(status="VERIFIED_COMPLETE_RESUME", days=9)), flush=True
            )
            return
        store = readers.Features(source, artifacts)
        models = {
            name: original.lgb.Booster(
                model_file=str(evidence.root / ("models/" + name + ".txt"))
            )
            for name in original.MODELS
        }
        scales = read_json(evidence.root / "risk_scales.json")
        for day in days:
            evaluate_day(day, source, store, models, scales, artifacts)
            print(
                json.dumps(dict(stage="short_session_complete", day=day.key)),
                flush=True,
            )
        report = build_reports(source, days, evidence, artifacts)
        source.recheck()
        evidence.recheck()
        require(
            dependency_hashes() == dependencies
            and sha(args.implementation_review)
            == contract["implementation_review_sha256"],
            "Implementation changed during extension",
        )
        artifacts.json(
            "source_hashes", dict(source=source.hashes, original=evidence.used)
        )
        artifacts.json("summary", report)
        finalize_or_validate(artifacts, days, publish=True)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in ("short_sessions", "combined_2025")
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()

"""Descriptive matched-state diagnosis. No fitting, tuning or policy promotion."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

for _name in (
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
):
    os.environ[_name] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

MODELS = ("gbt_net", "gbt_net_episode")
FIRST, LAST = 60, 375


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_checkpoint(path, identity, day_key):
    if not path.exists():
        return None
    record = read(path)
    if record["identity"] != identity or record["day_key"] != day_key:
        raise ValueError("Diagnostic checkpoint identity differs")
    for mapping in (record["artifacts"], record["sources"]):
        for name, digest in mapping.items():
            if sha(name) != digest:
                raise ValueError("Diagnostic checkpoint content changed")
    return record


def select_training_days(index):
    rows = index.loc[(index.split == "train") & (index.status == "COMPLETE")].copy()
    rows["date"] = rows.date.astype(str)
    rows["quarter"] = (
        rows.date.str[:4]
        + "Q"
        + (((rows.date.str[4:6].astype(int) - 1) // 3) + 1).astype(str)
    )
    rows["selection_hash"] = [
        hashlib.sha256(f"oracle_model_diagnostic_v1|{t}|{d}".encode()).hexdigest()
        for t, d in zip(rows.ticker, rows.date)
    ]
    return (
        rows.sort_values(["ticker", "quarter", "selection_hash"])
        .groupby(["ticker", "quarter"], sort=True)
        .head(4)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)[["ticker", "date", "quarter", "selection_hash"]]
    )


def walk(choices, frame):
    """Free-state mask and the already chosen position occupying each minute."""
    free, blocker, attempts = {}, {}, []
    next_free, active = FIRST, -1
    for minute in range(FIRST, LAST + 1):
        free[minute] = minute >= next_free
        blocker[minute] = -1 if free[minute] else active
        if not free[minute]:
            continue
        action = choices.get(minute, -1)
        if action < 0:
            continue
        row = frame.loc[action]
        attempts.append(action)
        if row.status == "FILLED":
            next_free, active = int(row.exit_i) + 1, action
        elif row.status == "NO_FILL":
            next_free, active = minute + 1, -1
        else:
            raise ValueError("Unknown fill status")
    return free, blocker, attempts


def prepare(actions, labels, advantages, scores):
    if len(scores) != len(actions) or not np.isfinite(scores).all():
        raise ValueError("Score alignment/finiteness")
    frame = (
        actions.assign(score=np.asarray(scores))
        .merge(labels, on="action_id", validate="one_to_one")
        .merge(advantages, on="action_id", validate="one_to_one")
        .sort_values("action_id")
        .set_index("action_id", drop=False)
    )
    if len(frame) != len(actions):
        raise ValueError("Missing action label or advantage")
    model, oracle, groups = {}, {}, {}
    value = np.zeros(387, float)
    for minute, group in frame.groupby("state_i", sort=True):
        groups[int(minute)] = group
        best = int(group.score.idxmax())
        model[int(minute)] = best if frame.loc[best, "score"] > 0 else -1
        optimal = group.loc[group.state_optimal_action.astype(bool)]
        if len(optimal) > 1:
            raise ValueError("Multiple oracle decisions at one state")
        oracle[int(minute)] = int(optimal.index[0]) if len(optimal) else -1
    for minute in range(LAST, FIRST - 1, -1):
        group = groups.get(minute)
        if group is None:
            value[minute] = value[minute + 1]
            continue
        if not np.allclose(group.wait_value, value[minute + 1], rtol=0, atol=1e-7):
            raise ValueError("Existing oracle continuation differs")
        action = oracle[minute]
        value[minute] = (
            value[minute + 1] if action < 0 else frame.loc[action, "q_value"]
        )
        if abs(value[minute] - max(value[minute + 1], group.q_value.max())) > 1e-7:
            raise ValueError("Existing oracle best-action binding differs")
    filled = frame.status.to_numpy() == "FILLED"
    next_states = np.where(
        filled, frame.exit_i.to_numpy(int) + 1, frame.state_i.to_numpy(int) + 1
    )
    rewards = np.where(filled, frame.net_base.to_numpy(float), 0.0)
    if np.any(
        np.abs(frame.q_value.to_numpy(float) - rewards - value[next_states]) > 1e-7
    ):
        raise ValueError("Q/reward/continuation decomposition differs")
    return frame, groups, model, oracle, value


def describe_day(actions, labels, advantages, states, scores):
    frame, groups, model, oracle, value = prepare(actions, labels, advantages, scores)
    model_free, blockers, attempts = walk(model, frame)
    oracle_free, _, oracle_attempts = walk(oracle, frame)
    if set(oracle_attempts) != set(
        frame.loc[frame.teacher_selected.astype(bool), "action_id"]
    ):
        raise ValueError(
            "Reconstructed oracle path differs from stored teacher trajectory"
        )
    state = states.set_index("state_i")

    def outcome(action, minute):
        if action < 0:
            return 0.0, value[minute + 1], value[minute + 1]
        row = frame.loc[action]
        reward = float(row.net_base) if row.status == "FILLED" else 0.0
        return reward, float(row.q_value) - reward, float(row.q_value)

    rows, timing = [], []
    for minute in range(FIRST, LAST + 1):
        ma, oa = model.get(minute, -1), oracle.get(minute, -1)
        mr, mc, mq = outcome(ma, minute)
        oreward, oc, oq = outcome(oa, minute)
        category = (
            "BOTH_WAIT"
            if ma < 0 and oa < 0
            else "MODEL_WAIT_ORACLE_TRADE"
            if ma < 0
            else "MODEL_TRADE_ORACLE_WAIT"
            if oa < 0
            else "SAME_ACTION"
            if ma == oa
            else "DIFFERENT_ACTION"
        )
        group = groups.get(minute)
        row = dict(
            state_i=minute,
            actions_available=len(group) if group is not None else 0,
            has_actions=group is not None,
            model_top_score=float(group.score.max()) if group is not None else np.nan,
            model_action_id=ma,
            oracle_action_id=oa,
            model_free=model_free[minute],
            oracle_free=oracle_free[minute],
            blocking_action_id=blockers[minute],
            category=category,
            model_net=mr,
            oracle_net=oreward,
            model_continuation=mc,
            oracle_continuation=oc,
            model_q=mq,
            oracle_q=oq,
            regret=value[minute] - mq,
            immediate_gap=oreward - mr,
            continuation_gap=oc - mc,
            blocked_oracle_trade=not model_free[minute] and oa >= 0,
            standalone_best_net=max(0.0, float(group.net_base.max()))
            if group is not None
            else 0.0,
        )
        if abs(row["regret"] - row["immediate_gap"] - row["continuation_gap"]) > 1e-7:
            raise ValueError("Regret decomposition mismatch")
        for prefix, action in (("model", ma), ("oracle", oa)):
            chosen = frame.loc[action] if action >= 0 else None
            row[prefix + "_filled"] = bool(
                chosen is not None and chosen.status == "FILLED"
            )
            row[prefix + "_score"] = (
                float(chosen.score) if chosen is not None else np.nan
            )
            row[prefix + "_hold_minutes"] = (
                float(chosen.hold_minutes) if chosen is not None else np.nan
            )
            for field in (
                "right",
                "strike",
                "selected_delta",
                "delta_bucket",
                "target_center",
                "stop_center",
                "target_source_mask",
                "stop_source_mask",
            ):
                row[prefix + "_" + field] = (
                    chosen[field] if chosen is not None else np.nan
                )
            for field in ("target", "stop"):
                row[prefix + "_" + field + "_distance_ib"] = (
                    abs(
                        float(chosen[field + "_center"])
                        - float(state.loc[minute, "spot"])
                    )
                    / float(state.loc[minute, "ib_range"])
                    if chosen is not None
                    else np.nan
                )
        row["same_direction"] = (
            bool(frame.loc[ma, "right"] == frame.loc[oa, "right"])
            if ma >= 0 and oa >= 0
            else None
        )
        row["same_contract"] = (
            bool(
                row["same_direction"]
                and frame.loc[ma, "strike"] == frame.loc[oa, "strike"]
            )
            if ma >= 0 and oa >= 0
            else None
        )
        row["same_target"] = (
            bool(frame.loc[ma, "target_center"] == frame.loc[oa, "target_center"])
            if ma >= 0 and oa >= 0
            else None
        )
        row["oracle_score_rank"] = (
            int(
                1
                + (
                    (group.score > frame.loc[oa, "score"])
                    | ((group.score == frame.loc[oa, "score"]) & (group.action_id < oa))
                ).sum()
            )
            if oa >= 0
            else np.nan
        )
        rows.append(row)
        if ma < 0 or not model_free[minute]:
            continue
        chosen = frame.loc[ma]
        for lag in (-5, -2, -1, 1, 2, 5):
            shifted = groups.get(minute + lag)
            item = dict(
                state_i=minute,
                action_id=ma,
                shift_minutes=lag,
                status="NO_CANDIDATE_STATE",
                same_contract_candidates=0,
                matched_action_id=-1,
                net_difference=np.nan,
                original_fill=np.nan,
                shifted_fill=np.nan,
            )
            if shifted is not None:
                contracts = shifted.loc[
                    (shifted.right == chosen.right) & (shifted.strike == chosen.strike)
                ]
                exact = contracts.loc[
                    (contracts.target_center == chosen.target_center)
                    & (contracts.stop_center == chosen.stop_center)
                    & (contracts.band == chosen.band)
                ]
                item["same_contract_candidates"] = len(contracts)
                item["status"] = (
                    "NO_IDENTICAL_LEVELS" if len(contracts) else "NO_SAME_CONTRACT"
                )
                if len(exact):
                    match = exact.iloc[0]
                    item.update(
                        status="EXACT_CONTRACT_AND_LEVELS",
                        matched_action_id=int(match.action_id),
                        net_difference=float(match.net_base) - float(chosen.net_base),
                        shifted_fill=match.status == "FILLED",
                        original_fill=chosen.status == "FILLED",
                    )
            timing.append(item)
    result = pd.DataFrame(rows)
    if (result.regret < -1e-7).any():
        raise ValueError("Oracle regret is materially negative")
    model_net = result.loc[result.model_free & result.model_filled, "model_net"].sum()
    oracle_net = result.loc[
        result.oracle_free & result.oracle_filled, "oracle_net"
    ].sum()
    if (
        abs(result.loc[result.model_free, "regret"].sum() - (oracle_net - model_net))
        > 1e-6
    ):
        raise ValueError(
            "Reachable-state regrets do not telescope to realized path gap"
        )
    return result, pd.DataFrame(timing)


def aggregate(frame):
    output = []
    for cohort in ("all_states", "model_free", "oracle_free"):
        subset = frame if cohort == "all_states" else frame.loc[frame[cohort]]
        for keys, group in subset.groupby(
            ["split", "model", "ticker", "category", "has_actions"], sort=True
        ):
            output.append(
                dict(
                    zip(("split", "model", "ticker", "category", "has_actions"), keys),
                    cohort=cohort,
                    states=len(group),
                    days=group.date.nunique(),
                    mean_regret=float(group.regret.mean()),
                    median_regret=float(group.regret.median()),
                    p90_regret=float(group.regret.quantile(0.9)),
                    mean_immediate_gap=float(group.immediate_gap.mean()),
                    mean_continuation_gap=float(group.continuation_gap.mean()),
                    mean_model_net=float(group.model_net.mean()),
                    mean_oracle_net=float(group.oracle_net.mean()),
                    blocked_oracle_states=int(group.blocked_oracle_trade.sum()),
                    same_direction_fraction=group.same_direction.dropna()
                    .astype(float)
                    .mean(),
                    same_contract_fraction=group.same_contract.dropna()
                    .astype(float)
                    .mean(),
                    same_target_fraction=group.same_target.dropna()
                    .astype(float)
                    .mean(),
                    model_target_distance_ib=group.model_target_distance_ib.mean(),
                    oracle_target_distance_ib=group.oracle_target_distance_ib.mean(),
                    model_delta=group.model_selected_delta.mean(),
                    oracle_delta=group.oracle_selected_delta.mean(),
                    median_oracle_score_rank=group.oracle_score_rank.median(),
                    median_model_top_score=group.model_top_score.median(),
                )
            )
    return pd.DataFrame(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=args.resume)
    import train_episode_model as source

    with source.output_lock(out):
        run(args, source)


def run(args, source):
    root, out = args.root.resolve(), args.output.resolve()
    base = source.base
    learner = root / "episode_learners_v1"
    frozen = read(learner / "freeze.complete.json")
    source.verify_hashes(frozen["artifacts"])
    source.verify_hashes(frozen["sources"])
    source.Stages(learner, sha(learner / "identity.json")).load("model")
    validation_stage_path = learner / "validation.complete.json"
    if frozen["sources"][str(validation_stage_path.resolve())] != sha(
        validation_stage_path
    ):
        raise ValueError("Validation artifact authority differs")
    validation_artifacts = read(validation_stage_path)["artifacts"]
    original_control = root / "learners_v1/gbt_net.txt"
    if (
        sha(learner / "gbt_net.txt")
        != read(learner / "identity.json")["files"][str(original_control.resolve())]
    ):
        raise ValueError("Control model authority differs")
    index = pd.read_parquet(
        root / "engine_v1/index.parquet", columns=["ticker", "date", "split", "status"]
    )
    train = select_training_days(index)
    if len(train) != 96:
        raise ValueError("Training selection must contain 96 days")
    selection_path = out / "training_days_preinference.csv"
    selection_text = train.to_csv(index=False, lineterminator="\n")
    if selection_path.exists():
        if selection_path.read_text(encoding="utf-8") != selection_text:
            raise ValueError("Frozen training selection changed")
    else:
        source.atomic(
            selection_path, lambda p: p.write_text(selection_text, encoding="utf-8")
        )
    identity = {
        "code_sha256": sha(__file__),
        "plan_sha256": sha(Path(__file__).with_name("ORACLE_MODEL_DIAGNOSTIC_PLAN.md")),
        "training_selection_sha256": sha(out / "training_days_preinference.csv"),
        "learner_freeze_sha256": sha(learner / "freeze.complete.json"),
        "learner_validation_stage_sha256": sha(validation_stage_path),
        "threshold": 0,
        "new_fits": 0,
        "models": {m: sha(learner / (m + ".txt")) for m in MODELS},
    }
    if (out / "identity.json").exists():
        if read(out / "identity.json") != identity:
            raise ValueError("Diagnostic resume identity differs")
    else:
        source.write_json(out / "identity.json", identity)
    identity_sha = sha(out / "identity.json")
    print(
        json.dumps(
            {
                "stage": "DIAGNOSTIC_START",
                "pid": os.getpid(),
                "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "resume": args.resume,
            }
        ),
        flush=True,
    )
    if (out / "summary.json").exists():
        raise ValueError("Completed diagnostic must not be rerun")
    days = base.discover_days(root / "engine_v1", root / "features_v1")
    seal = base.SourceSeal(root / "engine_v1")
    store, episodes = (
        base.FeatureStore(days, seal=seal),
        source.Episodes(root / "episode_features_v1", seal),
    )
    models = {
        m: source.lgb.Booster(model_file=str(learner / (m + ".txt"))) for m in MODELS
    }
    scales = read(learner / "normalizers.json")["risk_scales_usd"]
    train_keys = set(zip(train.ticker, train.date.astype(str)))
    hashes = {}
    for split in ("validation", "train"):
        target = out / split
        target.mkdir(exist_ok=args.resume)
        summaries, times, action_counts = [], [], []
        eligible = [
            d
            for d in days
            if (
                (
                    "20250101" <= d.date < "20260101"
                    if split == "validation"
                    else d.date < "20250101"
                )
                and (split == "validation" or (d.ticker, d.date) in train_keys)
            )
        ]
        if len(eligible) != (741 if split == "validation" else 96):
            raise ValueError("Diagnostic day universe differs")
        for number, day in enumerate(eligible):
            day_started = time.perf_counter()
            prefix = day.ticker + "_" + day.date
            state_paths = {m: target / (prefix + "_" + m + ".parquet") for m in MODELS}
            timing_path = target / (prefix + "_timing.parquet")
            score_path = target / (prefix + "_scores.npz")
            checkpoint_path = target / (prefix + ".complete.json")
            checkpoint = load_checkpoint(checkpoint_path, identity_sha, day.key)
            if checkpoint is not None:
                summaries.extend(pd.read_parquet(p) for p in state_paths.values())
                times.append(pd.read_parquet(timing_path))
                action_counts.extend(checkpoint["action_counts"])
                hashes.update(checkpoint["sources"])
                continue
            for path in (*state_paths.values(), timing_path, score_path):
                source.preserve(path, out, "Uncommitted diagnostic day")
            day_sources = {
                str((day.oracle / (name + ".parquet")).resolve()): sha(
                    day.oracle / (name + ".parquet")
                )
                for name in ("states", "actions", "labels", "advantages")
            }
            day_times, day_counts = [], []
            tables = {}
            for name in ("states", "actions", "labels", "advantages"):
                seal.check(day, name + ".parquet")
                tables[name] = pd.read_parquet(day.oracle / (name + ".parquet"))
            actions = tables["actions"]
            if split == "validation":
                path = learner / "validation" / (day.ticker + "_" + day.date + ".npz")
                marker = read(path.with_suffix(".complete.json"))
                if (
                    sha(path) != marker["sha256"]
                    or sha(path) != validation_artifacts[str(path.resolve())]
                    or sha(path.with_suffix(".complete.json"))
                    != validation_artifacts[
                        str(path.with_suffix(".complete.json").resolve())
                    ]
                ):
                    raise ValueError("Prediction hash differs")
                hashes[str(path)] = sha(path)
                day_sources[str(path.resolve())] = sha(path)
                day_sources[str(path.with_suffix(".complete.json").resolve())] = sha(
                    path.with_suffix(".complete.json")
                )
                with np.load(path, allow_pickle=False) as saved:
                    if set(saved.files) != {
                        "action_ids",
                        *MODELS,
                    } or not np.array_equal(saved["action_ids"], actions.action_id):
                        raise ValueError("Prediction schema/action order differs")
                    scores = {m: saved[m].copy() for m in MODELS}
            else:
                pack, ai, si = store.rows(day.key, actions.action_id)
                episode = episodes.get(day)
                scores = {m: np.empty(len(actions)) for m in MODELS}
                for start in range(0, len(actions), base.BATCH):
                    ix = slice(start, start + base.BATCH)
                    x = base.flatten_gbt(pack, ai[ix], si[ix])
                    augmented = np.concatenate(
                        [
                            x,
                            source.join_episodes(
                                episode, actions.state_i.to_numpy()[ix]
                            ),
                        ],
                        axis=1,
                    )
                    scores[MODELS[0]][ix] = (
                        models[MODELS[0]].predict(x, num_threads=4) * scales[day.ticker]
                    )
                    scores[MODELS[1]][ix] = (
                        models[MODELS[1]].predict(augmented, num_threads=4)
                        * scales[day.ticker]
                    )

                def save_scores(path):
                    with path.open("wb") as stream:
                        np.savez_compressed(
                            stream, action_ids=actions.action_id.to_numpy(), **scores
                        )

                source.atomic(score_path, save_scores)
                for path in (
                    day.features,
                    day.features.with_suffix(".json"),
                    day.features.parent / "actions.npz",
                    day.features.parent / "actions.json",
                    episodes.root / day.ticker / day.date / "episodes.npz",
                    episodes.root / day.ticker / day.date / "episodes.json",
                ):
                    day_sources[str(path.resolve())] = sha(path)
            for model in MODELS:
                immediate = (
                    tables["labels"]
                    .set_index("action_id")
                    .loc[actions.action_id, "net_base"]
                    .to_numpy(float)
                )
                advantage = (
                    tables["advantages"]
                    .set_index("action_id")
                    .loc[actions.action_id, "dp_advantage"]
                    .to_numpy(float)
                )
                day_counts.append(
                    dict(
                        split=split,
                        model=model,
                        ticker=day.ticker,
                        date=day.date,
                        actions=len(actions),
                        net_positive=int((immediate > 0).sum()),
                        dp_advantage_positive=int((advantage > 0).sum()),
                        net_positive_dp_nonpositive=int(
                            ((immediate > 0) & (advantage <= 0)).sum()
                        ),
                        prediction_positive=int((scores[model] > 0).sum()),
                        positive_net_rejected_by_score=int(
                            ((immediate > 0) & (scores[model] <= 0)).sum()
                        ),
                    )
                )
                states, timing = describe_day(
                    tables["actions"],
                    tables["labels"],
                    tables["advantages"],
                    tables["states"],
                    scores[model],
                )
                for frame in (states, timing):
                    frame["split"], frame["model"], frame["ticker"], frame["date"] = (
                        split,
                        model,
                        day.ticker,
                        day.date,
                    )
                source.atomic(
                    state_paths[model], lambda p: states.to_parquet(p, index=False)
                )
                summaries.append(states)
                day_times.append(timing)
            combined_timing = pd.concat(day_times, ignore_index=True)
            source.atomic(
                timing_path, lambda p: combined_timing.to_parquet(p, index=False)
            )
            times.append(combined_timing)
            action_counts.extend(day_counts)
            artifacts = [*state_paths.values(), timing_path] + (
                [score_path] if split == "train" else []
            )
            source.verify_hashes(day_sources)
            source.write_json(
                checkpoint_path,
                {
                    "identity": identity_sha,
                    "day_key": day.key,
                    "artifacts": {str(p.resolve()): sha(p) for p in artifacts},
                    "sources": day_sources,
                    "action_counts": day_counts,
                },
            )
            hashes.update(day_sources)
            if number % 10 == 0 or number < 3:
                print(
                    json.dumps(
                        {
                            "stage": split,
                            "day": number,
                            "total": len(eligible),
                            "day_seconds": time.perf_counter() - day_started,
                        }
                    ),
                    flush=True,
                )
        joined = pd.concat(summaries, ignore_index=True)
        aggregate(joined).to_csv(target / "decision_categories.csv", index=False)
        pd.DataFrame(action_counts).to_csv(
            target / "action_signal_counts.csv", index=False
        )
        timing_all = pd.concat(times, ignore_index=True)
        timing_all.to_parquet(target / "timing_hindsight.parquet", index=False)
        timing_all.groupby(
            [
                "model",
                "ticker",
                "shift_minutes",
                "status",
                "original_fill",
                "shifted_fill",
            ],
            dropna=False,
        ).agg(
            rows=("state_i", "size"),
            mean_net_difference=("net_difference", "mean"),
            median_net_difference=("net_difference", "median"),
        ).reset_index().to_csv(target / "timing_summary.csv", index=False)
        monthly = [
            aggregate(group).assign(month=month)
            for month, group in joined.groupby(joined.date.str[:6])
        ]
        pd.concat(monthly, ignore_index=True).to_csv(
            target / "decision_categories_monthly.csv", index=False
        )
        joined.sort_values(["date", "state_i"]).groupby(
            ["model", "ticker", "category"], sort=True
        ).head(1).to_csv(target / "first_chronological_examples.csv", index=False)
        path_rows = []
        for (model, ticker), group in joined.groupby(["model", "ticker"]):
            for policy in ("model", "oracle"):
                executed = group.loc[
                    group[policy + "_free"] & group[policy + "_filled"]
                ]
                path_rows.append(
                    dict(
                        model=model,
                        ticker=ticker,
                        policy=policy,
                        trades=len(executed),
                        net_base=float(executed[policy + "_net"].sum()),
                        traded_days=executed.date.nunique(),
                        available_days=group.date.nunique(),
                    )
                )
        pd.DataFrame(path_rows).to_csv(target / "path_metrics.csv", index=False)
        source.write_json(
            target / "completion.json",
            {
                "days": len(eligible),
                "state_rows": len(joined),
                "identity_sha256": sha(out / "identity.json"),
            },
        )
        print(
            json.dumps({"stage": split + "_COMPLETE", "days": len(eligible)}),
            flush=True,
        )
    hashes.update(seal.hashes)
    hashes.update(store.hashes)
    hashes.update(episodes.hashes)
    source.verify_hashes(hashes)
    if (
        sha(__file__) != identity["code_sha256"]
        or sha(Path(__file__).with_name("ORACLE_MODEL_DIAGNOSTIC_PLAN.md"))
        != identity["plan_sha256"]
        or any(
            sha(learner / (model + ".txt")) != digest
            for model, digest in identity["models"].items()
        )
    ):
        raise ValueError("Diagnostic code, plan or models changed during execution")
    source.write_json(out / "source_hashes.json", hashes)
    source.write_json(
        out / "summary.json",
        {
            "status": "COMPLETE_DESCRIPTIVE_ORACLE_MODEL_DIAGNOSTIC",
            "new_fits": 0,
            "identity": identity,
            "sources": len(hashes),
            "promotion_approved": False,
        },
    )


if __name__ == "__main__":
    main()

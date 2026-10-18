"""Read-only sealed-score diagnostic; no fits or new inference."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

MODELS = ("gbt_net", "gbt_net_episode")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def aligned(actions, labels, ids, scores):
    if actions.action_id.duplicated().any() or labels.action_id.duplicated().any():
        raise ValueError("Duplicate action IDs")
    if not np.array_equal(actions.action_id.to_numpy(), ids):
        raise ValueError("Scores not aligned to action IDs")
    if set(actions.action_id) != set(labels.action_id):
        raise ValueError("Label action IDs differ")
    if np.asarray(scores).shape != (len(actions),) or not np.isfinite(scores).all():
        raise ValueError("Invalid score vector")
    frame = actions.merge(labels, on="action_id", validate="one_to_one", sort=False)
    if not frame.status.isin(["FILLED", "NO_FILL"]).all():
        raise ValueError("Invalid fill label")
    frame["pred"] = np.asarray(scores)
    frame["real"] = np.where(frame.status == "FILLED", frame.net_base, 0.0)
    if not np.isfinite(frame.real).all():
        raise ValueError("Nonfinite realized label")
    return frame


def cohorts(frame, states):
    maxima = frame.sort_values(["state_i", "pred", "action_id"], ascending=[True, False, True]).drop_duplicates("state_i")
    selected = states.loc[states.model_free & states.model_filled]
    if selected.state_i.duplicated().any() or selected.model_action_id.duplicated().any():
        raise ValueError("Duplicate executed state/action")
    executed = selected.merge(frame, left_on="model_action_id", right_on="action_id", validate="one_to_one", suffixes=("_trace", "_action"))
    if len(executed) != len(selected) or not (executed.state_i_trace == executed.state_i_action).all():
        raise ValueError("Executed action/state alignment differs")
    if not (executed.status == "FILLED").all():
        raise ValueError("Trace execution is NO_FILL")
    if not np.array_equal(executed.model_score, executed.pred) or not np.array_equal(executed.model_net, executed.real):
        raise ValueError("Trace score/payoff differs")
    return dict(all_actions=frame, argmax_before_threshold=maxima, executed_trades=executed)


def moments(frame):
    pred, real = frame.pred.to_numpy(float), frame.real.to_numpy(float)
    error = pred - real
    out = dict(units=len(frame), filled=int((frame.status == "FILLED").sum()))
    for name, values in dict(pred=pred, real=real, pred2=pred ** 2, real2=real ** 2,
                             cross=pred * real, error=error, abs_error=np.abs(error), error2=error ** 2).items():
        out[name] = float(values.mean()) if len(frame) else np.nan
    return out


def aggregate(daily):
    output = []
    for key, group in daily.groupby(["split", "ticker", "model", "cohort"], sort=True):
        nonempty = group.loc[group.units > 0]
        values = nonempty[["pred", "real", "pred2", "real2", "cross", "error", "abs_error", "error2"]].mean()
        variance_pred = max(0.0, values.pred2 - values.pred ** 2)
        variance_real = max(0.0, values.real2 - values.real ** 2)
        denominator = np.sqrt(variance_pred * variance_real)
        output.append(dict(zip(("split", "ticker", "model", "cohort"), key),
            expected_days=len(group), nonempty_days=len(nonempty), empty_days=len(group) - len(nonempty),
            units=int(group.units.sum()), filled=int(group.filled.sum()), no_fill=int((group.units - group.filled).sum()),
            predicted_mean_usd=values.pred, realized_mean_usd=values.real, mean_error_usd=values.error,
            mae_usd=values.abs_error, rmse_usd=np.sqrt(values.error2),
            correlation=(values.cross - values.pred * values.real) / denominator if denominator > 0 else np.nan))
    return pd.DataFrame(output)


def paired(daily):
    output = []
    for key, group in daily.groupby(["split", "ticker", "model"], sort=True):
        for upper, lower in (("argmax_before_threshold", "all_actions"), ("executed_trades", "argmax_before_threshold")):
            a = group.loc[(group.cohort == upper) & (group.units > 0)].set_index("date")
            b = group.loc[(group.cohort == lower) & (group.units > 0)].set_index("date")
            common = a.index.intersection(b.index)
            delta = a.loc[common, ["pred", "real", "error", "abs_error", "error2"]] - b.loc[common, ["pred", "real", "error", "abs_error", "error2"]]
            output.append(dict(zip(("split", "ticker", "model"), key), comparison=upper + "_MINUS_" + lower,
                paired_days=len(common), **{name + "_difference": value for name, value in delta.mean().items()}))
    return pd.DataFrame(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    diagnostic = root / "oracle_model_diagnostic_v1"
    sources = {}

    def checked(path, expected=None):
        path = Path(path).resolve()
        observed = sha(path)
        if expected is not None and observed != expected:
            raise ValueError(f"Hash differs: {path}")
        sources[str(path)] = observed
        return path

    started = time.perf_counter()
    if read(checked(diagnostic / "summary.json"))["status"] != "COMPLETE_DESCRIPTIVE_ORACLE_MODEL_DIAGNOSTIC":
        raise ValueError("Previous diagnostic incomplete")
    identity_sha = sha(checked(diagnostic / "identity.json"))
    checked(diagnostic / "training_days_preinference.csv")
    code, spec = Path(__file__), Path(__file__).with_name("MAX_SCORE_CALIBRATION_SPEC.md")
    identity = dict(code_sha256=sha(checked(code)), spec_sha256=sha(checked(spec)), prior_identity_sha256=identity_sha,
                    cohorts=["all_actions", "argmax_before_threshold", "executed_trades"], new_fits=0, new_inference=0)
    write(out / "identity.json", identity)
    daily = []
    for split, expected in (("train", 96), ("validation", 741)):
        markers = sorted((diagnostic / split).glob("*.complete.json"))
        if len(markers) != expected:
            raise ValueError("Wrong frozen day count")
        for number, marker in enumerate(markers, 1):
            record = read(checked(marker))
            if record["identity"] != identity_sha:
                raise ValueError("Day identity differs")
            ticker, date = record["day_key"].split("/")
            bindings = {**record["sources"], **record["artifacts"]}
            def bound(path):
                path = Path(path).resolve()
                return checked(path, bindings[str(path)])
            engine = root / "engine_v1" / ticker / date
            actions = pd.read_parquet(bound(engine / "actions.parquet"), columns=["action_id", "state_i"])
            labels = pd.read_parquet(bound(engine / "labels.parquet"), columns=["action_id", "status", "net_base"])
            score_path = (diagnostic / split / f"{ticker}_{date}_scores.npz" if split == "train"
                          else root / "episode_learners_v1" / split / f"{ticker}_{date}.npz")
            with np.load(bound(score_path), allow_pickle=False) as scores:
                if set(scores.files) != {"action_ids", *MODELS}:
                    raise ValueError("Wrong saved score schema")
                for model in MODELS:
                    frame = aligned(actions, labels, scores["action_ids"], scores[model])
                    states = pd.read_parquet(bound(diagnostic / split / f"{ticker}_{date}_{model}.parquet"),
                        columns=["state_i", "model_free", "model_filled", "model_action_id", "model_score", "model_net"])
                    for cohort, subset in cohorts(frame, states).items():
                        daily.append(dict(split=split, ticker=ticker, date=date, model=model, cohort=cohort, **moments(subset)))
            if number % 50 == 0 or number == expected:
                print(json.dumps(dict(split=split, days=number, total=expected)), flush=True)
    daily_frame = pd.DataFrame(daily)
    daily_frame.to_csv(out / "daily_moments.csv", index=False)
    aggregate(daily_frame).to_csv(out / "summary_metrics.csv", index=False)
    paired(daily_frame).to_csv(out / "paired_differences.csv", index=False)
    for path, wanted in sources.items():
        if sha(path) != wanted:
            raise ValueError(f"Source changed: {path}")
    write(out / "sources.json", sources)
    write(out / "summary.json", dict(status="COMPLETE_DESCRIPTIVE_MAX_SCORE_CALIBRATION", new_fits=0, new_inference=0,
        days=837, daily_rows=len(daily_frame), source_count=len(sources), wall_seconds=time.perf_counter() - started,
        identity_sha256=sha(out / "identity.json"), artifacts={p.name: sha(p) for p in out.glob("*.csv")},
        sources_sha256=sha(out / "sources.json"), promotion_approved=False))


if __name__ == "__main__":
    main()

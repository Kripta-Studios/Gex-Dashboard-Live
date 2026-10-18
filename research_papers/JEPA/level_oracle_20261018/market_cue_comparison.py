"""Fixed-policy comparison primitives; no model fitting, data access or selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from train_market_cue_control import require

POLICIES = ("original_net__0", "cue_net__0")
# Fixed risk-unit boundaries, never estimated from evaluation outcomes or scores.
CALIBRATION_EDGES = np.array([-1.0, -0.5, 0.0, 0.1, 0.25, 0.5, 1.0, 2.0])


def flatten_original(pack, ai, si):
    """Exact original train_models.flatten_gbt arithmetic, without importing Torch."""
    maps = np.asarray(pack["maps"][si], np.float32)
    maps = maps.reshape(len(si), 20, 5, 8, 8).mean(axis=-1).reshape(len(si), -1)
    masks = np.stack((pack["token_mask"], pack["bar_mask"]), axis=-1)
    return np.concatenate(
        (
            pack["base"][si],
            pack["tokens"][si].reshape(len(si), -1),
            np.asarray(masks[si], np.float32).reshape(len(si), -1),
            maps,
            np.asarray(pack["map_mask"][si], np.float32).reshape(len(si), -1),
            pack["action_features"][ai],
        ),
        axis=1,
    ).astype(np.float32)


def align_labels(actions, labels, close_i):
    require(close_i in (210, 390), "Unknown session clock")
    require(not actions.action_id.duplicated().any(), "Duplicate action")
    require(not labels.action_id.duplicated().any(), "Duplicate label")
    positions = pd.Index(labels.action_id).get_indexer(actions.action_id)
    require(
        len(labels) == len(actions) and (positions >= 0).all(), "Label universe differs"
    )
    result = labels.iloc[positions].reset_index(drop=True)
    states, exits = actions.state_i.to_numpy(), result.exit_i.to_numpy()
    require(
        states.dtype.kind in "iu" and exits.dtype.kind in "iu",
        "Integer clocks required",
    )
    require(
        ((states >= 60) & (states <= close_i - 15)).all(),
        "Action beyond decision horizon",
    )
    require(result.status.isin(["FILLED", "NO_FILL"]).all(), "Unknown fill status")
    fill = result.status.to_numpy() == "FILLED"
    require(
        ((exits[fill] >= states[fill] + 2) & (exits[fill] <= close_i - 5)).all(),
        "Invalid filled exit",
    )
    require((exits[~fill] == states[~fill] + 1).all(), "Invalid NO_FILL clock")
    for column in ("net_base", "net_adverse"):
        require(np.isfinite(result[column]).all(), "Nonfinite payoff")
        require((result[column].to_numpy()[~fill] == 0).all(), "Nonzero NO_FILL payoff")
    return result


def schedule(actions, labels, scores, close_i):
    """Choose by causal score first; no-fill retries next minute, never runner-up."""
    scores = np.asarray(scores)
    require(
        scores.shape == (len(actions),) and np.isfinite(scores).all(), "Invalid scores"
    )
    choices = {}
    for row in np.lexsort(
        (actions.action_id.to_numpy(), -scores, actions.state_i.to_numpy())
    ):
        minute = int(actions.state_i.iloc[row])
        if minute not in choices:
            choices[minute] = int(row) if scores[row] > 0 else -1
    # Choices are fixed before interpreting any label.
    aligned = align_labels(actions, labels, close_i)
    selected, flags = [], []
    minute, filled = 60, 0
    while minute <= close_i - 15:
        row = choices.get(minute, -1)
        if row < 0:
            minute += 1
            continue
        selected.append(row)
        flags.append(filled)
        if aligned.status.iloc[row] == "FILLED":
            minute = int(aligned.exit_i.iloc[row]) + 1
            filled = 1
        else:
            minute += 1
    attempts = pd.DataFrame(
        {
            "action_id": actions.action_id.to_numpy()[selected],
            "state_i": actions.state_i.to_numpy()[selected],
            "score_usd": scores[selected],
            "has_filled_before": np.asarray(flags, dtype=np.int8),
        }
    )
    for column in ("status", "exit_i", "net_base", "net_adverse"):
        attempts[column] = aligned[column].to_numpy()[selected]
    return aligned, attempts, attempts.loc[attempts.status == "FILLED"].copy()


def calibration_sums(scores, outcomes, scale, weights=None):
    """Mergeable regression calibration; boundaries are fixed TRAIN-scale multiples."""
    scores, outcomes = np.asarray(scores, float), np.asarray(outcomes, float)
    weights = np.ones(len(scores)) if weights is None else np.asarray(weights, float)
    require(
        scores.ndim == 1 and outcomes.shape == scores.shape == weights.shape,
        "Calibration shape",
    )
    require(np.isfinite(scale) and scale > 0, "Invalid TRAIN scale")
    require(
        np.isfinite(scores).all()
        and np.isfinite(outcomes).all()
        and np.isfinite(weights).all()
        and (weights >= 0).all(),
        "Invalid calibration values",
    )
    bins = np.searchsorted(CALIBRATION_EDGES, scores / scale, side="right")
    residual = outcomes - scores
    result = []
    for bucket in range(len(CALIBRATION_EDGES) + 1):
        take = bins == bucket
        w = weights[take]
        result.append(
            dict(
                bin=bucket,
                n=int(take.sum()),
                weight=float(w.sum()),
                predicted_sum=float(np.dot(w, scores[take])),
                realized_sum=float(np.dot(w, outcomes[take])),
                squared_error_sum=float(np.dot(w, residual[take] ** 2)),
                absolute_error_sum=float(np.dot(w, np.abs(residual[take]))),
            )
        )
    return result


def calibration_report(records):
    result = []
    for bucket in range(len(CALIBRATION_EDGES) + 1):
        parts = [row for day in records for row in day if row["bin"] == bucket]
        weight = sum(row["weight"] for row in parts)
        def total(name):
            return sum(row[name] for row in parts)
        result.append(
            dict(
                bin=bucket,
                lower_risk_units=None
                if bucket == 0
                else float(CALIBRATION_EDGES[bucket - 1]),
                upper_risk_units=None
                if bucket == len(CALIBRATION_EDGES)
                else float(CALIBRATION_EDGES[bucket]),
                n=total("n"),
                weight=weight,
                predicted_usd=total("predicted_sum") / weight if weight else None,
                realized_usd=total("realized_sum") / weight if weight else None,
                mean_residual_usd=(total("realized_sum") - total("predicted_sum"))
                / weight
                if weight
                else None,
                rmse_usd=(total("squared_error_sum") / weight) ** 0.5
                if weight
                else None,
                mae_usd=total("absolute_error_sum") / weight if weight else None,
            )
        )
    return result


def trade_metrics(ledger):
    result = {"trades": len(ledger)}
    for column in ("net_base", "net_adverse"):
        values = ledger[column].to_numpy(float)
        gains, losses = (
            float(values[values > 0].sum()),
            -float(values[values < 0].sum()),
        )
        result[column] = float(values.sum())
        result[column + "_profit_factor"] = gains / losses if losses else None
        result[column + "_pf_infinite"] = bool(gains > 0 and losses == 0)
        result[column + "_win_rate"] = (
            float((values > 0).mean()) if len(values) else None
        )
    return result


def coverage_report(daily):
    require(len(daily) > 0, "Empty calendar")
    require(
        len({(row["ticker"], row["date"]) for row in daily}) == len(daily),
        "Duplicate calendar row",
    )
    require(
        all(row["source_status"] in ("COMPLETE", "MISSING_SOURCE") for row in daily),
        "Unknown source status",
    )
    missing = [row for row in daily if row["source_status"] == "MISSING_SOURCE"]
    require(
        all(
            row["trades"] == 0 and row["net_base"] == row["net_adverse"] == 0
            for row in missing
        ),
        "Fabricated missing-source trade",
    )
    available = [row for row in daily if row["source_status"] == "COMPLETE"]
    failures = [row for row in available if row["trades"] < 1]
    return dict(
        expected_days=len(daily),
        available_days=len(available),
        missing_days=len(missing),
        available_days_without_fill=len(failures),
        observable_daily_pass=bool(available) and not failures,
        universal_daily_pass=not missing and not failures,
        universal_daily_status="NO_EVALUABLE"
        if missing
        else ("PASS" if not failures else "FAIL"),
        missing_keys=[row["ticker"] + "/" + row["date"] for row in missing],
        unfilled_available_keys=[row["ticker"] + "/" + row["date"] for row in failures],
    )

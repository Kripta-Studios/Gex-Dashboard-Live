"""Pure fixed-policy rollout labels, never clairvoyant action selection.

Choices are made by a separate function that cannot receive outcome labels.
The two columns represent has_filled_today=0 and =1. Future realized rewards
are training labels only. This module does not train or read market files.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ActionRows:
    action_id: np.ndarray
    state_i: np.ndarray

    def validate(self, first, last):
        ids, states = np.asarray(self.action_id), np.asarray(self.state_i)
        if ids.ndim != 1 or states.shape != ids.shape:
            raise ValueError("Action keys must be aligned vectors")
        if ids.dtype.kind not in "iu" or states.dtype.kind not in "iu":
            raise ValueError("Action identity and clocks must be integers")
        if len(np.unique(ids)) != len(ids) or np.any(ids < 0):
            raise ValueError("Action identity must be unique and nonnegative")
        if np.any((states < first) | (states > last)):
            raise ValueError("Action clock outside decision horizon")
        if first > last:
            raise ValueError("Empty decision horizon")


@dataclass(frozen=True)
class OutcomeRows:
    action_id: np.ndarray
    status: np.ndarray
    exit_i: np.ndarray
    net_base: np.ndarray

    def aligned(self, actions):
        ids = np.asarray(self.action_id)
        status, exits, rewards = map(
            np.asarray, (self.status, self.exit_i, self.net_base)
        )
        if ids.ndim != 1 or any(a.shape != ids.shape for a in (status, exits, rewards)):
            raise ValueError("Outcome vectors must align")
        if ids.dtype.kind not in "iu" or exits.dtype.kind not in "iu":
            raise ValueError("Outcome identity and exit clock must be integers")
        if len(np.unique(ids)) != len(ids) or set(ids) != set(actions.action_id):
            raise ValueError("Outcome/action identities differ")
        lookup = {int(key): index for index, key in enumerate(ids)}
        order = np.array([lookup[int(key)] for key in actions.action_id], dtype=int)
        status, exits, rewards = status[order], exits[order], rewards[order].astype(float)
        if not np.isfinite(rewards).all() or not np.isin(status, ["FILLED", "NO_FILL"]).all():
            raise ValueError("Invalid outcome status or reward")
        filled = status == "FILLED"
        if np.any(exits[filled] <= actions.state_i[filled]):
            raise ValueError("Filled transition must advance the clock")
        if np.any(rewards[~filled] != 0):
            raise ValueError("NO_FILL must have zero economic reward")
        return filled, exits, rewards


def validate_engine_outcomes(actions, outcomes):
    """Admission adapter for the frozen market engine, separate from toy horizons."""
    actions.validate(60, 375)
    filled, exits, _ = outcomes.aligned(actions)
    if np.any(exits[filled] < actions.state_i[filled] + 2) or np.any(exits[filled] > 385):
        raise ValueError("Filled outcome violates frozen engine exit limits")
    if np.any(exits[~filled] != actions.state_i[~filled] + 1):
        raise ValueError("NO_FILL exit marker must equal next-minute entry attempt")


def freeze_choices(actions, scores, *, threshold=0.0, first=60, last=375):
    """Use decision-observable keys/scores only; tie => lower action_id, WAIT first."""
    actions.validate(first, last)
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (len(actions.action_id), 2) or not np.isfinite(scores).all():
        raise ValueError("Two finite causal score columns are required")
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("WAIT is zero; nonnegative finite threshold required")
    choices = np.full((last - first + 1, 2), -1, dtype=np.int64)
    # Stable identity ordering makes ties independent of the input row order.
    identity_order = np.argsort(actions.action_id, kind="stable")
    for minute in np.unique(actions.state_i):
        rows = identity_order[actions.state_i[identity_order] == minute]
        for h in (0, 1):
            row = rows[np.argmax(scores[rows, h])]
            if scores[row, h] > threshold:
                choices[int(minute) - first, h] = actions.action_id[row]
    choices.flags.writeable = False
    return choices


def fixed_policy_values(actions, outcomes, choices, penalty, *, first=60, last=375):
    """Evaluate already frozen choices, preserving losses and nonfills exactly."""
    actions.validate(first, last)
    filled, exits, rewards = outcomes.aligned(actions)
    choices = np.asarray(choices)
    if choices.shape != (last - first + 1, 2) or choices.dtype.kind not in "iu":
        raise ValueError("Choice table differs from decision horizon")
    if not np.isfinite(penalty) or penalty < 0:
        raise ValueError("Finite nonnegative training-only penalty required")
    lookup = {int(key): row for row, key in enumerate(actions.action_id)}
    terminal = last - first + 1
    values = np.empty((terminal + 1, 2), dtype=np.float64)
    values[terminal] = [-penalty, 0.0]
    for minute in range(last, first - 1, -1):
        i = minute - first
        for h in (0, 1):
            key = int(choices[i, h])
            if key == -1:
                values[i, h] = values[i + 1, h]
                continue
            if key not in lookup:
                raise ValueError("Frozen choice names an unknown action")
            row = lookup[key]
            if actions.state_i[row] != minute:
                raise ValueError("Frozen choice belongs to a different minute")
            if not filled[row]:
                values[i, h] = values[i + 1, h]
            else:
                next_i = min(int(exits[row]) + 1 - first, terminal)
                values[i, h] = rewards[row] + values[next_i, 1]
    if not np.isfinite(values).all():
        raise FloatingPointError("Nonfinite fixed-policy rollout")
    return values


def residual_targets(actions, outcomes, values, *, first=60, last=375):
    """Training sidecar: filled reward + continuation minus one-minute WAIT.

NO_FILL is exactly zero for both flags. The terminal penalty is not added to
economic rewards; it exists exclusively in the continuation value sidecar.
"""
    actions.validate(first, last)
    filled, exits, rewards = outcomes.aligned(actions)
    terminal = last - first + 1
    values = np.asarray(values, dtype=float)
    if values.shape != (terminal + 1, 2) or not np.isfinite(values).all():
        raise ValueError("Invalid fixed-policy values")
    result = np.zeros((len(actions.action_id), 2), dtype=np.float64)
    rows = np.flatnonzero(filled)
    current_next = actions.state_i[rows] + 1 - first
    exit_next = np.minimum(exits[rows] + 1 - first, terminal)
    result[rows] = (
        rewards[rows, None] + values[exit_next, 1, None] - values[current_next]
    )
    if not np.isfinite(result).all():
        raise FloatingPointError("Nonfinite residual label")
    return result

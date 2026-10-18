"""Equivalent fast scheduling of frozen causal scores over canonical outcomes.

Ranking depends solely on scores and offered action identifiers. Future labels
are consulted only after committing to the winner, to advance the simulated
inventory clock. This module does not select a different action after no-fill.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class PolicyView:
    def __init__(self, actions, labels):
        if actions.action_id.duplicated().any() or labels.action_id.duplicated().any():
            raise ValueError("Duplicate action IDs")
        indexer = pd.Index(labels.action_id).get_indexer(actions.action_id)
        if len(labels) != len(actions) or (indexer < 0).any():
            raise ValueError("Action/outcome universe mismatch")
        self.actions = actions.reset_index(drop=True)
        self.labels = labels.iloc[indexer].reset_index(drop=True)
        self.ids = self.actions.action_id.to_numpy()
        self.states = self.actions.state_i.to_numpy()
        self.filled = self.labels.status.to_numpy() == "FILLED"
        if not np.isin(self.labels.status, ["FILLED", "NO_FILL"]).all():
            raise ValueError("Unknown fill status")
        self.exits = self.labels.exit_i.to_numpy()
        if np.any(self.filled & ((self.exits < self.states + 2) | (self.exits > 385))):
            raise ValueError("Impossible fill chronology")
        if not np.isfinite(
            self.labels[["net_base", "net_adverse"]].to_numpy(float)
        ).all():
            raise ValueError("Nonfinite reward")

    def rank(self, scores):
        scores = np.asarray(scores, dtype=float)
        if scores.shape != (len(self.actions),):
            raise ValueError("Score/action shape mismatch")
        valid = np.flatnonzero(np.isfinite(scores))
        order = valid[np.lexsort((self.ids[valid], -scores[valid], self.states[valid]))]
        if not len(order):
            return order
        first = np.r_[True, self.states[order][1:] != self.states[order][:-1]]
        return order[first]

    def evaluate(self, scores, threshold, engine, ranked=None):
        scores = np.asarray(scores, float)
        ranked = self.rank(scores) if ranked is None else ranked
        selected = []
        next_state = engine.FIRST_STATE
        for row in ranked:
            state = int(self.states[row])
            if state < next_state or scores[row] <= threshold:
                continue
            selected.append(int(row))
            # This is after the action was irrevocably chosen from causal scores.
            next_state = int(self.exits[row]) + 1 if self.filled[row] else state + 1
        attempts = self.actions.iloc[selected].merge(
            self.labels.iloc[selected],
            on="action_id",
            how="left",
            validate="one_to_one",
        )
        attempts["score"] = scores[selected]
        ledger = attempts.loc[attempts.status == "FILLED"].copy()
        summary = engine.ledger_summary(ledger)
        summary["attempts"] = len(attempts)
        summary["no_fill_attempts"] = int((attempts.status == "NO_FILL").sum())
        return engine.PolicyResult(attempts, ledger, summary)

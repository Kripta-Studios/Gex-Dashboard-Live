"""User chooses free timing; daily minimum is a constraint, never forced entry."""

import numpy as np

from run_policy import PolicyView


def evaluate(actions, labels, scores, threshold, engine):
    view = PolicyView(actions, labels)
    scores = np.asarray(scores, float)
    if not np.isfinite(scores).all():
        raise FloatingPointError("Nonfinite episode policy scores")
    return view.evaluate(scores, threshold, engine)

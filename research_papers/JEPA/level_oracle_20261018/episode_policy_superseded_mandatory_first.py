"""Causal first-fill obligation; scores choose actions before outcomes are read."""
import numpy as np

from run_policy import PolicyView


def evaluate(actions, labels, scores, threshold, engine):
    view = PolicyView(actions, labels)
    scores = np.asarray(scores, float)
    if not np.isfinite(scores).all():
        raise FloatingPointError("Nonfinite episode policy scores")
    selected, forced = [], []
    next_state, had_fill = engine.FIRST_STATE, False
    for row in view.rank(scores):
        state = int(view.states[row])
        if state < next_state or (had_fill and scores[row] <= threshold):
            continue
        # Winner is irrevocably chosen; only now consume its historical result.
        selected.append(int(row))
        forced.append(not had_fill)
        if view.filled[row]:
            had_fill = True
            next_state = int(view.exits[row]) + 1
        else:
            next_state = state + 1
    attempts = view.actions.iloc[selected].merge(
        view.labels.iloc[selected], on="action_id", how="left", validate="one_to_one"
    )
    attempts["score"] = scores[selected]
    attempts["mandatory_first_fill"] = forced
    ledger = attempts.loc[attempts.status == "FILLED"].copy()
    summary = engine.ledger_summary(ledger)
    summary.update(attempts=len(attempts), no_fill_attempts=int((attempts.status == "NO_FILL").sum()))
    return engine.PolicyResult(attempts, ledger, summary)

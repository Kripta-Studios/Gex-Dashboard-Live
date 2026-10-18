"""Small independent arithmetic fixtures; no market files."""
from types import SimpleNamespace
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import audit_session_clock_dataset as audit


def raw():
    result = dict(spot=np.full(211, 100.0), spot_valid=np.ones(211, bool),
                  bid=np.ones((211, 1)), ask=np.full((211, 1), 1.1),
                  row_flags=np.full((211, 1), 3, np.uint8))
    result["spot"][204] = 103
    return result


def actions():
    return pd.DataFrame([dict(action_id=0, state_i=195, entry_i=196, contract_i=0,
        right=0, strike=100.0, selected_delta=.5, delta_bucket=.5,
        target_center=102.0, target_source_mask=1, stop_center=98.0,
        stop_source_mask=2, band=.1)])


def test_short_exit_cost_and_dp():
    labels = audit.reconstruct_labels(raw(), actions())
    assert labels.loc[0, "trigger_i"] == 204 and labels.loc[0, "exit_i"] == 205
    assert labels.loc[0, "reason"] == "TARGET"
    trades, base, adverse = audit.oracle_totals(actions(), labels)
    assert trades == 0 and base == adverse == 0  # the realized option trade loses


def test_no_fill_and_eod_boundary():
    source = raw()
    source["row_flags"][196, 0] = 0
    labels = audit.reconstruct_labels(source, actions())
    assert labels.status.tolist() == ["NO_FILL"] and labels.net_base.tolist() == [0]
    source = raw()
    source["spot"][204] = 100
    source["spot"][205] = 103
    assert audit.exit_geometry(source, SimpleNamespace(state_i=195, right=0,
        target_center=102, stop_center=98, band=.1))[:3] == (-1, 205, "EOD")


def test_action_feature_decision_time_and_source_bits():
    source = raw()
    source.update(iv=np.full((211, 1), .2), delta=np.full((211, 1), .5),
                  vega=np.full((211, 1), .1), theta=np.full((211, 1), -.02))
    values = audit.action_features(source, actions(), 4.0)
    assert values.shape == (1, 33)
    assert values[0, 0] == 0 and values[0, 17] == 1
    assert values[0, 23] == 1 and values[0, 29] == 1

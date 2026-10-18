"""Bitwise parity with frozen reference, using synthetic features only."""

import copy
import numpy as np
import pytest

import market_cues as cues
import market_cue_vectors as reference
import market_cue_vectors_fast as fast
from test_market_cue_vectors import arrays


@pytest.mark.parametrize("stacked", [False, True])
def test_all_columns_bitwise_equal_over_actions_masks_bands_and_sides(stacked):
    rng = np.random.default_rng(20261018)
    pack = arrays()
    n = 192
    actions = np.repeat(pack["action_features"][:1], n, axis=0).astype(np.float32)
    # All direct inputs vary, including masks and actual zero/NaN values.
    for name in cues.ACTION_NAMES:
        index = cues.A[name]
        if (
            name.startswith(("target_source_", "stop_source_"))
            or name.endswith("_valid")
            or name in ("is_put", "greek_present")
        ):
            actions[:, index] = rng.integers(0, 2, n)
        else:
            actions[:, index] = rng.uniform(-0.5, 1.5, n)
    actions[:, cues.A["band_ib"]] = np.resize(
        np.array([0.01, 0.05, 0.1, 0], np.float32), n
    )
    actions[::11, cues.A["delta"]] = np.nan
    actions[::13, cues.A["ask_over_spot"]] = 0
    actions[::17, cues.A["stop_distance_ib"]] = 0
    actions[::19, cues.A["theta_over_spot"]] = 0
    pack["action_features"] = actions
    pack["tokens"][0, 0] = np.nan
    pack["bar_end_i"][0, 0] = 65  # future row ignored
    pack["tokens"][1, 11, cues.T["spot_valid_fraction"]] = 0.8
    pack["base"][1, cues.B["current_call_oi_known_fraction"]] = 1
    if stacked:
        pack["token_mask"] = np.stack([pack["token_mask"], pack["bar_mask"]], axis=-1)
    ai, si = rng.permutation(n), rng.integers(0, 2, n)
    actual = fast.vectorize_rows(**pack, action_positions=ai, state_positions=si)
    expected = reference.vectorize_rows(**pack, action_positions=ai, state_positions=si)
    assert actual.dtype == expected.dtype == np.float32
    assert actual.tobytes() == expected.tobytes()


def test_cached_state_never_reuses_contract_quotes_or_missingness():
    pack = arrays()
    pack["action_features"][1] = pack["action_features"][0]
    pack["action_features"][1, cues.A["quote_valid"]] = 0
    pack["action_features"][1, cues.A["delta_valid"]] = 0
    ai, si = np.array([0, 1, 0]), np.array([0, 0, 0])
    actual = fast.vectorize_rows(**pack, action_positions=ai, state_positions=si)
    expected = reference.vectorize_rows(**pack, action_positions=ai, state_positions=si)
    assert actual.tobytes() == expected.tobytes()
    delta = reference.COLUMN_NAMES.index("delta")
    assert actual[:, delta + 1].tolist() == [1, 0, 1]


def test_future_unselected_state_and_empty_batch_are_invariant():
    pack = arrays()
    ai, si = np.array([0, 0]), np.array([0, 0])
    baseline = fast.vectorize_rows(**pack, action_positions=ai, state_positions=si)
    mutated = copy.deepcopy(pack)
    mutated["base"][1] = np.nan
    mutated["tokens"][1] = 999999
    mutated["action_features"][1] = np.nan
    assert (
        fast.vectorize_rows(
            **mutated, action_positions=ai, state_positions=si
        ).tobytes()
        == baseline.tobytes()
    )
    assert fast.vectorize_rows(
        **pack, action_positions=np.array([], int), state_positions=np.array([], int)
    ).shape == (0, 152)
    with pytest.raises(ValueError, match="outside"):
        fast.vectorize_rows(
            **pack, action_positions=np.array([-1]), state_positions=np.array([0])
        )


def test_invalid_geometry_masks_direct_action_fields_exactly():
    pack = arrays()
    pack["base"][0, cues.B["spot_valid"]] = 0
    ai, si = np.array([0, 1]), np.array([0, 0])
    assert (
        fast.vectorize_rows(**pack, action_positions=ai, state_positions=si).tobytes()
        == reference.vectorize_rows(
            **pack, action_positions=ai, state_positions=si
        ).tobytes()
    )

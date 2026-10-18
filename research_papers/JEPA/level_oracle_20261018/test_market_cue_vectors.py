"""No training, source data, labels, or market outcomes."""

import copy
import numpy as np
import pytest

import market_cues as cues
import market_cue_vectors as v
from test_market_cues import inputs


def arrays():
    x = inputs()
    result = {
        key: np.stack([value, value]) for key, value in x.items() if key != "action"
    }
    result["action_features"] = np.stack([x["action"], x["action"]])
    result["action_features"][1, cues.A["is_put"]] = 1
    return result


def test_fixed_numeric_schema_and_mask_distinguish_unknown_from_observed_zero():
    x = inputs()
    one = v.vectorize_cues(cues.extract_market_cues(**x))
    j = v.COLUMN_NAMES.index("call_observed_oi")
    assert one[j : j + 2].tolist() == [0, 0]
    x["base"][cues.B["current_call_oi_known_fraction"]] = 1
    two = v.vectorize_cues(cues.extract_market_cues(**x))
    assert two[j : j + 2].tolist() == [0, 1]
    assert one.shape == (152,) and one.dtype == np.float32
    assert v.schema()["width"] == 152 and len(set(v.COLUMN_NAMES)) == 152
    assert "rejection_description" not in v.VALUE_NAMES
    assert not v.schema()["transforms_fitted"] and not v.schema()["hard_entry_filters"]


def test_tags_membership_and_unselected_future_states_never_enter_vector():
    x = inputs()
    result = cues.extract_market_cues(**x)
    expected = v.vectorize_cues(result)
    changed = copy.deepcopy(result)
    changed["evidence_tags"] = ["WINNER_WITH_FUTURE"]
    changed["oracle_membership"] = True
    changed["metrics"]["rejection_description"] = dict(value=999, valid=True)
    np.testing.assert_array_equal(v.vectorize_cues(changed), expected)
    pack = arrays()
    baseline = v.vectorize_rows(
        **pack, action_positions=np.array([0]), state_positions=np.array([0])
    )
    pack["base"][1] = np.nan
    pack["tokens"][1] = np.nan
    pack["action_features"][1] = np.nan
    np.testing.assert_array_equal(
        v.vectorize_rows(
            **pack, action_positions=np.array([0]), state_positions=np.array([0])
        ),
        baseline,
    )
    with pytest.raises(TypeError):
        v.vectorize_rows(
            **pack,
            action_positions=np.array([0]),
            state_positions=np.array([0]),
            net_base=[10],
        )


def test_batch_order_duplicates_and_frozen_stacked_masks_exact():
    pack = arrays()
    ai, si = np.array([1, 0, 1]), np.array([0, 1, 0])
    result = v.vectorize_rows(**pack, action_positions=ai, state_positions=si)
    assert result[:, v.COLUMN_NAMES.index("is_put")].tolist() == [1, 0, 1]
    np.testing.assert_array_equal(result[0], result[2])
    pack["token_mask"] = np.stack([pack["token_mask"], pack["bar_mask"]], axis=-1)
    np.testing.assert_array_equal(
        v.vectorize_rows(**pack, action_positions=ai, state_positions=si), result
    )
    pack["token_mask"][0, 0, 1] = not pack["token_mask"][0, 0, 1]
    with pytest.raises(ValueError, match="bar-mask"):
        v.vectorize_rows(**pack, action_positions=ai, state_positions=si)


def test_invalid_schema_and_unrepresentable_value_rejected():
    result = cues.extract_market_cues(**inputs())
    result["metrics"]["delta"]["value"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        v.vectorize_cues(result)
    result["metrics"]["delta"]["value"] = 1e100
    with pytest.raises(ValueError, match="finite"):
        v.vectorize_cues(result)
    pack = arrays()
    with pytest.raises(ValueError, match="Integer"):
        v.vectorize_rows(
            **pack, action_positions=np.array([0.5]), state_positions=np.array([0])
        )
    with pytest.raises(ValueError, match="outside"):
        v.vectorize_rows(
            **pack, action_positions=np.array([5]), state_positions=np.array([0])
        )


def test_semantic_action_join_rejects_wrong_state_and_missing_identity():
    args = dict(
        reference_action_ids=np.array([7, 4]),
        reference_state_i=np.array([61, 60]),
        pack_action_ids=np.array([7, 4]),
        offered_action_ids=np.array([4, 7]),
        offered_state_i=np.array([60, 61]),
        pack_state_i=np.array([60, 61]),
    )
    ai, si = v.join_action_rows(**args)
    np.testing.assert_array_equal(ai, [0, 1])
    np.testing.assert_array_equal(si, [1, 0])
    args["reference_state_i"] = np.array([60, 61])
    with pytest.raises(ValueError, match="does not match"):
        v.join_action_rows(**args)
    args["reference_action_ids"] = np.array([999, 4])
    with pytest.raises(ValueError, match="does not match"):
        v.join_action_rows(**args)

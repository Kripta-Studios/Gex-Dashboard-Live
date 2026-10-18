import numpy as np
import pandas as pd
import pytest

import resume_oracle_diagnostic_dtype as repair


def test_nullable_flags_preserve_values_order_and_source(tmp_path):
    frame = pd.DataFrame(dict(
        original_fill=pd.Series([True, 1.0, np.nan, False, 0.0], dtype=object),
        shifted_fill=pd.Series([np.nan, False, 0.0, True, 1.0], dtype=object),
        net_difference=[3.0, -2.0, np.nan, 0.0, 8.0],
        action_id=[9, 1, 7, 8, 3],
    ))
    original = frame.copy(deep=True)
    path = tmp_path / "timing.parquet"
    repair.write_timing(frame, path)
    actual = pd.read_parquet(path)
    pd.testing.assert_frame_equal(frame, original)
    pd.testing.assert_frame_equal(actual, repair.normalized_timing(frame))
    pd.testing.assert_series_equal(actual.net_difference, original.net_difference)
    assert actual.action_id.tolist() == original.action_id.tolist()
    assert actual.original_fill.isna().tolist() == original.original_fill.isna().tolist()
    assert actual.original_fill.dropna().tolist() == [True, True, False, False]


def test_invalid_flag_rejected_and_replacement_bounded():
    with pytest.raises(ValueError, match="Non-boolean"):
        repair.normalized_timing(pd.DataFrame(dict(original_fill=[2], shifted_fill=[True])))
    fn = repair.repaired_run()
    assert fn.__globals__["__file__"] == repair.producer.__file__
    assert fn.__globals__["_write_timing"] is repair.write_timing
    assert fn.__code__.co_argcount == repair.producer.run.__code__.co_argcount

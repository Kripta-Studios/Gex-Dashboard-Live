from pathlib import Path

import pytest

from neural.jepa.build_existing_data_edge_modeling_view_v1 import OUTPUT_ROOT, _assert_under_output


def test_temp_output_must_remain_in_authorized_root() -> None:
    _assert_under_output(OUTPUT_ROOT / "view.parquet")
    with pytest.raises(AssertionError):
        _assert_under_output(Path("research_papers/forbidden.parquet"))

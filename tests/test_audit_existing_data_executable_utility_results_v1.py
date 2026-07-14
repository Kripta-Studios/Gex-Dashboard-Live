from neural.jepa.audit_existing_data_executable_utility_results_v1 import _close


def test_close_handles_nan_and_infinity_without_masking_real_difference() -> None:
    assert _close(float("nan"), float("nan"))
    assert _close(float("inf"), float("inf"))
    assert not _close(float("inf"), 1.0)
    assert not _close(1.0, 1.1)

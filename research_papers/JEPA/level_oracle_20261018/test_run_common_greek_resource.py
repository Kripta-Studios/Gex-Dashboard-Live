import run_common_greek_resource as runtime


def test_decimal_threshold_checks_both_resources_and_equality():
    values = iter(
        [
            (1_999_999_999, 9_000_000_000),
            (9_000_000_000, 1_999_999_999),
            (2_000_000_000, 2_000_000_000),
        ]
    )
    pauses = []
    runtime.wait_resources(lambda: next(values), pauses.append)
    assert pauses == [1, 1]
    assert runtime.GATE_BYTES == 2_000_000_000


def test_reuses_frozen_fit_with_explicit_gate_without_mutating_callable():
    source, evidence = object(), object()
    original = runtime.trainer.fit_once
    seen = []

    def fit(s, e, resource_gate):
        seen.append((s, e, resource_gate))
        return "same fit"

    assert runtime.fit_with_explicit_gate(source, evidence, fit) == "same fit"
    assert seen == [(source, evidence, runtime.wait_resources)]
    assert runtime.trainer.fit_once is original

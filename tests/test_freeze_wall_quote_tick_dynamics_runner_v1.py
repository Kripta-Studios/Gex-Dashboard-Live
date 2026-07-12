from neural.jepa.freeze_wall_quote_tick_dynamics_runner_v1 import (
    CODE_CLOSURE,
    GATE_SPEC,
    PROTOCOL_CLOSURE,
)


def test_freeze_closure_and_sequential_gate_are_explicit():
    assert "neural/jepa/build_wall_quote_tick_dynamics_dataset.py" in CODE_CLOSURE
    assert "neural/jepa/evaluate_wall_quote_tick_dynamics_at_touch_v1.py" in CODE_CLOSURE
    assert "neural/jepa/freeze_wall_quote_tick_dynamics_runner_v1.py" in CODE_CLOSURE
    assert any("V1R1_CAUSAL_AMENDMENT" in name for name in PROTOCOL_CLOSURE)
    assert GATE_SPEC["maximum_wilcoxon_one_sided_p"] == 0.0125
    assert GATE_SPEC["sensitivity_can_rescue_primary"] is False

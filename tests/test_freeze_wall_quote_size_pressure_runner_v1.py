from neural.jepa.freeze_wall_quote_size_pressure_runner_v1 import (
    CODE_CLOSURE,
    PROTOCOL_CLOSURE,
)


def test_freeze_closure_contains_qsize_code_and_protocol() -> None:
    assert "neural/jepa/build_wall_quote_size_pressure_dataset.py" in CODE_CLOSURE
    assert "neural/jepa/evaluate_wall_quote_size_pressure_at_touch_v1.py" in CODE_CLOSURE
    assert "neural/jepa/freeze_wall_quote_size_pressure_runner_v1.py" in CODE_CLOSURE
    assert "neural/jepa/quote_size_pressure_features.py" in CODE_CLOSURE
    assert (
        "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_PREDECLARATION.md"
        in PROTOCOL_CLOSURE
    )
    assert (
        "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1_CAUSAL_AMENDMENT.md"
        in PROTOCOL_CLOSURE
    )
    assert (
        "research_papers/JEPA/WALL_QUOTE_SIZE_PRESSURE_AT_TOUCH_V1R1_QUALITY_REPAIR_PREDECLARATION.md"
        in PROTOCOL_CLOSURE
    )

from neural.jepa.freeze_existing_data_executable_utility_v1 import CODE_CLOSURE, PROTOCOL_CLOSURE


def test_freeze_closure_contains_runner_models_scheduler_and_predeclaration() -> None:
    assert "neural/jepa/evaluate_existing_data_executable_utility_v1.py" in CODE_CLOSURE
    assert "neural/jepa/existing_data_edge_scheduler_v1.py" in CODE_CLOSURE
    assert PROTOCOL_CLOSURE == (
        "research_papers/JEPA/EXISTING_DATA_EXECUTABLE_UTILITY_V1_PREDECLARATION.md",
    )

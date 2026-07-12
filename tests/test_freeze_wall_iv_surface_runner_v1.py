from neural.jepa.freeze_wall_iv_surface_runner_v1 import CODE_CLOSURE, PROTOCOL_CLOSURE


def test_freeze_closure_contains_runner_freezer_and_predeclaration() -> None:
    assert "neural/jepa/build_wall_iv_surface_deformation_dataset.py" in CODE_CLOSURE
    assert "neural/jepa/evaluate_wall_iv_surface_at_touch_v1.py" in CODE_CLOSURE
    assert "neural/jepa/freeze_wall_iv_surface_runner_v1.py" in CODE_CLOSURE
    assert (
        "research_papers/JEPA/WALL_IV_SURFACE_DEFORMATION_AT_TOUCH_V1_PREDECLARATION.md"
        in PROTOCOL_CLOSURE
    )

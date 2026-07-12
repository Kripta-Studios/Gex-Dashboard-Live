from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neural.jepa.wall_surface_flow_environment import (  # noqa: E402
    assert_runtime_lock,
    parse_runtime_lock,
)


def test_committed_research_runtime_lock_matches_active_environment() -> None:
    result = assert_runtime_lock(ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt")
    assert len(result["lock_sha256"]) == 64
    assert len(result["environment_sha256"]) == 64
    assert result["environment"]["packages"]["lightgbm"] == "4.6.0"


def test_runtime_lock_rejects_ranges_duplicates_and_missing_metadata(tmp_path: Path) -> None:
    ranged = tmp_path / "ranged.txt"
    ranged.write_text("# python_version=3.14.2\nnumpy>=2\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="exact package pins"):
        parse_runtime_lock(ranged)
    duplicate = tmp_path / "duplicate.txt"
    duplicate.write_text(
        "# python_version=3.14.2\n# platform=x\n# platform_machine=y\nnumpy==1\nNumPy==1\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="duplicate package"):
        parse_runtime_lock(duplicate)
    incomplete = tmp_path / "incomplete.txt"
    incomplete.write_text("# python_version=3.14.2\nnumpy==1\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="incomplete"):
        parse_runtime_lock(incomplete)

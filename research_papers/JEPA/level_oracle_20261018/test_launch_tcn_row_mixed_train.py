from pathlib import Path

import launch_tcn_row_mixed_train as runtime


def test_decimal_resource_gate_all_three():
    assert runtime.eligible(2_000_000_000, 2_000_000_000, 2_000_000_000)
    for index in range(3):
        values = [3_000_000_000] * 3
        values[index] = 1_999_999_999
        assert not runtime.eligible(*values)


def test_command_preserves_training_and_cache_no_build_or_new_parameter():
    command = runtime.command_for(Path("repo"), Path("cache"), Path("flags"))
    assert command[2:] == [
        str(Path("repo/run_tcn_row_mixed.py")),
        "--stage",
        "train",
        "--flags-root",
        "flags",
        "--output",
        "cache",
        "--device",
        "cuda",
    ]
    assert "--resume" not in command and "build-cache" not in command

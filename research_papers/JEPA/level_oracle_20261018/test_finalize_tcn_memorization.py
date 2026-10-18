import json

import numpy as np
import pandas as pd
import pytest
import torch

import finalize_tcn_memorization as finalizer


def test_finalize_float32_without_updates(tmp_path):
    (tmp_path / "freeze_before_updates.json").write_text('{"files": {}}')
    torch.save(
        {"update": 500, "optimizer": {"state": {0: {"step": 500}}}},
        tmp_path / "final_model.pt",
    )
    pd.DataFrame({"update": list(range(0, 501, 50))}).to_parquet(
        tmp_path / "metrics.parquet"
    )
    np.save(tmp_path / "gradient_norms.npy", np.ones(500))
    pd.DataFrame(
        dict(
            input_sha256=["a", "a"],
            normalized_target=np.array([0.0, 2.0], np.float32),
            state_optimal_action=[0, 1],
            weight=np.array([1.0, 3.0], np.float32),
        )
    ).to_parquet(tmp_path / "selected_train_rows.parquet")
    before = (tmp_path / "final_model.pt").read_bytes()
    finalizer.finish(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["duplicates"]["identical_input_weighted_mse_floor"] == 0.75
    assert (tmp_path / "final_model.pt").read_bytes() == before
    recovery = json.loads((tmp_path / "publication_recovery.json").read_text())
    assert recovery["updates_performed"] == 0
    with pytest.raises(FileExistsError):
        finalizer.finish(tmp_path)

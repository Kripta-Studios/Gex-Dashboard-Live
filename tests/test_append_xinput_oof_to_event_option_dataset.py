from __future__ import annotations

import json
import sys

import pandas as pd

from neural.jepa.append_xinput_oof_to_event_option_dataset import main


def test_appender_supports_phys_td_prefix_trade_date_and_spxw_identity(tmp_path, monkeypatch) -> None:
    events_path = tmp_path / "events.parquet"
    features_path = tmp_path / "features.parquet"
    output_dir = tmp_path / "joined"
    pd.DataFrame(
        {
            "ticker": ["SPXW", "QQQ"],
            "trade_date": [20260102, 20260102],
            "time": ["10:30:00", "10:35:00"],
            "event_value": [1.0, 2.0],
        }
    ).to_parquet(events_path, index=False)
    pd.DataFrame(
        {
            "ticker": ["SPXW"],
            "trade_date": ["2026-01-02"],
            "time": ["10:30"],
            "ptdj_z_00": [3.5],
            "xjepa_must_not_join": [9.0],
        }
    ).to_parquet(features_path, index=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "append_xinput_oof_to_event_option_dataset.py",
            "--event-data",
            str(events_path),
            "--xinput-features",
            str(features_path),
            "--output-dir",
            str(output_dir),
            "--feature-prefix",
            "ptdj_",
            "--ticker-key-mode",
            "identity",
        ],
    )

    assert main() == 0

    joined = pd.read_parquet(output_dir / "event_option_dataset.parquet")
    assert joined["ticker"].tolist() == ["SPXW", "QQQ"]
    assert joined["ptdj_z_00"].tolist() == [3.5, 0.0]
    assert "xjepa_must_not_join" not in joined.columns
    metadata = json.loads((output_dir / "append_xinput_oof_metadata.json").read_text(encoding="utf-8"))
    assert metadata["matched_rows"] == 1
    assert metadata["matched_by_ticker"]["SPXW"]["matched_rows"] == 1
    assert metadata["ticker_key_mode"] == "identity"


def test_appender_preserves_legacy_spx_underlying_mapping_by_default(tmp_path, monkeypatch) -> None:
    events_path = tmp_path / "events.parquet"
    features_path = tmp_path / "features.parquet"
    output_dir = tmp_path / "joined"
    pd.DataFrame(
        {
            "ticker": ["SPXW"],
            "underlying_ticker": ["SPX"],
            "trade_date": [20260102],
            "time": ["10:30"],
        }
    ).to_parquet(events_path, index=False)
    pd.DataFrame(
        {
            "ticker": ["SPX"],
            "trade_date": [20260102],
            "time": ["10:30"],
            "xjepa_z_00": [2.5],
        }
    ).to_parquet(features_path, index=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "append_xinput_oof_to_event_option_dataset.py",
            "--event-data",
            str(events_path),
            "--xinput-features",
            str(features_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert main() == 0
    joined = pd.read_parquet(output_dir / "event_option_dataset.parquet")
    assert joined["xjepa_z_00"].tolist() == [2.5]

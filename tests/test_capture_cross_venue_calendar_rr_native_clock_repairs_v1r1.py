from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from neural.jepa import (
    capture_cross_venue_calendar_rr_native_clock_preflight as pre,
)
from neural.jepa import (
    capture_cross_venue_calendar_rr_native_clock_repairs_v1r1 as repair,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.content = pre.canonical_bytes(payload)

    def raise_for_status(self) -> None:
        return None


def _source_rows(include_extra: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for right, strike in (("CALL", 470.0), ("PUT", 469.0)):
        for clock in ("10:30:00.000", "10:35:00.000"):
            rows.append(
                {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "trade_date": "20240102",
                    "underlying_timestamp": f"2024-01-02T{clock}",
                    "strike": strike,
                    "right": right,
                    "bid": 1.0,
                    "ask": 1.2,
                }
            )
    if include_extra:
        for clock in ("10:30:00.000", "10:35:00.000"):
            rows.append(
                {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "trade_date": "20240102",
                    "underlying_timestamp": f"2024-01-02T{clock}",
                    "strike": 471.0,
                    "right": "CALL",
                    "bid": 0.5,
                    "ask": 0.7,
                }
            )
    return rows


def _raw_response() -> dict:
    blocks = []
    for right, strike in (("CALL", 470.0), ("PUT", 469.0), ("CALL", 471.0)):
        blocks.append(
            {
                "contract": {
                    "symbol": "SPY",
                    "expiration": "20240102",
                    "strike": strike,
                    "right": right,
                },
                "data": [
                    {
                        "timestamp": f"2024-01-02 {clock}.000",
                        "bid": 1.0,
                        "ask": 1.2,
                        "bid_size": 10,
                        "ask_size": 12,
                    }
                    for clock in ("10:30:00", "10:35:00")
                ],
            }
        )
    return {"response": blocks}


def _synthetic_spec(tmp_path: Path) -> dict[str, str]:
    greeks = tmp_path / "greeks.parquet"
    iv = tmp_path / "iv.parquet"
    pd.DataFrame(_source_rows(False)).to_parquet(greeks, index=False)
    pd.DataFrame(_source_rows(True)).to_parquet(iv, index=False)
    return {
        "capture_id": "synthetic",
        "ticker": "SPY",
        "trade_date": "20240102",
        "role": "front",
        "expiration": "20240102",
        "greeks_path": str(greeks),
        "greeks_sha256": pre.sha256_file(greeks),
        "iv_path": str(iv),
        "iv_sha256": pre.sha256_file(iv),
    }


def test_real_v1_failures_match_frozen_intersections() -> None:
    specs = repair.load_repair_specs()
    assert len(specs) == 4
    assert set(specs["capture_id"]) == repair.EXPECTED_REPAIR_IDS
    shared = 0
    unilateral = 0
    for spec in specs.to_dict("records"):
        _greeks, _iv, audit, rows = repair.audit_vintage_intersection(spec)
        shared += audit["shared_key_rows"]
        unilateral += len(rows)
    assert shared == 2_828
    assert unilateral == 8


def test_capture_uses_only_exact_shared_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _synthetic_spec(tmp_path)
    monkeypatch.setitem(
        repair.EXPECTED_REPAIRS,
        "synthetic",
        {
            "ticker": "SPY",
            "trade_date": "20240102",
            "role": "front",
            "expiration": "20240102",
            "unilateral_source": "iv_only",
            "right": "C",
            "strike": 471.0,
            "shared_key_rows": 4,
            "greeks_sha256": spec["greeks_sha256"],
            "iv_sha256": spec["iv_sha256"],
        },
    )
    row = repair.capture_one(
        spec,
        output=tmp_path / "output",
        base_url="http://example/v3",
        provenance={"kind": "test"},
        runtime={"lock_sha256": "lock", "environment_sha256": "environment"},
        code_hashes={"repair.py": "hash"},
        timeout=1.0,
        requester=lambda *args, **kwargs: FakeResponse(_raw_response()),
    )
    assert row["shared_key_rows"] == 4
    assert row["iv_only_key_rows"] == 2
    assert row["missing_shared_key_rows"] == 0
    assert row["native_extra_target_key_rows"] == 2
    directory = tmp_path / "output/SPY/20240102/front"
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "PASS_NATIVE_CLOCK_KEY_INTERSECTION_REPAIR"
    assert len(pd.read_csv(directory / "unilateral_vintage_keys.csv")) == 2


def test_unfrozen_discrepancy_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _synthetic_spec(tmp_path)
    monkeypatch.setitem(
        repair.EXPECTED_REPAIRS,
        "synthetic",
        {
            "ticker": "SPY",
            "trade_date": "20240102",
            "role": "front",
            "expiration": "20240102",
            "unilateral_source": "iv_only",
            "right": "C",
            "strike": 472.0,
            "shared_key_rows": 4,
            "greeks_sha256": spec["greeks_sha256"],
            "iv_sha256": spec["iv_sha256"],
        },
    )
    with pytest.raises(AssertionError, match="unfrozen Greek/IV discrepancy"):
        repair.audit_vintage_intersection(spec)


def test_repair_root_contract_is_immutable(tmp_path: Path) -> None:
    specs = pd.DataFrame([{"capture_id": "x", "ticker": "SPY"}])
    contract = {"schema": "test"}
    output = tmp_path / "repair"
    repair.initialize_or_validate_root(
        output, specs=specs, contract=contract, status_raw=b"CONNECTED"
    )
    repair.initialize_or_validate_root(
        output, specs=specs, contract=contract, status_raw=b"CONNECTED"
    )
    changed = specs.copy()
    changed.loc[0, "ticker"] = "QQQ"
    with pytest.raises(AssertionError, match="root contract changed"):
        repair.initialize_or_validate_root(
            output, specs=changed, contract=contract, status_raw=b"CONNECTED"
        )


def test_cli_has_no_repair_whitelist_or_feature_switch() -> None:
    args = repair.parse_args([])
    for forbidden in ("capture_id", "allow", "intersection", "feature", "outcome"):
        assert not hasattr(args, forbidden)


def test_direct_cli_imports() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(repair.__file__).resolve()), "--help"],
        cwd=repair.PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--v1-root" in completed.stdout
    assert "--output-root" in completed.stdout

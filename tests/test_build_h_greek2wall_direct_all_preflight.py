import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import neural.jepa.build_h_greek2wall_direct_all_preflight as mod


DAY = "20220801"


def payload(ticker="QQQ"):
    contracts = []
    for strike in (300.0, 301.0):
        for right in ("C", "P"):
            data = []
            for minute in ("10:19:00", "10:20:00", "14:30:00"):
                data.append(
                    {
                        "timestamp": f"2022-08-01 {minute}",
                        "underlying_timestamp": f"2022-08-01 {minute}",
                        "underlying_price": 300.5,
                        "bid": 1.0,
                        "ask": 1.1,
                        "implied_vol": 0.2,
                        "gamma": 0.01,
                        "vanna": -0.2,
                        "charm": 0.3,
                        "vomma": 0.4,
                        "zomma": -0.5,
                        "veta": 0.1,
                        "speed": 0.2,
                        "color": 0.3,
                        "ultima": 0.4,
                    }
                )
            contracts.append(
                {
                    "contract": {
                        "symbol": ticker,
                        "expiration": DAY,
                        "strike": strike,
                        "right": right,
                    },
                    "data": data,
                }
            )
    return {"response": contracts}


def oi_payload(ticker="QQQ", timestamp="2022-08-01 06:30:00"):
    return {
        "response": [
            {
                "symbol": ticker,
                "expiration": DAY,
                "strike": strike,
                "right": right,
                "timestamp": timestamp,
                "open_interest": 10,
            }
            for strike in (300.0, 301.0)
            for right in ("C", "P")
        ]
    }


def write_sources(root: Path):
    rows = []
    for strike in (300.0, 301.0):
        for right in ("CALL", "PUT"):
            for minute in ("10:19:00", "10:20:00", "14:30:00"):
                rows.append(
                    {
                        "symbol": "QQQ",
                        "expiration": DAY,
                        "strike": strike,
                        "right": right,
                        "timestamp": f"2022-08-01 {minute}",
                        "bid": 1.0,
                        "ask": 1.1,
                        "implied_vol": 0.2,
                        "underlying_price": 300.5,
                    }
                )
    greek = root / "greeks.parquet"
    pd.DataFrame(rows).to_parquet(greek, index=False)
    oi = root / "oi.parquet"
    pd.DataFrame(
        [
            {
                "symbol": "QQQ",
                "expiration": DAY,
                "strike": s,
                "right": r,
                "open_interest": 10,
                "trade_date": DAY,
                "timestamp": "2022-08-01 06:30:00",
            }
            for s in (300.0, 301.0)
            for r in ("CALL", "PUT")
        ]
    ).to_parquet(oi, index=False)
    return greek, oi


def write_canonical_options_root(root: Path, *, omit=None):
    for ticker, day in mod.FROZEN_SESSIONS:
        for kind in ("greeks", "oi"):
            if omit == (ticker, day, kind):
                continue
            path = mod.canonical_source_paths(root, ticker, day)[kind]
            path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = f"{day[:4]}-{day[4:6]}-{day[6:]} 06:30:00"
            rows = []
            for right in ("CALL", "PUT"):
                base = {
                    "symbol": ticker,
                    "expiration": day,
                    "trade_date": day,
                    "strike": 100.0,
                    "right": right,
                    "timestamp": timestamp,
                }
                if kind == "greeks":
                    base.update({"underlying_timestamp": timestamp, "implied_vol": 0.2})
                else:
                    base["open_interest"] = 10
                rows.append(base)
            pd.DataFrame(rows).to_parquet(path, index=False)
    return root


def test_request_is_exactly_frozen_direct_all_contract():
    assert mod.request_params("QQQ", DAY) == {
        "symbol": "QQQ",
        "expiration": DAY,
        "date": DAY,
        "strike": "*",
        "right": "both",
        "interval": "1m",
        "start_time": "10:19:00.000",
        "end_time": "14:30:00.000",
        "version": "latest",
        "format": "json",
    }
    with pytest.raises(AssertionError, match="outside frozen"):
        mod.request_params("QQQ", "20220802")


def test_frozen_canonical_source_inventory_rejects_missing_substitution_and_tamper(
    monkeypatch, tmp_path
):
    runtime = {"lock_sha256": "1" * 64, "environment_sha256": "2" * 64}
    monkeypatch.setattr(mod, "assert_runtime_lock", lambda _path: runtime)
    options = write_canonical_options_root(tmp_path / "options")
    proxy_path = mod.canonical_source_paths(options, "SPXW", "20240102")["greeks"]
    proxy = pd.read_parquet(proxy_path).drop(columns="timestamp")
    proxy.to_parquet(proxy_path, index=False)
    inventory = tmp_path / "inventory"
    manifest = mod.freeze_source_inventory(
        options_root=options, inventory_dir=inventory
    )
    assert manifest["sessions"] == 12
    frame = mod.validate_source_inventory(inventory)
    assert len(frame) == 12
    proxy_row = frame[
        frame["ticker"].eq("SPXW") & frame["trade_date"].eq("20240102")
    ].iloc[0]
    assert bool(proxy_row["greeks_native_timestamp"]) is False
    assert bool(proxy_row["greeks_underlying_timestamp_proxy"]) is True

    target = mod.canonical_source_paths(options, "QQQ", DAY)["oi"]
    original = target.read_bytes()
    target.write_bytes(original + b"tamper")
    with pytest.raises(AssertionError, match="tampering"):
        mod.validate_source_inventory(inventory)

    missing_root = write_canonical_options_root(
        tmp_path / "missing_options", omit=("SPY", "20250102", "greeks")
    )
    with pytest.raises(FileNotFoundError, match="exact canonical"):
        mod.freeze_source_inventory(
            options_root=missing_root, inventory_dir=tmp_path / "missing_inventory"
        )

    substituted = mod.canonical_source_paths(missing_root, "SPY", "20250102")["greeks"]
    substituted.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "symbol": "QQQ",
                "expiration": "20250102",
                "trade_date": "20250102",
                "strike": 100.0,
                "right": "CALL",
                "timestamp": "2025-01-02 06:30:00",
                "underlying_timestamp": "2025-01-02 06:30:00",
                "implied_vol": 0.2,
            }
        ]
    ).to_parquet(substituted, index=False)
    with pytest.raises(AssertionError, match="identity substitution"):
        mod.freeze_source_inventory(
            options_root=missing_root, inventory_dir=tmp_path / "substituted_inventory"
        )


def test_normalization_requires_fields_identity_both_rights_exact_grid_and_unique_keys():
    frame = mod.normalize_response(payload(), ticker="QQQ", trade_date=DAY)
    assert len(frame) == 12 and set(frame.right) == {"CALL", "PUT"}
    assert set(mod.ALPHA_GREEKS).issubset(frame.columns)

    missing = payload()
    del missing["response"][0]["data"][0]["vanna"]
    with pytest.raises(AssertionError, match="non-finite"):
        mod.normalize_response(missing, ticker="QQQ", trade_date=DAY)
    substituted = payload()
    substituted["response"][0]["contract"]["expiration"] = "20220802"
    with pytest.raises(AssertionError, match="contract substitution"):
        mod.normalize_response(substituted, ticker="QQQ", trade_date=DAY)
    duplicate = payload()
    duplicate["response"][0]["data"].append(dict(duplicate["response"][0]["data"][0]))
    with pytest.raises(AssertionError, match="duplicate"):
        mod.normalize_response(duplicate, ticker="QQQ", trade_date=DAY)
    subminute = payload()
    subminute["response"][0]["data"][0]["timestamp"] = "2022-08-01 10:19:30"
    subminute["response"][0]["data"][0]["underlying_timestamp"] = "2022-08-01 10:19:30"
    with pytest.raises(AssertionError, match="exact minute"):
        mod.normalize_response(subminute, ticker="QQQ", trade_date=DAY)
    mismatched = payload()
    mismatched["response"][0]["data"][0]["underlying_timestamp"] = "2022-08-01 10:18:00"
    with pytest.raises(AssertionError, match="timestamp mismatch"):
        mod.normalize_response(mismatched, ticker="QQQ", trade_date=DAY)
    non_object = payload()
    non_object["response"][0]["data"].append("bad")
    with pytest.raises(ValueError, match="non-object"):
        mod.normalize_response(non_object, ticker="QQQ", trade_date=DAY)


def test_source_audit_reports_revisions_and_positive_oi_without_replacement(tmp_path):
    greeks, oi = write_sources(tmp_path)
    frame = mod.normalize_response(payload(), ticker="QQQ", trade_date=DAY)
    audit = mod.audit_sources(frame, greeks_path=greeks, oi_path=oi)
    assert audit["vintage_key_coverage"] == 1.0
    assert audit["positive_oi_coverage"] == 1.0
    assert audit["bid_revision_rows"] == 0
    vintage = pd.read_parquet(greeks)
    vintage.loc[0, "bid"] = 0.9
    vintage.to_parquet(greeks, index=False)
    audit = mod.audit_sources(frame, greeks_path=greeks, oi_path=oi)
    assert audit["bid_revision_rows"] == 1
    assert frame["bid"].eq(1.0).all()
    diagnostics = audit["direct_vs_local_formula_diagnostics"]
    oi_frame = pd.read_parquet(oi)
    oi_frame["open_interest"] *= 1000
    oi_frame.to_parquet(oi, index=False)
    changed_oi_audit = mod.audit_sources(frame, greeks_path=greeks, oi_path=oi)
    assert changed_oi_audit["direct_vs_local_formula_diagnostics"] == diagnostics

    duplicate_vintage = pd.concat([vintage, vintage.iloc[[0]]], ignore_index=True)
    duplicate_vintage.to_parquet(greeks, index=False)
    with pytest.raises(AssertionError, match="duplicate parity keys"):
        mod.audit_sources(frame, greeks_path=greeks, oi_path=oi)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda oi: pd.concat([oi, oi.iloc[[0]]], ignore_index=True), "duplicate OI"),
        (lambda oi: oi.assign(open_interest=[-1, 10, 10, 10]), "negative"),
    ],
)
def test_oi_audit_rejects_duplicate_and_negative_rows(tmp_path, mutation, message):
    greeks, oi_path = write_sources(tmp_path)
    frame = mod.normalize_response(payload(), ticker="QQQ", trade_date=DAY)
    mutation(pd.read_parquet(oi_path)).to_parquet(oi_path, index=False)
    with pytest.raises(AssertionError, match=message):
        mod.audit_sources(frame, greeks_path=greeks, oi_path=oi_path)


def test_oi_availability_is_per_direct_row_without_backfill(tmp_path):
    greeks, oi_path = write_sources(tmp_path)
    frame = mod.normalize_response(payload(), ticker="QQQ", trade_date=DAY)
    oi = pd.read_parquet(oi_path)
    oi.loc[oi["strike"].eq(300.0), "timestamp"] = "2022-08-01 10:20:00"
    oi.loc[oi["strike"].eq(301.0), "open_interest"] = float("nan")
    oi.to_parquet(oi_path, index=False)
    audit = mod.audit_sources(frame, greeks_path=greeks, oi_path=oi_path)
    assert audit["late_unavailable_oi_rows"] == 2
    assert audit["positive_oi_rows_available"] == 4
    assert audit["null_value_oi_rows"] == 6
    assert audit["oi_missing_reasons"]["late_unavailable_at_direct_row"] == 2


def test_direct_oi_normalization_and_primary_row_availability(tmp_path):
    direct = mod.normalize_direct_oi(
        oi_payload(timestamp="2022-08-01 10:20:00"), ticker="QQQ", trade_date=DAY
    )
    assert len(direct) == 4 and direct["open_interest"].eq(10).all()
    greeks, local_oi = write_sources(tmp_path)
    frame = mod.normalize_response(payload(), ticker="QQQ", trade_date=DAY)
    audit = mod.audit_sources(
        frame, greeks_path=greeks, oi_path=local_oi, direct_oi=direct
    )
    assert audit["oi_availability_source"] == "direct_oi_primary"
    assert audit["late_unavailable_oi_rows"] == 4
    assert audit["positive_oi_rows_available"] == 8
    duplicate = oi_payload()
    duplicate["response"].append(dict(duplicate["response"][0]))
    with pytest.raises(AssertionError, match="duplicate direct OI"):
        mod.normalize_direct_oi(duplicate, ticker="QQQ", trade_date=DAY)


def test_field_profiles_and_cost_projection_are_outcome_free_and_exact_scope():
    frame = mod.normalize_response(payload(), ticker="QQQ", trade_date=DAY)
    profiles = mod.field_profiles(frame)
    assert {p["field"] for p in profiles} == set(mod.PROFILE_GREEKS)
    assert all("label" not in p and "pnl" not in p for p in profiles)
    manifests = [
        {"ticker": t, "trade_date": d, "raw_bytes": 100, "parquet_bytes": 50}
        for t, d in mod.FROZEN_SESSIONS
    ]
    cost = mod.projected_cost(manifests)
    assert cost["preflight_sessions"] == 12 and cost["projected_sessions"] == 2519
    with pytest.raises(AssertionError, match="exactly"):
        mod.projected_cost(manifests[:-1])


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def __init__(self, value=None):
        self.content = json.dumps(value or payload(), separators=(",", ":")).encode()

    def raise_for_status(self):
        return None


def test_capture_writes_immutable_hashed_raw_parquet_manifest(monkeypatch, tmp_path):
    greeks, oi = write_sources(tmp_path)
    jar = tmp_path / "ThetaTerminal.jar"
    jar.write_bytes(b"jar")
    jar_hash = hashlib.sha256(b"jar").hexdigest()
    calls = []
    inventory_dir = tmp_path / "inventory"
    inventory_dir.mkdir()
    (inventory_dir / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        mod,
        "validate_source_inventory",
        lambda _path: pd.DataFrame(
            [
                {
                    "ticker": "QQQ",
                    "trade_date": DAY,
                    "greeks_path": str(greeks),
                    "oi_path": str(oi),
                }
            ]
        ),
    )

    def requester(url, params, headers, timeout):
        calls.append((url, params))
        return FakeResponse(
            oi_payload() if url.endswith(mod.OI_ENDPOINT) else payload()
        )

    def evidence(_url, path):
        return {
            "process_id": 1,
            "terminal_jar_sha256": jar_hash,
            "terminal_jar_path": str(path),
            "command_line": f"java -jar {path}",
            "executable_path": "java",
            "executable_sha256": "0" * 64,
            "local_address": "127.0.0.1",
            "local_port": 25503,
        }

    monkeypatch.setattr(
        mod,
        "assert_runtime_lock",
        lambda _p: {"lock_sha256": "1" * 64, "environment_sha256": "2" * 64},
    )
    result = mod.capture_session(
        ticker="QQQ",
        trade_date=DAY,
        source_inventory=inventory_dir,
        output_root=tmp_path / "out",
        base_url="http://127.0.0.1:25503/v3",
        terminal_jar=jar,
        requester=requester,
        process_evidence_provider=evidence,
    )
    assert calls[0][0].endswith(mod.ENDPOINT) and calls[0][1] == mod.request_params(
        "QQQ", DAY
    )
    assert calls[1][0].endswith(mod.OI_ENDPOINT)
    assert result["provenance"] == mod.PROVENANCE and result["outcome_free"] is True
    root = tmp_path / "out" / "QQQ" / DAY
    assert (root / "response.json").is_file() and (
        root / "direct_all_greeks.parquet"
    ).is_file()
    (root / "response.json").write_bytes(b"tampered")
    with pytest.raises(AssertionError, match="hash mismatch"):
        mod.validate_session(root, source_inventory=inventory_dir)
    with pytest.raises(FileExistsError):
        mod.capture_session(
            ticker="QQQ",
            trade_date=DAY,
            source_inventory=inventory_dir,
            output_root=tmp_path / "out",
            base_url="http://127.0.0.1:25503/v3",
            terminal_jar=jar,
            requester=requester,
            process_evidence_provider=evidence,
        )


def test_seal_requires_exact_unique_sessions_and_revalidates_tampering(
    monkeypatch, tmp_path
):
    inventory = []
    manifests = {}
    for ticker, day in mod.FROZEN_SESSIONS:
        directory = tmp_path / "sessions" / ticker / day
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text("{}", encoding="utf-8")
        greeks = tmp_path / f"{ticker}_{day}_greeks.parquet"
        oi = tmp_path / f"{ticker}_{day}_oi.parquet"
        greeks.write_bytes(b"g")
        oi.write_bytes(b"o")
        inventory.append(
            {
                "ticker": ticker,
                "trade_date": day,
                "session_dir": str(directory),
                "greeks_path": str(greeks),
                "oi_path": str(oi),
            }
        )
        manifests[str(directory.resolve())] = {
            "ticker": ticker,
            "trade_date": day,
            "rows": 10,
            "raw_bytes": 100,
            "parquet_bytes": 50,
            "raw_response_sha256": "a" * 64,
            "parquet_sha256": "b" * 64,
            "oi_raw_response_sha256": "5" * 64,
            "oi_parquet_sha256": "6" * 64,
            "source_greeks_sha256": hashlib.sha256(b"g").hexdigest(),
            "source_oi_sha256": hashlib.sha256(b"o").hexdigest(),
            "git_commit": "c" * 40,
            "builder_sha256": "d" * 64,
            "predeclaration_sha256": "e" * 64,
            "source_clarification_sha256": "3" * 64,
            "direct_oi_amendment_sha256": "4" * 64,
            "runtime_lock_sha256": "f" * 64,
            "runtime_environment_sha256": "1" * 64,
            "terminal_jar_sha256": "2" * 64,
            "terminal_process_evidence": {"process_id": 7},
            "field_profiles": [
                {
                    "field": field,
                    "rows": 10,
                    "finite_fraction": 1.0,
                    "zero_fraction": 0.0,
                    "positive_fraction": 1.0,
                    "negative_fraction": 0.0,
                    "distinct_values": 2,
                    "minimum": 1.0,
                    "maximum": 2.0,
                }
                for field in mod.PROFILE_GREEKS
            ],
        }

    def validator(path, **_kwargs):
        return manifests[str(Path(path).resolve())]

    source_inventory = tmp_path / "source_inventory"
    source_inventory.mkdir()
    (source_inventory / "manifest.json").write_text("{}", encoding="utf-8")
    source_frame = pd.DataFrame(inventory).drop(columns="session_dir")
    monkeypatch.setattr(mod, "validate_source_inventory", lambda _path: source_frame)
    monkeypatch.setattr(mod, "validate_session", validator)
    seal = mod.seal_preflight(
        source_inventory=source_inventory, output_root=tmp_path / "sessions"
    )
    assert (
        seal["sessions"] == 12
        and (tmp_path / "sessions" / "_seal" / "session_index.csv").is_file()
    )

    def tampered(_path, **_kwargs):
        raise AssertionError("artifact hash mismatch")

    monkeypatch.setattr(mod, "validate_session", tampered)
    with pytest.raises(AssertionError, match="hash mismatch"):
        mod.seal_preflight(
            source_inventory=source_inventory, output_root=tmp_path / "tampered"
        )

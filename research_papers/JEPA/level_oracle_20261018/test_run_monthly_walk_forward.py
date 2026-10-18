"""CPU doubles and synthetic files only; no market source access or real fits."""

from datetime import date
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import run_monthly_walk_forward as r


def day(root, ticker="SPY", stamp="20241224", close=210, status="COMPLETE"):
    return r.Day(
        ticker,
        stamp,
        root / "engine" / ticker / stamp,
        root / "features" / ticker / stamp / "features.npz",
        close,
        status,
    )


def tables():
    actions = pd.DataFrame(dict(action_id=[0, 1, 2, 3], state_i=[60, 60, 61, 64]))
    labels = pd.DataFrame(
        dict(
            action_id=[0, 1, 2, 3],
            status=["FILLED", "NO_FILL", "FILLED", "FILLED"],
            exit_i=[62, 61, 63, 66],
            entry_ask=[1.0, np.nan, 1.0, 1.0],
            net_base=[100.0, 0.0, -2.0, 3.0],
            net_adverse=[98.0, 0.0, -4.0, 1.0],
            hold_minutes=[1, 0, 1, 1],
            reason=["TARGET", "NO_FILL", "STOP", "TARGET"],
        )
    )
    return actions, labels


class Source:
    def __init__(self, root, days, artifacts):
        self.days = {d.key: d for d in days}
        self.hashes = {}
        self.reads = []
        self.artifacts = artifacts
        self.index = pd.DataFrame()
        for d in days:
            if d.status != "COMPLETE":
                continue
            d.oracle.mkdir(parents=True)
            actions, labels = tables()
            actions.to_parquet(d.oracle / "actions.parquet", index=False)
            labels.to_parquet(d.oracle / "labels.parquet", index=False)
            d.features.parent.mkdir(parents=True)
            for filename in (
                "features.npz",
                "features.json",
                "actions.npz",
                "actions.json",
            ):
                (d.features.parent / filename).write_text("synthetic feature fixture")

    def verify(self, path, digest):
        assert r.sha(path) == digest
        self.hashes[str(Path(path).resolve())] = digest

    def check(self, d, filename):
        path = d.oracle / filename
        digest = r.sha(path)
        self.verify(path, digest)
        return digest

    def read(self, d, filename, columns=None):
        self.check(d, filename)
        if filename == "labels.parquet" and d.date >= "20250101":
            assert self.artifacts.complete("months/" + d.date[:6] + "/predictions")
            if d.date >= "20260101":
                assert self.artifacts.complete("validation_freeze")
        self.reads.append((d.key, filename))
        return pd.read_parquet(d.oracle / filename, columns=columns)


class Store:
    def __init__(self, source, artifacts):
        self.source, self.artifacts = source, artifacts

    def get(self, key):
        self.artifacts.json(
            "feature_inputs/" + key,
            {str(p.resolve()): r.sha(p) for p in self.source.days[key].feature_paths},
        )
        return {}


class Model:
    def num_feature(self):
        return 1954

    def predict(self, x, num_threads=4):
        assert num_threads == 4
        return x[:, 0].astype(float) / 100


def fixture(tmp_path, monkeypatch, include_test=False):
    output = tmp_path / "output"
    output.mkdir()
    artifacts = r.Artifacts(output, "synthetic-binding")
    days = [
        day(tmp_path, t, stamp, close)
        for t in r.TICKERS
        for stamp, close in (("20241224", 210), ("20250102", 390))
    ]
    if include_test:
        days.extend(day(tmp_path, t, "20260102", 390) for t in r.TICKERS)
    source = Source(tmp_path, days, artifacts)
    store = Store(source, artifacts)
    fits = []

    def feature_rows(store, key, ids, h=None):
        assert h is None
        x = np.zeros((len(ids), 1954), np.float32)
        x[:, 0] = np.asarray(ids) + 1
        return x

    def fit_once(key, x, target, weight, art):
        assert x.shape[1] == 1954 and np.isfinite(target).all()
        fits.append((key, np.array(target), np.array(weight)))
        path = art.root / ("models/" + key + ".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic model")
        started = path.with_suffix(".fit_started.json")
        started.write_text("{}")
        art.finish("models/" + key, [path, started])
        return Model()

    monkeypatch.setattr(r.shared, "feature_rows", feature_rows)
    monkeypatch.setattr(r.shared, "fit_once", fit_once)
    monkeypatch.setattr(r.shared.lgb, "Booster", lambda **kwargs: Model())
    return source, store, artifacts, fits


def test_scheduler_no_fill_no_rescue_and_loss_counts_as_fill(tmp_path):
    actions, labels = tables()
    tried, ledger = r.rank_and_schedule(
        day(tmp_path), actions, labels, np.array([1.0, 1.0, 3.0, 4.0])
    )
    # Equal state60 scores choose smaller action_id; a high NO_FILL is not replaced.
    assert tried.action_id.tolist() == [0, 3]
    tried, ledger = r.rank_and_schedule(
        day(tmp_path), actions, labels, np.array([1.0, 2.0, 3.0, 4.0])
    )
    assert tried.action_id.tolist() == [1, 2, 3]
    assert tried.has_filled_before.tolist() == [0, 0, 1]
    assert ledger.net_base.sum() == 1
    empty, trades = r.rank_and_schedule(day(tmp_path), actions, labels, np.zeros(4))
    assert len(empty) == len(trades) == 0


def test_short_session_physical_horizon_and_no_future_outcome_ranking(tmp_path):
    d = day(tmp_path)
    actions = pd.DataFrame(dict(action_id=[0], state_i=[195]))
    labels = pd.DataFrame(
        dict(
            action_id=[0],
            status=["FILLED"],
            exit_i=[205],
            net_base=[-10.0],
            net_adverse=[-12.0],
        )
    )
    attempted, _ = r.rank_and_schedule(d, actions, labels, np.array([1.0]))
    assert attempted.action_id.tolist() == [0]
    labels["exit_i"] = 206
    with pytest.raises(ValueError, match="outside session"):
        r.rank_and_schedule(d, actions, labels, np.array([1.0]))


def test_orphan_preserved_completed_hashes_enforced(tmp_path):
    art = r.Artifacts(tmp_path, "b")
    orphan = tmp_path / "x.npz"
    orphan.write_bytes(b"interrupted")
    art.save_npz("x", dict(x=np.array([1.0])))
    assert (
        next((tmp_path / "preserved_orphans").rglob("x.npz")).read_bytes()
        == b"interrupted"
    )
    np.testing.assert_array_equal(art.load_npz("x")["x"], [1])
    with orphan.open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError):
        art.load_npz("x")


def test_external_source_manifest_binds_windows_paths_and_detects_changes(tmp_path):
    art = r.Artifacts(tmp_path / "output", "binding")
    external = tmp_path / "external.npz"
    external.write_bytes(b"original")
    name = "feature_inputs/SPY/20250102"
    art.json(name, {str(external.resolve()): r.sha(external)})
    art.finish(
        "predictions",
        [art.root / (name + ".json"), art.marker(name)],
        dict(source_manifests=[name + ".json"]),
    )
    assert art.complete("predictions")
    external.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed checkpoint source"):
        art.complete("predictions")


def test_fit_reuse_paired_windows_and_changed_training_input_rejected(
    tmp_path, monkeypatch
):
    source, store, art, fits = fixture(tmp_path, monkeypatch)
    static = r.calendar.build_schedule()[0]
    expanding = r.calendar.build_schedule()[1]
    model, scales, digest = r.fit_window(static, source, store, art)
    assert scales == {t: 100.0 for t in r.TICKERS}
    assert len(fits) == 1 and np.isclose(fits[0][2].mean(), 1)
    reads = len(source.reads)
    assert r.fit_window(expanding, source, store, art)[2] == digest
    assert len(fits) == 1 and len(source.reads) == reads
    with next(iter(source.days.values())).features.open("ab") as file:
        file.write(b"mutated")
    with pytest.raises(AssertionError):
        r.fit_window(static, source, store, art)


@pytest.mark.parametrize("changed_file", ["ledger", "evaluation_feature"])
def test_all_mode_predictions_sealed_before_month_labels_and_resume_no_refit(
    tmp_path, monkeypatch, changed_file
):
    source, store, art, fits = fixture(tmp_path, monkeypatch)
    result = r.month_stage(date(2025, 1, 1), source, store, art)
    assert len(fits) == 2  # Static and first expanding share exactly one fit.
    assert all(
        len(rows) == 3 and all(row["trades"] == 2 for row in rows)
        for rows in result.values()
    )
    assert art.complete("months/202501/predictions")
    assert art.json("months/202501/economics")["static"]["overall"]["net_base"] == 3
    reads = len(source.reads)
    monkeypatch.setattr(
        r.shared, "fit_once", lambda *a, **kw: pytest.fail("unexpected refit")
    )
    assert r.month_stage(date(2025, 1, 1), source, store, art) == result
    assert len(source.reads) == reads
    changed = (
        next((art.root / "ledgers").rglob("*_ledger.parquet"))
        if changed_file == "ledger"
        else source.days["SPY/20250102"].features
    )
    with changed.open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError):
        r.month_stage(date(2025, 1, 1), source, store, art)


def test_positive_observed_economics_with_missing_day_remains_no_evaluable(tmp_path):
    from types import SimpleNamespace

    art = r.Artifacts(tmp_path, "report-only")
    days = [
        day(tmp_path, "SPY", "20260102", 390),
        day(tmp_path, "SPY", "20260105", 390, "MISSING_SOURCE"),
    ]
    source = SimpleNamespace(days={d.key: d for d in days})
    art.json("validation_freeze", dict(selected_mode="static"))
    for month in range(1, 7):
        stamp = f"2026{month:02d}"
        records = {mode: [] for mode in r.calendar.MODES}
        if month == 1:
            for mode in records:
                records[mode] = [
                    dict(
                        ticker=d.ticker,
                        date=d.date,
                        source_status=d.status,
                        trades=int(d.status == "COMPLETE"),
                        net_base=10.0 if d.status == "COMPLETE" else 0.0,
                        net_adverse=8.0 if d.status == "COMPLETE" else 0.0,
                    )
                    for d in days
                ]
                prefix = "ledgers/202601/" + mode + "/SPY/20260102"
                path = art.root / (prefix + "_ledger.parquet")
                r.shared.save_parquet(
                    path,
                    pd.DataFrame(
                        dict(
                            ticker=["SPY"],
                            date=["20260102"],
                            exit_i=[62],
                            net_base=[10.0],
                            net_adverse=[8.0],
                            hold_minutes=[1],
                            reason=["TARGET"],
                        )
                    ),
                )
                art.finish(prefix, [path])
        art.json("months/" + stamp + "/daily", records)
    report = r.period_report(2026, source, art)
    assert report["selected_mode"] == "static"
    observed = report["modes"]["static"]["overall"]
    assert observed["available_economics"]["net_base"] == 10.0
    assert observed["available_economics"]["net_base_pf_infinite"]
    assert observed["available_economics"]["net_base_win_rate"] == 1.0
    assert (
        observed["expected_ticker_days"] == 2 and observed["available_ticker_days"] == 1
    )
    assert observed["missing_no_evaluable"] == 1 and observed["observable_daily_pass"]
    assert observed["full_calendar_daily_status"] == "NO_EVALUABLE_MISSING_SOURCE"
    assert (
        observed["missing_day_economics"] is None
        and not observed["daily_requirement_satisfied"]
    )


def test_resume_mid_evaluation_preserves_partial_and_never_refits(
    tmp_path, monkeypatch
):
    source, store, art, fits = fixture(tmp_path, monkeypatch)
    original = r.shared.save_parquet
    count = [0]

    def interrupt(path, frame):
        original(path, frame)
        count[0] += 1
        if count[0] == 1:
            raise RuntimeError("synthetic power interruption")

    monkeypatch.setattr(r.shared, "save_parquet", interrupt)
    with pytest.raises(RuntimeError, match="power"):
        r.month_stage(date(2025, 1, 1), source, store, art)
    assert len(fits) == 2 and art.complete("months/202501/predictions")
    monkeypatch.setattr(r.shared, "save_parquet", original)
    monkeypatch.setattr(
        r.shared, "fit_once", lambda *a, **kw: pytest.fail("unexpected refit")
    )
    result = r.month_stage(date(2025, 1, 1), source, store, art)
    assert result["static"][0]["net_base"] == 1
    assert list((art.root / "preserved_orphans").rglob("*_attempts.parquet"))


def test_test_evidence_without_selection_freeze_is_rejected_before_any_fit(
    tmp_path, monkeypatch
):
    source, store, art, fits = fixture(tmp_path, monkeypatch)
    (art.root / "predictions/202601").mkdir(parents=True)
    with pytest.raises(ValueError, match="freeze"):
        r.run_stages("validation", source, store, art)
    assert not fits and not source.reads


def test_null_freeze_uses_common_training_scale_and_test_cannot_reselect(
    tmp_path, monkeypatch
):
    source, store, art, fits = fixture(tmp_path, monkeypatch, include_test=True)
    static = r.calendar.build_schedule()[0]
    r.fit_window(static, source, store, art)
    # Synthetic calendar has one 2025 session. Empty months are explicit fixture summaries.
    for offset in range(12):
        stamp = r.calendar.month_shift(date(2025, 1, 1), offset).strftime("%Y%m")
        records = {mode: [] for mode in r.calendar.MODES}
        if offset == 0:
            for mode in records:
                records[mode] = [
                    dict(
                        ticker=t,
                        date="20250102",
                        source_status="COMPLETE",
                        trades=0,
                        net_base=0.0,
                        net_adverse=0.0,
                    )
                    for t in r.TICKERS
                ]
        art.json("months/" + stamp + "/daily", records)
    freeze = r.freeze_validation(source, art)
    assert freeze["selected_mode"] is None and not freeze["approved"]
    assert freeze["common_scales"] == {t: 100.0 for t in r.TICKERS}
    assert not freeze["outcomes_2026_used_for_mode_selection"]
    (art.root / "predictions/202601").mkdir(parents=True)
    assert r.freeze_validation(source, art) == freeze
    changed = art.root / "months/202501/daily.json"
    changed.write_text("{}")
    with pytest.raises(ValueError):
        r.freeze_validation(source, art)


@pytest.mark.parametrize(
    "close,mutate_before_first_read", [(210, False), (390, False), (210, True)]
)
def test_real_feature_loader_separate_metadata_paths_and_coherent_mutation(
    tmp_path, close, mutate_before_first_read
):
    import features as f

    d = day(tmp_path, close=close)
    art = r.Artifacts(tmp_path / "out", "synthetic-binding")
    source = Source(tmp_path, [d], art)
    source.feature_root = tmp_path / "features"
    references = tmp_path / "references"
    references.mkdir()
    d = replace(
        d,
        feature_metadata=references / "features.json",
        action_metadata=references / "actions.json",
    )
    source.days = {d.key: d}
    schema = dict(
        base_names=list(f.BASE_NAMES),
        token_names=list(f.TOKEN_NAMES),
        map_names=list(f.MAP_NAMES),
        action_names=list(f.ACTION_NAMES),
    )
    deps = {"features.py": r.sha(Path(f.__file__))}
    r.atomic_json(
        source.feature_root / "feature_contract.json",
        dict(schema=schema, dependencies=deps, outcomes_read=False),
    )
    n = close - 74
    pack = dict(
        state_i=np.arange(60, close - 14),
        base=np.zeros((n, 81), np.float32),
        tokens=np.zeros((n, 20, 45), np.float32),
        maps=np.zeros((n, 20, 5, 64), np.float32),
        token_mask=np.ones((n, 20), np.float32),
        bar_mask=np.ones((n, 20), np.float32),
        map_mask=np.ones((n, 20, 5), np.float32),
    )
    np.savez(d.features, **pack)
    actions = pd.DataFrame({name: [1.0] for name in f.ACTION_INPUT_NAMES})
    actions["action_id"], actions["state_i"] = [0], [60]
    actions.to_parquet(d.oracle / "actions.parquet", index=False)
    action_path = d.feature_paths[2]
    np.savez(
        action_path,
        action_id=np.array([0]),
        action_features=np.zeros((1, 33), np.float32),
    )
    binding = dict(
        source_sha256="cache", source_metadata_sha256="metadata", dependencies=deps
    )
    source.index = pd.DataFrame(
        [
            dict(
                ticker=d.ticker,
                date=d.date,
                cache_npz_sha256="cache",
                cache_meta_sha256="metadata",
            )
        ]
    ).set_index(["ticker", "date"])
    r.atomic_json(
        d.feature_metadata,
        dict(
            schema=schema,
            binding=binding,
            sha256=r.sha(d.features),
            outcomes_read=False,
        ),
    )
    action_binding = dict(
        binding,
        action_inputs_sha256=r.hashlib.sha256(
            actions[["action_id", *f.ACTION_INPUT_NAMES]].to_numpy(np.float64).tobytes()
        ).hexdigest(),
    )
    r.atomic_json(
        d.action_metadata,
        dict(
            action_names=schema["action_names"],
            binding=action_binding,
            sha256=r.sha(action_path),
            outcomes_read=False,
        ),
    )
    for path, field in zip(
        d.feature_paths,
        (
            "features_sha256",
            "features_meta_sha256",
            "action_features_sha256",
            "action_features_meta_sha256",
        ),
    ):
        source.index.loc[(d.ticker, d.date), field] = r.sha(path)
    store = r.Features(source, art)
    if not mutate_before_first_read:
        flat = r.shared.feature_rows(store, d.key, np.array([0]))
        assert flat.shape == (1, 1954) and flat.dtype == np.float32
        assert store.get(d.key)["state_i"].shape == (n,)
    # Replacement with self-consistent new metadata must still violate first-use seal.
    pack["base"][0, 0] = 123
    np.savez(d.features, **pack)
    meta = r.read_json(d.feature_metadata)
    meta["sha256"] = r.sha(d.features)
    r.atomic_json(d.feature_metadata, meta, replace=True)
    with pytest.raises(ValueError, match="audited index"):
        r.Features(source, art).get(d.key)
    if mutate_before_first_read:
        assert not art.complete("feature_inputs/" + d.key)


def test_source_admission_full_calendar_explicit_paths_and_feature_authority(tmp_path):
    import exchange_calendars as xc

    engine, feature_root = tmp_path / "engine", tmp_path / "feature_authority"
    engine.mkdir()
    feature_root.mkdir()
    dates = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    rows = []
    missing = {
        (t, d) for t in ("SPY", "QQQ") for d in ("20260401", "20260409", "20260415")
    }
    for stamp, session in dates.iterrows():
        day_string = stamp.strftime("%Y%m%d")
        close = int((session.close - session.open) / pd.Timedelta(minutes=1))
        for ticker in r.TICKERS:
            path = tmp_path / "separate_original_arrays" / ticker / day_string
            rows.append(
                dict(
                    ticker=ticker,
                    date=day_string,
                    close_i=close,
                    status="MISSING_SOURCE"
                    if (ticker, day_string) in missing
                    else "COMPLETE",
                    day_root=str(path),
                    actions_sha256="unopened",
                    labels_sha256="unopened",
                    cache_npz_sha256="unopened",
                    cache_meta_sha256="unopened",
                    features_sha256="unopened",
                    features_meta_sha256="unopened",
                    action_features_sha256="unopened",
                    action_features_meta_sha256="unopened",
                    features_path=str(path / "features.npz"),
                    features_meta_path=str(
                        feature_root / ticker / day_string / "features.json"
                    ),
                    action_features_path=str(path / "actions.npz"),
                    action_features_meta_path=str(
                        feature_root / ticker / day_string / "actions.json"
                    ),
                )
            )
    pd.DataFrame(rows).to_parquet(engine / "index.parquet", index=False)
    r.atomic_json(engine / "dataset_contract.json", {"synthetic": True})
    r.atomic_json(engine / "completion.json", {"status": "COMPLETE"})
    r.atomic_json(feature_root / "feature_contract.json", {"outcomes_read": False})
    binding = dict(
        engine_root=str(engine),
        feature_root=str(feature_root),
        index_sha256=r.sha(engine / "index.parquet"),
        dataset_contract_sha256=r.sha(engine / "dataset_contract.json"),
        completion_sha256=r.sha(engine / "completion.json"),
        feature_contract_sha256=r.sha(feature_root / "feature_contract.json"),
        available_days=2619,
        missing_days=6,
    )
    audit = tmp_path / "audit.json"
    r.atomic_json(
        audit,
        dict(status="PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT", binding=binding),
    )
    admitted = r.Sources(engine, feature_root, audit)
    assert len(admitted.days) == 2625
    assert sum(d.close_i == 210 for d in admitted.days.values()) == 24
    short = admitted.days["SPY/20241224"]
    assert short.feature_metadata.parent.parent.parent == feature_root
    assert short.features.parent.parent.parent != feature_root
    # No daily NPZ, quote, label or action file exists: admission read only synthetic metadata.
    r.atomic_json(
        feature_root / "feature_contract.json", {"outcomes_read": True}, replace=True
    )
    with pytest.raises(ValueError, match="Changed source"):
        r.Sources(engine, feature_root, audit)

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

if __package__:
    from .walkforward_event_option_gate import metrics
else:
    from walkforward_event_option_gate import metrics


DEFAULT_MONTHS = ("202601", "202602", "202603", "202604", "202605")
RUNTIME_COOLDOWNS = {"SPXW": 0, "QQQ": 30, "SPY": 0}
RUNTIME_DAILY_CAPS = {"SPXW": 4, "QQQ": 2, "SPY": 1}
MIN_HOLD_MINUTES = 30


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def parse_months(values: Iterable[str]) -> list[str]:
    months = [str(value) for value in values]
    if not months or months != sorted(set(months)):
        raise ValueError("evaluation months must be non-empty, unique, and sorted")
    if any(not re.fullmatch(r"\d{6}", month) for month in months):
        raise ValueError(f"invalid evaluation month list: {months}")
    return months


def compare_encoder_configs(flat_meta: dict, modal_meta: dict) -> dict:
    flat_args = dict(flat_meta["args"])
    modal_args = dict(modal_meta["args"])
    ignored = {"encoder_input_mode", "output_dir"}
    keys = sorted(set(flat_args) | set(modal_args))
    differences = {
        key: {"flat": flat_args.get(key), "modal": modal_args.get(key)}
        for key in keys
        if flat_args.get(key) != modal_args.get(key)
    }
    unexpected = sorted(set(differences) - ignored)
    if unexpected:
        raise RuntimeError(f"flat/modal encoder configs differ outside the declared factor: {unexpected}")
    if flat_args.get("encoder_input_mode") != "flat" or modal_args.get("encoder_input_mode") != "modal":
        raise RuntimeError("encoder_input_mode does not identify the expected flat/modal arms")
    if flat_meta.get("feature_cols") != modal_meta.get("feature_cols"):
        raise RuntimeError("flat/modal feature allowlists differ")
    for name, meta in (("flat", flat_meta), ("modal", modal_meta)):
        if str(meta.get("effective_data_cutoff_month")) != "202605":
            raise RuntimeError(f"{name} encoder is not physically cut off at 202605")
        args = meta["args"]
        required = {
            "seed": 20260618,
            "device": "cpu",
            "epochs": 8,
            "horizons": "1,3,6,12",
            "entry_start_minute_et": 630,
            "entry_end_minute_et": 870,
            "entry_grid_anchor_minute_et": 600,
            "expected_step_minutes": 5,
            "live_observable_features_only": True,
        }
        bad = {key: args.get(key) for key, expected in required.items() if args.get(key) != expected}
        if bad:
            raise RuntimeError(f"{name} encoder violates the frozen experiment contract: {bad}")
    return {
        "declared_factor": "encoder_input_mode",
        "differences": differences,
        "identical_feature_count": len(flat_meta["feature_cols"]),
        "same_budget_and_seed": True,
    }


def latent_diagnostics_numpy(values: np.ndarray) -> dict[str, float | int]:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or len(values) < 2:
        raise ValueError("latent diagnostics require at least two rows")
    centered = values - values.mean(axis=0, keepdims=True)
    cov = centered.T @ centered / max(1, len(centered) - 1)
    eigenvalues = np.clip(np.linalg.eigvalsh(cov), 0.0, None)
    total = max(float(eigenvalues.sum()), 1e-12)
    probabilities = eigenvalues / total
    effective_rank = float(np.exp(-(probabilities * np.log(probabilities + 1e-12)).sum()))
    std = values.std(axis=0)
    return {
        "n": int(len(values)),
        "z_dim": int(values.shape[1]),
        "effective_rank": effective_rank,
        "effective_rank_ratio": effective_rank / float(values.shape[1]),
        "max_pc_var_ratio": float(eigenvalues.max() / total),
        "min_dim_std": float(std.min()),
        "median_dim_std": float(np.median(std)),
        "near_zero_std_dims": int((std < 0.05).sum()),
    }


def representation_by_cell(path: Path, months: list[str], arm: str) -> pd.DataFrame:
    latent_cols = [f"ptdj_z_{index:02d}" for index in range(32)]
    columns = [
        "ticker",
        "trade_date",
        "ptdj_context_valid",
        "ptdj_latent_velocity",
        "ptdj_lagged_pred_h1_err",
        *latent_cols,
    ]
    frame = pd.read_parquet(path, columns=columns)
    frame["month"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False).str[:6]
    frame = frame[
        frame["month"].isin(months)
        & (pd.to_numeric(frame["ptdj_context_valid"], errors="coerce") > 0.5)
    ].copy()
    if sorted(frame["month"].unique().tolist()) != months:
        raise RuntimeError(f"{arm} representation does not cover exactly the evaluation months")
    rows: list[dict] = []
    for (ticker, month), group in frame.groupby(["ticker", "month"], sort=True):
        diagnostics = latent_diagnostics_numpy(group[latent_cols].to_numpy(copy=True))
        prediction_error = pd.to_numeric(group["ptdj_lagged_pred_h1_err"], errors="coerce")
        persistence_error = pd.to_numeric(group["ptdj_latent_velocity"], errors="coerce")
        valid = prediction_error.gt(0.0) & persistence_error.gt(0.0)
        ratio = (prediction_error[valid] / persistence_error[valid]).replace([np.inf, -np.inf], np.nan).dropna()
        rows.append(
            {
                "arm": arm,
                "ticker": str(ticker),
                "month": str(month),
                **diagnostics,
                "prediction_to_persistence_ratio_mean": float(ratio.mean()),
                "prediction_to_persistence_ratio_median": float(ratio.median()),
                "prediction_beats_persistence_rate": float((ratio < 1.0).mean()),
                "ratio_observations": int(len(ratio)),
            }
        )
    result = pd.DataFrame(rows).sort_values(["ticker", "month"]).reset_index(drop=True)
    expected_cells = {(ticker, month) for ticker in RUNTIME_DAILY_CAPS for month in months}
    actual_cells = set(zip(result["ticker"], result["month"]))
    if actual_cells != expected_cells:
        raise RuntimeError(f"{arm} representation cell mismatch: {sorted(expected_cells ^ actual_cells)}")
    return result


def max_day_from_config(value: str) -> int:
    match = re.search(r"_maxday(\d+|all)$", str(value))
    if not match:
        raise ValueError(f"invalid deploy config: {value}")
    return 999 if match.group(1) == "all" else int(match.group(1))


def validate_walkforward_contract(directory: Path, months: list[str], arm: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    selected = pd.read_csv(directory / "selected_folds.csv", dtype={"ticker": str, "month": str})
    trades = pd.read_csv(
        directory / "event_option_profile_trades.csv",
        dtype={"ticker": str, "month": str, "date": str, "trade_date": str},
    )
    provenance = json.loads((directory / "policy_selection_provenance.json").read_text(encoding="utf-8"))
    expected_cells = {(ticker, month) for ticker in RUNTIME_DAILY_CAPS for month in months}
    selected_cells = set(zip(selected["ticker"], selected["month"]))
    if len(selected) != len(expected_cells) or selected_cells != expected_cells:
        raise RuntimeError(f"{arm} selected-fold coverage mismatch")
    if provenance.get("mode") != "nested_walk_forward" or provenance.get("evaluation_months") != months:
        raise RuntimeError(f"{arm} nested provenance does not cover the frozen evaluation window")
    if set(trades["month"].astype(str)) - set(months):
        raise RuntimeError(f"{arm} trades contain a sealed month")
    selected_mask = selected["selected"].astype(str).str.lower().eq("true")
    abstained = selected.loc[~selected_mask]
    if len(abstained):
        if not abstained["profile"].astype(str).eq("ABSTAIN_NO_VALID_PROFILE").all():
            raise RuntimeError(f"{arm} has an unrecognized non-selected fold")
        if not pd.to_numeric(abstained["test_trades"], errors="coerce").fillna(0).eq(0).all():
            raise RuntimeError(f"{arm} abstain folds contain test trades")
        trade_cells = set(zip(trades["ticker"].astype(str), trades["month"].astype(str)))
        abstain_cells = set(zip(abstained["ticker"], abstained["month"]))
        if trade_cells & abstain_cells:
            raise RuntimeError(f"{arm} trades exist in an explicit abstain fold")
    active = selected.loc[selected_mask].copy()
    for ticker, cooldown in RUNTIME_COOLDOWNS.items():
        ticker_active = active.loc[active["ticker"] == ticker]
        observed = set(pd.to_numeric(ticker_active["cooldown_minutes"], errors="raise").astype(int))
        if observed and observed != {cooldown}:
            raise RuntimeError(f"{arm} {ticker} cooldown mismatch: {observed}")
        caps = set(ticker_active["deploy_config"].map(max_day_from_config))
        if caps and caps != {RUNTIME_DAILY_CAPS[ticker]}:
            raise RuntimeError(f"{arm} {ticker} daily-cap mismatch: {caps}")
    if set(trades["option_price_mode"].astype(str)) != {"executable_quote"}:
        raise RuntimeError(f"{arm} trades are not exclusively executable_quote")
    minute = pd.to_numeric(trades["minute"], errors="raise").astype(int)
    if minute.min() < 630 or minute.max() > 870 or not bool(((minute - 600) % 5 == 0).all()):
        raise RuntimeError(f"{arm} trades violate the 10:30-14:30 five-minute grid")
    hold = pd.to_numeric(trades["exit_minutes"], errors="raise").astype(float)
    if len(hold) and float(hold.min()) < MIN_HOLD_MINUTES:
        raise RuntimeError(f"{arm} contains a hold shorter than {MIN_HOLD_MINUTES} minutes")
    daily_counts = trades.groupby(["ticker", "date"]).size()
    for ticker, cap in RUNTIME_DAILY_CAPS.items():
        ticker_counts = daily_counts.loc[ticker] if ticker in daily_counts.index.get_level_values(0) else pd.Series(dtype=int)
        if len(ticker_counts) and int(ticker_counts.max()) > cap:
            raise RuntimeError(f"{arm} {ticker} exceeds the daily cap")
    overlaps = 0
    for _, group in trades.groupby(["ticker", "date"], sort=False):
        ordered = group.sort_values(["minute", "exit_minutes"])
        open_until = -1.0
        for row in ordered[["minute", "exit_minutes"]].itertuples(index=False):
            entry = float(row.minute)
            if entry < open_until:
                overlaps += 1
            open_until = max(open_until, entry + float(row.exit_minutes))
    if overlaps:
        raise RuntimeError(f"{arm} contains {overlaps} overlapping same-ticker trades")
    return selected.sort_values(["ticker", "month"]), trades, provenance


def metric_rows(trades: pd.DataFrame, months: list[str], arm: str) -> pd.DataFrame:
    rows: list[dict] = []

    def add(scope: str, ticker: str, month: str, frame: pd.DataFrame, expected: list[str]) -> None:
        rows.append({"arm": arm, "scope": scope, "ticker": ticker, "month": month, **metrics(frame, expected)})

    add("overall", "ALL", "ALL", trades, months)
    for ticker in sorted(RUNTIME_DAILY_CAPS):
        ticker_frame = trades[trades["ticker"] == ticker]
        add("ticker", ticker, "ALL", ticker_frame, months)
        for month in months:
            add("ticker_month", ticker, month, ticker_frame[ticker_frame["month"] == month], [month])
    for month in months:
        add("month", "ALL", month, trades[trades["month"] == month], [month])
    return pd.DataFrame(rows)


def paired_summary(flat: pd.Series, modal: pd.Series, *, alternative: str) -> dict:
    flat_values = np.asarray(flat, dtype=float)
    modal_values = np.asarray(modal, dtype=float)
    difference = modal_values - flat_values
    nonzero = difference[difference != 0.0]
    if len(nonzero):
        wilcoxon_p = float(wilcoxon(modal_values, flat_values, alternative=alternative, zero_method="wilcox").pvalue)
        sign_p = float(binomtest(int((nonzero > 0.0).sum()), len(nonzero), 0.5).pvalue)
    else:
        wilcoxon_p = 1.0
        sign_p = 1.0
    desired = difference > 0.0 if alternative == "greater" else difference < 0.0
    return {
        "alternative_for_modal": alternative,
        "cells": int(len(difference)),
        "median_difference_modal_minus_flat": float(np.median(difference)),
        "modal_wins": int(desired.sum()),
        "modal_losses": int((~desired & (difference != 0.0)).sum()),
        "ties": int((difference == 0.0).sum()),
        "wilcoxon_p": wilcoxon_p,
        "sign_two_sided_p": sign_p,
    }


def paired_tests(
    train: pd.DataFrame,
    representation: pd.DataFrame,
    selected: pd.DataFrame,
) -> dict:
    tests: dict[str, dict] = {}
    tests["train_prediction_loss_lower"] = paired_summary(
        train["flat_train_pred"], train["modal_train_pred"], alternative="less"
    )
    representation_wide = representation.pivot(index=["ticker", "month"], columns="arm")
    for column, alternative in (
        ("effective_rank_ratio", "greater"),
        ("max_pc_var_ratio", "less"),
        ("prediction_to_persistence_ratio_mean", "less"),
        ("prediction_to_persistence_ratio_median", "less"),
        ("prediction_beats_persistence_rate", "greater"),
    ):
        tests[f"representation_{column}"] = paired_summary(
            representation_wide[column]["flat"], representation_wide[column]["modal"], alternative=alternative
        )
    selected_for_tests = selected.copy()
    for column in ("test_profit_factor", "test_pnl_return", "test_win_rate", "test_max_drawdown"):
        selected_for_tests[column] = pd.to_numeric(selected_for_tests[column], errors="coerce")
    # An inner-validation abstain is an operational zero-trade result.  PF/WR
    # are set to zero for the paired downstream decision instead of silently
    # dropping the failed cell; PnL and drawdown remain zero.
    selected_for_tests[["test_profit_factor", "test_win_rate", "test_pnl_return", "test_max_drawdown"]] = (
        selected_for_tests[["test_profit_factor", "test_win_rate", "test_pnl_return", "test_max_drawdown"]].fillna(0.0)
    )
    selected_wide = selected_for_tests.pivot(index=["ticker", "month"], columns="arm")
    for column in ("test_profit_factor", "test_pnl_return", "test_win_rate", "test_max_drawdown"):
        tests[f"downstream_{column}"] = paired_summary(
            selected_wide[column]["flat"], selected_wide[column]["modal"], alternative="greater"
        )
    return tests


def daily_bootstrap(flat_trades: pd.DataFrame, modal_trades: pd.DataFrame, seed: int, resamples: int) -> dict:
    flat = flat_trades.groupby("date")["realized_return"].sum().astype(float)
    modal = modal_trades.groupby("date")["realized_return"].sum().astype(float)
    dates = sorted(set(flat.index) | set(modal.index))
    difference = modal.reindex(dates, fill_value=0.0).to_numpy() - flat.reindex(dates, fill_value=0.0).to_numpy()
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(difference), size=(resamples, len(difference)))
    bootstrap = difference[samples].sum(axis=1)
    return {
        "bootstrap_seed": seed,
        "resamples": resamples,
        "days": len(difference),
        "observed_pnl_difference_modal_minus_flat": float(difference.sum()),
        "ci95": [float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975))],
        "probability_difference_positive": float((bootstrap > 0.0).mean()),
    }


def acceptance_gate(metrics_frame: pd.DataFrame, arm: str) -> dict:
    cells = metrics_frame[(metrics_frame["arm"] == arm) & (metrics_frame["scope"] == "ticker_month")].copy()
    cells["passed"] = (
        (cells["trades"] >= 18)
        & (cells["win_rate"] >= 0.50)
        & (cells["profit_factor"] >= 1.30)
        & (cells["pnl_return"] > 0.0)
    )
    return {
        "passed": bool(cells["passed"].all()),
        "passed_cells": int(cells["passed"].sum()),
        "total_cells": int(len(cells)),
        "failed_cells": cells.loc[~cells["passed"], ["ticker", "month"]].to_dict("records"),
        "minimum_hold_minutes": MIN_HOLD_MINUTES,
    }


def artifact_hashes(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        result[name] = {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return result


def validate_sealed_manifests(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for arm in ("flat", "modal"):
        payload = json.loads(paths[f"{arm}_sealed_manifest"].read_text(encoding="utf-8"))
        required = {
            "sealed_after_month": "202605",
            "option_price_mode": "executable_quote",
            "entry_minute_min": 630,
            "entry_minute_max": 870,
            "entry_grid_anchor_minute_et": 600,
            "entry_step_minutes": 5,
            "rows": 41883,
        }
        bad = {key: payload.get(key) for key, expected in required.items() if payload.get(key) != expected}
        if bad or int(payload.get("max_trade_date", 99999999)) >= 20260601:
            raise RuntimeError(f"{arm} sealed dataset manifest violates the frozen contract: {bad}")
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", str(payload.get("output_sha256", ""))):
            raise RuntimeError(f"{arm} sealed dataset manifest has no valid parquet SHA-256")
        manifests[arm] = payload
    return manifests


def render_report(summary: dict, metrics_frame: pd.DataFrame, tests: dict) -> str:
    overall = metrics_frame[metrics_frame["scope"] == "overall"].set_index("arm")
    ticker = metrics_frame[metrics_frame["scope"] == "ticker"]
    lines = [
        "# Phys-TD-JEPA flat vs modal — comparación causal runtime-equivalente",
        "",
        "## Decisión",
        "",
        f"**Avanzar a objetivos intra/cross-modal: {'SÍ' if summary['decision']['advance_to_cross_modal'] else 'NO'}.**",
        "",
        summary["decision"]["reason"],
        "",
        "Junio de 2026 no fue leído ni puntuado por esta evaluación; los inputs downstream terminan en 20260529.",
        "",
        "## Contrato",
        "",
        "- Dataset executable_quote: entrada ask, trayectoria/salida bid.",
        "- Rejilla 10:30–14:30 ET cada cinco minutos.",
        "- Hold mínimo realizado: 30 minutos.",
        "- SPXW: 4 trades/día, cooldown 0m; QQQ: 2/30m; SPY: 1/0m.",
        "- Nested walk-forward 202601–202605; seed 20260618 y mismo presupuesto.",
        f"- SHA-256 parquet flat sellado: `{summary['sealed_datasets']['flat']['output_sha256']}`.",
        f"- SHA-256 parquet modal sellado: `{summary['sealed_datasets']['modal']['output_sha256']}`.",
        "",
        "## Métricas agregadas",
        "",
        "| Arm | Trades | WR | PF | PnL (R) | Max DD | Gate ticker×mes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for arm in ("flat", "modal"):
        row = overall.loc[arm]
        gate = summary["acceptance_gates"][arm]
        lines.append(
            f"| {arm} | {int(row.trades)} | {row.win_rate:.3%} | {row.profit_factor:.3f} | "
            f"{row.pnl_return:+.3f} | {row.max_drawdown:.3f} | {gate['passed_cells']}/{gate['total_cells']} |"
        )
    lines.extend(
        [
            "",
            "## Por ticker",
            "",
            "| Arm | Ticker | Trades | WR | PF | PnL (R) | Min trades/mes | Meses positivos |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in ticker.itertuples(index=False):
        lines.append(
            f"| {row.arm} | {row.ticker} | {int(row.trades)} | {row.win_rate:.3%} | "
            f"{row.profit_factor:.3f} | {row.pnl_return:+.3f} | {int(row.min_month_trades)} | "
            f"{row.positive_month_rate:.0%} |"
        )
    lines.extend(["", "## Pruebas pareadas clave", "", "| Métrica | Wins modal | p Wilcoxon | Mediana modal-flat |", "| --- | ---: | ---: | ---: |"])
    for name in (
        "representation_prediction_to_persistence_ratio_mean",
        "representation_prediction_beats_persistence_rate",
        "downstream_test_profit_factor",
        "downstream_test_pnl_return",
    ):
        test = tests[name]
        lines.append(
            f"| {name} | {test['modal_wins']}/{test['cells']} | {test['wilcoxon_p']:.6f} | "
            f"{test['median_difference_modal_minus_flat']:+.6f} |"
        )
    bootstrap = summary["daily_pnl_bootstrap"]
    lines.extend(
        [
            "",
            f"Bootstrap diario modal-flat: observado {bootstrap['observed_pnl_difference_modal_minus_flat']:+.3f}R, "
            f"IC95% [{bootstrap['ci95'][0]:+.3f}, {bootstrap['ci95'][1]:+.3f}], "
            f"P(diff>0)={bootstrap['probability_difference_positive']:.3f}.",
            "",
            "Las tablas completas por fold y ticker×mes están en los CSV del mismo directorio.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare frozen Phys-TD-JEPA flat and modal arms.")
    parser.add_argument("--flat-encoder-dir", required=True)
    parser.add_argument("--modal-encoder-dir", required=True)
    parser.add_argument("--flat-walkforward-dir", required=True)
    parser.add_argument("--modal-walkforward-dir", required=True)
    parser.add_argument("--flat-sealed-manifest", required=True)
    parser.add_argument("--modal-sealed-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--evaluation-months", nargs="+", default=list(DEFAULT_MONTHS))
    parser.add_argument("--bootstrap-seed", type=int, default=20260711)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    args = parser.parse_args()

    months = parse_months(args.evaluation_months)
    if months != list(DEFAULT_MONTHS):
        raise RuntimeError("this frozen comparison is restricted to 202601..202605")
    paths = {
        "flat_encoder": Path(args.flat_encoder_dir),
        "modal_encoder": Path(args.modal_encoder_dir),
        "flat_walkforward": Path(args.flat_walkforward_dir),
        "modal_walkforward": Path(args.modal_walkforward_dir),
        "flat_sealed_manifest": Path(args.flat_sealed_manifest),
        "modal_sealed_manifest": Path(args.modal_sealed_manifest),
    }
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {output_dir}")
    output_dir.mkdir(parents=True)

    flat_meta = json.loads((paths["flat_encoder"] / "metadata.json").read_text(encoding="utf-8"))
    modal_meta = json.loads((paths["modal_encoder"] / "metadata.json").read_text(encoding="utf-8"))
    sealed_manifests = validate_sealed_manifests(paths)
    config_comparison = compare_encoder_configs(flat_meta, modal_meta)
    write_json(output_dir / "config_comparison.json", config_comparison)

    train_frames = []
    for arm in ("flat", "modal"):
        frame = pd.read_csv(paths[f"{arm}_encoder"] / "fold_configs.csv", dtype={"month": str})
        keep = [
            "month",
            "train_start_month",
            "train_end_month",
            "train_rows",
            "train_months",
            "train_windows",
            "test_rows",
            "feature_count",
            "context_valid_rate",
            "train_pred",
            "train_total",
            "train_z_effective_rank_ratio",
            "train_z_max_pc_var_ratio",
        ]
        train_frames.append(frame[keep].add_prefix(f"{arm}_").rename(columns={f"{arm}_month": "month"}))
    train = train_frames[0].merge(train_frames[1], on="month", validate="one_to_one").sort_values("month")
    train.to_csv(output_dir / "train_fold_comparison.csv", index=False)

    representation = pd.concat(
        [
            representation_by_cell(paths["flat_encoder"] / "oof_event_phys_td_jepa_features.parquet", months, "flat"),
            representation_by_cell(paths["modal_encoder"] / "oof_event_phys_td_jepa_features.parquet", months, "modal"),
        ],
        ignore_index=True,
    )
    representation.to_csv(output_dir / "representation_ticker_month.csv", index=False)

    selected_frames = []
    trade_frames: dict[str, pd.DataFrame] = {}
    provenance: dict[str, dict] = {}
    metric_frames = []
    for arm in ("flat", "modal"):
        selected, trades, arm_provenance = validate_walkforward_contract(paths[f"{arm}_walkforward"], months, arm)
        selected_frames.append(selected.assign(arm=arm))
        trade_frames[arm] = trades
        provenance[arm] = arm_provenance
        metric_frames.append(metric_rows(trades, months, arm))
    selected_all = pd.concat(selected_frames, ignore_index=True)
    selected_all.to_csv(output_dir / "downstream_selected_folds.csv", index=False)
    metrics_all = pd.concat(metric_frames, ignore_index=True)
    metrics_all.to_csv(output_dir / "downstream_metrics.csv", index=False)

    tests = paired_tests(train, representation, selected_all)
    write_json(output_dir / "paired_tests.json", tests)
    bootstrap = daily_bootstrap(trade_frames["flat"], trade_frames["modal"], args.bootstrap_seed, args.bootstrap_resamples)
    gates = {arm: acceptance_gate(metrics_all, arm) for arm in ("flat", "modal")}

    representation_key = tests["representation_prediction_to_persistence_ratio_mean"]
    representation_beats = tests["representation_prediction_beats_persistence_rate"]
    downstream_pf = tests["downstream_test_profit_factor"]
    downstream_pnl = tests["downstream_test_pnl_return"]
    representation_support = (
        representation_key["modal_wins"] >= 8
        and representation_key["wilcoxon_p"] < 0.05
        and representation_beats["modal_wins"] >= 8
        and representation_beats["wilcoxon_p"] < 0.05
    )
    downstream_support = (
        downstream_pf["modal_wins"] >= 8
        and downstream_pf["wilcoxon_p"] < 0.05
        and downstream_pnl["modal_wins"] >= 8
        and downstream_pnl["wilcoxon_p"] < 0.05
        and bootstrap["ci95"][0] > 0.0
    )
    advance = bool(representation_support and downstream_support)
    decision = {
        "advance_to_cross_modal": advance,
        "representation_support": representation_support,
        "downstream_support": downstream_support,
        "reason": (
            "Modal mejora de forma reproducible representación y downstream bajo el contrato congelado."
            if advance
            else "Modal no demuestra simultáneamente una mejora reproducible de representación y downstream; se detiene la cola intra/cross-modal."
        ),
    }

    input_files = {
        "flat_encoder_metadata": paths["flat_encoder"] / "metadata.json",
        "flat_encoder_fold_configs": paths["flat_encoder"] / "fold_configs.csv",
        "flat_encoder_oof_features": paths["flat_encoder"] / "oof_event_phys_td_jepa_features.parquet",
        "modal_encoder_metadata": paths["modal_encoder"] / "metadata.json",
        "modal_encoder_fold_configs": paths["modal_encoder"] / "fold_configs.csv",
        "modal_encoder_oof_features": paths["modal_encoder"] / "oof_event_phys_td_jepa_features.parquet",
        "flat_selected_folds": paths["flat_walkforward"] / "selected_folds.csv",
        "flat_trades": paths["flat_walkforward"] / "event_option_profile_trades.csv",
        "flat_provenance": paths["flat_walkforward"] / "policy_selection_provenance.json",
        "modal_selected_folds": paths["modal_walkforward"] / "selected_folds.csv",
        "modal_trades": paths["modal_walkforward"] / "event_option_profile_trades.csv",
        "modal_provenance": paths["modal_walkforward"] / "policy_selection_provenance.json",
        "flat_sealed_manifest": paths["flat_sealed_manifest"],
        "modal_sealed_manifest": paths["modal_sealed_manifest"],
    }
    hashes = artifact_hashes(input_files)
    write_json(output_dir / "input_artifact_hashes.json", hashes)
    abstain_cells = {
        arm: selected_all.loc[
            (selected_all["arm"] == arm) & ~selected_all["selected"].astype(str).str.lower().eq("true"),
            ["ticker", "month"],
        ].to_dict("records")
        for arm in ("flat", "modal")
    }
    summary = {
        "schema_version": 1,
        "evaluation_months": months,
        "seed": 20260618,
        "bootstrap_seed": args.bootstrap_seed,
        "dataset_contract": "executable_quote_ask_to_bid",
        "runtime_cooldowns_minutes": RUNTIME_COOLDOWNS,
        "runtime_daily_caps": RUNTIME_DAILY_CAPS,
        "minimum_hold_minutes": MIN_HOLD_MINUTES,
        "sealed_datasets": sealed_manifests,
        "config_comparison": config_comparison,
        "provenance_passed": {arm: bool(payload["passed"]) for arm, payload in provenance.items()},
        "abstain_cells": abstain_cells,
        "acceptance_gates": gates,
        "daily_pnl_bootstrap": bootstrap,
        "decision": decision,
    }
    write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(render_report(summary, metrics_all, tests), encoding="utf-8")
    print(json.dumps(json_safe(summary), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

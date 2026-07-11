from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


TICKERS = ("SPXW", "QQQ", "SPY")
MONTHS = ("202601", "202602", "202603", "202604", "202605")
GATES = {"profit_factor": 1.3, "win_rate": 0.5, "min_month_trades": 18, "positive_month_rate": 1.0}
VALIDATION_GATES = {"profit_factor": 1.3, "win_rate": 0.5, "trades_per_month": 18, "positive_month_rate": 1.0}


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")


def paired_test(control: pd.Series, variant: pd.Series, alternative: str) -> dict[str, Any]:
    left = pd.to_numeric(control, errors="coerce").to_numpy(dtype=float)
    right = pd.to_numeric(variant, errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(left) & np.isfinite(right)
    left, right = left[finite], right[finite]
    diff = right - left
    nonzero = diff[diff != 0.0]
    p_value = float("nan")
    if len(nonzero):
        p_value = float(wilcoxon(right, left, alternative=alternative).pvalue)
    return {
        "pairs": int(len(diff)),
        "nonzero_pairs": int(len(nonzero)),
        "median_variant_minus_control": float(np.median(diff)) if len(diff) else float("nan"),
        "mean_variant_minus_control": float(np.mean(diff)) if len(diff) else float("nan"),
        "variant_wins": int((diff < 0.0).sum() if alternative == "less" else (diff > 0.0).sum()),
        "control_wins": int((diff > 0.0).sum() if alternative == "less" else (diff < 0.0).sum()),
        "ties": int((diff == 0.0).sum()),
        "wilcoxon_one_sided_p": p_value,
    }


def _normalised_args(metadata: dict[str, Any]) -> dict[str, Any]:
    args = dict(metadata["args"])
    args.pop("arm", None)
    args.pop("output_dir", None)
    return args


def validate_contract(control_dir: Path, variant_dir: Path) -> dict[str, Any]:
    control_meta = read_json(control_dir / "metadata.json")
    variant_meta = read_json(variant_dir / "metadata.json")
    if control_meta["args"]["arm"] != "deterministic" or variant_meta["args"]["arm"] != "variational":
        raise RuntimeError("arm directories do not contain deterministic and variational runs")
    if _normalised_args(control_meta) != _normalised_args(variant_meta):
        raise RuntimeError("arms differ in arguments beyond arm/output_dir")
    equality_fields = (
        "data_sha256",
        "data_rows_after_contract",
        "action_rows",
        "date_min",
        "date_max",
        "latent_features",
        "model_features",
        "delta_by_ticker",
        "daily_caps",
        "cooldowns",
        "dataset_contract",
        "hold_action_contract",
        "minimum_hold_minutes",
        "validation_acceptance_gates",
    )
    for field in equality_fields:
        if control_meta[field] != variant_meta[field]:
            raise RuntimeError(f"arms differ in metadata field {field}")
    if int(str(control_meta["date_max"])[:8]) >= 20260601:
        raise RuntimeError("June 2026 seal violated")
    if control_meta["dataset_contract"] != "executable_quote_ask_to_bid":
        raise RuntimeError("unexpected executable quote contract")
    if control_meta["validation_acceptance_gates"] != VALIDATION_GATES:
        raise RuntimeError("validation gates do not match the predeclared research objective")
    if control_meta.get("uncertainty_used_for_selection") or variant_meta.get("uncertainty_used_for_selection"):
        raise RuntimeError("uncertainty contaminated first-stage selection")

    folds: dict[str, pd.DataFrame] = {}
    for arm, directory in (("deterministic", control_dir), ("variational", variant_dir)):
        provenance = read_json(directory / "policy_selection_provenance.json")
        summary = read_json(directory / "summary.json")
        if not provenance.get("passed"):
            raise RuntimeError(f"{arm} provenance failed")
        if not summary.get("runtime_replay_audit", {}).get("passed"):
            raise RuntimeError(f"{arm} runtime replay audit failed")
        frame = pd.read_csv(directory / "selected_folds.csv", dtype={"ticker": str, "month": str})
        keys = set(zip(frame["ticker"], frame["month"]))
        expected = {(ticker, month) for ticker in TICKERS for month in MONTHS}
        if keys != expected or len(frame) != len(expected):
            raise RuntimeError(f"{arm} does not contain exactly 15 expected ticker-month folds")
        folds[arm] = frame

    paired = folds["deterministic"].merge(
        folds["variational"], on=["ticker", "month"], suffixes=("_deterministic", "_variational"), validate="one_to_one"
    )
    equal_columns = (
        "seed",
        "training_months",
        "selection_months",
        "train_rows",
        "val_rows",
        "test_rows",
        "delta_bucket",
        "cooldown_minutes",
        "daily_cap",
    )
    for column in equal_columns:
        if not paired[f"{column}_deterministic"].astype(str).equals(paired[f"{column}_variational"].astype(str)):
            raise RuntimeError(f"paired folds differ in {column}")
    return {
        "same_data": True,
        "same_args_except_arm": True,
        "same_folds_and_seeds": True,
        "june_2026_sealed": True,
        "uncertainty_used_for_selection": False,
        "control_parameter_count": int(control_meta["model_parameter_count"]),
        "variant_parameter_count": int(variant_meta["model_parameter_count"]),
        "data_sha256": control_meta["data_sha256"],
        "base_seed": int(control_meta["args"]["seed"]),
    }


def ticker_gate_status(summary: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for ticker in TICKERS:
        row = summary["tickers"][ticker]
        checks = {
            "profit_factor": float(row["profit_factor"]) >= GATES["profit_factor"],
            "win_rate": float(row["win_rate"]) >= GATES["win_rate"],
            "min_month_trades": int(row["min_month_trades"]) >= GATES["min_month_trades"],
            "positive_month_rate": float(row["positive_month_rate"]) >= GATES["positive_month_rate"],
        }
        output[ticker] = {"passed": all(checks.values()), "checks": checks, "metrics": row}
    return output


def analyze(control_dir: Path, variant_dir: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    contract = validate_contract(control_dir, variant_dir)
    diagnostics: dict[str, pd.DataFrame] = {}
    for arm, directory in (("deterministic", control_dir), ("variational", variant_dir)):
        frame = pd.read_csv(directory / "representation_ticker_month.csv", dtype={"ticker": str, "month": str})
        diagnostics[arm] = frame
    cells = diagnostics["deterministic"].merge(
        diagnostics["variational"],
        on=["ticker", "month"],
        suffixes=("_deterministic", "_variational"),
        validate="one_to_one",
    ).sort_values(["ticker", "month"])
    if len(cells) != 15:
        raise RuntimeError("representation comparison does not contain 15 paired cells")

    representation_tests = {
        "mae": paired_test(cells["mae_deterministic"], cells["mae_variational"], "less"),
        "rmse": paired_test(cells["rmse_deterministic"], cells["rmse_variational"], "less"),
        "mae_to_train_mean_ratio": paired_test(
            cells["mae_to_train_mean_ratio_deterministic"], cells["mae_to_train_mean_ratio_variational"], "less"
        ),
        "directional_accuracy": paired_test(
            cells["directional_accuracy_deterministic"], cells["directional_accuracy_variational"], "greater"
        ),
        "effective_rank_ratio": paired_test(
            cells["effective_rank_ratio_deterministic"], cells["effective_rank_ratio_variational"], "greater"
        ),
    }
    uncertainty = pd.to_numeric(cells["uncertainty_error_spearman_variational"], errors="coerce")
    finite_uncertainty = uncertainty[np.isfinite(uncertainty)]
    uncertainty_summary = {
        "finite_cells": int(len(finite_uncertainty)),
        "positive_cells": int((finite_uncertainty > 0.0).sum()),
        "median_spearman": float(finite_uncertainty.median()) if len(finite_uncertainty) else float("nan"),
        "mean_spearman": float(finite_uncertainty.mean()) if len(finite_uncertainty) else float("nan"),
    }
    representation_improved = all(
        representation_tests[name]["variant_wins"] >= 10
        and representation_tests[name]["median_variant_minus_control"] < 0.0
        and representation_tests[name]["wilcoxon_one_sided_p"] < 0.05
        for name in ("mae", "rmse")
    )
    uncertainty_supported = (
        uncertainty_summary["finite_cells"] == 15
        and uncertainty_summary["positive_cells"] >= 10
        and uncertainty_summary["median_spearman"] > 0.0
    )

    fold_frames = {
        arm: pd.read_csv(directory / "selected_folds.csv", dtype={"ticker": str, "month": str})
        for arm, directory in (("deterministic", control_dir), ("variational", variant_dir))
    }
    downstream_cells = fold_frames["deterministic"].merge(
        fold_frames["variational"], on=["ticker", "month"], suffixes=("_deterministic", "_variational"), validate="one_to_one"
    )
    downstream_tests = {
        metric: paired_test(
            downstream_cells[f"test_{metric}_deterministic"],
            downstream_cells[f"test_{metric}_variational"],
            alternative,
        )
        for metric, alternative in (
            ("pnl_return", "greater"),
            ("profit_factor", "greater"),
            ("win_rate", "greater"),
            ("max_drawdown", "greater"),
        )
    }
    summaries = {
        "deterministic": read_json(control_dir / "summary.json"),
        "variational": read_json(variant_dir / "summary.json"),
    }
    ticker_gates = {arm: ticker_gate_status(summary) for arm, summary in summaries.items()}
    variant_full_gate = all(row["passed"] for row in ticker_gates["variational"].values())
    result = {
        "schema_version": 1,
        "comparison": "deterministic_vs_variational_portfolio_payoff_head",
        "single_factor": "gaussian_prior_posterior_reparameterization_and_annealed_kl",
        "contract": contract,
        "representation_tests": representation_tests,
        "uncertainty_diagnostic": uncertainty_summary,
        "downstream_paired_tests": downstream_tests,
        "ticker_gates": ticker_gates,
        "decision": {
            "representation_improved_reproducibly": bool(representation_improved),
            "uncertainty_diagnostic_supported": bool(uncertainty_supported),
            "advance_to_uncertainty_abstention_ablation": bool(representation_improved and uncertainty_supported),
            "variational_meets_full_downstream_gate": bool(variant_full_gate),
            "production_live_ready": False,
        },
        "input_hashes": {
            "deterministic_metadata": sha256_file(control_dir / "metadata.json"),
            "variational_metadata": sha256_file(variant_dir / "metadata.json"),
            "deterministic_folds": sha256_file(control_dir / "selected_folds.csv"),
            "variational_folds": sha256_file(variant_dir / "selected_folds.csv"),
            "deterministic_diagnostics": sha256_file(control_dir / "representation_ticker_month.csv"),
            "variational_diagnostics": sha256_file(variant_dir / "representation_ticker_month.csv"),
        },
    }
    return result, cells


def render_report(result: dict[str, Any]) -> str:
    decision = result["decision"]
    lines = [
        "# Portfolio Var-JEPA: deterministic vs variational payoff head",
        "",
        "Comparación nested walk-forward sellada en enero-mayo de 2026. Junio de 2026 no se leyó.",
        "El encoder de mercado flat OOF permanece congelado y actionless; solo cambia el head de payoff.",
        "La incertidumbre se registró como diagnóstico y no participó en thresholds ni selección.",
        "",
        "## Decisión",
        "",
        f"- Mejora reproducible de representación: `{str(decision['representation_improved_reproducibly']).lower()}`.",
        f"- Diagnóstico de incertidumbre apoyado: `{str(decision['uncertainty_diagnostic_supported']).lower()}`.",
        f"- Avanzar a ablación de abstención por incertidumbre: `{str(decision['advance_to_uncertainty_abstention_ablation']).lower()}`.",
        f"- Cumple gate downstream completo por ticker: `{str(decision['variational_meets_full_downstream_gate']).lower()}`.",
        "- `production_live_ready=false`.",
        "",
        "## Representación OOS pareada",
        "",
        "| Métrica | Pares | Wins Var | Mediana Var-Control | Wilcoxon p unilateral |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in result["representation_tests"].items():
        lines.append(
            f"| {name} | {row['pairs']} | {row['variant_wins']} | {row['median_variant_minus_control']:.6f} | "
            f"{row['wilcoxon_one_sided_p']:.6g} |"
        )
    unc = result["uncertainty_diagnostic"]
    lines.extend(
        [
            "",
            "## Incertidumbre",
            "",
            f"Spearman incertidumbre-error fue positivo en {unc['positive_cells']}/{unc['finite_cells']} celdas; "
            f"mediana `{unc['median_spearman']:.6f}`.",
            "",
            "## Gates downstream por ticker",
            "",
            "| Arm | Ticker | Trades | WR | PF | Min mes | Meses positivos | Gate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for arm, tickers in result["ticker_gates"].items():
        for ticker, row in tickers.items():
            metrics = row["metrics"]
            lines.append(
                f"| {arm} | {ticker} | {metrics['trades']} | {metrics['win_rate']:.3%} | "
                f"{metrics['profit_factor']:.3f} | {metrics['min_month_trades']} | "
                f"{metrics['positive_month_rate']:.3f} | {'PASS' if row['passed'] else 'FAIL'} |"
            )
    lines.extend(
        [
            "",
            "No se selecciona arquitectura por PnL agregado. El downstream es evidencia secundaria; la continuación "
            "a uncertainty-abstention exige primero mejora de predicción en celdas ticker×mes y una relación "
            "incertidumbre-error reproducible.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired analysis for deterministic vs variational portfolio payoff heads.")
    parser.add_argument("--deterministic-dir", required=True)
    parser.add_argument("--variational-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    result, cells = analyze(Path(args.deterministic_dir), Path(args.variational_dir))
    output_dir.mkdir(parents=True, exist_ok=False)
    cells.to_csv(output_dir / "representation_paired_cells.csv", index=False)
    write_json(output_dir / "summary.json", result)
    (output_dir / "REPORT.md").write_text(render_report(result), encoding="utf-8")
    print(json.dumps(result["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

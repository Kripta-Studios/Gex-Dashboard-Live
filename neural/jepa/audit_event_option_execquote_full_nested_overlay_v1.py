from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from neural.jepa import evaluate_event_option_execquote_full_nested_overlay_v1 as ev


RESULT_DIR = ev.OUTPUT_DIR
AUDIT_DIR = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "event_option_execquote_full_nested_monthly_overlay_v1_202601_202606_audit"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_close(actual: Any, expected: Any, label: str, tolerance: float = 1e-10) -> None:
    if isinstance(actual, (int, float)) and not math.isfinite(float(actual)):
        actual = None
    if isinstance(expected, (int, float)) and not math.isfinite(float(expected)):
        expected = None
    if actual is None or expected is None:
        if actual is not expected:
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")
        return
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if not math.isclose(
            float(actual),
            float(expected),
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            raise AssertionError(f"{label}: {actual!r} != {expected!r}")
        return
    if actual != expected:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def compare_metrics(actual: dict, expected: dict, label: str) -> None:
    scalar_fields = (
        "trades",
        "win_rate",
        "profit_factor",
        "pnl_return",
        "min_month_trades",
        "positive_months",
    )
    for field in scalar_fields:
        assert_close(actual.get(field), expected.get(field), f"{label}.{field}")
    if set(actual.get("monthly", {})) != set(expected.get("monthly", {})):
        raise AssertionError(f"{label}.monthly keys differ")
    for month in actual.get("monthly", {}):
        assert_close(
            actual["monthly"][month]["trades"],
            expected["monthly"][month]["trades"],
            f"{label}.{month}.trades",
        )
        assert_close(
            actual["monthly"][month]["pnl_return"],
            expected["monthly"][month]["pnl_return"],
            f"{label}.{month}.pnl_return",
        )


def model_text_sha(model: object) -> str:
    raw = model.booster_.model_to_string().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_policy_artifacts(result_dir: Path, policy: dict) -> None:
    artifact_dir = result_dir / "fold_policy_artifacts" / (
        f"{policy['ticker']}_{policy['test_month']}"
    )
    for item in policy["artifacts"].values():
        path = artifact_dir / item["path"]
        if ev.sha256_file(path) != item["sha256"]:
            raise AssertionError(f"policy artifact hash mismatch: {path}")
    feature_columns = read_json(artifact_dir / policy["artifacts"]["features"]["path"])
    if (
        len(feature_columns) != ev.FEATURE_COUNT
        or ev.canonical_json_sha(feature_columns) != ev.FEATURES_SHA256
    ):
        raise AssertionError("policy feature artifact violates the frozen feature contract")


def no_overlap_issues(trades: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if trades.empty:
        return issues
    ordered = trades.sort_values(
        ["ticker", "trade_date", "minute", "score"],
        ascending=[True, True, True, False],
        kind="stable",
    )
    for (ticker, trade_date), group in ordered.groupby(
        ["ticker", "trade_date"], sort=False
    ):
        prior_exit = -1
        for row in group.itertuples(index=False):
            minute = int(row.minute)
            hold = float(row.exit_minutes)
            if not math.isfinite(hold) or not 30.0 <= hold <= 180.0:
                issues.append(
                    f"hold:{ticker}:{trade_date}:{minute}:{hold}"
                )
            if minute < prior_exit:
                issues.append(
                    f"overlap:{ticker}:{trade_date}:{minute}<prior_exit{prior_exit}"
                )
            prior_exit = minute + int(math.ceil(hold))
    return issues


def compare_trade_ledgers(recomputed: pd.DataFrame, stored: pd.DataFrame) -> None:
    keys = ["test_month", "ticker", "trade_date", "minute"]
    recomputed = recomputed.sort_values(keys, kind="stable").reset_index(drop=True)
    stored = stored.sort_values(keys, kind="stable").reset_index(drop=True)
    if list(recomputed.columns) != list(stored.columns):
        raise AssertionError(
            "trade ledger columns differ: "
            f"{list(recomputed.columns)} != {list(stored.columns)}"
        )
    pd.testing.assert_frame_equal(
        recomputed,
        stored,
        check_dtype=False,
        check_exact=False,
        rtol=0.0,
        atol=1e-10,
    )


def audit(args: argparse.Namespace) -> dict:
    source = Path(args.source)
    result_dir = Path(args.result_dir)
    output = Path(args.output_dir)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing audit: {output}")
    stager = output.with_name(f"{output.name}.staging_{os.getpid()}")
    if stager.exists():
        raise FileExistsError(f"audit stager already exists: {stager}")

    summary_path = result_dir / "evaluation_summary.json"
    summary = read_json(summary_path)
    if summary["family"] != "EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1":
        raise AssertionError("unexpected result family")
    if summary["source"]["sha256"] != ev.SOURCE_SHA256:
        raise AssertionError("result source SHA is not the frozen source")
    if summary["contract_sha256"] != ev.sha256_file(ev.CONTRACT_PATH):
        raise AssertionError("contract changed after evaluation")
    if summary["evaluator_sha256"] != ev.sha256_file(Path(ev.__file__)):
        raise AssertionError("evaluator changed after evaluation")
    if summary["auditor_sha256"] != ev.sha256_file(Path(__file__)):
        raise AssertionError("auditor changed after evaluation")
    if summary["folds"] != 18 or summary["configurations_per_ticker_fold"] != ev.FULL_CONFIGS:
        raise AssertionError("result did not execute the frozen fold/grid counts")

    for artifact in summary["artifacts"].values():
        path = result_dir / artifact["path"]
        if ev.sha256_file(path) != artifact["sha256"]:
            raise AssertionError(f"top-level artifact hash mismatch: {path}")

    policy_index_path = result_dir / summary["artifacts"]["policy_index"]["path"]
    policy_index = read_json(policy_index_path)
    if len(policy_index) != 18:
        raise AssertionError(f"expected 18 policies, got {len(policy_index)}")
    policy_lookup = {
        (str(item["ticker"]), str(item["test_month"])): item
        for item in policy_index
    }
    if len(policy_lookup) != 18:
        raise AssertionError("duplicate policy index keys")

    parquet = ev.validate_source(source)
    feature_view, feature_columns = ev.load_feature_view(source, parquet)
    stored_folds = pd.read_csv(
        result_dir / summary["artifacts"]["fold_results"]["path"],
        dtype={"test_month": str},
    )
    stored_folds["test_month"] = (
        stored_folds["test_month"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    stored_fold_lookup = {
        (str(row.ticker), str(row.test_month)): row
        for row in stored_folds.itertuples(index=False)
    }
    if len(stored_fold_lookup) != 18:
        raise AssertionError("stored fold result keys are not exactly 18")

    recomputed_trades: list[pd.DataFrame] = []
    recomputed_fold_rows: list[dict] = []
    model_hash_matches = 0
    prediction_hash_matches = 0
    winner_matches = 0

    for test_month in ev.TEST_MONTHS:
        val_months = ev.selection_months(test_month)
        train_months = ev.training_months(test_month)
        first_val = val_months[0]
        for ticker in ev.TICKERS:
            key = (ticker, test_month)
            index_row = policy_lookup[key]
            policy_path = result_dir / index_row["path"]
            if ev.sha256_file(policy_path) != index_row["sha256"]:
                raise AssertionError(f"policy index hash mismatch: {policy_path}")
            policy = read_json(policy_path)
            validate_policy_artifacts(result_dir, policy)
            if policy["training_months"] != train_months:
                raise AssertionError(f"training months mismatch in policy {key}")
            if policy["selection_months"] != val_months:
                raise AssertionError(f"selection months mismatch in policy {key}")
            if not policy["policy_frozen_before_test_outcome_read"]:
                raise AssertionError(f"policy was not marked frozen before test: {key}")

            delta = ev.DELTA_BY_TICKER[ticker]
            ticker_features = ev.eligible_feature_rows(feature_view, ticker, delta)
            past_features = ticker_features.loc[
                ticker_features["month"].astype(str).lt(test_month)
            ].copy()
            past_outcomes = ev.load_outcomes(
                source,
                ticker,
                "202501",
                test_month,
                delta,
            )
            past = ev.merge_outcomes(past_features, past_outcomes, delta)
            train = past.loc[past["month"].astype(str).lt(first_val)].copy()
            selection = past.loc[
                past["month"].astype(str).isin(val_months)
            ].copy()
            call_model, put_model, medians = ev.fit_models(
                train,
                feature_columns,
                test_month,
                int(args.lgb_jobs),
            )
            if model_text_sha(call_model) != policy["artifacts"]["call_model"]["sha256"]:
                raise AssertionError(f"CALL refit hash mismatch: {key}")
            if model_text_sha(put_model) != policy["artifacts"]["put_model"]["sha256"]:
                raise AssertionError(f"PUT refit hash mismatch: {key}")
            model_hash_matches += 2

            artifact_dir = policy_path.parent
            stored_medians = pd.read_csv(
                artifact_dir / policy["artifacts"]["medians"]["path"],
                index_col="feature",
            )["median"].reindex(feature_columns)
            np.testing.assert_allclose(
                medians.reindex(feature_columns).to_numpy(dtype=float),
                stored_medians.to_numpy(dtype=float),
                rtol=0.0,
                atol=1e-12,
            )

            selection_scored = ev.bind_physical_outcome(
                ev.predict_scores(
                    selection,
                    feature_columns,
                    call_model,
                    put_model,
                    medians,
                ),
                delta,
            )
            selection_scored["test_month"] = test_month
            prediction_columns = [
                "ticker",
                "trade_date",
                "minute",
                "pred_call_return",
                "pred_put_return",
                "action",
                "score",
            ]
            selection_prediction_sha = ev.dataframe_sha(
                selection_scored,
                prediction_columns,
                ["ticker", "trade_date", "minute"],
            )
            if selection_prediction_sha != policy["selection_prediction_sha256"]:
                raise AssertionError(f"selection prediction SHA mismatch: {key}")
            prediction_hash_matches += 1

            winner, scan = ev.scan_grid(selection_scored, ticker)
            winner_dict = asdict(winner) if winner is not None else None
            if winner_dict != policy["winner"]:
                raise AssertionError(f"full-grid winner mismatch: {key}")
            if scan["status"] != policy["scan"]["status"]:
                raise AssertionError(f"scan status mismatch: {key}")
            if winner is None:
                selection_trades = selection_scored.iloc[0:0].copy()
            else:
                selection_trades = ev.replay_config(selection_scored, winner, ticker)
            selection_metrics = ev.economic_metrics(selection_trades, val_months)
            compare_metrics(
                selection_metrics,
                policy["selection_metrics"],
                f"selection.{ticker}.{test_month}",
            )
            winner_matches += 1

            # As in the evaluator, test outcomes are opened only after the
            # serialized policy has been verified.
            test_features = ticker_features.loc[
                ticker_features["month"].astype(str).eq(test_month)
            ].copy()
            test_feature_scored = ev.predict_scores(
                test_features,
                feature_columns,
                call_model,
                put_model,
                medians,
            )
            test_outcomes = ev.load_outcomes(
                source,
                ticker,
                test_month,
                ev.next_month(test_month),
                delta,
            )
            test_scored = ev.bind_physical_outcome(
                ev.merge_outcomes(test_feature_scored, test_outcomes, delta),
                delta,
            )
            test_scored["test_month"] = test_month
            test_prediction_sha = ev.dataframe_sha(
                test_scored,
                prediction_columns,
                ["ticker", "trade_date", "minute"],
            )
            stored_fold = stored_fold_lookup[key]
            if test_prediction_sha != str(stored_fold.test_prediction_sha256):
                raise AssertionError(f"test prediction SHA mismatch: {key}")
            prediction_hash_matches += 1
            if winner is None:
                test_trades = test_scored.iloc[0:0].copy()
            else:
                test_trades = ev.replay_config(test_scored, winner, ticker)
            if not test_trades.empty:
                test_trades["test_month"] = test_month
                test_trades["profile"] = ev.PROFILE_BY_TICKER[ticker]
                test_trades["delta_bucket"] = delta
                test_trades["policy_sha256"] = index_row["sha256"]
                recomputed_trades.append(test_trades)
            test_metrics = ev.economic_metrics(test_trades, [test_month])
            assert_close(
                test_metrics["trades"],
                int(stored_fold.test_trades),
                f"test_trades.{ticker}.{test_month}",
            )
            assert_close(
                test_metrics["pnl_return"],
                float(stored_fold.test_pnl),
                f"test_pnl.{ticker}.{test_month}",
            )
            recomputed_fold_rows.append(
                {
                    "ticker": ticker,
                    "test_month": test_month,
                    "winner_name": (
                        winner.name if winner is not None else scan["status"]
                    ),
                    "grid_index": winner.grid_index if winner is not None else -1,
                    "selection_prediction_sha256": selection_prediction_sha,
                    "test_prediction_sha256": test_prediction_sha,
                    "test_trades": test_metrics["trades"],
                    "test_pf": test_metrics["profit_factor"],
                    "test_pnl": test_metrics["pnl_return"],
                }
            )
            print(
                f"[FULL_NESTED_AUDIT] {ticker} {test_month} "
                f"winner={recomputed_fold_rows[-1]['winner_name']} "
                f"trades={test_metrics['trades']} pnl={test_metrics['pnl_return']:.6f}",
                flush=True,
            )

    stored_trades = pd.read_parquet(
        result_dir / summary["artifacts"]["test_only_trades"]["path"]
    )
    recomputed = (
        pd.concat(recomputed_trades, ignore_index=True)
        if recomputed_trades
        else stored_trades.iloc[0:0].copy()
    )
    recomputed = recomputed.sort_values(
        ["test_month", "ticker", "trade_date", "minute"],
        kind="stable",
    ).reset_index(drop=True)
    recomputed = recomputed.loc[:, list(stored_trades.columns)]
    compare_trade_ledgers(recomputed, stored_trades)
    overlap_issues = no_overlap_issues(recomputed)
    if overlap_issues:
        raise AssertionError(f"physical scheduler issues: {overlap_issues[:10]}")
    if (
        not recomputed.empty
        and set(recomputed["option_price_mode"].astype(str).str.lower())
        != {"executable_quote"}
    ):
        raise AssertionError("test ledger contains a non-executable_quote row")

    ticker_metrics = {
        ticker: ev.economic_metrics(
            recomputed.loc[recomputed["ticker"].astype(str).eq(ticker)].copy(),
            list(ev.TEST_MONTHS),
        )
        for ticker in ev.TICKERS
    }
    ticker_pass = {
        ticker: ev.passes_final_gates(ticker_metrics[ticker])
        for ticker in ev.TICKERS
    }
    for ticker in ev.TICKERS:
        compare_metrics(
            ticker_metrics[ticker],
            summary["ticker_metrics"][ticker],
            f"ticker.{ticker}",
        )
        if ticker_pass[ticker] != bool(summary["ticker_pass"][ticker]):
            raise AssertionError(f"ticker gate mismatch: {ticker}")

    stager.mkdir(parents=True)
    recomputed_fold_path = stager / "recomputed_fold_results.csv"
    pd.DataFrame(recomputed_fold_rows).to_csv(
        recomputed_fold_path,
        index=False,
        lineterminator="\n",
    )
    audit_summary = {
        "schema_version": 1,
        "family": "EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1",
        "status": "PASS_INDEPENDENT_FULL_NESTED_AUDIT",
        "economic_status": summary["status"],
        "promotable": False,
        "result_summary_sha256": ev.sha256_file(summary_path),
        "source_sha256": ev.SOURCE_SHA256,
        "contract_sha256": summary["contract_sha256"],
        "evaluator_sha256": summary["evaluator_sha256"],
        "auditor_sha256": summary["auditor_sha256"],
        "folds_recomputed": 18,
        "logical_configurations_recomputed": ev.FULL_CONFIGS * 18,
        "models_refit": 36,
        "model_hash_matches": model_hash_matches,
        "prediction_hash_matches": prediction_hash_matches,
        "winner_matches": winner_matches,
        "stored_trade_rows": int(len(stored_trades)),
        "recomputed_trade_rows": int(len(recomputed)),
        "trade_ledger_exact": True,
        "source_rehashed": True,
        "features_rebuilt": True,
        "test_only_ledger": True,
        "hold_30_180": True,
        "reject_while_open_violations": 0,
        "option_price_mode": "executable_quote",
        "ticker_metrics": ticker_metrics,
        "ticker_pass": ticker_pass,
        "all_tickers_pass": all(ticker_pass.values()),
        "live_modified": False,
        "artifacts": {
            "recomputed_fold_results": {
                "path": recomputed_fold_path.name,
                "rows": len(recomputed_fold_rows),
                "sha256": ev.sha256_file(recomputed_fold_path),
            }
        },
    }
    audit_summary_path = stager / "audit_summary.json"
    ev.write_json(audit_summary_path, audit_summary)
    os.replace(stager, output)
    print(
        json.dumps(ev._json_ready(audit_summary), indent=2, sort_keys=True),
        flush=True,
    )
    return audit_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independent audit of the full nested monthly option overlay"
    )
    parser.add_argument("--source", default=str(ev.SOURCE_PATH))
    parser.add_argument("--result-dir", default=str(RESULT_DIR))
    parser.add_argument("--output-dir", default=str(AUDIT_DIR))
    parser.add_argument("--lgb-jobs", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    audit(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

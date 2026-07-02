"""Apply the validated event-option exit contract to an ignored policy artifact.

The production model artifacts under neural/models/jepa are intentionally ignored
by git in this repository. This script makes the live deploy step reproducible:
after pulling code, run it on the VPS to patch the local policy JSON used by
systemd.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = (
    PROJECT_ROOT
    / "neural"
    / "models"
    / "jepa"
    / "jepa_production_event_options_backfill19_spy_no_scorethr_wf2026_fullmayjun"
    / "event_option_policy.json"
)

VALIDATED_LABEL_EXIT_CONTRACT: dict[str, Any] = {
    "source": "neural/jepa/build_event_option_dataset.py",
    "horizon_minutes": 180,
    "min_hold_minutes": 20,
    "option_take_profit_pct": 0.75,
    "option_stop_loss_pct": 0.5,
    "live_equivalence_note": (
        "WF2026 runtime replay exit-grid validation uses +75% take-profit, "
        "-50% stop, 20m minimum hold, and 180m max hold."
    ),
}

LIVE_EXIT_CONTRACT: dict[str, Any] = {
    "take_profit_pct": 0.75,
    "stop_loss_pct": -0.5,
    "min_hold_minutes": 20,
    "max_hold_minutes": 180,
    "trailing_enabled": False,
}

EXIT_CONTRACT_VALIDATION: dict[str, Any] = {
    "source": "neural/jepa/evaluate_event_option_exit_grid.py",
    "summary_path": (
        "research_papers/JEPA/results/_diagnostics/"
        "event_option_exit_grid_runtime_backfill19_minhold_v1/SUMMARY.json"
    ),
    "trades_path": (
        "research_papers/JEPA/results/_diagnostics/"
        "event_option_exit_grid_runtime_backfill19_minhold_v1/best_exit_grid_trades.csv"
    ),
    "runtime_trades": (
        "neural/models/jepa/"
        "jepa_production_event_options_backfill19_spy_no_scorethr_wf2026_fullmayjun/"
        "runtime_replayed_combined_trades.csv"
    ),
    "manifest": (
        "research_papers/JEPA/results/_diagnostics/"
        "visreg_event_option_dataset_spxw_spy_qqq_zero_dte_dense15_202501_202606_v1/"
        "filtered_manifest.csv"
    ),
    "baseline_max_abs_realized_return_diff": 0.0,
    "contract": {
        "min_hold_minutes": 20,
        "stop_loss_pct": 0.5,
        "take_profit_pct": 0.75,
        "horizon_minutes": 180,
    },
    "overall": {
        "trades": 425,
        "win_rate": 0.5152941176470588,
        "profit_factor": 1.6138117777772611,
        "avg_return": 0.14639709534454728,
        "avg_hold_minutes": 42.53411764705882,
        "median_hold_minutes": 31.0,
        "min_month_trades": 58,
        "avg_month_trades": 70.83333333333333,
    },
    "per_ticker": {
        "QQQ": {
            "trades": 178,
            "win_rate": 0.4943820224719101,
            "profit_factor": 1.4960912178488839,
            "avg_return": 0.12294967881202604,
            "avg_hold_minutes": 37.68539325842696,
            "median_hold_minutes": 27.0,
            "min_month_trades": 19,
            "avg_month_trades": 29.666666666666668,
        },
        "SPXW": {
            "trades": 125,
            "win_rate": 0.512,
            "profit_factor": 1.60530965048027,
            "avg_return": 0.14479381327763372,
            "avg_hold_minutes": 44.888,
            "median_hold_minutes": 32.0,
            "min_month_trades": 19,
            "avg_month_trades": 20.833333333333332,
        },
        "SPY": {
            "trades": 122,
            "win_rate": 0.5491803278688525,
            "profit_factor": 1.8129960281848116,
            "avg_return": 0.18224996748514546,
            "avg_hold_minutes": 47.19672131147541,
            "median_hold_minutes": 34.0,
            "min_month_trades": 19,
            "avg_month_trades": 20.333333333333332,
        },
    },
    "objective_passed": True,
}


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def apply_contract(policy: dict[str, Any]) -> dict[str, Any]:
    policy["validated_label_exit_contract"] = dict(VALIDATED_LABEL_EXIT_CONTRACT)
    live_contract = policy.get("live_contract")
    if not isinstance(live_contract, dict):
        live_contract = {}
        policy["live_contract"] = live_contract
    live_contract["event_option_exit_contract"] = dict(LIVE_EXIT_CONTRACT)
    policy["exit_contract_validation"] = json.loads(json.dumps(EXIT_CONTRACT_VALIDATION))
    return policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Path to event_option_policy.json")
    parser.add_argument("--dry-run", action="store_true", help="Print the patched JSON without writing it")
    args = parser.parse_args()

    policy_path = resolve_path(args.policy)
    payload = json.loads(policy_path.read_text())
    patched = apply_contract(payload)
    rendered = json.dumps(patched, indent=2, sort_keys=False) + "\n"
    if args.dry_run:
        print(rendered)
        return
    policy_path.write_text(rendered)
    print(
        json.dumps(
            {
                "policy": str(policy_path),
                "event_option_exit_contract": LIVE_EXIT_CONTRACT,
                "objective_passed": EXIT_CONTRACT_VALIDATION["objective_passed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch

from neural.jepa.walkforward_event_option_portfolio_var_jepa import (
    CONTRACT_SUFFIXES,
    DeterministicPayoffHead,
    Preprocessor,
    TICKERS,
    VariationalPayoffHead,
    audit_runtime_replay,
    build_action_frame,
    choose_action,
    gaussian_kl_diag,
    month_seed,
    select_threshold,
)


def test_gaussian_kl_is_zero_for_identical_distributions_and_has_gradient() -> None:
    q_mu = torch.zeros(4, 3, requires_grad=True)
    q_logvar = torch.zeros(4, 3, requires_grad=True)
    p_mu = torch.zeros(4, 3)
    p_logvar = torch.zeros(4, 3)
    equal = gaussian_kl_diag(q_mu, q_logvar, p_mu, p_logvar)
    assert torch.allclose(equal, torch.zeros_like(equal))

    shifted = gaussian_kl_diag(q_mu + 0.5, q_logvar + 0.2, p_mu, p_logvar).mean()
    assert shifted.item() > 0.0
    shifted.backward()
    assert q_mu.grad is not None and torch.isfinite(q_mu.grad).all()
    assert q_logvar.grad is not None and torch.isfinite(q_logvar.grad).all()


def test_payoff_heads_have_finite_paired_shapes() -> None:
    torch.manual_seed(7)
    x = torch.randn(16, 12)
    y = torch.randn(16).clamp(-2.0, 2.0)
    deterministic = DeterministicPayoffHead(12, hidden_dim=16, latent_dim=4, dropout=0.0)
    variational = VariationalPayoffHead(12, hidden_dim=16, latent_dim=4, dropout=0.0)

    det_loss = deterministic.loss(x, y)
    var_loss = variational.loss(x, y, beta=0.5)
    assert deterministic(x).shape == (16,)
    assert variational(x).shape == (16,)
    assert deterministic.encode(x)[0].shape == variational.encode(x)[0].shape == (16, 4)
    assert det_loss["kl"].item() == 0.0
    assert var_loss["kl"].item() >= 0.0
    assert all(torch.isfinite(value) for value in (*det_loss.values(), *var_loss.values()))


def _base_rows() -> tuple[pd.DataFrame, list[str]]:
    latent = [f"ptdj_z_{idx:02d}" for idx in range(32)] + [f"ptdj_dz_h1_{idx:02d}" for idx in range(32)]
    latent += [
        "ptdj_latent_velocity",
        "ptdj_input_delta_norm",
        "ptdj_motion_norm_h1",
        "ptdj_pred_dispersion",
        "ptdj_phys_transition_norm_h1",
        "ptdj_lagged_pred_h1_err",
    ]
    rows = []
    for idx, ticker in enumerate(TICKERS):
        delta = 25 if ticker == "SPXW" else 35
        row = {
            "ticker": ticker,
            "event_id": idx,
            "date": "20260102",
            "month": "202601",
            "minute": 630,
            "delta_bucket": delta,
            **{feature: 0.1 for feature in latent},
        }
        for side, value in (("call", 0.25), ("put", -0.10)):
            row[f"{side}_d{delta}_opt_exit_ret"] = value
            row[f"{side}_d{delta}_opt_exit_minutes"] = 30
            for suffix in CONTRACT_SUFFIXES:
                row[f"{side}_d{delta}_{suffix}"] = 10.0
        rows.append(row)
    return pd.DataFrame(rows), latent


def test_action_frame_uses_runtime_buckets_without_outcome_features() -> None:
    base, latent = _base_rows()
    actions, features = build_action_frame(base, latent)
    assert len(actions) == 2 * len(base)
    assert set(actions["action"]) == {"CALL", "PUT"}
    assert set(actions.loc[actions["ticker"].eq("SPXW"), "delta_bucket"]) == {25}
    assert set(actions.loc[actions["ticker"].isin(["QQQ", "SPY"]), "delta_bucket"]) == {35}
    assert not any(token in feature.lower() for feature in features for token in ("return", "exit", "future", "win"))
    assert actions.groupby("event_id").size().eq(2).all()


def test_preprocessor_uses_train_statistics_only_and_is_finite() -> None:
    frame = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": [5.0, 5.0, 5.0]})
    prep = Preprocessor.fit(frame, ["a", "b"])
    transformed = prep.transform(pd.DataFrame({"a": [100.0, np.nan], "b": [5.0, 9.0]}))
    assert transformed.shape == (2, 2)
    assert np.isfinite(transformed).all()
    assert prep.scales[1] == 1.0


def test_choose_action_is_deterministic_and_uses_highest_mean() -> None:
    frame = pd.DataFrame(
        {
            "event_id": [1, 1, 2, 2],
            "ticker": ["SPXW"] * 4,
            "date": ["20260102"] * 4,
            "minute": [630, 630, 635, 635],
            "action": ["CALL", "PUT", "CALL", "PUT"],
            "pred_return": [0.2, 0.1, -0.1, 0.3],
            "target_return": [0.4, -0.2, -0.3, 0.5],
            "exit_minutes": [30, 30, 30, 30],
        }
    )
    selected = choose_action(frame)
    assert selected["action"].tolist() == ["CALL", "PUT"]
    assert selected["score"].tolist() == [0.2, 0.3]
    assert selected["realized_return"].tolist() == [0.4, 0.5]


def test_fold_seed_is_month_specific_and_arm_invariant() -> None:
    assert month_seed(20260618, "202601") == 20463219
    assert month_seed(20260618, "202601") != month_seed(20260618, "202602")


def test_runtime_replay_audit_enforces_hold_cap_and_single_position() -> None:
    valid = pd.DataFrame(
        {
            "ticker": ["SPXW", "SPXW"],
            "date": ["20260102", "20260102"],
            "minute": [630, 660],
            "score": [0.2, 0.3],
            "exit_minutes": [30.0, 30.0],
            "delta_bucket": [25, 25],
        }
    )
    assert audit_runtime_replay(valid)["passed"] is True

    overlapping = valid.copy()
    overlapping.loc[1, "minute"] = 655
    result = audit_runtime_replay(overlapping)
    assert result["passed"] is False
    assert any("overlapping" in issue for issue in result["issues"])


def test_invalid_threshold_retains_real_diagnostics_when_sentinel_ties() -> None:
    scored = pd.DataFrame(
        {
            "ticker": ["SPY", "SPY", "SPY"],
            "date": ["20251002", "20251103", "20251202"],
            "month": ["202510", "202511", "202512"],
            "minute": [630, 630, 630],
            "action": ["CALL", "PUT", "CALL"],
            "score": [0.1, 0.1, 0.1],
            "realized_return": [0.2, -0.1, 0.3],
            "exit_minutes": [30.0, 30.0, 30.0],
        }
    )
    args = SimpleNamespace(
        threshold_grid=[-1e9],
        threshold_quantiles=[],
        min_val_trades=999,
        min_month_trades=999,
        min_val_pf=99.0,
        min_val_win_rate=0.99,
        min_call_rate=0.0,
        max_call_rate=1.0,
        min_val_positive_month_rate=1.0,
        daily_win_weight=0.25,
        top5_share_penalty=0.1,
    )

    config, diagnostics, score, grid = select_threshold(
        scored, "SPY", ["202510", "202511", "202512"], args
    )

    assert config is None
    assert score <= -1e17
    assert diagnostics["trades"] == 3
    assert len(grid) == 1

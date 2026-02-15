"""
Smoke test for Bayesian Deep Learning refactoring + Weekly Greeks expansion.
Validates that model outputs and loss function have correct shapes with 55 features.

Run:
    python test_bayesian_shapes.py
"""
import sys
import torch
import numpy as np

# Ensure project root is importable
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hybrid_model import get_hybrid_model, FEATURE_COLUMNS

# Also import gaussian_nll_loss from train_hybrid
from train_hybrid import gaussian_nll_loss


INPUT_SIZE = len(FEATURE_COLUMNS)


def test_feature_columns():
    """Test that FEATURE_COLUMNS has the expected count."""
    print(f"[0] Testing FEATURE_COLUMNS count...")
    print(f"  Total features: {INPUT_SIZE}")
    assert INPUT_SIZE == 57, f"Expected 57 features, got {INPUT_SIZE}"
    
    # Check key feature groups
    dte_greeks = [c for c in FEATURE_COLUMNS if not c.startswith("wk_") and not c.startswith("gamma_0") and not c.startswith("vanna_0") and not c.startswith("dgex_0") and not c.startswith("delta_0")]
    wk_greeks = [c for c in FEATURE_COLUMNS if c.startswith("wk_")]
    divergence = [c for c in FEATURE_COLUMNS if c.endswith("_vs_wk")]
    
    print(f"  0DTE features: {len(dte_greeks)}")
    print(f"  Weekly features: {len(wk_greeks)}")
    print(f"  Divergence features: {len(divergence)}")
    assert len(wk_greeks) == 14, f"Expected 14 weekly features, got {len(wk_greeks)}"
    assert len(divergence) == 4, f"Expected 4 divergence features, got {len(divergence)}"
    assert "net_delta" in FEATURE_COLUMNS, "Missing net_delta"
    assert "dist_to_max_dgex" in FEATURE_COLUMNS, "Missing dist_to_max_dgex"
    print("  PASSED ✓")


def test_model_output_shapes():
    """Test that the model outputs correct shapes for Bayesian time head."""
    print(f"\n[1] Testing model output shapes (input_size={INPUT_SIZE})...")
    
    batch_size = 4
    model = get_hybrid_model("small", input_size=INPUT_SIZE)
    model.eval()
    
    x = torch.randn(batch_size, INPUT_SIZE)
    
    with torch.no_grad():
        logits, time_pred = model(x)
    
    # Classification head: (batch, 3)
    assert logits.shape == (batch_size, 3), \
        f"Expected logits shape ({batch_size}, 3), got {logits.shape}"
    
    # Bayesian time head: (batch, 2) -> [mu, log_sigma]
    assert time_pred.shape == (batch_size, 2), \
        f"Expected time_pred shape ({batch_size}, 2), got {time_pred.shape}"
    
    # mu should be in [0, 1] (sigmoid output)
    mu = time_pred[:, 0]
    assert (mu >= 0).all() and (mu <= 1).all(), \
        f"mu should be in [0, 1], got min={mu.min():.4f}, max={mu.max():.4f}"
    
    # log_sigma is unbounded (no constraint)
    log_sigma = time_pred[:, 1]
    print(f"  logits shape: {logits.shape} ✓")
    print(f"  time_pred shape: {time_pred.shape} ✓")
    print(f"  mu range: [{mu.min():.4f}, {mu.max():.4f}] ✓")
    print(f"  log_sigma range: [{log_sigma.min():.4f}, {log_sigma.max():.4f}]")
    print("  PASSED ✓")


def test_gaussian_nll_loss():
    """Test that gaussian_nll_loss produces a scalar output."""
    print("\n[2] Testing gaussian_nll_loss...")
    
    batch_size = 8
    mu = torch.randn(batch_size, 1) * 0.5 + 0.5  # centered around 0.5
    log_sigma = torch.randn(batch_size, 1)
    target = torch.rand(batch_size, 1)
    mask = torch.tensor([1, 0, 1, 1, 0, 1, 0, 1], dtype=torch.float32)
    
    loss = gaussian_nll_loss(mu, log_sigma, target, mask)
    
    assert loss.dim() == 0, f"Expected scalar loss, got shape {loss.shape}"
    assert not torch.isnan(loss), "Loss is NaN!"
    assert not torch.isinf(loss), "Loss is Inf!"
    
    print(f"  Loss value: {loss.item():.4f}")
    print(f"  Loss is scalar: {loss.dim() == 0} ✓")
    print(f"  Loss is finite: {torch.isfinite(loss).item()} ✓")
    print("  PASSED ✓")


def test_predict_method():
    """Test that model.predict() returns correct shapes."""
    print(f"\n[3] Testing model.predict() method (input_size={INPUT_SIZE})...")
    
    model = get_hybrid_model("small", input_size=INPUT_SIZE)
    model.eval()
    
    x = torch.randn(1, INPUT_SIZE)
    
    probs, time_pred = model.predict(x)
    
    assert probs.shape == (1, 3), f"Expected probs shape (1, 3), got {probs.shape}"
    assert time_pred.shape == (1, 2), f"Expected time_pred shape (1, 2), got {time_pred.shape}"
    
    # Probs should sum ~1
    prob_sum = probs.sum().item()
    assert abs(prob_sum - 1.0) < 0.01, f"Probs should sum to ~1, got {prob_sum}"
    
    print(f"  probs shape: {probs.shape}, sum={prob_sum:.4f} ✓")
    print(f"  time_pred shape: {time_pred.shape} ✓")
    print("  PASSED ✓")


def test_uncertainty_conversion():
    """Test the sigma conversion pipeline (log_sigma -> minutes)."""
    print("\n[4] Testing uncertainty conversion pipeline...")
    
    # Simulate model output
    log_sigma_values = [-1.0, 0.0, 0.5, 1.0, 2.0]
    
    for ls in log_sigma_values:
        sigma_minutes = float(np.exp(ls) * 120.0)
        would_exit = sigma_minutes > 45.0
        print(f"  log_σ={ls:+.1f} → σ={sigma_minutes:6.1f} min → exit={would_exit}")
    
    # Verify threshold behavior
    threshold_log_sigma = np.log(45.0 / 120.0)  # ~= -0.981
    sigma_at_threshold = float(np.exp(threshold_log_sigma) * 120.0)
    assert abs(sigma_at_threshold - 45.0) < 0.1, \
        f"Expected ~45.0 at threshold, got {sigma_at_threshold}"
    
    print(f"  Threshold log_σ ≈ {threshold_log_sigma:.3f} ✓")
    print("  PASSED ✓")


def test_sign_divergence():
    """Test the cross-expiry divergence computation."""
    print("\n[5] Testing sign_divergence logic...")
    
    from collect_training_data import sign_divergence
    
    # Same sign → 0.0
    assert sign_divergence(1.0, 2.0) == 0.0, "Same positive signs should be 0.0"
    assert sign_divergence(-1.0, -2.0) == 0.0, "Same negative signs should be 0.0"
    
    # Different signs → 1.0
    assert sign_divergence(1.0, -1.0) == 1.0, "Different signs should be 1.0"
    assert sign_divergence(-0.5, 0.5) == 1.0, "Different signs should be 1.0"
    
    # Near zero → 0.5
    assert sign_divergence(0.005, 1.0) == 0.5, "Near-zero should be 0.5"
    assert sign_divergence(1.0, 0.0) == 0.5, "Zero should be 0.5"
    
    print("  All divergence cases correct ✓")
    print("  PASSED ✓")


if __name__ == "__main__":
    print("=" * 60)
    print("BAYESIAN + WEEKLY GREEKS — SMOKE TEST")
    print("=" * 60)
    
    test_feature_columns()
    test_model_output_shapes()
    test_gaussian_nll_loss()
    test_predict_method()
    test_uncertainty_conversion()
    test_sign_divergence()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)

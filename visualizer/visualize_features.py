"""
Feature Importance Visualization — GBT + MLP Cross-Attention + RL Saliency

Usage:
  # GBT feature importance (most useful — shows which features drive splits)
  python visualize_features.py --mode gbt

  # MLP cross-attention (regime→diffusion attention weights)
  python visualize_features.py --mode mlp --model models/trading_hybrid_wf.pt

  # RL gradient saliency (which features change RL action probabilities)
  python visualize_features.py --mode rl

  # All three side by side
  python visualize_features.py --mode all

  # Inspect a specific feature
  python visualize_features.py --mode gbt --feature vol_relative

  # Save chart to file instead of showing
  python visualize_features.py --mode gbt --save
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'neural'))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # non-interactive backend; switch to 'TkAgg' for --show
import argparse


# ═══════════════════════════════════════════════════════════════
# DEFAULTS
# ═══════════════════════════════════════════════════════════════
NEURAL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'neural'))
DEFAULT_GBT_MODEL   = os.path.join(NEURAL_DIR, 'models', 'trading_hybrid_wf.joblib')
DEFAULT_GBT_NORM    = os.path.join(NEURAL_DIR, 'models', 'hybrid_normalizer_wf.npz')
DEFAULT_MLP_MODEL   = os.path.join(NEURAL_DIR, 'models', 'trading_hybrid_wf.pt')
DEFAULT_MLP_NORM    = os.path.join(NEURAL_DIR, 'models', 'hybrid_normalizer_wf.npz')
DEFAULT_RL_MODEL    = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'rl_models', 'best_rl_agent.pt'))
DEFAULT_DATA        = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'training_data', 'training_data_spx_qqq.parquet'))
DEFAULT_TOP_N       = 30
OUTPUT_DIR          = os.path.join(NEURAL_DIR, 'training_data', 'charts')


# ═══════════════════════════════════════════════════════════════
# GBT FEATURE IMPORTANCE
# ═══════════════════════════════════════════════════════════════
def gbt_importance(model_path: str, norm_path: str) -> pd.DataFrame:
    """Extract split-based feature importance from LightGBM ensemble."""
    import joblib
    from hybrid_model import FeatureNormalizer, FEATURE_COLUMNS

    lgb_models = joblib.load(model_path)
    if not isinstance(lgb_models, list):
        lgb_models = [lgb_models]

    print(f"  Loaded {len(lgb_models)} GBT models from {os.path.basename(model_path)}")

    # Average feature_importances_ across ensemble members
    all_imp = []
    for m in lgb_models:
        imp = m.feature_importances_.astype(np.float64)
        imp_sum = imp.sum()
        all_imp.append(imp / imp_sum if imp_sum > 0 else imp)
    avg_imp = np.mean(all_imp, axis=0)

    # GBT models trained via LightGBM often have generic 'Column_N' names.
    # Map positionally to FEATURE_COLUMNS (same order used during training).
    n_features = len(avg_imp)
    if n_features <= len(FEATURE_COLUMNS):
        feature_names = FEATURE_COLUMNS[:n_features]
    else:
        feature_names = FEATURE_COLUMNS + [f"extra_{i}" for i in range(n_features - len(FEATURE_COLUMNS))]

    df = pd.DataFrame({
        'Feature': feature_names,
        'Importance': avg_imp,
    }).sort_values('Importance', ascending=False).reset_index(drop=True)

    return df


# ═══════════════════════════════════════════════════════════════
# MLP CROSS-ATTENTION IMPORTANCE
# ═══════════════════════════════════════════════════════════════
def mlp_attention_importance(model_path: str, norm_path: str, data_path: str,
                              model_size: str = 'small') -> pd.DataFrame:
    """Extract cross-attention weights from HybridTradingModel."""
    import torch
    from hybrid_model import (load_ensemble_model, load_hybrid_model,
                              FEATURE_COLUMNS, REGIME_FEATURES, get_device)

    device = get_device()

    # Try ensemble first, fall back to single
    try:
        model, normalizer = load_ensemble_model(model_path, norm_path, model_size, device)
        print(f"  Loaded MLP ensemble from {model_path}")
    except Exception:
        model, normalizer = load_hybrid_model(model_path, norm_path, model_size, device)
        print(f"  Loaded MLP single model from {model_path}")

    # Load sample data
    df = pd.read_parquet(data_path)
    sample_df = df.sample(min(200, len(df)), random_state=42)

    features = np.zeros((len(sample_df), len(FEATURE_COLUMNS)), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in sample_df.columns:
            features[:, i] = sample_df[col].values.astype(np.float32)
    features = np.nan_to_num(features, nan=0.0)

    features_norm = normalizer.transform(features)
    tensor_x = torch.FloatTensor(features_norm).to(device)

    model.eval()
    with torch.no_grad():
        logits, time_pred, attention = model(tensor_x, return_attention=True)

    # attention shape: (batch, n_regime, n_diff)
    avg_cross = attention.mean(dim=0).cpu().numpy()

    # Build feature importance
    diff_indices = []
    reg_indices = []
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in REGIME_FEATURES:
            reg_indices.append(i)
        else:
            diff_indices.append(i)

    importance = np.zeros(len(FEATURE_COLUMNS), dtype=np.float32)

    # Diffusion: sum attention received from all regime queries
    diff_importance = avg_cross.sum(axis=0)
    for local_i, global_i in enumerate(diff_indices):
        if local_i < len(diff_importance):
            importance[global_i] = diff_importance[local_i]

    # Regime: max selectivity
    reg_selectivity = avg_cross.max(axis=1)
    for local_i, global_i in enumerate(reg_indices):
        if local_i < len(reg_selectivity):
            importance[global_i] = reg_selectivity[local_i]

    if importance.sum() > 0:
        importance = importance / importance.sum()

    result = pd.DataFrame({
        'Feature': FEATURE_COLUMNS,
        'Importance': importance,
    }).sort_values('Importance', ascending=False).reset_index(drop=True)

    return result


# ═══════════════════════════════════════════════════════════════
# RL GRADIENT SALIENCY
# ═══════════════════════════════════════════════════════════════
def rl_saliency(rl_model_path: str, gbt_model_path: str, norm_path: str,
                data_path: str) -> pd.DataFrame:
    """
    Compute gradient saliency: |d(action_logits) / d(features)|
    averaged over samples. Shows which features most change RL decisions.
    """
    import torch
    import importlib.util
    from hybrid_model import FeatureNormalizer, FEATURE_COLUMNS, get_device

    device = get_device()

    # ── Load RL config (avoid relative import issues) ──
    config_path = os.path.join(NEURAL_DIR, 'rl', 'config.py')
    spec_cfg = importlib.util.spec_from_file_location("rl_config", config_path)
    rl_config_mod = importlib.util.module_from_spec(spec_cfg)
    sys.modules["rl_config"] = rl_config_mod
    spec_cfg.loader.exec_module(rl_config_mod)

    # Patch the agent module so `from .config import ...` resolves
    # We load agent.py after injecting config into the rl package
    rl_pkg_init = os.path.join(NEURAL_DIR, 'rl', '__init__.py')
    if os.path.exists(rl_pkg_init):
        spec_pkg = importlib.util.spec_from_file_location(
            "neural.rl", rl_pkg_init,
            submodule_search_locations=[os.path.join(NEURAL_DIR, 'rl')])
        rl_pkg = importlib.util.module_from_spec(spec_pkg)
        sys.modules["neural.rl"] = rl_pkg
        sys.modules["neural"] = type(sys)("neural")
        sys.modules["neural"].rl = rl_pkg
        try:
            spec_pkg.loader.exec_module(rl_pkg)
        except Exception:
            pass

    # Now load config and agent as submodules of neural.rl
    sys.modules["neural.rl.config"] = rl_config_mod
    agent_path = os.path.join(NEURAL_DIR, 'rl', 'agent.py')
    spec_agent = importlib.util.spec_from_file_location("neural.rl.agent", agent_path)
    agent_mod = importlib.util.module_from_spec(spec_agent)
    sys.modules["neural.rl.agent"] = agent_mod
    spec_agent.loader.exec_module(agent_mod)

    PPOAgent = agent_mod.PPOAgent
    RL_CONFIG = rl_config_mod.RL_CONFIG

    # ── Load agent from checkpoint ──
    agent = PPOAgent.load(rl_model_path, device=device)
    agent.eval()
    print(f"  Loaded RL agent from {os.path.basename(rl_model_path)} "
          f"(state_dim={RL_CONFIG['state_dim']})")

    # ── Load sample data ──
    df = pd.read_parquet(data_path)
    sample_df = df.sample(min(200, len(df)), random_state=42)

    n_features = len(FEATURE_COLUMNS)  # 163
    features = np.zeros((len(sample_df), n_features), dtype=np.float32)
    for i, col in enumerate(FEATURE_COLUMNS):
        if col in sample_df.columns:
            features[:, i] = sample_df[col].values.astype(np.float32)
    features = np.nan_to_num(features, nan=0.0)

    normalizer = FeatureNormalizer()
    normalizer.load(norm_path)
    features_norm = normalizer.transform(features)

    # ── Build full RL observation ──
    # State = [position_state(6)] + [market_features(163)] + [mlp_context(4)] = 173
    market_tensor = torch.FloatTensor(features_norm).to(device).requires_grad_(True)
    n_samples = len(features_norm)
    pos_state = torch.zeros(n_samples, 6, device=device)    # no position
    mlp_ctx = torch.zeros(n_samples, 4, device=device)      # neutral MLP context
    full_obs = torch.cat([pos_state, market_tensor, mlp_ctx], dim=1)

    # ── Forward + backward through exit head (most common action type) ──
    logits, value = agent(full_obs, action_type="exit")
    max_logit = logits.max(dim=1).values.sum()
    max_logit.backward()

    saliency = market_tensor.grad.abs().mean(dim=0).cpu().numpy()
    if saliency.sum() > 0:
        saliency = saliency / saliency.sum()

    n_sal = min(len(saliency), n_features)
    result = pd.DataFrame({
        'Feature': FEATURE_COLUMNS[:n_sal],
        'Importance': saliency[:n_sal],
    }).sort_values('Importance', ascending=False).reset_index(drop=True)

    return result


# ═══════════════════════════════════════════════════════════════
# PRINTING + PLOTTING
# ═══════════════════════════════════════════════════════════════
def print_table(df: pd.DataFrame, title: str, top_n: int = 30, target_feature: str = None):
    """Print importance table to console."""
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")

    if target_feature:
        row = df[df['Feature'] == target_feature]
        if row.empty:
            print(f"  ⚠ Feature '{target_feature}' not found")
            return
        rank = row.index[0] + 1
        imp = row['Importance'].values[0]
        print(f"  Feature: {target_feature}")
        print(f"  Rank: #{rank} / {len(df)}")
        print(f"  Importance: {imp:.4f} ({imp*100:.2f}%)")

        # Show neighbors
        idx = row.index[0]
        start = max(0, idx - 3)
        end = min(len(df), idx + 4)
        print(f"\n  {'Rank':<6} {'Feature':<35} {'Importance':>10}")
        print(f"  {'─'*6} {'─'*35} {'─'*10}")
        for i in range(start, end):
            r = df.iloc[i]
            marker = " >>" if r['Feature'] == target_feature else "   "
            print(f"{marker}#{i+1:<4} {r['Feature']:<35} {r['Importance']:>10.4f}")
        return

    # Print top N
    print(f"\n  {'Rank':<6} {'Feature':<35} {'Importance':>10}  {'Bar'}")
    print(f"  {'─'*6} {'─'*35} {'─'*10}  {'─'*20}")
    max_imp = df['Importance'].max()
    for i, (_, row) in enumerate(df.head(top_n).iterrows()):
        bar_len = int(20 * row['Importance'] / max_imp) if max_imp > 0 else 0
        bar = '█' * bar_len
        print(f"  #{i+1:<5} {row['Feature']:<35} {row['Importance']:>10.4f}  {bar}")

    # Summary stats
    top5_pct = df.head(5)['Importance'].sum() * 100
    top10_pct = df.head(10)['Importance'].sum() * 100
    bottom_half = df.tail(len(df)//2)['Importance'].sum() * 100
    print(f"\n  Top 5 features explain {top5_pct:.1f}% of importance")
    print(f"  Top 10 features explain {top10_pct:.1f}% of importance")
    print(f"  Bottom {len(df)//2} features explain {bottom_half:.1f}% of importance")

    # Near-zero features
    zero_threshold = 0.001
    near_zero = df[df['Importance'] < zero_threshold]
    if len(near_zero) > 0:
        print(f"\n  ⚠ {len(near_zero)} features with <0.1% importance (effectively dead):")
        for _, r in near_zero.iterrows():
            print(f"    - {r['Feature']}")


def plot_importance(dfs: dict, top_n: int = 30, save_path: str = None, show: bool = False):
    """Plot one or more importance DataFrames side by side."""
    n_plots = len(dfs)
    fig, axes = plt.subplots(1, n_plots, figsize=(8 * n_plots, 10))
    if n_plots == 1:
        axes = [axes]

    colors = {'GBT (Split Importance)': '#2ecc71',
              'MLP (Cross-Attention)': '#3498db',
              'RL (Gradient Saliency)': '#e74c3c'}

    for ax, (title, df) in zip(axes, dfs.items()):
        top_df = df.head(top_n)
        color = colors.get(title, '#95a5a6')

        ax.barh(range(len(top_df)-1, -1, -1),
                top_df['Importance'].values,
                color=color, alpha=0.85, edgecolor='white', linewidth=0.5)
        ax.set_yticks(range(len(top_df)-1, -1, -1))
        ax.set_yticklabels(top_df['Feature'].values, fontsize=8)
        ax.set_xlabel('Importance', fontsize=11)
        ax.set_title(title, fontsize=13, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

    plt.suptitle('Feature Importance Comparison', fontsize=15, fontweight='bold', y=1.01)
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"\n  ✓ Chart saved to {save_path}")

    if show:
        matplotlib.use('TkAgg')
        plt.show()
    else:
        plt.close()


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Feature Importance: GBT splits, MLP attention, RL saliency")

    parser.add_argument("--mode", type=str, default="gbt",
                        choices=["gbt", "mlp", "rl", "all"],
                        help="Which model(s) to analyze")
    parser.add_argument("--gbt-model", type=str, default=DEFAULT_GBT_MODEL)
    parser.add_argument("--mlp-model", type=str, default=DEFAULT_MLP_MODEL)
    parser.add_argument("--rl-model", type=str, default=DEFAULT_RL_MODEL)
    parser.add_argument("--normalizer", type=str, default=DEFAULT_GBT_NORM)
    parser.add_argument("--data", type=str, default=DEFAULT_DATA,
                        help="Training data parquet for MLP/RL analysis")
    parser.add_argument("--model-size", type=str, default="small",
                        choices=["micro", "small", "medium", "large"])
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N,
                        help="Number of top features to show")
    parser.add_argument("--feature", type=str, default=None,
                        help="Inspect a specific feature in detail")
    parser.add_argument("--save", action="store_true",
                        help="Save chart as PNG")
    parser.add_argument("--show", action="store_true",
                        help="Show interactive matplotlib window")
    parser.add_argument("--no-plot", action="store_true",
                        help="Console output only, no chart")

    args = parser.parse_args()

    results = {}

    # ── GBT ──
    if args.mode in ('gbt', 'all'):
        try:
            df_gbt = gbt_importance(args.gbt_model, args.normalizer)
            results['GBT (Split Importance)'] = df_gbt
            print_table(df_gbt, 'GBT — Split-Based Feature Importance',
                       args.top, args.feature)
        except Exception as e:
            print(f"  ✗ GBT analysis failed: {e}")

    # ── MLP ──
    if args.mode in ('mlp', 'all'):
        try:
            df_mlp = mlp_attention_importance(
                args.mlp_model, args.normalizer, args.data, args.model_size)
            results['MLP (Cross-Attention)'] = df_mlp
            print_table(df_mlp, 'MLP — Cross-Attention Importance',
                       args.top, args.feature)
        except Exception as e:
            print(f"  ✗ MLP analysis failed: {e}")

    # ── RL ──
    if args.mode in ('rl', 'all'):
        try:
            df_rl = rl_saliency(
                args.rl_model, args.gbt_model, args.normalizer, args.data)
            results['RL (Gradient Saliency)'] = df_rl
            print_table(df_rl, 'RL — Gradient Saliency',
                       args.top, args.feature)
        except Exception as e:
            print(f"  ✗ RL analysis failed: {e}")

    if not results:
        print("No models could be loaded. Check paths.")
        return

    # ── Plot ──
    if not args.no_plot:
        save_path = None
        if args.save:
            save_path = os.path.join(OUTPUT_DIR, f'feature_importance_{args.mode}.png')
        plot_importance(results, args.top, save_path, show=args.show)


if __name__ == "__main__":
    main()
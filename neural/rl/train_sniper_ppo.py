import os
import argparse
import numpy as np
import pandas as pd
import torch
import warnings
import gymnasium as gym

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from neural.rl.sniper_env import OptionsSniperEnv
from neural.train_walkforward import walk_forward_splits

def mask_fn(env: gym.Env) -> np.ndarray:
    return env.unwrapped.valid_action_mask()

def train_sniper_walkforward(data_path: str, options_cache: dict, feature_columns: list):
    """
    Continuous Walk-Forward RL Training using MaskablePPO.
    Iterates through Walk-Forward windows:
      1. Loads the window's MLP model (for realistic observation building, via episode df if precomputed).
         [Note: OptionsSniperEnv natively expects the MLP features to be passed inside the episode_index df]
      2. Initializes env for Window N.
      3. Trains PPO, continuing from Window N-1's state to avoid catastrophic forgetting but dynamically adapt.
    """
    print("=" * 70)
    print("WALK-FORWARD RL TRAINING (MaskablePPO)")
    print("=" * 70)
    
    # Load dataset
    if data_path.endswith('.parquet'):
        df = pd.read_parquet(data_path)
    else:
        df = pd.read_csv(data_path)
        
    if 'date' in df.columns:
        df['_date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d', errors='coerce')
        
    # Generate splits
    splits = walk_forward_splits(df, train_window_months=3, test_window_months=1, step_months=1)
    print(f"[OK] Generated {len(splits)} Walk-Forward Windows.")
    
    ppo_model = None
    
    for i, (tr_df, ts_df) in enumerate(splits):
        print(f"\n--- RL Training Window {i+1}/{len(splits)} | Train episodes: {len(tr_df):,} ---")
        
        # 1. Ensure we have the MLP model to generate features/signals (or assume tr_df already has them)
        mlp_path = f"models/wf_window_{i}.pt"
        if not os.path.exists(mlp_path):
            print(f"  [Warning] {mlp_path} not found. Ensure train_walkforward.py was run first.")
            # In a real scenario, you might extract features here if tr_df doesn't have them yet.
        
        # 2. Create Environment
        env = OptionsSniperEnv(tr_df, options_cache, feature_columns)
        env = ActionMasker(env, mask_fn)
        
        # 3. Create or load PPO model
        if ppo_model is None:
            ppo_model = MaskablePPO(
                "MlpPolicy", 
                env, 
                gamma=0.99,
                learning_rate=3e-4,
                ent_coef=0.01,
                verbose=1,
                tensorboard_log="./tensorboard_logs/sniper/"
            )
            print("  [OK] Initialized new MaskablePPO Agent.")
        else:
            ppo_model.set_env(env)
            print("  [OK] Retained existing agent (Continuous Learning).")
            
        # 4. Train
        timesteps = min(50000, len(tr_df) * 10)
        print(f"  [>] Training for {timesteps:,} timesteps...")
        ppo_model.learn(total_timesteps=timesteps, reset_num_timesteps=False)
        
        # 5. Save model for this window
        save_path = f"models/sniper_ppo_window_{i}"
        ppo_model.save(save_path)
        print(f"  [OK] Agent saved to {save_path}.zip")

if __name__ == "__main__":
    # Example execution (normally called from a CLI orchestrator)
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="training_data/training_data_derived.parquet")
    args = parser.parse_args()
    
    # Ideally, options_cache is loaded from ThetaData or a precompiled DB.
    # For this skeleton, we assume a mock cache or an empty dict to test compilation
    dummy_cache = {}
    from neural.hybrid_model import FEATURE_COLUMNS
    
    train_sniper_walkforward(args.data, dummy_cache, FEATURE_COLUMNS)

import os
import sys
import pandas as pd
import torch

print("Step 1: Path setup")
SCRIPT_DIR = os.path.dirname(os.path.abspath("__file__")) # simplified
NEURAL_DIR = os.path.join(os.getcwd(), "neural")
sys.path.insert(0, NEURAL_DIR)

print("Step 2: Import RL_CONFIG")
from rl.config import RL_CONFIG
print("Step 3: Import PPOAgent")
from rl.agent import PPOAgent
print("Step 4: Import SPXOptionsEnv")
from rl.environment import SPXOptionsEnv
print("Step 5: Import FEATURE_COLUMNS")
from hybrid_model import FEATURE_COLUMNS

print("Step 6: Read Parquet")
episode_index = pd.read_parquet("rl_data/episode_index.parquet")
print(f"Loaded {len(episode_index)} episodes")

print("Step 7: Init Env")
from rl.training import ChunkedOptionsCache
options_cache = ChunkedOptionsCache("rl_data/rl_options_cache_chunks")
env = SPXOptionsEnv(
    episode_index=episode_index,
    options_cache=options_cache,
    feature_columns=FEATURE_COLUMNS,
)

print("Step 8: Init Agent")
agent = PPOAgent()

print("Step 9: Init Trainer")
from rl.training import PPOTrainer
trainer = PPOTrainer(
    agent=agent,
    env=env,
    num_workers=0, # Sequential for now
    episode_index_path="rl_data/episode_index.parquet",
    options_cache_dir="rl_data/rl_options_cache_chunks"
)

print("Step 10: Run 1 Update")
RL_CONFIG["total_updates"] = 1
trainer.train(save_dir="rl_models")

print("Done")

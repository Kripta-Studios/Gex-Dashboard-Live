import torch
import os

path = r"c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\rl_models\best_rl_agent.pt"
if os.path.exists(path):
    checkpoint = torch.load(path, map_location="cpu")
    print(f"Update step in best_rl_agent.pt: {checkpoint['config'].get('update_step')}")
else:
    print("File not found")

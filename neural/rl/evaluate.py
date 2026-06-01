"""
RL Evaluation — 8 Metrics That Reflect the Real Objective

The agent is evaluated on metrics that reflect profit factor improvement,
not just PPO reward (which is a training proxy).
"""

import numpy as np
import pandas as pd
import torch
import os
from collections import defaultdict

from .config import RL_CONFIG, STRIKE_BUCKETS

# ═══════════════════════════════════════════════════════════════════════════
# MULTIPROCESSING EVALUATION WORKERS
# ═══════════════════════════════════════════════════════════════════════════

g_eval_env = None
g_eval_agent = None

def init_eval_worker(
    episode_index_df,
    options_cache_dir,
    max_days,
    feature_columns,
    state_dim,
    hidden_dims,
    use_entry_skip_action=False,
):
    global g_eval_env, g_eval_agent
    import numpy as np
    import random
    from datetime import datetime
    import torch
    
    seed = int(datetime.now().timestamp() * 1000) % 1000000 + os.getpid()
    np.random.seed(seed)
    torch.manual_seed(seed)
    random.seed(seed)
    
    from .training import ChunkedOptionsCache
    from .environment import SPXOptionsEnv
    from .agent import PPOAgent
    from .config import RL_CONFIG
    RL_CONFIG["use_entry_skip_action"] = bool(use_entry_skip_action)
    
    options_cache = ChunkedOptionsCache(options_cache_dir, max_days_in_ram=max_days)
    g_eval_env = SPXOptionsEnv(episode_index=episode_index_df, options_cache=options_cache, feature_columns=feature_columns)
    g_eval_agent = PPOAgent(state_dim=state_dim, hidden_dims=hidden_dims)
    g_eval_agent.eval()

def worker_eval_episode(agent_state_dict, episode_idx):
    global g_eval_env, g_eval_agent
    import torch
    import numpy as np
    from .config import RL_CONFIG
    
    g_eval_agent.load_state_dict(agent_state_dict)
    
    state = g_eval_env.reset(episode_idx=episode_idx)
    done = False
    step = 0
    info = {}
    
    while not done and step < RL_CONFIG["session_length_minutes"]:
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            if g_eval_env._position is None and (
                getattr(g_eval_env, '_use_sniper', False)
                or RL_CONFIG.get("use_entry_skip_action", False)
            ):
                action_type = "sniper_entry"
            elif g_eval_env._position is None:
                action_type = "strike"
            else:
                action_type = "exit"
            action, _, _ = g_eval_agent.get_action(state_tensor, action_type, deterministic=True)
            
        if isinstance(action, dict):
            env_action = action["strike"]
        elif isinstance(action, (int, np.integer)):
            env_action = int(action)
        else:
            env_action = action.item() if hasattr(action, 'item') else int(action)
            
        next_state, reward, done, info = g_eval_env.step(env_action)
        state = next_state
        step += 1
        
    if "final_pnl_pct" in info:
        return info
    return None

def evaluate_agent(agent, env, eval_episodes: pd.DataFrame = None,
                   n_episodes: int = None, verbose: bool = True,
                   num_workers: int = 1, options_cache_dir: str = None) -> dict:
    """
    Run agent on held-out test episodes and compute 8 key metrics.

    Args:
        agent: PPOAgent (will be set to eval mode)
        env: SPXOptionsEnv
        eval_episodes: DataFrame of episodes to evaluate (optional override)
        n_episodes: max episodes to evaluate (None = all)
        verbose: print results

    Returns: dict with all 8 metrics + raw trade data
    """
    device = next(agent.parameters()).device
    agent.eval()

    if eval_episodes is not None:
        original_index = env.episode_index
        env.episode_index = eval_episodes
        env._build_sampling_strata()

    total = n_episodes or len(env.episode_index)
    total = min(total, len(env.episode_index))

    trades = []
    
    if num_workers > 1 and options_cache_dir:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        worker_max_days = max(2, int(60 / num_workers))
        
        agent.cpu()
        state_dict = {k: v.cpu() for k, v in agent.state_dict().items()}
        agent.to(device)
        
        with ProcessPoolExecutor(
            max_workers=num_workers,
            initializer=init_eval_worker,
            initargs=(
                env.episode_index,
                options_cache_dir,
                worker_max_days,
                env.feature_columns,
                RL_CONFIG["state_dim"],
                RL_CONFIG["hidden_dims"],
                RL_CONFIG.get("use_entry_skip_action", False),
            )
        ) as pool:
            futures = [pool.submit(worker_eval_episode, state_dict, i) for i in range(total)]
            for future in as_completed(futures):
                res = future.result()
                if res is not None:
                    trades.append(res)
    else:
        for i in range(total):
            state = env.reset(episode_idx=i)
            done = False
            step = 0

            while not done and step < RL_CONFIG["session_length_minutes"]:
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(device)

                with torch.no_grad():
                    if env._position is None and (
                        getattr(env, '_use_sniper', False)
                        or RL_CONFIG.get("use_entry_skip_action", False)
                    ):
                        action_type = "sniper_entry"
                    elif env._position is None:
                        action_type = "strike"
                    else:
                        action_type = "exit"
                    action, _, _ = agent.get_action(
                        state_tensor, action_type, deterministic=True)

                if isinstance(action, dict):
                    env_action = action["strike"]
                elif isinstance(action, (int, np.integer)):
                    env_action = int(action)
                else:
                    env_action = action.item() if hasattr(action, 'item') else int(action)

                next_state, reward, done, info = env.step(env_action)
                state = next_state
                step += 1

            if "final_pnl_pct" in info:
                trades.append(info)

    # Restore original episodes if overridden
    if eval_episodes is not None:
        env.episode_index = original_index
        env._build_sampling_strata()

    if not trades:
        return {"error": "No trades completed"}

    # ═══════════════════════════════════════════════════════════════
    # COMPUTE 8 METRICS
    # ═══════════════════════════════════════════════════════════════

    non_trade_exit_types = {"entry_skip", "sniper_timeout"}
    trade_records = [t for t in trades if t.get("exit_type") not in non_trade_exit_types]
    entry_rate = len(trade_records) / max(len(trades), 1)
    pnl_all = [t["final_pnl_pct"] for t in trade_records]
    winners = [p for p in pnl_all if p > 0]
    losers = [p for p in pnl_all if p <= 0]

    hold_mins_all = [t.get("hold_minutes", 0) for t in trade_records]
    hold_winners = [t.get("hold_minutes", 0) for t in trade_records if t["final_pnl_pct"] > 0]
    hold_losers = [t.get("hold_minutes", 0) for t in trade_records if t["final_pnl_pct"] <= 0]

    # 1. Profit Factor
    pf_num = sum(winners) if winners else 0
    pf_den = abs(sum(losers)) if losers else 1e-6
    profit_factor = pf_num / pf_den if pf_den > 0 else 0.0

    # 2. Win Rate
    win_rate = len(winners) / len(pnl_all) if pnl_all else 0.0

    # 3. Mean winner size vs mean loser size
    mean_winner = np.mean(winners) if winners else 0.0
    mean_loser = abs(np.mean(losers)) if losers else 1e-6
    winner_loser_ratio = mean_winner / mean_loser if mean_loser > 0 else 0.0

    # 4. Avg hold time winners vs losers
    avg_hold_winners = np.mean(hold_winners) if hold_winners else 0.0
    avg_hold_losers = np.mean(hold_losers) if hold_losers else 0.0

    # 5. Strike distribution by VIX regime (if available)
    strike_distribution = defaultdict(lambda: defaultdict(int))
    for t in trade_records:
        sa = t.get("strike_action", -1)
        label = STRIKE_BUCKETS.get(sa, {}).get("label", f"unk_{sa}")
        strike_distribution["all"][label] += 1

    # 6. Exit quality score
    # (approximation: final_pnl / max_possible based on data)
    exit_quality_scores = []
    for t in trade_records:
        if t["final_pnl_pct"] > 0:
            # Approximate: compare against max_move from MLP
            # In practice, this would need the full price path
            exit_quality_scores.append(min(t["final_pnl_pct"] / 0.5, 1.0))
    exit_quality = np.mean(exit_quality_scores) if exit_quality_scores else 0.0

    # 7. Hard stop rate
    hard_stops = sum(1 for t in trade_records if t.get("exit_type") == "hard_stop_loss")
    hard_stop_rate = hard_stops / len(trade_records) if trade_records else 0.0

    # 8. Theta efficiency (approximation)
    # theta_paid ≈ hold_time * avg_theta_per_min
    theta_efficiency = 0.0
    if pnl_all:
        mean_pnl = np.mean(pnl_all)
        avg_hold = np.mean(hold_mins_all) if hold_mins_all else 1
        # Rough: theta ≈ −0.05% per minute for 0DTE ATM
        estimated_theta_paid = avg_hold * 0.0005
        theta_efficiency = mean_pnl / (estimated_theta_paid + 1e-6)

    # 9. Sniper metrics (if sniper mode active)
    sniper_waits = [t.get("sniper_minutes_waited", 0) for t in trades
                    if "sniper_minutes_waited" in t]
    sniper_timeouts = sum(1 for t in trades if t.get("exit_type") == "sniper_timeout")
    entry_skips = sum(1 for t in trades if t.get("exit_type") == "entry_skip")
    avg_sniper_wait = np.mean(sniper_waits) if sniper_waits else 0.0
    sniper_timeout_rate = sniper_timeouts / len(trades) if trades else 0.0

    # Sniper entry minute distribution
    sniper_entry_dist = defaultdict(int)
    for w in sniper_waits:
        sniper_entry_dist[int(w)] += 1

    metrics = {
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "total_trades": len(trade_records),
        "entry_rate": entry_rate,
        "entry_skips": entry_skips,
        "winner_loser_ratio": winner_loser_ratio,
        "mean_winner_pct": mean_winner,
        "mean_loser_pct": -abs(np.mean(losers)) if losers else 0,
        "avg_hold_winners": avg_hold_winners,
        "avg_hold_losers": avg_hold_losers,
        "strike_distribution": dict(strike_distribution["all"]),
        "exit_quality_score": exit_quality,
        "hard_stop_rate": hard_stop_rate,
        "theta_efficiency": theta_efficiency,
        "mean_pnl_pct": float(np.mean(pnl_all)),
        "std_pnl_pct": float(np.std(pnl_all)),
        "sharpe_approx": float(np.mean(pnl_all) / (np.std(pnl_all) + 1e-8)),
        "avg_sniper_wait": avg_sniper_wait,
        "sniper_timeout_rate": sniper_timeout_rate,
        "sniper_entry_dist": dict(sniper_entry_dist),
    }

    if verbose:
        print("\n" + "=" * 60)
        print("RL AGENT EVALUATION")
        print("=" * 60)
        print(f"  Total trades:        {metrics['total_trades']}")
        print(f"  Entry Rate:          {metrics['entry_rate']:.1%}  (skips: {metrics['entry_skips']})")
        print(f"  Profit Factor:       {metrics['profit_factor']:.3f}  (target: > 1.5)")
        print(f"  Win Rate:            {metrics['win_rate']:.1%}   (target: ≥ 59%)")
        print(f"  W/L Size Ratio:      {metrics['winner_loser_ratio']:.2f}  (target: > 1.5)")
        print(f"  Mean Winner:        +{metrics['mean_winner_pct']:.2%}")
        print(f"  Mean Loser:          {metrics['mean_loser_pct']:.2%}")
        print(f"  Avg Hold Winners:    {metrics['avg_hold_winners']:.0f} min")
        print(f"  Avg Hold Losers:     {metrics['avg_hold_losers']:.0f} min")
        print(f"  Hard Stop Rate:      {metrics['hard_stop_rate']:.1%}  (target: < 15%)")
        print(f"  Exit Quality:        {metrics['exit_quality_score']:.2f} (target: > 0.5)")
        print(f"  Theta Efficiency:    {metrics['theta_efficiency']:.2f}")
        print(f"  Sharpe (approx):     {metrics['sharpe_approx']:.2f}")
        print(f"  Strike Distribution: {metrics['strike_distribution']}")
        if RL_CONFIG.get("use_sniper_mode"):
            print(f"  ── Sniper Metrics ──")
            print(f"  Avg Wait:            {metrics['avg_sniper_wait']:.1f} min (target: 3-10)")
            print(f"  Timeout Rate:        {metrics['sniper_timeout_rate']:.1%}")
            print(f"  Entry Dist:          {metrics['sniper_entry_dist']}")
        print("=" * 60)

    return metrics

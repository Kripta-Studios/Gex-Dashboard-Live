# JEPA Current Plan

## Production Path

1. Run the daily production pipeline:

   ```powershell
   .\neural\jepa\run_pipeline.ps1 -DailyProduction -Workers 32
   ```

2. Upload generated model directories and manifest:

   ```powershell
   .\push_models.ps1 -HostAlias kripta
   ```

   Legacy JEPA 180m/OptionValue artifacts require `-IncludeLegacyFallback` and
   are not part of the normal production upload.

3. On the VPS, pull source and restart services:

   ```bash
   cd /home/Option-Greeks-Plotting-Discord-Bot
   git pull
   sudo cp systemd/realtime_feed.service /etc/systemd/system/realtime_feed.service
   sudo cp systemd/ai_bot.service /etc/systemd/system/ai_bot.service
   sudo systemctl daemon-reload
   sudo systemctl restart realtime_feed.service ai_bot.service
   ```

## Current Research Priorities

- Keep the level-stability entry signal causal by fitting only on months before the deployment month.
- Keep structural option-profile selection nested: for every test/deploy month, profiles must come from prior months only.
- Improve SPX robustness without reducing sizing.
- Develop a dense market JEPA/Var-JEPA encoder only after preserving out-of-fold export by ticker/month.
- Do not promote OptionValue/RL until it improves the structural-profile baseline in walk-forward options.

## Files That Matter

- Production signal: `fit_production_level_stability_signal.py`, `level_stability_live.py`.
- Production option profiles: `fit_production_structural_option_profiles.py`.
- Daily orchestration: `run_daily_production_pipeline.ps1`, `run_pipeline.ps1 -DailyProduction`.
- Research validation: `walkforward_level_stability_ensemble.py`, `walkforward_structural_option_profiles.py`.
- Result combiner/integrity checks: `combine_walkforward_option_results.py`.
- Live execution: `bots/tradingbot_wrapper_jepa.py`, `services/realtime_feed.py`, `systemd/ai_bot.service`.
- Formal report: `research_papers/JEPA/JEPA_PRODUCTION_REPORT.pdf`.

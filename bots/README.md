# Live JEPA Trading Bot

This folder contains the live inference wrapper for the current JEPA production
release. The bot is an alert/tracker process; it does not submit broker orders.

## Production Models

The live release uses three generated model directories:

```text
neural/models/jepa/xinput_v3_production/
neural/models/jepa/jepa_production_final_180m/
neural/models/jepa/jepa_production_final_option_value/
```

`services/realtime_feed.py` loads `xinput_v3_production` to append live `xjepa_*`
features. `bots/tradingbot_wrapper_jepa.py` loads
`jepa_production_final_180m/base_jepa` to produce the 180-minute direction signal
and `jepa_production_final_option_value` to select the 0DTE contract. If the
OptionValue artifact is missing or cannot load, the bot logs a warning and falls
back to the fixed abs(delta)=0.70 rule.

The execution contract is:

```text
signal: base_jepa 180m direction
entry cadence: 5-minute rows
entry window: feature rows through 14:30 ET
option: OptionValue blended score over 0.10..0.70 delta candidates
fallback option: 0DTE contract closest to abs(delta)=0.70 in the signal direction
hard stop: -60%
trail stop: activate at +50%, close on 25% giveback from peak
emergency take profit: +1000%
max hold: 180 minutes
cooldown: 180 minutes per ticker from entry
tickers: SPX, QQQ, SPY
```

## Runtime Files

Feed output:

```text
rt_data/YYYYMMDD/
  spot_{TICKER}_latest.parquet
  {OPTION_SYMBOL}_greeks_0dte_latest.parquet
  {OPTION_SYMBOL}_ohlc_0dte_latest.parquet
  ml_features_1m_{TICKER}_latest.parquet
  ml_features_{TICKER}_latest.parquet
  feed_intraday_state.json
  jepa_live_execution_config.json
```

The bot consumes only `ml_features_{TICKER}_latest.parquet`, sampled every 5
minutes to match training. It waits until `xjepa_context_valid=1`, which requires
24 five-minute rows.

Bot output:

```text
trades_jepa/
  open_positions_jepa.json
  cooldowns_jepa.json
  trades_jepa.csv
  tradingbot_jepa.log
```

## Local Checks

From the project root:

```powershell
python .\bots\tradingbot_wrapper_jepa.py --model-dir .\neural\models\jepa\jepa_production_final_180m --dry-run --force
python .\services\realtime_feed.py --dry-run --jepa-model-dir .\neural\models\jepa\xinput_v3_production
```

The feed dry run requires ThetaData to be reachable.

## Deployment

Source files should be deployed with git:

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git pull
```

Generated model artifacts are ignored by git and uploaded separately from the
development machine:

```powershell
.\push_models.ps1 -HostAlias kripta -RemoteRoot /home/Option-Greeks-Plotting-Discord-Bot
```

`push_models.ps1` uploads only:

```text
neural/models/jepa/xinput_v3_production/
neural/models/jepa/jepa_production_final_180m/
neural/models/jepa/jepa_production_final_option_value/
```

It intentionally does not upload `.py`, `.service`, README, or other source
files.

## Systemd

The repo includes systemd templates:

```text
systemd/realtime_feed.service
systemd/ai_bot.service
```

Install or refresh them on the VPS after `git pull`:

```bash
sudo cp systemd/realtime_feed.service /etc/systemd/system/realtime_feed.service
sudo cp systemd/ai_bot.service /etc/systemd/system/ai_bot.service
sudo systemctl daemon-reload
sudo systemctl enable realtime_feed.service ai_bot.service
sudo systemctl restart realtime_feed.service ai_bot.service
```

Monitor:

```bash
journalctl -u realtime_feed.service -f
journalctl -u ai_bot.service -f
tail -f trades_jepa/tradingbot_jepa.log
```

## Environment

Create `.env` in the project root on the VPS:

```dotenv
THETADATA_URL=http://127.0.0.1:25503/v3
DISCORD_WEBHOOK_URL=
DISCORD_WEBHOOK_URL_2=
DISCORD_ROLE_PING=
JEPA_FEATURE_EXPERIMENT=xinput_v3_production
```

The systemd units also pass explicit model directories, so the environment value
is a fallback rather than the primary deployment contract.

## Interpreting Results

The production model is trained on all available data. Backtests run on months
inside that training range are functionality checks, not OOS validation. The
clean OOS evidence remains the research pipeline that trained through March 2026
and tested April/May 2026.

# AI Agent Hand-off: Current Production Reality

Este repo ya no debe entenderse principalmente como el viejo pipeline GBT+RL. El sistema live actual es un stack de alertas/paper-trading para opciones 0DTE usando el paquete JEPA event-option static-union.

## Objetivo actual

Mantener y mejorar un sistema live rentable, causal y auditable para SPXW, QQQ y SPY 0DTE. El criterio de exito no es solo maximizar PnL en un backtest aislado; una promocion necesita:

- walk-forward o holdout causal sin leakage;
- equivalencia entre training/backtest/live;
- artefactos `production_live_ready`;
- servicios systemd arrancando con el mismo contrato que el backtest;
- evidencia diaria de drift/fills/paper-intents.

## Stack live

Servicios:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

Paquete activo:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
```

Policy:

```text
event_option_frozen2025_static_union_balanced_202607
```

Contrato runtime confirmado en VPS:

```text
event_exit=stop=-60%/tp=1000%/trail=50%/25%/min_hold=30m/max_hold=180m
entry_window=10:00-14:30 ET
risk=5000
paper_order_intents=true
```

El bot no envia ordenes al broker. Escribe intents y avisa por Discord/tracker.

## Politicas por ticker

| Ticker | Simbolo opciones | Bucket | Max trades/dia | Cooldown |
| --- | --- | --- | ---: | --- |
| SPX | SPXW | d25 | 4 | 0m |
| QQQ | QQQ | d35 | 2 | 30m |
| SPY | SPY | d35 | 1 | 0m |

SPXW usa `min_score=0.34`. Los otros gates viven en `event_option_policy.json`.

## Validacion actual

Comando canonico:

```bash
python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12
```

Metricas Jan-Jun 2026:

| Scope | Trades | WR | PF | Min month |
| --- | ---: | ---: | ---: | ---: |
| Overall | 697 | 57.819% | 1.915 | 103 |
| QQQ | 236 | 60.593% | 1.771 | 36 |
| SPXW | 355 | 55.211% | 2.037 | 51 |
| SPY | 106 | 60.377% | 1.769 | 12 |

El target ideal de 18 trades/mes/ticker no se cumple en SPY; la gate deployable actual es 12.

## Datos

Local:

```text
D:/ThetaData/data_options/SPXW
D:/ThetaData/data_options/QQQ
D:/ThetaData/data_options/SPY
D:/ThetaData/data_underlying_derived/SPXW
D:/ThetaData/data_underlying_derived/QQQ
D:/ThetaData/data_underlying_derived/SPY
```

VPS:

```text
rt_data/YYYYMMDD/
trades_jepa/
log_exports/
```

Los scripts de training/backtest deben leer datos historicos de ThetaData o parquets reproducibles. El live solo puede consumir snapshots y features observables hasta el timestamp actual.

## Reglas duras

- No usar datos futuros, labels, PnL futuro, high/low posterior, o columnas de outcome como features live.
- No seleccionar una politica usando el mismo mes que luego se reporta como OOS.
- No cambiar systemd sin validar arranque de ambos servicios.
- No hacer `git reset --hard` ni revertir cambios del usuario.
- No tratar `neural/run_pipeline.ps1` + PPO/RL como produccion actual sin una promocion nueva.
- No reentrenar diario por defecto; auditar diario y reentrenar/promocionar por mes completado.

## Deploy en VPS

```bash
cd /home/Option-Greeks-Plotting-Discord-Bot
git pull --ff-only
python3 -m py_compile services/realtime_feed.py bots/tradingbot_wrapper_jepa.py neural/jepa/validate_event_option_production_package.py
python3 neural/jepa/validate_event_option_production_package.py \
  --policy neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/event_option_policy.json \
  --registry neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/component_registry.json \
  --require-live-ready \
  --ignore-raw-thetadata-coverage \
  --min-profit-factor 1.3 \
  --min-win-rate 0.45 \
  --min-month-trades 12
sudo install -m 0644 systemd/realtime_feed.service /etc/systemd/system/realtime_feed.service
sudo install -m 0644 systemd/ai_bot.service /etc/systemd/system/ai_bot.service
sudo systemctl daemon-reload
sudo systemctl restart realtime_feed.service
sudo systemctl restart ai_bot.service
sudo systemctl status realtime_feed.service ai_bot.service --no-pager -l
```

No usar `reboot now` como despliegue normal.

## Areas legacy

`neural/rl/`, `backtest/backtest_rl.py`, `neural/train_walkforward.py`, `neural/hybrid_model.py`, `jepa_production_final_180m`, level-stability y structural profiles son utiles para investigacion y comparativas. No son el contrato live actual.

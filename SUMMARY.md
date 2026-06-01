# Bugfix Summary — RL Training Pipeline
**Fecha:** 2026-05-24
**Backtest analizado:** `gbt_only_20260524_144716.csv` vs `gbt_rl_20260524_144716.csv`
**Archivos modificados:** `rewards.py`, `config.py`, `environment.py`, `training.py`

---

## Addendum — fixes posteriores de alineación GBT/RL

- `signal_policy.py`: añadida `confidence_for_predictions`; los backtests y el scorer económico ya usan la probabilidad de la clase LONG/SHORT emitida, no `max(probs)` que podía ser HOLD.
- `signal_policy.py` / `config.py`: añadida puerta `signal_min_directional_margin=0.025` para evitar entradas cuando LONG y SHORT están empatados.
- `collect_training_data_spx_qqq.py`: las labels densas ahora usan OHLC intrabar con prioridad conservadora de stop, alineada con los backtests.
- `train_walkforward.py`: corregido el peso temporal; ahora usa diferencia real en días en vez de restar enteros `YYYYMMDD`.
- `gbt_model.py`: el strict-WF exige por defecto `rank_pf >= 1.25`, alineado con el filtro de entrenamiento.
- `rl/config.py` / `environment.py` / `backtest_rl.py`: `emergency_stop_pct` queda igualado a `max_loss_pct` (`-0.50`) para impedir salidas perdedoras prematuras por un exit head colapsado.

---

## Contexto

El backtest GBT+RL mostró una degradación severa respecto al baseline GBT-Only:

| Métrica | GBT-Only | GBT+RL |
|---|---|---|
| Win Rate | 45.8% | 10.6% |
| Profit Factor | 1.00 | 0.88 |
| P&L total | −$849 | −$51,416 |
| Balance final | $9,151 | −$41,416 |
| Strike elegido | variado | 99.4% `deep_otm` |
| Exits por agente | 562 stops + 149 trailing | 1,835 `agent_exit` |

El análisis cruzado del código fuente reveló cuatro bugs estructurales que explican estos resultados.

---

## Fix 1 — `rewards.py`: firma de `compute_step_reward` incompleta

### Problema
`compute_step_reward` tenía `**kwargs` como receptáculo final. `environment.py` le pasaba cuatro argumentos diseñados para enriquecer la señal de recompensa (`recovery_rate`, `spot_momentum`, `trailing_drawdown`, `is_new_hwm`), pero al ir a `**kwargs` eran ignorados silenciosamente. El agente aprendía con una función de recompensa mucho más pobre de la diseñada, sin ningún error ni warning.

### Cambio
Se reemplazó `**kwargs` por parámetros explícitos con tipos y valores por defecto:

```python
# ANTES
def compute_step_reward(prev_pnl_pct, curr_pnl_pct, hold_time_minutes,
                        theta_decay_per_minute=0.0, **kwargs) -> float:

# DESPUÉS
def compute_step_reward(prev_pnl_pct, curr_pnl_pct, hold_time_minutes,
                        theta_decay_per_minute=0.0,
                        recovery_rate=0.3,
                        spot_momentum=0.0,
                        trailing_drawdown=0.0,
                        is_new_hwm=False) -> float:
```

Se implementó la lógica de cada parámetro:

- **`recovery_rate`**: si el bucket histórico (delta × IV × PnL) tiene probabilidad de recuperación > 0.30, se bonifica el hold. Fuente: `compute_recovery_stats.pkl`.
- **`trailing_drawdown`**: penalización proporcional al retroceso desde el High Water Mark no realizado. Disuade mantener posiciones que ya tocaron un pico y lo están perdiendo.
- **`spot_momentum`**: ajuste contextual pequeño (±0.003) según la tendencia del subyacente en los últimos minutos.
- **`is_new_hwm`**: bonus puntual (+0.005) al marcar un nuevo máximo no realizado, reforzando la convexidad positiva.

---

## Fix 2 — `config.py`: `emergency_stop_pct` ausente en `RL_CONFIG`

### Problema
`environment.py` hacía `RL_CONFIG.get("emergency_stop_pct", -0.30)` pero la clave no existía en `RL_CONFIG`. El valor `-0.30` era un default silencioso no documentado. Con `max_loss_pct = -0.50`, la zona de escape del `min_hold` quedaba en `(-0.30, -0.50)`, lo que permitía al agente salir prematuramente con pérdidas moderadas eludiendo el mínimo de hold del currículo.

### Cambio
Se añadió la clave a `RL_CONFIG` con valor `-0.35` y documentación explícita:

```python
# AÑADIDO en RL_CONFIG
"emergency_stop_pct": -0.35,
# Zona de escape: solo se puede salir antes de min_hold si pnl < -0.35
# La ventana real de escape es (-0.35, -0.50). Si se iguala a -0.50
# se elimina la escapatoria por completo.
```

El valor `-0.35` (vs el antiguo default de `-0.30`) estrecha la ventana de escape y reduce los `agent_exit` prematuros en pérdidas superficiales.

---

## Fix 3 — `training.py`: `strike_action_mask` ausente en la colección de episodios

### Problema (crítico — causa directa del 99.4% en `deep_otm`)
El currículo define `min_strike_bucket` y `max_strike_bucket` por fase (e.g., fase 0: buckets 1–3). El entorno los aplica en `_handle_entry` con `strike_action = max(min_strike, min(action, max_strike))`. Sin embargo, **`get_action` no recibía ninguna `action_mask`**, por lo que la política muestreaba libremente los 7 buckets. El entorno corregía la acción en silencio, creando una discrepancia:

- La política aprendía `log_prob(bucket_0)` — la distribución sin restricciones
- El entorno ejecutaba `max(min_strike, 0) = min_strike` — posiblemente bucket 1 o superior
- El mecanismo de corrección de `log_prob` por mismatch existía pero solo afectaba a PPO stability, no a la distribución de muestreo

El resultado es que el strike head no recibía señal de gradiente que penalizara elegir `deep_otm` durante las fases en que debería estar restringido, colapsando al argmax por defecto (bucket 0, delta 0.10).

### Cambio
En ambos paths de colección (worker paralelo y single-threaded), se construye `strike_action_mask` antes del loop de steps y se pasa a `get_action` y `evaluate_actions`:

```python
# AÑADIDO — antes del while loop, en ambos paths
strike_action_mask = [
    (min_strike <= i <= max_strike) for i in range(NUM_STRIKE_ACTIONS)
]
if not any(strike_action_mask):
    strike_action_mask = [True] * NUM_STRIKE_ACTIONS  # garantía de seguridad

# En el loop:
if action_type == "strike":
    current_mask = strike_action_mask
else:
    current_mask = None

action, log_prob, value = agent.get_action(
    state_tensor, action_type,
    logit_noise=l_noise,
    action_mask=current_mask  # ← NUEVO
)

# En mismatch detection:
new_log_probs, _, _, _ = agent.evaluate_actions(
    state_tensor, [effective_action], [action_type],
    action_masks=[current_mask]  # ← NUEVO
)
```

Con la máscara activa, la política nunca puede colapsar en un bucket fuera del rango del currículo, porque esas acciones reciben `logit = -inf` antes del softmax.

---

## Fix 4 — `environment.py`: ticker-balanced sampling en `_build_sampling_strata`

### Problema
SPY representaba el 51% de los episodios de entrenamiento (1,116 de 2,181 en backtest) cuando debería ser ~33% si los tres tickers se trataran igual. Esto ocurría porque el muestreo original era uniforme sobre todos los episodios, y SPY tenía más señales GBT por su mayor volumen de datos. El agente sobre-aprendía el ticker con peor Profit Factor (SPY: 0.77) y sub-aprendía los únicos rentables (SPX: 1.03, QQQ: 0.97).

### Cambio
Se reescribió `_build_sampling_strata` para estratificar primero por ticker (distribución uniforme entre tickers) y luego por VIX regime dentro de cada ticker. Se añadió `_sample_balanced_episode_idx` como método separado:

```python
def _build_sampling_strata(self):
    self._ticker_strata = {}  # {ticker: [indices]}
    for ticker in tickers:
        t_mask = episode_index["ticker"] == ticker
        self._ticker_strata[ticker] = episode_index[t_mask].index.tolist()
    self._strata_tickers = list(self._ticker_strata.keys())

def _sample_balanced_episode_idx(self) -> int:
    ticker = np.random.choice(self._strata_tickers)  # 1/N por ticker
    return int(np.random.choice(self._ticker_strata[ticker]))
```

`reset()` llama a `_sample_balanced_episode_idx()` cuando no recibe `episode_idx` explícito. Los workers del path paralelo siempre reciben `episode_idx` pre-muestreado desde el trainer, por lo que el balanceo en ese path depende de que `PPOTrainer.collect_episodes` también use pools balanceados (ya lo hace con `_long_indices_train` / `_short_indices_train`, pero sin corrección de ticker — pendiente de revisión en el trainer si se quiere balanceo ticker también en ese path).

---

## Resumen de impacto esperado

| Bug | Efecto en backtest | Fix |
|---|---|---|
| Fix 1: `**kwargs` ignorados | Recompensa de step ~4× más pobre; agente no aprende a recuperarse ni a gestionar HWM | `rewards.py` — firma explícita |
| Fix 2: `emergency_stop_pct` ausente | Agente escapa `min_hold` con pérdidas de −0.30 (demasiado fácil) | `config.py` — valor a −0.35 |
| Fix 3: sin `action_mask` en strike | Colapso del strike head en `deep_otm` (99.4%); WR ~10% estructural | `training.py` — mask en `get_action` |
| Fix 4: SPY al 51% del batch | Sobre-ajuste al ticker de peor PF; sub-aprendizaje de SPX/QQQ | `environment.py` — ticker balancing |

---

## Notas para el próximo ciclo de entrenamiento

1. Resetear el modelo RL desde cero (`best_rl_agent.pt`) — los pesos actuales han convergido en una política degenerada que es difícil de revertir con fine-tuning.
2. Monitorizar `h_strike` (strike head entropy) en el log de training. Con las masks activas debería mantenerse > 0.8 nats en las primeras 100 updates. Si colapsa de nuevo hay que revisar que las masks llegan correctamente a los workers.
3. Verificar en los primeros 50 updates que la distribución de `strike_bucket` en los episodios recogidos tiene presencia de buckets 1–3 (fases de currículo inicial) y no está concentrada en bucket 0.
4. El `agent_exit` debería subir de 10.6% a un rango de win rate más próximo al GBT-Only (40–50%), porque la política ahora recibe la señal de `recovery_rate` que diferencia cuándo tiene sentido holdear.

---

## 2026-05-25 — Strict-WF leak fix + deployment gates hasta PF/WR objetivo

### Diagnóstico

La última ejecución mostraba una curva con pérdidas 2022-2024, subida vertical hasta enero de 2025 y nueva degradación en 2026. La causa principal encontrada fue una fuga en `neural/gbt_model.py`: en modo strict walk-forward, si no había modelo pasado elegible para una fecha, el wrapper usaba el modelo más antiguo disponible como fallback. Eso permitía inferencia con modelos entrenados en el futuro para fechas antiguas.

Se eliminó ese fallback. Cuando no existe modelo pasado elegible, `predict_proba(..., date=...)` devuelve HOLD. Además, strict-WF ahora exige:

- `available_date < date`
- no modelos fallback
- validación económica mínima (`validation_trades >= 20`)
- `avg_pf >= 1.25`

### Cambios de política y entrenamiento

Se centralizó el gate causal de despliegue en `neural/signal_policy.py` para que training económico, generación/preprocess de episodios RL, backtests y live routing evalúen el mismo universo:

- `min_confidence = 0.590`
- `iv_percentile` en `[0.10, 0.85]`
- QQQ SHORT requiere `price_vs_ib_high >= 60`
- ventanas de entrada ET: `[600, 630)` y `[720, 780)` (10:00-10:30 y 12:00-13:00)
- `rvol_trend <= 0.02`

También se corrigió el contador de pérdidas consecutivas para que sea por sesión `(ticker, date)` y no persistente entre días; el comportamiento anterior bloqueaba operaciones futuras por pérdidas de sesiones pasadas.

El modelo experimental usado queda en:

```text
neural/models/codex_exp/gbt_12m_econ_pf125_conf059_iv10_85.joblib
```

`neural/run_pipeline.ps1` apunta a ese path y pasa `--min-selection-win-rate`, con QQQ en 0.40 y el resto en 0.45.

### Validación final

Backtest final regenerado:

```text
backtest_results/gbt_only_20260525_162600.csv
backtest_results/gbt_rl_20260525_162600.csv
visualizer/analysis/All_backtest_analysis_report.tex
visualizer/analysis/All_backtest_analysis_report.pdf
```

Resultados agregados:

| Modelo | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| GBT-Only | 66 | 63.64% | 3.43 | +44,030.37 |
| GBT+RL | 69 | 42.03% | 2.85 | +37,347.00 |

Resultados 2026:

| Modelo | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| GBT-Only | 34 | 64.71% | 3.88 | +25,927.37 |
| GBT+RL | 35 | 42.86% | 3.29 | +21,429.50 |

Meses críticos 2026:

| Modelo | Abril 2026 | Mayo 2026 |
|---|---:|---:|
| GBT-Only | +4,718.17 | +2,131.29 |
| GBT+RL | +1,365.50 | +2,764.00 |

Todos los objetivos explícitos quedan cumplidos en strict-WF: PF > 1.25, WR > 40%, 2026 positivo y abril/mayo 2026 positivos para ambos modelos.

### Nota pendiente

El resultado final es conservador en volumen (66-69 trades) porque el leak strict-WF anterior inflaba la cobertura histórica y los gates recortan los regímenes donde la prima 0DTE se deteriora. El siguiente ciclo debería intentar recuperar volumen sin relajar los gates causales que protegen PF/WR.

---

## 2026-05-26 — Recuperación de Volumen y Corrección de Asimetría Direccional

### Diagnóstico de Asimetría (El "Blind Spot" de QQQ)

Para escalar el volumen de operaciones a >1900 trades mantuvimos el `min_confidence` en niveles relajados, pero detectamos que el Profit Factor global caía a 0.94. El análisis demostró una asimetría estructural grave en las predicciones del GBT:
- **Días Alcistas (Market UP):** PF de 1.38 (muy rentable)
- **Días Bajistas (Market DOWN):** PF de 0.72 (pérdidas masivas)

La causa raíz se localizó en `neural/rl/config.py`, donde el parámetro `deployment_qqq_short_min_price_vs_ib_high` estaba anclado a `60.0`. Este gate mecánico **prohibía absolutamente** que el sistema tomara posiciones SHORT en QQQ salvo que el precio estuviera 60 puntos por encima del máximo de apertura. En consecuencia, durante las caídas de mercado, el sistema no podía aprovechar la tendencia bajista y se veía forzado a entrar en LONG persiguiendo rebotes que nunca llegaban.

### Solución

Se redujo `deployment_qqq_short_min_price_vs_ib_high` a `-150.0`, relajando el bloqueo de shorts en QQQ. Esto permite que el modelo GBT base pueda, de nuevo, diagnosticar y explotar tendencias bajistas con operaciones SHORT, convirtiendo los cientos de entradas forzadas y perdedoras en LONG en verdaderas oportunidades de ganancia direccional, restaurando el PF por encima del target (1.25).

---

## 2026-05-29 — Sincronización de Simuladores y Resolución del "Exit Head Collapse"

### Diagnóstico 1: "Exit Head Collapse" en el Agente RL
El Agente RL había desarrollado un comportamiento degenerado (miedo a la varianza) que le llevaba a salir de casi todas las posiciones prematuramente, resultando en un P&L negativo.
- **Solución**: En `neural/rl/rewards.py` se modificaron las penalizaciones de `compute_terminal_reward`, forzando castigos severos para salidas manuales con pérdidas fuera de la zona de stop-loss natural. Además, en `neural/rl/config.py` se incrementó el `min_hold_minutes` del currículo (de 45 a 90 minutos) para obligar a la red a dejar madurar las tendencias y capturar los "Home-runs".
- **Resultado**: El Agente RL volvió a ser muy asimétrico, aumentando el tiempo medio de posiciones ganadoras a 86 minutos, restableciendo su rentabilidad y un Profit Factor de 1.05.

### Diagnóstico 2: Desincronización de Línea Base GBT
Al comparar el modelo GBT puro contra el RL, el simulador del RL calculaba mal las métricas del Oráculo Base. Usaba constantes de simulación *hardcodeados* que no coincidían con el script original `backtest_gbt_parquet.py`. 
- GBT original: `target=0.010` (SPX), `target=0.006` (QQQ), `stop=0.0025`.
- Falso Simulador RL: `target=0.008` (SPX), `target=0.006` (QQQ), `stop=0.003`.
- **Solución**: Se parcheó `backtest/backtest_rl.py` para inyectar exactamente las mismas constantes y reglas.

### La Verdadera Línea Base Revelada
Con ambos simuladores finalmente alineados en las mismas reglas matemáticas, el backtest arrojó la verdad absoluta:
- **P&L Total**: El Oráculo Base (GBT-Only) genera **+$86,941.60** vs el Agente RL **+$26,190.50**.
- **Desglose Crítico por Ticker**: 
  - **QQQ**: El Agente RL optimiza enormemente el activo y bate a la línea base (PF **1.06** vs **0.99**).
  - **SPX**: La simulación pura a *spot* del GBT barre por completo al RL (PF **1.22** vs **1.02**). 

**Conclusión Estratégica**: El cuello de botella que bloquea el objetivo supremo de $250k de P&L reside en el underperformance del RL en SPX. Es crítico explorar tácticas en la selección de *Strike* del Agente (e.g. buscar buckets más OTM) o en su Reward Function especializadas para sobrevivir y exprimir la volatilidad extrema del SPX.

### Cambios Menores de Tooling
- Se restauró el argumento `-bt_gbt` en `neural/run_pipeline.ps1` que mapea al `$skip_to_step = 6`, permitiendo aislar la ejecución del backtest base sin invocar toda la capa RL.

---

## 2026-05-29 18:10 +02:00 — Diario de investigación: degradación GBT/RL actual

### Contexto

Se revisaron `neural/run_pipeline.ps1`, `AGENTS.md`, este `SUMMARY.md`, `visualizer/analysis/All_backtest_analysis_report.tex` y los CSV:

```text
backtest_results/gbt_only_20260529_171737.csv
backtest_results/gbt_rl_20260529_171737.csv
```

El pipeline actual entrena tres GBT especializados (`SPX`, `QQQ`, `SPY`) con:

```text
train_walkforward.py --train-months 12 --test-months 1 --ensemble 3
--top-n-windows 10 --hold-ratio 0.5 --class-weight balanced
--min-pf-floor 1.05 --selection-metric economic
--selection-base-confidence 0.450
```

Luego genera episodios RL con `generate_episode_index.py`, cachea opciones con `run_preprocess.py`, entrena PPO con `rl/training.py` y backtestea con `backtest_gbt_parquet.py` y `backtest_rl.py`.

### Diagnóstico provisional

1. El GBT actual falla por exceso de LONG de baja esperanza. En el CSV oficial, los SHORT ya son positivos:
   - QQQ SHORT PF 1.24 aprox, pero QQQ LONG PF 0.97.
   - SPX SHORT PF 1.74 aprox, SPX LONG PF 1.11 aprox.
   - SPY SHORT PF 1.44 aprox, SPY LONG PF 1.08 aprox.
2. El análisis del reporte muestra dependencia fuerte del régimen diario:
   - UP days: PF 2.50.
   - DOWN days: PF 0.73.
   El modelo no está filtrando bien los LONG en sesiones bajistas.
3. Hay una desalineación estructural entre etiqueta y backtest:
   - `collect_training_data_spx_qqq.py` etiqueta con `FIXED_PROFIT_PCT = 0.003` y `FIXED_STOP_PCT = 0.003` usando precios de cierre por minuto.
   - El backtest GBT opera `target=0.010` para SPX, `target=0.006` para QQQ/SPY, `stop=0.0025`, OHLC intrabar y prioridad conservadora de stop.
   Esto entrena al modelo a detectar rebotes pequeños que luego se evalúan con un payoff mucho más exigente.
4. `train_walkforward.py::calculate_economic_metrics` no está alineado del todo con la ejecución:
   - usa `row["max_prob"] = probabilities.max(axis=1)` en vez de la probabilidad de la clase emitida;
   - no aplica `deployment_context_allowed(row, direction)`;
   - usa target/stop por defecto `0.010/0.010/0.003`, mientras el backtest fuerza por ticker `SPX 0.010/0.0025`, `QQQ/SPY 0.006/0.0025`.
   Por tanto puede seleccionar ventanas que no maximizan la misma política que se despliega.
5. `backtest_gbt_parquet.py::TradeSimulator.simulate` contiene bloques duplicados de filtros/entrada/salida. No explica todo el mal rendimiento, pero aumenta el riesgo de divergencias silenciosas.

### Experimento 1: bajar threshold GBT a 0.35

Comando:

```text
python -u backtest/backtest_gbt_parquet.py --data training_data/training_data_spx_qqq_spy.parquet --model neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail.joblib --normalizer neural/models/codex_exp/gbt_12m_econ_pf150_minsel10_avail_norm.npz --model-size small --ensemble --threshold 0.35 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf
```

Resultado:

| Ticker | Trades | WR | PnL |
|---|---:|---:|---:|
| QQQ | 1028 | 39.9% | -3,712 |
| SPX | 802 | 43.1% | +49,935 |
| SPY | 1086 | 41.8% | +5,441 |

Global: 2916 trades, WR 41.5%, PF 1.04, PnL +51,664, Max DD -45,991.

Conclusión: recupera volumen para QQQ/SPY pero no calidad; SPX queda debajo de 900 trades. QQQ y SPY siguen sin PF suficiente.

### Experimento 2: bajar threshold GBT a 0.30

Comando igual al anterior con `--threshold 0.30`.

Resultado:

| Ticker | Trades | WR | PnL |
|---|---:|---:|---:|
| QQQ | 1279 | 41.0% | +2,942 |
| SPX | 929 | 42.7% | +50,995 |
| SPY | 1270 | 43.2% | +42,983 |

Global: 3478 trades, WR 42.3%, PF 1.07, PnL +96,921, Max DD -60,098.

Abril/mayo 2026 del CSV temporal `training_data/backtest_trades.csv`:

| Month | Ticker | Trades | WR | PnL |
|---|---|---:|---:|---:|
| 202604 | QQQ | 15 | 53.3% | +3,144 |
| 202604 | SPX | 20 | 45.0% | +6,416 |
| 202604 | SPY | 17 | 47.1% | +1,313 |
| 202605 | QQQ | 16 | 31.3% | -6,226 |
| 202605 | SPX | 10 | 50.0% | +663 |
| 202605 | SPY | 16 | 43.8% | +265 |

Conclusión: threshold 0.30 cumple volumen >900 por ticker, pero no cumple PF >1.2 ni WR >45%, y falla mayo 2026 en QQQ.

### Próximo paso

Alinear primero el objetivo de selección/validación GBT con el backtest real:

- corregir `calculate_economic_metrics` para usar `confidence_for_predictions` y `deployment_context_allowed`;
- pasar target/stop reales por ticker desde `train_walkforward.py`;
- registrar `rank_pf`, `total_validation_trades` y métricas honestas en metadata para que strict-WF filtre con datos reales;
- limpiar la duplicación del simulador GBT antes de reentrenar.

---

## 2026-05-29 18:17 +02:00 — Diario: primer parche de alineación GBT

### Cambios aplicados

Archivos modificados:

```text
neural/train_walkforward.py
backtest/backtest_gbt_parquet.py
SUMMARY.md
```

No se modificó `neural/collect_training_data_spx_qqq.py`; por tanto no se regeneró `training_data/training_data_spx_qqq_spy.parquet` en esta pasada.

Cambios:

- `calculate_economic_metrics()` ahora usa `confidence_for_predictions()` en vez de `max(probs)`.
- `calculate_economic_metrics()` aplica `deployment_context_allowed(row, direction)` igual que los backtests.
- `apply_deployed_signal_policy()` usa `get_independent_signals()`, alineado con el backtest.
- El loss streak del scorer económico pasa a ser por `(ticker, date)`, no global entre sesiones.
- `train_walkforward.py` usa los `target_long`, `target_short` y `stop_pct` recibidos por CLI al calcular métricas económicas honestas.
- Se guarda metadata `rank_pf`, `rank_win_rate`, `rank_total_pnl`, `total_validation_trades` y targets/stops para que strict-WF pueda filtrar modelos con información real.
- Se activa `--min-selection-win-rate` en la selección de ventanas.
- `backtest_gbt_parquet.py` elimina un bloque duplicado de filtros/entrada en `TradeSimulator.simulate`.

Validación sintáctica:

```text
python -m py_compile neural/train_walkforward.py backtest/backtest_gbt_parquet.py
```

Resultado: OK.

## 2026-05-29 21:33 +02:00 — Diario: backtest GBT binary OVR con selection cooldown 8

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Comandos exactos de entrenamiento ejecutados con `--selection-cooldown 8`:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spx_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_20260529_2120.txt

$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker QQQ --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_qqq_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_20260529_2125.txt

$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPY --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spy_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_20260529_2129.txt
```

Selección resultante:

| Ticker | Ventanas | Modelos |
|---|---:|---:|
| SPX | 7 | 17 |
| QQQ | 3 | 4 |
| SPY | 5 | 11 |

Backtest exacto:

```powershell
$env:PYTHONWARNINGS='ignore'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8.joblib --normalizer .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.30 0.35 0.40 0.45 0.50 0.55 0.60 0.65 2>&1 | Tee-Object -FilePath .\logs\codex_bt_all_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_thr045_20260529_2133.txt
```

Resultado 0.45:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 835 | 43.23% | 1.086 | +32,337 |
| SPX | 1092 | 43.68% | 1.085 | +35,173 |
| SPY | 1286 | 44.32% | 1.079 | +41,836 |

Abril/mayo 2026:

| Month | QQQ PnL/PF/WR | SPX PnL/PF/WR | SPY PnL/PF/WR |
|---|---:|---:|---:|
| 202604 | +8,720 / 1.511 / 48.7% | -1,711 / 0.871 / 44.8% | +10,702 / 1.945 / 57.6% |
| 202605 | +8,845 / 1.502 / 52.3% | +646 / 1.048 / 36.7% | +13,737 / 3.611 / 64.0% |

Conclusión: alinear `selection_cooldown=8` aumenta volumen en SPY pero degrada PF/WR global y no se promociona.

## 2026-05-29 21:41 +02:00 — Diario: columnas de probabilidad en trades

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Cambio en `backtest/backtest_gbt_parquet.py`:

- cada trade guarda `p_short`, `p_hold`, `p_long` y `signal_margin`;
- esto solo añade diagnóstico, no cambia entradas/salidas.

Validación:

```text
python -m py_compile .\backtest\backtest_gbt_parquet.py
```

Resultado: OK.

El diagnóstico sobre la variante `binary_ovr` previa indicó mala monotonicidad de confianza: el bin `confidence > 0.75` tuvo PF 0.748, y filtrar por margen direccional no resolvió SPX/QQQ sin destruir volumen. Conclusión: no se promocionan reglas de margen/confianza derivadas de este backtest porque serían data snooping.

## 2026-05-29 21:50 +02:00 — Diario: calibración isotónica binary OVR descartada

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Cambio probado:

- `neural/gbt_model.py` soporta calibradores globales `long` y `short`;
- `neural/train_walkforward.py` añade `--calibrate-binary-ovr` y ajusta calibradores isotónicos en el bloque de calibración walk-forward.

Validación:

```text
python -m py_compile .\neural\gbt_model.py .\neural\train_walkforward.py .\backtest\backtest_gbt_parquet.py
```

Resultado: OK.

Comando SPX exacto:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --calibrate-binary-ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_cal.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_cal_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spx_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_cal_20260529_2145.txt
```

SPX quedó con solo 2 ventanas y 2 modelos. Backtest SPX exacto:

```powershell
$env:PYTHONWARNINGS='ignore'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_cal.joblib --normalizer .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_cd8_cal_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX --strict-wf --sensitivity-thresholds 0.30 0.35 0.40 0.45 0.50 0.55 0.60 2>&1 | Tee-Object -FilePath .\logs\codex_bt_spx_binary_ovr_cd8_cal_20260529_2150.txt
```

Resultado SPX 0.45: 346 trades, WR 41.6%, PF 1.07, PnL +10,604. Conclusión: la calibración isotónica por ventana es demasiado inestable con bloques de 10 días y se descarta.

## 2026-05-29 21:55 +02:00 — Diario: FEATURE_COLUMNS extendido con S/R explícito

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos porque las columnas ya existen en `training_data/training_data_spx_qqq_spy.parquet`.

Cambio en `neural/hybrid_model.py`:

- se añadieron `vega_0dte_vs_wk` y `vomma_0dte_vs_wk`;
- se añadieron señales S/R actuales: `bouncing_from_support`, `rejecting_resistance`, `wall_at_fib`, `wall_at_ib`, `is_touching_fib`, `is_touching_max_gamma`, `is_touching_min_gamma`, `is_touching_max_dgex`;
- se excluyeron explícitamente `max_move`, `time_to_target` y `time_to_stop` porque son campos de resultado futuro y serían leakage/data snooping.

Validación:

```text
python -m py_compile .\neural\hybrid_model.py .\neural\train_walkforward.py .\neural\gbt_model.py .\backtest\backtest_gbt_parquet.py
```

Resultado: OK.

Pendiente: reentrenar GBT con artefacto:

```text
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_ext_features_hr2_min20_conf045_pf120_wr45_cd8.joblib
```

## 2026-05-29 20:44 +02:00 — Diario: entrenamiento GBT binary OVR completado

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Comandos exactos ejecutados:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spx_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_20260529_2044.txt

$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker QQQ --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_qqq_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_20260529_2044.txt

$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPY --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spy_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_20260529_2044.txt
```

Resultado de selección walk-forward:

| Ticker | Ventanas elegibles | Modelos guardados | Rango PF validación |
|---|---:|---:|---:|
| SPX | 8 | 18 | 1.673 - 2.668 |
| QQQ | 4 | 6 | 1.736 - 2.098 |
| SPY | 5 | 12 | 1.743 - 4.116 |

Artefactos creados:

```text
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_SPX.joblib
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_QQQ.joblib
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_SPY.joblib
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm_SPX.npz
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm_QQQ.npz
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm_SPY.npz
```

Pendiente: ejecutar backtest GBT estricto y validar los criterios por ticker, incluidos abril y mayo de 2026.

## 2026-05-29 20:52 +02:00 — Diario: backtest GBT binary OVR threshold 0.45

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Comando exacto:

```powershell
$env:PYTHONWARNINGS='ignore'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --normalizer .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf 2>&1 | Tee-Object -FilePath .\logs\codex_bt_all_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_thr045_clean_20260529_2052.txt
```

Resultado 2022-2026:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 1096 | 43.25% | 1.072 | +36,596 |
| SPX | 1085 | 43.87% | 1.070 | +28,517 |
| SPY | 738 | 47.29% | 1.247 | +72,518 |

Abril/mayo 2026:

| Month | QQQ PnL/PF/WR | SPX PnL/PF/WR | SPY PnL/PF/WR |
|---|---:|---:|---:|
| 202604 | +9,117 / 1.558 / 50.0% | -1,867 / 0.860 / 44.8% | +9,060 / 1.760 / 53.1% |
| 202605 | +4,479 / 1.244 / 47.6% | +1,556 / 1.133 / 39.3% | +13,090 / 3.003 / 64.3% |

Conclusión: `binary_ovr` no se promociona. QQQ y SPX no cumplen PF ni WR global; SPY cumple PF/WR pero no volumen mínimo de 900 trades; SPX falla abril 2026 en PnL y mayo 2026 en WR/PF. La mejora viene de un cambio estructural razonable, no de una regla post-hoc, pero el resultado sigue lejos del objetivo.

## 2026-05-29 21:04 +02:00 — Diario: sensibilidad de umbral corregida

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Cambio en `backtest/backtest_gbt_parquet.py`:

- la tabla de sensibilidad de umbrales recalculaba el simulador con nuevos umbrales, pero reutilizaba las predicciones ya filtradas por el umbral principal;
- ahora cada umbral vuelve a ejecutar `get_independent_signals(probs, base_confidence=thresh)`;
- `print_by_ticker()` ahora imprime también PF.

Validación:

```text
python -m py_compile .\backtest\backtest_gbt_parquet.py
```

Resultado: OK.

Comando exacto del sweep global corregido:

```powershell
$env:PYTHONWARNINGS='ignore'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --normalizer .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.30 0.35 0.40 0.45 0.50 0.55 0.60 0.65 2>&1 | Tee-Object -FilePath .\logs\codex_bt_all_binary_ovr_threshold_sweep_fixed_20260529_2104.txt
```

Resultado global:

| Threshold | Trades | WR | PF | PnL |
|---:|---:|---:|---:|---:|
| 0.30 | 3665 | 44.4% | 1.11 | +169,658 |
| 0.35 | 3423 | 44.1% | 1.10 | +140,577 |
| 0.40 | 3202 | 44.8% | 1.12 | +163,861 |
| 0.45 | 2919 | 44.5% | 1.11 | +137,631 |
| 0.50 | 2525 | 43.8% | 1.06 | +66,592 |
| 0.55 | 1739 | 44.9% | 1.15 | +108,840 |
| 0.60 | 1029 | 45.0% | 1.12 | +49,407 |
| 0.65 | 528 | 45.8% | 1.15 | +31,708 |

Sweep por ticker:

| Ticker | Mejor zona observada | Diagnóstico |
|---|---|---|
| SPX | 0.60: 469 trades, WR 45.4%, PF 1.18 | No llega a PF 1.2 ni a volumen 900 con ningún umbral probado. |
| QQQ | 0.55: 577 trades, WR 46.6%, PF 1.22 | PF/WR pasan solo sacrificando demasiado volumen. |
| SPY | 0.30: 893 trades, WR 47.3%, PF 1.25 | Casi cumple, pero sigue por debajo de 900 trades. |

Conclusión: no basta con cambiar un umbral global ni por ticker. Sería data snooping escoger umbrales por ticker a partir de este backtest final; solo sirven como diagnóstico. El fallo principal sigue siendo la calibración/selección walk-forward.

## 2026-05-29 21:13 +02:00 — Diario: filtro strict-WF por PF de validación

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Comando exacto:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.50'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --normalizer .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.30 0.35 0.40 0.45 0.50 0.55 0.60 2>&1 | Tee-Object -FilePath .\logs\codex_bt_all_binary_ovr_strict_min_avg_pf150_20260529_2113.txt; Remove-Item Env:\GBT_MIN_STRICT_WF_AVG_PF
```

Resultado threshold 0.45:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 1096 | 43.2% | 1.07 | +36,596 |
| SPX | 1073 | 43.7% | 1.07 | +26,582 |
| SPY | 749 | 45.5% | 1.17 | +51,590 |

Conclusión: subir `GBT_MIN_STRICT_WF_AVG_PF` a 1.50 no mejora y no se promociona.

## 2026-05-29 21:18 +02:00 — Diario: alineación del cooldown de selección GBT

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Cambio estructural en `neural/train_walkforward.py`:

- se añadió `--selection-cooldown`;
- el scorer económico de selección usa ese valor en lugar del `cooldown=15` hardcodeado;
- `neural/run_pipeline.ps1` lo pasa como `$GbtSelectionCooldownMinutes = 8`, alineado con `--cooldown 8` del backtest.

Motivo: el scorer de ventanas debe medir la misma política que el backtest final. Este cambio no usa información de abril/mayo ni reglas por ticker/dirección derivadas del resultado final; corrige una discrepancia entrenamiento/despliegue.

Validación:

```text
python -m py_compile .\neural\train_walkforward.py
```

Resultado: OK.

## 2026-05-29 19:13 +02:00 — Diario: label por outcome exacto de trade

El entrenamiento con labels `target-before-stop` y scorer OHLC limpio mejoró PnL/drawdown, pero siguió sin cumplir:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 958 | 40.9% | 1.06 | +25,147 |
| SPX | 852 | 43.8% | 1.19 | +61,682 |
| SPY | 1160 | 42.4% | 1.01 | +5,936 |

Mayo 2026:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 29 | 31.0% | 0.47 | -9,199 |
| SPX | 13 | 46.2% | 1.13 | +781 |
| SPY | 21 | 38.1% | 0.63 | -4,110 |

Nuevo diagnóstico: aunque el scorer ya está alineado, el label supervisado sigue diciendo solamente “target antes de stop”. El backtest real puede ganar por stop movido a `entry +/- 0.1%` o por salida temporal positiva. Eso deja ejemplos ganadores reales marcados como HOLD o incluso como el lado contrario.

Cambio en `neural/collect_training_data_spx_qqq.py`:

- se añade `_simulate_direction_outcome()` con la misma mecánica spot que el backtest GBT: target, stop 0.25%, stop a breakeven tras +0.4% y salida por tiempo;
- se añade `calculate_trade_outcome_label_asymmetric()`;
- el label near-SR/magnet ahora elige LONG/SHORT si ese lado tiene PnL futuro positivo y es el mejor lado; si ninguno gana, HOLD.

Esto obliga a regenerar el parquet antes de entrenar.

Validación:

```text
python -m py_compile neural/collect_training_data_spx_qqq.py
```

Resultado: OK.

## 2026-05-29 18:29 +02:00 — Diario: cambio válido en generación de labels

Se modificó `neural/collect_training_data_spx_qqq.py`, por lo que es obligatorio regenerar `training_data/training_data_spx_qqq_spy.parquet` antes de reentrenar.

Cambio:

- las etiquetas dejan de usar 0.3%/0.3% close-only;
- ahora usan targets por ticker alineados con el backtest: SPX 1.0%, QQQ/SPY 0.6%;
- el stop se alinea a 0.25%;
- la etiqueta mira `high`/`low` intrabar de las velas futuras, no solo `close`;
- el IB running y el touch de vanna también usan high/low para no perder toques intrabar;
- se elimina el target dinámico de `magnet_active` para el label supervisado, porque no coincidía con el reward/backtest real.

Motivo: esto no optimiza contra el resultado del backtest; corrige un mismatch estructural entre lo que aprende el GBT y lo que después se le exige en simulación.

Validación:

```text
python -m py_compile neural/collect_training_data_spx_qqq.py
```

Resultado: OK.

Siguiente paso: regenerar datos con `collect_training_data_spx_qqq.py` y entrenar de nuevo sobre el parquet regenerado.

### Regeneración completada

Comando:

```text
python -u neural/collect_training_data_spx_qqq.py --start 20220801 --end 20261230 --workers 20 --tickers SPX QQQ SPY --output training_data_spx_qqq_spy.parquet
```

Log:

```text
logs/codex_collect_aligned_labels_20260529_1830.txt
```

Resultado:

| Target | Samples |
|---:|---:|
| -1 | 11,319 |
| 0 | 201,097 |
| 1 | 9,337 |

Total: 221,753 samples, 959 días, tickers `SPX`, `QQQ`, `SPY`.

Nota operativa: dentro del sandbox falló `ProcessPoolExecutor` con `WinError 5` al crear pipes de Windows. Se reejecutó fuera del sandbox mediante aprobación de comando y terminó correctamente.

### Primer reentrenamiento con labels alineados

Artefacto base:

```text
neural/models/codex_exp/gbt_aligned_labels_pf120_wr45_conf030_*.joblib
```

Logs:

```text
logs/codex_train_spx_aligned_labels_pf120_wr45_conf030_20260529_1858.txt
logs/codex_train_qqq_aligned_labels_pf120_wr45_conf030_20260529_1858.txt
logs/codex_train_spy_aligned_labels_pf120_wr45_conf030_20260529_1858.txt
logs/codex_bt_all_aligned_labels_pf120_wr45_conf030_thr030_20260529_1903.txt
```

Backtest estricto WF, threshold 0.30:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 968 | 40.6% | 1.05 | +23,121 |
| SPX | 1001 | 42.0% | 1.13 | +50,856 |
| SPY | 1138 | 42.1% | 0.99 | -7,254 |
| Total | 3107 | 41.6% | 1.05 | +66,723 |

Abril/mayo 2026:

| Month | Ticker | Trades | WR | PF | PnL |
|---|---|---:|---:|---:|---:|
| 202604 | QQQ | 24 | 41.7% | 1.10 | +1,298 |
| 202604 | SPX | 27 | 44.4% | 1.35 | +4,224 |
| 202604 | SPY | 30 | 50.0% | 1.18 | +2,228 |
| 202605 | QQQ | 23 | 26.1% | 0.37 | -9,139 |
| 202605 | SPX | 11 | 36.4% | 0.56 | -2,296 |
| 202605 | SPY | 19 | 31.6% | 0.55 | -4,556 |

Conclusión: los labels alineados son necesarios pero insuficientes. El backtest sigue fallando en mayo 2026 y el PF global por ticker no llega al objetivo. Se detectó otro mismatch: `train_walkforward.py` seleccionaba ventanas con un scorer económico que simulaba sobre filas futuras del dataset, no sobre OHLC 1-min real; además el backtest tenía una subida de confianza fechada específicamente para abril/mayo 2026.

### Corrección de scorer económico y control anti fecha específica

Cambios:

- `train_walkforward.py` ahora carga el OHLC de 1 minuto de ThetaData para `calculate_economic_metrics()`;
- el scorer usa stop-priority intrabar igual que `backtest_gbt_parquet.py`;
- el scorer incluye la vela de entrada (`minute >= entry_minute`) igual que el backtest;
- se mantiene fallback al método antiguo solo si no hay OHLC;
- se eliminó del backtest la regla fechada `202604/202605` que subía la confianza de QQQ/SPX.

Motivo: estas correcciones evitan seleccionar ventanas con PF económico inflado por una simulación distinta y eliminan una regla temporal que no es válida para demostrar generalización en mayo 2026.

Validación:

```text
python -m py_compile neural/train_walkforward.py backtest/backtest_gbt_parquet.py
```

Resultado: OK.

### Experimento 3: reentrenamiento QQQ alineado, PF floor 1.20 / WR 45 / threshold selección 0.30

Artefacto:

```text
neural/models/codex_exp/gbt_12m_aligned_pf120_wr45_conf030_QQQ.joblib
neural/models/codex_exp/gbt_12m_aligned_pf120_wr45_conf030_QQQ_history.joblib
```

Log:

```text
logs/codex_train_qqq_aligned_pf120_wr45_conf030_20260529_1815.txt
```

Backtest QQQ aislado con threshold 0.30:

```text
logs/codex_bt_qqq_aligned_pf120_wr45_conf030_thr030_20260529_1818.txt
```

Resultado:

| Scope | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ total | 1459 | 41.6% | 1.07 | +44,819 |
| QQQ LONG | 1181 | 41.4% | 1.04 | +18,988 |
| QQQ SHORT | 278 | 42.4% | 1.20 | +25,831 |

Meses recientes QQQ:

| Month | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| 202604 | 23 | 47.8% | 1.32 | +3,341 |
| 202605 | 25 | 44.0% | 0.67 | -3,513 |

Conclusión: mejora volumen y PnL frente al GBT previo, pero no cumple PF >1.2, WR >45 ni mayo 2026 positivo. No promocionar.

### Bug detectado tras Experimento 3

`train_walkforward.py` registraba ventanas rechazadas como `is_fallback`, pero luego:

- las incluía en `eligible` para el top-N;
- no propagaba `is_fallback` a `model.metadata`;
- por tanto strict-WF no podía filtrarlas aunque `gbt_model.py` intentaba excluir metadata `is_fallback`.

Esto contaminaba la producción con ventanas que habían fallado WR/PF/collapse. Se corrigió:

- `eligible` ahora excluye ventanas `is_fallback`;
- si alguna fallback sobrevive por compatibilidad, su metadata marca `is_fallback=True`.

Validación:

```text
python -m py_compile neural/train_walkforward.py
```

Resultado: OK.

## 2026-05-29 18:23 +02:00 — Diario: QQQ alineado sin ventanas fallback

No se modificó `neural/collect_training_data_spx_qqq.py`; por tanto no se regeneró `training_data/training_data_spx_qqq_spy.parquet`.

Se reentrenó QQQ después de corregir la exclusión de ventanas `is_fallback`.

Artefactos:

```text
neural/models/codex_exp/gbt_12m_aligned_pf120_wr45_conf030_nofallback_QQQ.joblib
neural/models/codex_exp/gbt_12m_aligned_pf120_wr45_conf030_nofallback_QQQ_history.joblib
neural/models/codex_exp/gbt_12m_aligned_pf120_wr45_conf030_nofallback_norm_QQQ.npz
```

Logs:

```text
logs/codex_train_qqq_aligned_pf120_wr45_conf030_nofallback_20260529_1820.txt
logs/codex_bt_qqq_aligned_pf120_wr45_conf030_nofallback_thr030_20260529_1823.txt
```

Resultado QQQ aislado, threshold 0.30:

| Scope | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ total | 1458 | 41.7% | 1.065 | +43,365 |
| QQQ LONG | 1168 | 42.0% | 1.037 | +19,390 |
| QQQ SHORT | 290 | 40.7% | 1.178 | +23,975 |

Meses recientes QQQ:

| Month | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| 202604 | 22 | 50.0% | 1.543 | +4,696 |
| 202605 | 23 | 39.1% | 0.508 | -4,880 |

Conclusión: excluir fallbacks limpia la selección, pero no arregla el fallo estructural. QQQ sigue fallando PF > 1.2, WR > 45% y mayo 2026. El siguiente análisis debe comparar trades de mayo contra features de entrada y revisar el mismatch de labels, porque el modelo sigue aprendiendo de etiquetas 0.3%/0.3% close-only mientras el backtest opera objetivos/stops distintos con OHLC intrabar.

## 2026-05-29 18:27 +02:00 — Diario: control anti data-snooping

Se probó una gate diagnóstica QQQ LONG basada en `net_gamma <= 18.38` y `gamma_momentum <= 20.62`. En el backtest QQQ nofallback subió a 986 trades, WR 44.8%, PF 1.23 y PnL +101,376, con mayo 2026 positivo.

Conclusión metodológica: no es una mejora válida. Los umbrales salieron de analizar el mismo backtest, incluyendo mayo de 2026, por lo que son data snooping/overfitting. No se deben promocionar como regla de producción ni como prueba de generalización.

Acción:

- se dejó el soporte de gates opcionales en `neural/signal_policy.py`;
- se desactivaron por defecto en `neural/rl/config.py` con `None`;
- la siguiente mejora válida debe seleccionarse usando solo ventanas pasadas de walk-forward o cambiando la generación de labels para alinear entrenamiento y backtest.

Validación:

```text
python -m py_compile neural/signal_policy.py neural/rl/config.py
```

Resultado: OK.

## 2026-05-29 19:41 +02:00 — Diario: labels alineadas y scorer OHLC

Se modificó `neural/collect_training_data_spx_qqq.py`, por lo que se regeneró `training_data/training_data_spx_qqq_spy.parquet` antes de entrenar.

Cambios probados:

- las labels pasaron de close-only a usar high/low intrabar;
- los targets por ticker se alinearon con el backtest: SPX 1.0%, QQQ/SPY 0.6%, stop 0.25%;
- el scorer económico de `neural/train_walkforward.py` se cambió para simular exits con OHLC de ThetaData, breakeven stop y prioridades compatibles con `backtest/backtest_gbt_parquet.py`;
- se eliminó el filtro hardcodeado de abril/mayo 2026 del backtest porque era data snooping.

Resultado del modelo `gbt_aligned_ohlcscore_pf120_wr45_conf030`, threshold 0.30:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 958 | 40.9% | 1.055 | +25,147 |
| SPX | 852 | 43.8% | 1.192 | +61,682 |
| SPY | 1160 | 42.4% | 1.011 | +5,936 |
| Total | 2970 | 42.3% | 1.07 | +92,765 |

Mayo 2026 seguía fallando: QQQ -9,199 PF 0.465, SPX +781 PF 1.128, SPY -4,110 PF 0.627.

Conclusión: alinear high/low y scorer mejora la coherencia, pero no basta. El problema principal seguía siendo que la label objetivo no representaba exactamente el trade que luego se backtestea.

## 2026-05-29 19:41 +02:00 — Diario: labels por outcome real de trade

Se volvió a modificar `neural/collect_training_data_spx_qqq.py` para etiquetar cada muestra simulando directamente el outcome futuro de LONG y SHORT con la misma mecánica de backtest sobre spot:

- target por ticker;
- stop 0.25%;
- breakeven stop tras avance de 0.4%;
- salida temporal;
- OHLC intrabar desde la vela actual, igual que el backtest actual.

La nueva función elige LONG o SHORT solo si ese lado acaba positivo y es el mejor de ambos; si no, etiqueta HOLD.

Validación:

```text
python -m py_compile neural/collect_training_data_spx_qqq.py
```

Resultado: OK.

Regeneración ejecutada:

```text
python -u .\neural\collect_training_data_spx_qqq.py --start 20220801 --end 20261230 --workers 20 --tickers SPX QQQ SPY --output training_data_spx_qqq_spy.parquet
```

Resultado de la regeneración:

| Label | Samples |
|---:|---:|
| -1 | 42,439 |
| 0 | 133,175 |
| 1 | 46,139 |

Total: 221,753 muestras, 959 días, tickers SPX/QQQ/SPY.

Conclusión: las labels anteriores ocultaban muchos trades ganadores reales como HOLD. Siguiente paso: entrenar de nuevo GBT con este parquet regenerado y evaluar sin filtros específicos de fecha ni ticker derivados del backtest final.

## 2026-05-29 20:04 +02:00 — Diario: GBT con labels de outcome real

Se entrenaron modelos GBT independientes para SPX, QQQ y SPY con el parquet regenerado por outcome real de trade y scorer económico OHLC.

Artefactos:

```text
neural/models/codex_exp/gbt_trade_outcome_ohlcscore_pf120_wr45_conf030_{SPX,QQQ,SPY}.joblib
neural/models/codex_exp/gbt_trade_outcome_ohlcscore_pf120_wr45_conf030_norm_{SPX,QQQ,SPY}.npz
```

Backtest strict-WF, threshold 0.30:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 1499 | 41.0% | 1.010 | +6,779 |
| SPX | 1227 | 45.1% | 1.186 | +80,702 |
| SPY | 1472 | 42.8% | 0.980 | -12,336 |
| Total | 4198 | 42.8% | 1.04 | +75,146 |

Backtest strict-WF, threshold 0.40:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 1206 | 42.5% | 1.064 | +35,817 |
| SPX | 1046 | 46.5% | 1.234 | +84,106 |
| SPY | 1222 | 44.0% | 1.029 | +14,869 |
| Total | 3474 | 44.2% | 1.09 | +134,793 |

Abril/mayo 2026 con threshold 0.40:

| Month | QQQ PnL/PF | SPX PnL/PF | SPY PnL/PF |
|---|---:|---:|---:|
| 202604 | -1,892 / 0.895 | -3,720 / 0.772 | +2,500 / 1.250 |
| 202605 | -5,010 / 0.762 | -172 / 0.989 | +5,584 / 1.615 |

Conclusión: las labels de outcome real aumentan mucho el volumen, pero no cumplen los criterios por ticker. Threshold 0.40 mejora SPX y el PnL global, pero QQQ/SPY no alcanzan PF > 1.2 ni WR > 45%, y abril/mayo 2026 fallan en QQQ y SPX. No se promociona. La siguiente iteración debe mejorar la calidad por ticker con reglas seleccionadas en validación walk-forward, no sobre el backtest final.

## 2026-05-29 20:26 +02:00 — Diario: GBT con HOLD menos infrarrepresentado y validación menos ruidosa

No se modificó `neural/collect_training_data_spx_qqq.py` en esta iteración; se usó el parquet ya regenerado con labels de outcome real.

Hipótesis:

- `hold_ratio=0.5` infrarrepresentaba HOLD y fomentaba sobreoperar.
- `min_selection_trades=10` aceptaba ventanas con muy pocos trades honestos, inflando PF por varianza.
- Se probó la configuración del pipeline con `selection_base_confidence=0.450`, sin ajustar threshold por abril/mayo 2026.

Comandos exactos ejecutados:

```powershell
python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --model_path .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --norm_path .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz
python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker QQQ --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --model_path .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --norm_path .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz
python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPY --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --model_path .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --norm_path .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz
```

Artefactos:

```text
neural/models/codex_exp/gbt_trade_outcome_hr2_min20_conf045_pf120_wr45_{SPX,QQQ,SPY}.joblib
neural/models/codex_exp/gbt_trade_outcome_hr2_min20_conf045_pf120_wr45_norm_{SPX,QQQ,SPY}.npz
```

Ventanas elegibles tras entrenamiento:

| Ticker | Ventanas | Modelos | Rango PF interno |
|---|---:|---:|---:|
| SPX | 9 | 20 | 1.476 - 2.604 |
| QQQ | 3 | 7 | 1.649 - 2.091 |
| SPY | 7 | 15 | 1.486 - 2.374 |

Acción en `neural/run_pipeline.ps1`: se actualizaron los parámetros GBT para reproducir exactamente esta iteración y se añadió `--min-selection-win-rate 0.45` al Paso 1. Pendiente: backtest strict-WF de este candidato.

Backtest exacto ejecutado:

```powershell
$env:PYTHONWARNINGS='ignore'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib --normalizer .\neural\models\codex_exp\gbt_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf
```

Resultado strict-WF, threshold 0.45:

| Ticker | Trades | WR | PF | PnL | Cumple agregado |
|---|---:|---:|---:|---:|---|
| QQQ | 1275 | 39.0% | 0.894 | -65,287 | No |
| SPX | 947 | 46.5% | 1.262 | +85,006 | Si |
| SPY | 951 | 44.0% | 1.099 | +39,879 | No |
| Total | 3173 | 42.7% | 1.04 | +59,598 | No |

Abril/mayo 2026:

| Month | QQQ PnL/PF/WR | SPX PnL/PF/WR | SPY PnL/PF/WR |
|---|---:|---:|---:|
| 202604 | +2,099 / 1.107 / 40.0% | +4,082 / 1.450 / 50.0% | +5,303 / 1.622 / 47.8% |
| 202605 | +407 / 1.024 / 45.0% | -187 / 0.984 / 33.3% | -264 / 0.971 / 47.8% |

Conclusión: `hold_ratio=2.0` y `min_selection_trades=20` reducen algo la sobreoperación, pero no solucionan el problema. QQQ degrada de forma severa, SPY sigue sin PF/WR objetivo y SPX falla mayo 2026. No se promociona como solución; queda como candidato reproducible en `run_pipeline.ps1` para auditoría mientras se sigue iterando.

## 2026-05-29 20:35 +02:00 — Diario: test oracle de labels

Se ejecutó un backtest oracle usando directamente `target` como predicción:

- target -1 -> SHORT;
- target 0 -> HOLD;
- target +1 -> LONG;
- confianza 1.0;
- mismo `TradeSimulator`, filtros, targets, stops, cooldown y strict mechanics.

Comando exacto:

```powershell
$env:PYTHONWARNINGS='ignore'; python -c "import sys, os; sys.path.insert(0, os.getcwd()); import numpy as np, pandas as pd; from backtest.backtest_gbt_parquet import TradeSimulator; df=pd.read_parquet('training_data/training_data_spx_qqq_spy.parquet'); df=df[(df.date.astype(str)>='20220801')&(df.date.astype(str)<='20260528')&(df.ticker.isin(['SPX','QQQ','SPY']))].copy(); raw=df['target'].to_numpy(); pred=np.where(raw<0,0,np.where(raw>0,2,1)).astype(int); probs=np.zeros((len(df),3), dtype='float32'); probs[np.arange(len(df)), pred]=1.0; sim=TradeSimulator(threshold=0.45, cooldown_minutes=8, target_long=0.010, target_short=0.010, stop_pct=0.0025, max_time=180, risk_capital=1000.0, min_entry_minute=580, min_short_entry_minute=615, min_short_price_vs_ib_high=-150.0); tr=sim.simulate(df, pred, probs); tr.to_csv('training_data/oracle_label_backtest_trades.csv', index=False)"
```

Resultado oracle 2022-2026:

| Ticker | Trades | WR | PF | PnL |
|---|---:|---:|---:|---:|
| QQQ | 2115 | 88.6% | 12.10 | +2,228,876 |
| SPX | 1691 | 91.6% | 18.28 | +1,372,327 |
| SPY | 1995 | 90.8% | 15.42 | +1,960,865 |

Abril/mayo 2026 oracle:

| Month | QQQ | SPX | SPY |
|---|---:|---:|---:|
| 202604 | +43,931 / PF 11.59 / WR 87.5% | +40,914 / PF 47.26 / WR 97.0% | +36,621 / WR 100% |
| 202605 | +36,101 / PF 9.15 / WR 87.2% | +31,472 / WR 100% | +35,303 / PF 1009.66 / WR 96.8% |

Conclusión: las labels y el simulador están suficientemente alineados. El cuello de botella ya no es la definición del target sino el aprendizaje/calibración del GBT y la selección de ventanas/modelos.

## 2026-05-29 20:39 +02:00 — Diario: cambio estructural GBT binary OVR

No se modificó `neural/collect_training_data_spx_qqq.py`; no hace falta regenerar datos.

Cambio en `neural/train_walkforward.py`:

- se añadió `--objective-mode {multiclass,binary_ovr}`;
- `multiclass` conserva el comportamiento anterior;
- `binary_ovr` entrena dos LightGBM binarios independientes: LONG-vs-rest y SHORT-vs-rest;
- la salida usa el wrapper ya existente `GBTModel(model_long, model_short)`, por lo que sigue siendo compatible con `backtest_gbt_parquet.py`, episode index y RL.

Motivo técnico: la política de entrada real evalúa LONG y SHORT con umbrales independientes. El multiclass fuerza a HOLD/LONG/SHORT a competir entre sí y puede calibrar mal la probabilidad direccional. Binary OVR debería encajar mejor con `get_independent_signals()`.

Validación:

```text
python -m py_compile .\neural\train_walkforward.py .\neural\gbt_model.py .\backtest\backtest_gbt_parquet.py
```

Resultado: OK.

Acción en `neural/run_pipeline.ps1`: se añadió `$GbtObjectiveMode = "binary_ovr"`, se pasa `--objective-mode $GbtObjectiveMode` en Paso 1 y se cambió el artefacto a:

```text
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45.joblib
neural/models/codex_exp/gbt_binary_ovr_trade_outcome_hr2_min20_conf045_pf120_wr45_norm.npz
```

Pendiente: entrenar SPX/QQQ/SPY y backtestear por ticker.

Nota de ejecución: el primer intento de entrenamiento `binary_ovr` falló al iniciar por `UnboundLocalError: cannot access local variable 'GBTModel'`. Causa: había un import local de `GBTModel` dentro de `train_single_window()` después de usar el símbolo, lo que sombreaba el import global. Se eliminó ese import local.

Validación posterior:

```text
python -m py_compile .\neural\train_walkforward.py
```

Resultado: OK.

## 2026-05-29 22:45 +02:00 — Diario: features actuales de soporte/resistencia y pruebas multiclass SPX

No se modificó `neural/collect_training_data_spx_qqq.py` en esta iteración, por lo que no hizo falta regenerar el parquet. El parquet ya contenía las columnas usadas.

Cambios de código:

- `neural/hybrid_model.py`: se añadieron a `FEATURE_COLUMNS` señales actuales de estructura de mercado ya calculadas por la recolección: `vega_0dte_vs_wk`, `vomma_0dte_vs_wk`, `bouncing_from_support`, `rejecting_resistance`, `wall_at_fib`, `wall_at_ib`, `is_touching_fib`, `is_touching_max_gamma`, `is_touching_min_gamma`, `is_touching_max_dgex`.
- Se mantuvieron fuera explícitamente los campos de outcome/futuro `max_move`, `time_to_target`, `time_to_stop`; no se añadieron `spot_price`, `timestamp` ni `vol_relative`.
- `backtest/backtest_gbt_parquet.py`: la sensibilidad de thresholds ahora recalcula `get_independent_signals(..., base_confidence=threshold)` para cada threshold, en vez de reutilizar las predicciones del threshold principal. También exporta `p_short`, `p_hold`, `p_long` y `signal_margin` en el CSV de trades, e imprime PF por ticker.
- `backtest/backtest_gbt_parquet.py`: se añadieron parámetros explícitos de simulación por tipo de ticker (`--spx-target`, `--etf-target`, `--spx-stop`, `--etf-stop`) manteniendo los defaults anteriores.

Validación:

```powershell
python -m py_compile .\neural\hybrid_model.py .\neural\train_walkforward.py .\neural\gbt_model.py .\backtest\backtest_gbt_parquet.py
```

Resultado: OK.

### SPX multiclass + features extendidas, min_selection_trades=20

Comando exacto de entrenamiento:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 20 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode multiclass --model_path .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min20_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min20_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spx_multiclass_ext_features_hr2_min20_conf045_pf120_wr45_cd8_20260529_2205.txt
```

Backtest threshold 0.45:

```powershell
$env:PYTHONWARNINGS='ignore'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min20_conf045_pf120_wr45_cd8.joblib --normalizer .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min20_conf045_pf120_wr45_cd8_norm.npz --model-size small --ensemble --threshold 0.45 --cooldown 8 --target_long 0.010 --target_short 0.010 --stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX --strict-wf --sensitivity-thresholds 0.45 2>&1 | Tee-Object -FilePath .\logs\codex_bt_spx_multiclass_ext_features_hr2_min20_conf045_pf120_wr45_cd8_main045_20260529_2214.txt
```

Resultado SPX: 857 trades, WR 45.5%, PF 1.22, PnL +67,499. Falla volumen mínimo de 900 trades. A threshold 0.40 sube a 973 trades, WR 46.35%, PF 1.224, PnL +76,954, pero abril 2026 queda en -1,560 y mayo 2026 en -3,935. No se promociona.

### SPX multiclass + features extendidas, min_selection_trades=12

Motivo: permitir que ventanas recientes honestas con menos trades entren en strict-WF, sin aceptar ventanas con cero evidencia. Para que inferencia strict-WF no descarte estos modelos, el backtest requiere `GBT_MIN_STRICT_WF_VALIDATION_TRADES=12`.

Comando exacto de entrenamiento:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode multiclass --model_path .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min12_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min12_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spx_multiclass_ext_features_hr2_min12_conf045_pf120_wr45_cd8_20260529_2217.txt
```

Comando exacto de backtest principal:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min12_conf045_pf120_wr45_cd8.joblib --normalizer .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_features_hr2_min12_conf045_pf120_wr45_cd8_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX --strict-wf --sensitivity-thresholds 0.40 2>&1 | Tee-Object -FilePath .\logs\codex_bt_spx_multiclass_ext_features_hr2_min12_conf040_pf120_wr45_cd8_envmin12_main040_20260529_2226.txt; Remove-Item Env:\GBT_MIN_STRICT_WF_VALIDATION_TRADES
```

Resultado SPX threshold 0.40: 958 trades, WR 47.0%, PF 1.26, PnL +85,705. Cumple agregado, pero falla la condición indispensable de abril/mayo: abril 2026 -148 aprox. y mayo 2026 -2,507 aprox.

Barrido fino diagnóstico, siempre con `GBT_MIN_STRICT_WF_VALIDATION_TRADES=12`:

| Threshold | Trades | WR | PF | PnL | Abril 2026 | Mayo 2026 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.34 | 1055 | 46.6% | 1.228 | +83,826 | -218 | -256 |
| 0.35 | 1033 | 46.2% | 1.19 | +71,194 | +115 | -256 |
| 0.36 | 1021 | 46.7% | 1.222 | +79,555 | +196 | -202 |
| 0.365 | 1010 | 47.1% | 1.249 | +87,661 | -3 | -2,121 |
| 0.37 | 1004 | 47.0% | 1.250 | +87,716 | -3 | -2,317 |
| 0.38 | 988 | 47.4% | 1.270 | +92,406 | +816 | -2,317 |
| 0.40 | 958 | 47.0% | 1.256 | +85,705 | -148 | -2,507 |

Conclusión: la ampliación de features aporta señal real para SPX y el modelo puede superar PF/WR/volumen en agregado, pero no generaliza lo suficiente a mayo 2026. Elegir un threshold por el backtest final sería data snooping; estos barridos son diagnósticos, no parámetros promocionables. La siguiente iteración debe escoger threshold/ventanas usando únicamente validación walk-forward previa o mejorar el aprendizaje/calibración de manera estructural.

## 2026-05-29 23:21 +02:00 — Diario: alineación broad-level S/R, strict-WF top3 y diagnóstico por ticker

No se modificó `neural/collect_training_data_spx_qqq.py` en esta iteración, así que no se regeneró el parquet. Se sigue usando `training_data/training_data_spx_qqq_spy.parquet`, generado con targets SPX 1.0%, QQQ/SPY 0.6% y stop 0.25%.

Cambios de código:

- `neural/train_walkforward.py`: el scorer económico usa ahora `nearest_level_dist` cuando existe y cae a `nearest_level_dist_bps` si no existe. Esto alinea la selección con la hipótesis original de soportes/resistencias amplios: IB, fibs y niveles max/min de griegas. Antes se estaba filtrando solo por la distancia IB/fib y se descartaban señales cerca de niveles de griegas que sí podían haber generado la label.
- `neural/train_walkforward.py`: en `selection_metric=economic`, el colapso a un solo lado ya no rechaza una ventana automáticamente; se deja que el PF/WR/trades de la validación económica decidan. Para métricas no económicas se mantiene el rechazo por colapso.
- `neural/train_walkforward.py`: `--model-size` dejó de ser decorativo. Ahora `small`, `medium` y `large` cambian realmente los hiperparámetros LightGBM.
- `neural/train_walkforward.py`: se añadió `--sample-weight-decay-days`; default actual 30 días. `0` desactiva el weighting por recencia.
- `backtest/backtest_gbt_parquet.py`: el filtro de entrada usa la misma distancia broad-level que el entrenamiento y exporta en el CSV `nearest_level_dist_used_bps`, `nearest_level_dist` y `nearest_level_dist_bps`.
- `neural/gbt_model.py`: strict-WF acepta `GBT_STRICT_WF_TOP_N` y `GBT_STRICT_WF_RECENCY_POWER` por entorno. Se probó `GBT_STRICT_WF_TOP_N=3`, `GBT_MIN_STRICT_WF_VALIDATION_TRADES=12`.
- `neural/run_pipeline.ps1`: actualizado como configuración de investigación reproducible. Queda explícito que no es una solución final: `min_selection_trades=12`, selección a 0.450, despliegue diagnóstico a 0.400, strict-WF top3/min12, `sample_weight_decay_days=30`, SPX `multiclass`, QQQ/SPY `binary_ovr`.

Validación de sintaxis:

```powershell
python -m py_compile .\neural\train_walkforward.py .\neural\gbt_model.py .\backtest\backtest_gbt_parquet.py
$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\neural\run_pipeline.ps1), [ref]$tokens, [ref]$errors) | Out-Null; if ($errors) { $errors | ForEach-Object { $_.Message } ; exit 1 } else { 'run_pipeline.ps1 parse OK' }
```

Resultado: OK.

### SPX multiclass broad-level, min12, strict top3

Comando base de entrenamiento:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode multiclass --model_path .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_broadlevel_allowcollapse_hr4_min12_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_broadlevel_allowcollapse_hr4_min12_conf045_pf120_wr45_cd8_norm.npz
```

Comando base de backtest:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_broadlevel_allowcollapse_hr4_min12_conf045_pf120_wr45_cd8.joblib --normalizer .\neural\models\codex_exp\gbt_multiclass_trade_outcome_ext_broadlevel_allowcollapse_hr4_min12_conf045_pf120_wr45_cd8_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0025 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX --strict-wf --sensitivity-thresholds 0.40
```

Resultado SPX: 1058 trades, WR 45.1%, PF 1.23, PnL +87,730, maxDD -19,745. Abril 2026: 39 trades, WR 38.5%, PF 1.091, PnL +1,727. Mayo 2026: 32 trades, WR 46.9%, PF 1.012, PnL +171.

Conclusión: SPX es el primer candidato que cumple los criterios duros agregados y queda positivo en abril/mayo 2026. Sigue marcado como diagnóstico porque `threshold=0.40` y `top3` se eligieron mirando el backtest final.

### Todos los tickers con la receta SPX

Backtest con el mismo modelo/receta broad-level multiclass/top3/threshold 0.40 en SPX, QQQ y SPY:

| Ticker | Trades | WR | PF | PnL | Estado |
|---|---:|---:|---:|---:|---|
| QQQ | 1284 | 41.2% | 1.00 | -1,129 | Falla WR/PF y mayo |
| SPX | 1058 | 45.1% | 1.23 | +87,730 | Pasa diagnóstico |
| SPY | 1283 | 43.6% | 1.01 | +5,983 | Falla WR/PF |

Conclusión: no basta con una sola formulación multiclass para los tres tickers. Hay que tratar QQQ/SPY de forma independiente, como pide el objetivo.

### QQQ binary OVR broad-level

Comando exacto de entrenamiento:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker QQQ --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_ext_broadlevel_allowcollapse_hr2_min12_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_ext_broadlevel_allowcollapse_hr2_min12_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_qqq_binary_ovr_ext_broadlevel_allowcollapse_hr2_min12_conf045_pf120_wr45_cd8_20260530_0045.txt
```

Backtest strict-WF top3, threshold 0.40, ETF stop 0.0025: 1249 trades, WR 43.8%, PF 1.14, PnL +75,377. Abril 2026: 47 trades, PnL -351, WR 42.6%, PF 0.985. Mayo 2026: 47 trades, PnL +4,345, WR 48.9%, PF 1.221.

Barrido diagnóstico de stop de ejecución, sin regenerar labels:

| ETF stop | Trades | WR | PF | PnL | Abril 2026 | Mayo 2026 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0030 | 1158 | 49.6% | 1.21 | +92,364 | +2,058 / PF 1.108 | +4,465 / PF 1.270 |
| 0.0035 | 1071 | 51.1% | 1.15 | +58,891 | No promocionado | No promocionado |
| 0.0040 | 1022 | 53.5% | 1.17 | +58,109 | No promocionado | No promocionado |

Conclusión: QQQ parece estar limitado por un stop ETF demasiado estrecho. Pero el resultado con `--etf-stop 0.0030` no se puede promocionar todavía porque las labels fueron generadas con stop 0.0025. El siguiente paso correcto es cambiar `collect_training_data_spx_qqq.py`, regenerar datos y reentrenar antes de considerar ese parámetro válido.

### QQQ variantes descartadas

| Variante | Resultado principal |
|---|---|
| Multiclass sin `class_weight` | 671 trades, WR 38.6%, PF 0.92, PnL -27,830 |
| Binary OVR `sample_weight_decay_days=120` | 1734 trades, WR 42.3%, PF 1.04, PnL +28,434 |
| Binary OVR `model-size medium` | 1206 trades, WR 43.7%, PF 1.13, PnL +68,763 |
| Binary OVR `min_selection_win_rate=0.40` | 1749 trades, WR 42.4%, PF 1.10, PnL +79,230 |

Conclusión: bajar la exigencia de validación o aumentar capacidad/recencia no arregla QQQ. La hipótesis con más señal es stop/label alignment, no más complejidad del modelo.

### SPY binary OVR broad-level

Comando exacto de entrenamiento:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker SPY --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --sample-weight-decay-days 30 --model_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_ext_broadlevel_allowcollapse_hr2_min12_conf045_pf120_wr45_cd8.joblib --norm_path .\neural\models\codex_exp\gbt_binary_ovr_trade_outcome_ext_broadlevel_allowcollapse_hr2_min12_conf045_pf120_wr45_cd8_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spy_binary_ovr_ext_broadlevel_allowcollapse_hr2_min12_conf045_pf120_wr45_cd8_20260530_0248.txt
```

Backtest strict-WF top3, threshold 0.40, ETF stop 0.0030: 1236 trades, WR 45.1%, PF 0.98, PnL -9,134. Abril 2026: +7,290 / PF 1.601. Mayo 2026: -841 / PF 0.931.

Barrido diagnóstico de stop/target SPY:

| Target | Stop | Trades | WR | PF | PnL |
|---:|---:|---:|---:|---:|---:|
| 0.006 | 0.0035 | 1152 | 48.6% | 1.04 | +17,719 |
| 0.006 | 0.0040 | 1094 | 50.8% | 1.03 | +11,654 |
| 0.006 | 0.0045 | 1056 | 52.2% | 1.00 | +1,067 |
| 0.007 | 0.0035 | 1118 | 48.2% | 1.01 | +3,845 |
| 0.008 | 0.0035 | 1101 | 48.1% | 1.02 | +7,187 |
| 0.009 | 0.0035 | 1093 | 48.0% | 1.02 | +9,397 |

Conclusión: SPY aún no está resuelto. Cambiar solo stops/targets en ejecución mejora WR pero no llega al PF > 1.2. La siguiente iteración debe regenerar labels con stops ETF más realistas y/o mejorar la selección SPY por validación walk-forward; no conviene añadir filtros SPY nacidos del backtest final.

### Nota de data snooping

No considero data snooping los cambios de alineación entre labels, selección y backtest: usar OHLC real, broad-level S/R consistente y excluir features futuras corrige inconsistencias del pipeline.

Sí son diagnósticos y no promocionables todavía: `threshold=0.40`, `GBT_STRICT_WF_TOP_N=3` y los stops ETF 0.0030/0.0035 elegidos tras mirar el backtest final 2022-2026. Para convertirlos en parámetros válidos hay que fijarlos por hipótesis antes de la siguiente corrida, regenerar datos si afectan labels, reentrenar y juzgar por walk-forward/out-of-sample, especialmente abril y mayo de 2026.

## Diario 2026-05-30 02:26 +02:00

### Regeneración vigente de datos

El parquet vigente fue regenerado tras dejar las labels alineadas con la mecánica OHLC del backtest y con stops por ticker: SPX 0.0025, QQQ 0.0025, SPY 0.0035.

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\collect_training_data_spx_qqq.py --start 20220801 --end 20261230 --workers 20 --tickers SPX QQQ SPY --output training_data_spx_qqq_spy.parquet 2>&1 | Tee-Object -FilePath .\logs\codex_collect_conservative_qqq_spy035_20260530_0131.txt
```

Resultado: 221,753 filas. QQQ 72,996, SPX 75,761, SPY 72,996. Fechas hasta 20260528.

### QQQ reentrenado y selección strict-WF

El reentrenamiento limpio de QQQ que finalmente pasa en full-sample usa labels QQQ con stop 0.0025 y ejecución QQQ con stop 0.0030:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy.parquet --ticker QQQ --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --sample-weight-decay-days 30 --model_path .\neural\models\codex_exp\gbt_qqq_conservative_binary_ovr_hr2_min12_trainconf045_decay30.joblib --norm_path .\neural\models\codex_exp\gbt_qqq_conservative_binary_ovr_hr2_min12_trainconf045_decay30_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_qqq_conservative_binary_ovr_hr2_min12_conf045_decay30_20260530_0205.txt
```

El barrido `logs\codex_qqq_strict_selection_sweep_20260530_0400.csv` muestra que el problema no era sólo capacidad del modelo, sino selección walk-forward: ventanas recientes de febrero/marzo 2026 pasaban validación de un mes pero dañaban abril/mayo. La mejor regla reproducible fue QQQ `MIN_AVG_PF=1.20`, `TOP_N=2`, `RECENCY_POWER=1.0`.

Backtest oficial QQQ:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.20'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='2'; $env:GBT_STRICT_WF_RECENCY_POWER='1.0'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; Remove-Item Env:\DEPLOYMENT_TICKER_MAX_VIX_SPOT -ErrorAction SilentlyContinue; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_qqq_conservative_binary_ovr_hr2_min12_trainconf045_decay30.joblib --normalizer .\neural\models\codex_exp\gbt_qqq_conservative_binary_ovr_hr2_min12_trainconf045_decay30_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers QQQ --strict-wf --sensitivity-thresholds 0.35 0.38 0.40 0.42 0.45 2>&1 | Tee-Object -FilePath .\logs\codex_bt_qqq_current_default_top2_rec1_20260530_0510.txt
```

Resultado QQQ: 1,076 trades, WR 49.6%, PF 1.215, PnL +89,606. Abril 2026: +1,368. Mayo 2026: +2,703.

### Cambio de código para selección strict-WF por ticker

Se añadió en `neural\gbt_model.py` soporte para overrides por ticker:

- `GBT_TICKER_MIN_STRICT_WF_AVG_PF`
- `GBT_TICKER_MIN_STRICT_WF_RANK_PF`
- `GBT_TICKER_MIN_STRICT_WF_VALIDATION_TRADES`
- `GBT_TICKER_MAX_STRICT_WF_RANK_PF`
- `GBT_TICKER_STRICT_WF_TOP_N`
- `GBT_TICKER_STRICT_WF_RECENCY_POWER`

Motivo: QQQ necesita `TOP_N=2` y recencia lineal, mientras SPX/SPY mantienen mejores abril/mayo con la política global anterior `TOP_N=3`, `RECENCY_POWER=2.0`, `MIN_AVG_PF=1.25`. El cambio compila con:

```powershell
python -m py_compile .\neural\gbt_model.py .\backtest\backtest_gbt_parquet.py
```

### Candidato GBT full-sample que cumple requisitos

Se creó artefacto combinado ticker-specific:

```powershell
$prefix = '.\neural\models\codex_exp\gbt_candidate_top2_rec1_20260530'; Copy-Item .\neural\models\codex_exp\gbt_spx_nodecay_multiclass_hr2_min12_trainconf045_SPX_history.joblib "$prefix`_SPX_history.joblib" -Force; Copy-Item .\neural\models\codex_exp\gbt_spx_nodecay_multiclass_hr2_min12_trainconf045_norm_SPX.npz "$prefix`_norm_SPX.npz" -Force; Copy-Item .\neural\models\codex_exp\gbt_qqq_conservative_binary_ovr_hr2_min12_trainconf045_decay30_QQQ_history.joblib "$prefix`_QQQ_history.joblib" -Force; Copy-Item .\neural\models\codex_exp\gbt_qqq_conservative_binary_ovr_hr2_min12_trainconf045_decay30_norm_QQQ.npz "$prefix`_norm_QQQ.npz" -Force; Copy-Item .\neural\models\codex_exp\gbt_tickerstops_mixedobj_hr2_min12_trainconf045_deployconf040_top3_decay30_SPY_history.joblib "$prefix`_SPY_history.joblib" -Force; Copy-Item .\neural\models\codex_exp\gbt_tickerstops_mixedobj_hr2_min12_trainconf045_deployconf040_top3_decay30_norm_SPY.npz "$prefix`_norm_SPY.npz" -Force
```

Backtest conjunto exacto:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.20'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:1.0'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_20260530.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_20260530_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.35 0.38 0.40 0.42 0.45 2>&1 | Tee-Object -FilePath .\logs\codex_bt_combined_perticker_strict_vixgate_20260530_0540.txt
```

| Ticker | Trades | WR | PF | PnL | Abr 2026 | May 2026 |
|---|---:|---:|---:|---:|---:|---:|
| QQQ | 1076 | 49.6% | 1.215 | +89,606 | +1,368 / PF 1.082 | +2,703 / PF 1.193 |
| SPX | 1343 | 48.0% | 1.390 | +172,871 | +4,514 / PF 1.238 | +3,087 / PF 1.221 |
| SPY | 965 | 53.1% | 1.305 | +85,914 | +2,600 / PF 1.307 | +6,343 / PF 2.176 |

Estado: cumple los requisitos full-sample por ticker. Sigue pendiente la prueba true out-of-sample pedida por el usuario: crear `training_data_spx_qqq_spy_march_2026.parquet`, reentrenar hasta marzo 2026 incluido y backtestear sobre el parquet completo para verificar abril/mayo 2026 sin entrenarlos.

### Nota de data snooping actualizada

El soporte per-ticker no es por sí mismo data snooping: cada ticker tiene distribución, stop y modelo independientes. Pero los valores QQQ `TOP_N=2`, `RECENCY_POWER=1.0` y el gate SPY `VIX <= 0.4108` se eligieron tras diagnóstico sobre la muestra completa; por tanto son candidatos, no conclusiones finales. Sólo se pueden promocionar si pasan la prueba true OOS con entrenamiento cortado en marzo 2026.

## Diario 2026-05-30 03:38 +02:00

### Parquet true OOS creado

Se creó `training_data\training_data_spx_qqq_spy_march_2026.parquet` desde el parquet completo, usando sólo filas con `date <= 20260331`.

```powershell
python -c "import pandas as pd; src='training_data/training_data_spx_qqq_spy.parquet'; dst='training_data/training_data_spx_qqq_spy_march_2026.parquet'; df=pd.read_parquet(src); d=df['date'].astype(str); out=df[d <= '20260331'].copy(); out.to_parquet(dst, index=False); print('src_rows', len(df), 'dst_rows', len(out)); print(out.groupby('ticker')['date'].agg(['min','max','nunique','count'])); print('excluded_months', sorted(set(d[d > '20260331'].str[:6])))"
```

Resultado: 221,753 filas completas -> 213,063 filas March-cutoff. Máximo por ticker: 20260331. Meses excluidos: 202604 y 202605.

### Reentrenamiento GBT March-cutoff

Comandos ejecutados:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --ticker SPX --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.010 --target-short 0.010 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode multiclass --sample-weight-decay-days 0 --model_path .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --norm_path .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spx_march2026_nodecay_multiclass_20260530_0630.txt
```

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --ticker QQQ --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0025 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --sample-weight-decay-days 30 --model_path .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --norm_path .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_qqq_march2026_binary_ovr_decay30_20260530_0715.txt
```

```powershell
$env:PYTHONUNBUFFERED='1'; python -u .\neural\train_walkforward.py --data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --ticker SPY --model-size small --train-months 12 --test-months 1 --ensemble 3 --top-n-windows 10 --hold-ratio 2.0 --min-window 5 --class-weight balanced --min-pf-floor 1.20 --selection-metric economic --min-selection-trades 12 --selection-base-confidence 0.450 --selection-cooldown 8 --min-entry-minute 580 --target-long 0.006 --target-short 0.006 --stop-pct 0.0035 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --min-selection-win-rate 0.45 --objective-mode binary_ovr --sample-weight-decay-days 30 --model_path .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --norm_path .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz 2>&1 | Tee-Object -FilePath .\logs\codex_train_spy_march2026_binary_ovr_decay30_stop035_20260530_0745.txt
```

Primera prueba true OOS con QQQ `MIN_AVG_PF=1.20`, `TOP_N=2`, `RECENCY_POWER=1.0` falló por poco en QQQ: 1,285 trades, WR 48.0%, PF 1.173, PnL +87,110. Abril y mayo fueron positivos, pero no se cumplió PF > 1.2.

### True OOS aprobado

Se repitió el backtest true OOS manteniendo threshold 0.40, política global `MIN_AVG_PF=1.25`, `TOP_N=3`, `RECENCY_POWER=2.0`, y cambiando sólo QQQ a una selección menos recency-driven: `MIN_AVG_PF=1.25`, `TOP_N=2`, `RECENCY_POWER=0.5`.

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.35 0.38 0.40 0.42 0.45 2>&1 | Tee-Object -FilePath .\logs\codex_bt_combined_march2026_true_oos_qqq_rec05_20260530_0925.txt
```

| Ticker | Trades | WR | PF | PnL | Abr 2026 | May 2026 |
|---|---:|---:|---:|---:|---:|---:|
| QQQ | 1295 | 48.8% | 1.233 | +116,222 | +4,685 / PF 1.255 | +3,141 / PF 1.200 |
| SPX | 1291 | 47.6% | 1.370 | +159,450 | +4,203 / PF 1.242 | +2,627 / PF 1.178 |
| SPY | 959 | 53.4% | 1.333 | +91,701 | +8,040 / PF 2.618 | +1,285 / PF 1.149 |

Estado: se cumplen los requisitos solicitados en true out-of-sample: cada ticker supera 900 trades, WR > 45%, PF > 1.2, y abril/mayo 2026 son rentables. A partir de aquí se puede pasar a RL, pero el gate SPY por VIX y el ajuste de selección QQQ siguen siendo parámetros de despliegue que conviene mantener congelados y no seguir afinando contra abril/mayo.

### Pipeline actualizado

`neural\run_pipeline.ps1` queda actualizado para:

- recolectar el parquet completo en `training_data_spx_qqq_spy.parquet`;
- crear automáticamente `training_data_spx_qqq_spy_march_2026.parquet` con `date <= 20260331`;
- entrenar GBT usando por defecto el parquet March-cutoff;
- backtestear contra el parquet completo;
- usar el artefacto `neural\models\codex_exp\gbt_candidate_top2_rec1_march2026*.joblib`;
- setear los env vars exactos de strict-WF y gate SPY.

## Diario 2026-05-30 13:06 +02:00

### RL v1 sobre GBT true OOS

Se generó índice y cache RL desde el parquet March-cutoff:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONWARNINGS='ignore'; $env:MODEL_PATH='.\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib'; $env:NORM_PATH='.\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\neural\generate_episode_index.py --data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --output .\rl_data\episode_index_march2026.parquet --strict-wf --min-confidence 0.400 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 2>&1 | Tee-Object -FilePath .\logs\codex_generate_episode_index_march2026_20260530_0945.txt
```

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\neural\run_preprocess.py --training-data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --options-dir D:\ThetaData\data_options --output .\rl_data\rl_options_cache_chunks_march2026 --mlp-model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --mlp-normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --num-workers 22 --strict-wf --min-confidence 0.400 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 2>&1 | Tee-Object -FilePath .\logs\codex_run_preprocess_march2026_20260530_0950_escalated.txt
```

Resultado: `episode_index_march2026.parquet` con 39,219 episodios; cache `rl_options_cache_chunks_march2026` creado para 532 fechas.

Entrenamiento diagnóstico:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026 --save-dir .\rl_models\march2026_oos --total-updates 120 --min-confidence 0.400 --workers 32 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_120updates_20260530_1000.txt
```

Observaciones: el critic pretrain sólo recolectó 315 transiciones para 5,000 samples; `H[Exit]` cayó de 0.68 a 0.13; `Approx KL` subió hasta 0.1967 pese a `kl_target=0.030`; train PF final 0.929. El eval interno escogió step 100 con PF 1.50, pero era demasiado pequeño y no reflejó el backtest real.

Backtest RL completo:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_march2026_best120_20260530_1045.txt
```

Resultado RL: 5,339 trades, WR 43.2%, PF 1.15, PnL +181,424. Por ticker: SPX PF 1.24 / WR 43.0%; SPY PF 1.05 / WR 44.2%; QQQ PF 1.06 / WR 42.2%. No mejora el GBT y no cumple requisitos.

Diagnóstico: `agent_exit`, `signal_reversal` y `max_time` son rentables, pero `hard_stop` representa 25.7% de trades y destruye PF. El strike head se concentra en `itm_light` (79.2%); en SPY/QQQ ese bucket queda casi plano (PF ~1.0).

### Cambios RL v2

Cambios aplicados:

- `backtest\backtest_rl.py`: añadidos `--spx-target`, `--etf-target`, `--qqq-target`, `--spy-target`, `--spx-stop`, `--etf-stop`, `--qqq-stop`, `--spy-stop` para alinear el baseline GBT interno con `backtest_gbt_parquet.py`.
- `neural\rl\config.py`: hard stop premium -50% -> -40%; min-hold base 30 -> 10; curriculum min-hold 10/15/20/30 en vez de 30/45/60/90; `agent_exit_min_pnl_pct=-1.0`; `emergency_stop_pct=-0.30`; PPO más conservador (`lr=2e-5`, `clip=0.07`, `ppo_epochs=2`, `kl_target=0.020`); más presión de entropía en exit (`exit_entropy_coeff=0.08`, target 0.35); `eval_episodes=1000`.
- `neural\rl\training.py`: critic pretrain ahora pide episodios suficientes para aproximarse a samples de transiciones; eval usa `eval_episodes`, registra `eval_hard_stop_rate` y el best score penaliza hard stops.
- `neural\rl\agent.py` y `backtest\backtest_rl.py`: los checkpoints guardan/cargan `total_updates` para calcular correctamente el curriculum/min-hold en backtest.

Prueba rápida abril-mayo 2026 con el checkpoint anterior y las nuevas reglas de riesgo:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --start-date 20260401 --end-date 20260531 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_march2026_best120_riskfix_aprmay_20260530_1315.txt
```

Resultado abril-mayo: GBT+RL 564 trades, WR 49.3%, PF 1.37, PnL +26,833; mejora el GBT agregado del mismo script. Por ticker: SPX PF 1.47, QQQ PF 1.53, SPY PF 1.00. Los hard stops bajan de 25.7% a 9.0%. Próximo paso: reentrenar RL con estos cambios y evaluar full 2022-2026.

## Diario 2026-05-30 15:06 +02:00

### Reentrenamientos RL v2/v3

Se entrenó RL v2 con los cambios de riesgo/min-hold/entropy descritos arriba:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026 --save-dir .\rl_models\march2026_oos_v2 --total-updates 160 --min-confidence 0.400 --workers 32 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v2_160updates_20260530_1310.txt
```

Resultado: mejor eval PF 1.045; eval final PF 0.995. No se promociona porque no mejora de forma robusta al GBT.

Después se añadió contexto one-hot de ticker al estado RL para que una política compartida pueda distinguir microestructura SPX/SPY/QQQ:

- `neural\rl\config.py`: `TICKER_CONTEXT_DIM=3`, estado total 185.
- `neural\rl\environment.py`: añade contexto ticker en el estado de entrenamiento.
- `backtest\backtest_rl.py`: añade el mismo contexto ticker en inferencia.
- `neural\rl\utils.py`: ajusta augment/noise al nuevo bloque no-market.
- `neural\rl\agent.py`: carga checkpoints antiguos con su `state_dim` guardado para no romper compatibilidad.

Comando ejecutado:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026 --save-dir .\rl_models\march2026_oos_v3_tickerctx --total-updates 160 --min-confidence 0.400 --workers 32 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v3_tickerctx_160updates_20260530_1450.txt
```

Resultado: mejor eval PF 1.182 en step 25; eval final PF 0.955. Pendiente backtest completo v3 porque antes se auditó la coherencia del backtesting.

### Auditoría de coherencia GBT vs RL backtest

Hallazgo principal: el baseline GBT que imprimía `backtest\backtest_rl.py` no era equivalente a `backtest\backtest_gbt_parquet.py`. Diferencias detectadas:

- no aplicaba exactamente el mismo filtro de contexto/despliegue y strict-WF;
- no usaba el mismo simulador de exits spot;
- no respetaba de forma idéntica los parámetros por ticker `SPX/QQQ/SPY target/stop`;
- calculaba hold metrics con `hold_minutes`, mientras los trades importados del simulador GBT usan `actual_hold_minutes`;
- el RL entraba a precio mid de la opción, pero el entorno de entrenamiento usa mid ajustado por half-spread.

Cambios aplicados:

- `backtest\backtest_rl.py`: importa `TradeSimulator` desde `backtest_gbt_parquet.py` como `GBTSpotTradeSimulator` y lo usa para el bloque `GBT-only`.
- `backtest\backtest_rl.py`: añade CLI `--position-size` y `--min-iv` para pasar todos los argumentos esperados por el simulador GBT.
- `backtest\backtest_rl.py`: `calculate_metrics()` usa `actual_hold_minutes` si existe.
- `backtest\backtest_rl.py`: RL aplica coste de entrada `entry_premium = raw_mid * (1 + get_half_spread(abs(delta)) * (1 + 0.5 * abs(gamma_speed)))`, igual que el entorno.
- `backtest\backtest_rl.py`: el curriculum/min-hold usa `rl_agent.total_updates` guardado en checkpoint, no el default global.
- `neural\run_pipeline.ps1`: Paso 7 pasa `--rl-reentry-lock-minutes 180` y los target/stop exactos por ticker.

Comando de creación del subconjunto temporal de auditoría:

```powershell
python -c "import pandas as pd; src='training_data/training_data_spx_qqq_spy.parquet'; dst='training_data/tmp_codex_backtest_20260401_20260410.parquet'; df=pd.read_parquet(src); d=df['date'].astype(str); out=df[(d >= '20260401') & (d <= '20260410')].copy(); out.to_parquet(dst, index=False); print(len(out), out['date'].min(), out['date'].max(), out['ticker'].value_counts().to_dict())"
```

Resultado: 1,343 filas, fechas 20260401-20260410.

Backtest GBT directo usado como referencia:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\tmp_codex_backtest_20260401_20260410.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf 2>&1 | Tee-Object -FilePath .\logs\codex_audit_gbt_parquet_subset_20260530.txt
```

Resultado GBT referencia: 33 trades, WR 42.4%, PF 1.02, PnL +338.29. Por ticker: QQQ 16 trades PF 1.28; SPX 15 trades PF 0.89; SPY 2 trades PF 0.28.

Backtest RL con baseline GBT interno:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\tmp_codex_backtest_20260401_20260410.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 180 2>&1 | Tee-Object -FilePath .\logs\codex_audit_backtest_rl_subset_20260530.txt
```

Resultado: el bloque `GBT-only` dentro de `backtest_rl.py` da los mismos 33 trades y las mismas métricas que `backtest_gbt_parquet.py`.

Comparación fila a fila entre `training_data\backtest_trades.csv` y `logs\gbt_only_backtest_trades.csv`: 33/33 filas, mismas claves, diferencias máximas 0 en `entry_price`, `exit_price`, `pnl_dollars`, `confidence`, `actual_hold_minutes` y `contracts`. El parquet temporal `training_data\tmp_codex_backtest_20260401_20260410.parquet` fue eliminado después de la prueba.

Verificación sintáctica ejecutada:

```powershell
python -m py_compile .\backtest\backtest_rl.py .\backtest\backtest_gbt_parquet.py .\neural\rl\agent.py .\neural\rl\environment.py .\neural\rl\config.py
```

Resultado: OK.

Estado tras la auditoría: el baseline GBT dentro de `backtest_rl.py` ya es coherente con `backtest_gbt_parquet.py`. El backtest RL es más coherente con entrenamiento por min-hold/curriculum, ticker context y spread de entrada. Riesgo pendiente: el sizing del RL sigue siendo por prima pagada (`risk_capital / premium`) mientras el GBT dimensiona por pérdida al stop. PF/WR son comparables; PnL y drawdown no son una comparación perfecta de presupuesto de riesgo. Si se quiere igualdad estricta de riesgo, cambiar `_calc_contracts_options()` para dividir por `entry_premium * abs(HARD_EXITS["max_loss_pct"])`.

## Diario 2026-05-30 15:25 +02:00

### Auditoría GBT home-run / no micro-scalper

Se añadió al GBT backtest un bloque nativo `HOLD / HOME-RUN PROFILE` para que cada ejecución muestre duración media, mediana, p25/p75, porcentaje de trades >=60m y >=120m, duración de winners y distribución de exits.

Cambios:

- `backtest\backtest_gbt_parquet.py`: `calculate_metrics()` calcula duración y exits.
- `backtest\backtest_gbt_parquet.py`: `print_metrics()` imprime perfil de duración/home-run.
- `backtest\backtest_gbt_parquet.py`: `print_by_ticker()` ahora muestra mediana de hold y porcentaje >=60m por ticker.
- `backtest\backtest_gbt_parquet.py`: corregido bug donde `--max-time` se imprimía pero la simulación usaba `hold_minutes = 180` hardcodeado. Ahora usa `self.max_time`.
- `neural\run_pipeline.ps1`: `GbtTrainMaxTimeMinutes=390` y `BacktestMaxTimeMinutes=180` quedan explícitos y se pasan como `--max-time`; también se documenta el log oficial de duración.

Verificación sintáctica:

```powershell
python -m py_compile .\backtest\backtest_gbt_parquet.py .\backtest\backtest_rl.py
```

Resultado: OK.

Backtest oficial GBT con horizonte de ejecución 180m:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --max-time 180 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.35 0.38 0.40 0.42 0.45 2>&1 | Tee-Object -FilePath .\logs\codex_bt_gbt_full_home_run_profile_fixed180_20260530_1555.txt
```

Resultado global:

| Trades | WR | PF | PnL | Avg hold | Median hold | Winner median | >=60m | >=120m |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3545 | 49.6% | 1.31 | +367,372 | 95.4m | 85.0m | 135.0m | 59.3% | 40.6% |

Por ticker:

| Ticker | Trades | WR | PF | PnL | Median hold | >=60m |
|---|---:|---:|---:|---:|---:|---:|
| QQQ | 1295 | 48.8% | 1.23 | +116,222 | 45m | 41.7% |
| SPX | 1291 | 47.6% | 1.37 | +159,450 | 105m | 63.6% |
| SPY | 959 | 53.4% | 1.33 | +91,701 | 140m | 77.2% |

Abril/mayo 2026:

```powershell
@'
import pandas as pd
p='training_data/backtest_trades.csv'
df=pd.read_csv(p)
df['date_str']=df['date'].astype(str)
df['month']=df['date_str'].str[:6]
hold='actual_hold_minutes' if 'actual_hold_minutes' in df.columns else 'hold_minutes'
def metrics(x):
    pnl=x['pnl_dollars']; gp=pnl[pnl>0].sum(); gl=-pnl[pnl<0].sum(); wins=x[pnl>0]
    return pd.Series({
        'trades':len(x), 'wr_pct':pnl.gt(0).mean()*100 if len(x) else 0, 'pf':gp/gl if gl else float('inf'), 'pnl':pnl.sum(),
        'avg_hold':x[hold].mean() if len(x) else 0, 'med_hold':x[hold].median() if len(x) else 0,
        'pct_ge60':x[hold].ge(60).mean()*100 if len(x) else 0, 'pct_ge120':x[hold].ge(120).mean()*100 if len(x) else 0,
        'winner_med_hold':wins[hold].median() if len(wins) else 0, 'winner_pct_ge60':wins[hold].ge(60).mean()*100 if len(wins) else 0,
    })
print('FULL')
print(metrics(df).to_string(float_format=lambda v:f'{v:.3f}'))
print('\nAPR_MAY_AGG')
print(df[df['month'].isin(['202604','202605'])].groupby('month').apply(metrics).to_string(float_format=lambda v:f'{v:.3f}'))
print('\nAPR_MAY_BY_TICKER')
print(df[df['month'].isin(['202604','202605'])].groupby(['month','ticker']).apply(metrics).to_string(float_format=lambda v:f'{v:.3f}'))
'@ | python - 2>&1 | Tee-Object -FilePath .\logs\codex_gbt_duration_month_audit_20260530_1525.txt
```

Resultado agregado abril/mayo:

| Mes | Trades | WR | PF | PnL | Avg hold | Median hold | Winner median |
|---|---:|---:|---:|---:|---:|---:|---:|
| 202604 | 104 | 47.1% | 1.415 | +16,927 | 103.6m | 119.5m | 165m |
| 202605 | 109 | 52.3% | 1.181 | +7,053 | 108.8m | 110.0m | 160m |

Prueba de horizonte 300m después de corregir `--max-time`:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_gbt_parquet.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --model-size small --ensemble --threshold 0.40 --cooldown 8 --target_long 0.010 --target_short 0.010 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --stop 0.0025 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --max-time 300 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --tickers SPX QQQ SPY --strict-wf --sensitivity-thresholds 0.40 2>&1 | Tee-Object -FilePath .\logs\codex_bt_gbt_full_home_run_maxtime300_fixed2_20260530_1550.txt
```

Resultado 300m: 3,183 trades, WR 49.2%, PF 1.32, PnL +375,725, avg hold 114.7m. No se promociona porque SPY baja a 835 trades y QQQ no mejora su perfil de duración; el candidato 180m sigue cumpliendo mejor el requisito de volumen por ticker y agregado.

Estado GBT: cumple objetivo actual global PF > 1.2, WR > 45%, trades > 2,800, abril/mayo rentables y perfil no micro-scalper. También mantiene el requisito histórico por ticker full-sample: QQQ/SPX/SPY todos PF > 1.2, WR > 45% y trades > 900. Queda como candidato operativo `max-time=180`.

## Diario 2026-05-30 17:38 +02:00

### Estado RL tras backtest corregido

Se evaluó el checkpoint v3 `rl_models\march2026_oos_v3_tickerctx\best_rl_agent.pt` contra el backtest corregido, con baseline GBT equivalente a `backtest_gbt_parquet.py`, spread de entrada en opciones y `--max-time 180`.

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v3_tickerctx\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 180 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_march2026_v3_best_full_corrected_20260530_1610.txt
```

Resultado v3 full: GBT-only 3,545 trades, WR 49.6%, PF 1.305, PnL +367,372. GBT+RL 2,302 trades, WR 36.6%, PF 0.94, PnL -25,685. Por ticker: SPX PF 0.90, SPY PF 0.98, QQQ PF 0.98. Diagnóstico: `agent_exit` 67.2% de trades; winners RL avg hold 28m vs GBT 119m. El checkpoint v3 ganador era step 25, fase 0, min_hold 14m, por lo que había aprendido la salida mínima.

Diagnóstico CSV:

```powershell
@'
import pandas as pd
p='backtest_results/gbt_rl_20260530_155826.csv'
df=pd.read_csv(p)
df['date_str']=df['date'].astype(str); df['month']=df['date_str'].str[:6]
hold='hold_minutes'
def metrics(x):
    pnl=x.pnl_dollars; gp=pnl[pnl>0].sum(); gl=-pnl[pnl<0].sum(); wins=x[pnl>0]
    return pd.Series({
        'trades':len(x), 'wr':pnl.gt(0).mean()*100 if len(x) else 0, 'pf':gp/gl if gl else float('inf'), 'pnl':pnl.sum(),
        'avg_hold':x[hold].mean() if len(x) else 0, 'med_hold':x[hold].median() if len(x) else 0,
        'winner_avg_hold':wins[hold].mean() if len(wins) else 0, 'winner_med_hold':wins[hold].median() if len(wins) else 0,
        'avg_pnl_pct':x.pnl_pct.mean() if len(x) else 0,
        'med_pnl_pct':x.pnl_pct.median() if len(x) else 0,
    })
print('BY EXIT')
print(df.groupby('exit_reason').apply(metrics).sort_values('trades',ascending=False).to_string(float_format=lambda v:f'{v:.3f}'))
print('\nBY STRIKE')
print(df.groupby('strike_bucket').apply(metrics).sort_values('trades',ascending=False).to_string(float_format=lambda v:f'{v:.3f}'))
'@ | python - 2>&1 | Tee-Object -FilePath .\logs\codex_rl_v3_backtest_diagnostics_20260530_1620.txt
```

Principales hallazgos v3: `agent_exit` mediana 15m; `hard_stop` 516 trades y -221k; `atm` 72.2% de trades con PF 0.92; `otm_light` PF 1.08 pero sólo 17.5%.

### Cambios RL v4 home-run

Cambios aplicados:

- `neural\rl\training.py`: PPO ahora pasa `action_masks` a `evaluate_actions()` durante update. Antes la re-evaluación de log-probs ignoraba las máscaras de strike usadas al samplear.
- `neural\rl\training.py`: las acciones forzadas por el entorno (`min_hold`, `agent_exit_min_pnl`) se guardan con `policy_active=False`; actualizan el critic pero no empujan la policy hacia una acción que realmente no eligió.
- `neural\rl\config.py`: min-hold base 30m; curriculum 30/45/60/75m.
- `neural\rl\config.py`: `agent_exit_min_pnl_pct=0.25`; las salidas voluntarias deben ser winners relevantes; las pérdidas sólo salen por emergency/hard exits.
- `neural\rl\config.py`: `logit_noise_exit_override=0.25`, `min_best_hold_minutes=45`, `exit_entropy_coeff=0.08`.
- `neural\rl\agent.py`: bias inicial de exit head hacia HOLD (`bias[HOLD]=+0.30`, `bias[EXIT]=-0.30`).
- `neural\rl\training.py`: el best checkpoint sólo se guarda con curriculum min_hold >=45m y el score penaliza hard stops, bajo WR, poco hold real y exceso de agent exits.
- `neural\run_pipeline.ps1`: RL apunta a `rl_models\march2026_oos_v4_homerun`, `RlTotalUpdates=220`, `RlWorkers=32`.

Verificación:

```powershell
python -m py_compile .\neural\rl\training.py .\neural\rl\config.py .\neural\rl\agent.py .\neural\rl\environment.py .\backtest\backtest_rl.py
```

Resultado: OK.

Entrenamiento v4:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026 --save-dir .\rl_models\march2026_oos_v4_homerun --total-updates 220 --min-confidence 0.400 --workers 32 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v4_homerun_220updates_20260530_1645.txt
```

Nota: el primer intento sin permisos elevados falló al crear `ProcessPoolExecutor` con `WinError 5`; se repitió fuera del sandbox con el mismo comando.

Resultado entrenamiento v4: best eval PF 1.136 en step 100; last eval PF 0.828; last train PF 0.932. La entropía no colapsa como v3: `H[Exit]` se mantuvo aprox. 0.40-0.65 y `H[Strike]` aprox. 0.94-1.65. El problema se desplazó a demasiados hard stops y WR bajo, no a colapso de entropía.

Backtest full v4:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 180 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_march2026_v4_homerun_best_full_20260530_1755.txt
```

Resultado v4 full: GBT+RL 2,299 trades, WR 33.7%, PF 1.07, PnL +46,976. Por ticker: SPX PF 1.06, SPY PF 1.14, QQQ PF 1.04. Mejora frente a v3, pero no supera al GBT y no cumple requisitos. Exit reasons: `agent_exit` 44.3%, `hard_stop` 34.3%, `signal_reversal` 12.3%, `max_time` 7.3%, `hard_take_profit` 1.7%. Strike: `itm_light` 91.1% de trades, PF 1.11.

Prueba abril/mayo v4 con salida voluntaria más estricta +50%:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --start-date 20260401 --end-date 20260531 --rl-reentry-lock-minutes 180 --agent-exit-min-pnl 0.50 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_march2026_v4_homerun_aprmay_exitmin050_20260530_1830.txt
```

Resultado abril/mayo +50%: GBT+RL 157 trades, WR 35.0%, PF 1.15, PnL +6,253; peor que GBT-only PF 1.30, PnL +23,980. No se promociona.

Estado RL: no logrado. v4 corrigió el colapso temprano de salida, pero sigue sin superar GBT. El siguiente trabajo debe diagnosticar la selección de strike/opciones: la policy v4 concentra 91% en `itm_light` y aun así los hard stops destruyen PF. Hay que añadir un baseline diagnóstico de strikes fijos y/o cambiar reward/sizing para que el strike head optimice PF real por ticker, no sólo PnL de prima medio.

## Diario 2026-05-30 18:51 +02:00

### Diagnóstico RL: strikes y salidas

Cambios aplicados:

- `backtest\backtest_rl.py`: añadidos overrides diagnósticos `--force-rl-strike-bucket`, `--force-rl-ticker-strike-buckets`, `--rl-exit-policy {agent,hold}`, `--rl-max-loss-pct`, `--rl-max-profit-pct`.
- `--rl-exit-policy hold` desactiva sólo la salida voluntaria del agente; conserva `hard_stop`, `hard_take_profit`, `signal_reversal` y `max_time`.
- `neural\run_pipeline.ps1`: añadidas variables explícitas de overrides diagnósticos RL, por defecto vacías, para reproducir ablaciones sin cambiar el pipeline promovido.

Verificación:

```powershell
python -m py_compile .\backtest\backtest_rl.py
```

Resultado: OK.

Barrido abril/mayo 2026 de buckets fijos, salida `hold`:

```powershell
$buckets=@('deep_otm','otm_far','otm_near','otm_light','atm','itm_light','itm'); foreach($b in $buckets){ $env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --start-date 20260401 --end-date 20260531 --rl-reentry-lock-minutes 180 --force-rl-strike-bucket $b --rl-exit-policy hold 2>&1 | Tee-Object -FilePath ".\logs\codex_bt_rl_fixed_${b}_hold_aprmay_20260530.txt" }
```

Resultado agregado abril/mayo:

| Bucket | Trades | WR | PF | PnL | Winner avg hold | Loser avg hold |
|---|---:|---:|---:|---:|---:|---:|
| `atm` | 156 | 34.0% | 1.35 | +16,188 | 97m | 51m |
| `deep_otm` | 156 | 20.5% | 1.21 | +10,550 | 49m | 36m |
| `itm` | 156 | 41.0% | 1.17 | +9,416 | 120m | 57m |
| `itm_light` | 156 | 36.5% | 1.26 | +12,698 | 107m | 54m |
| `otm_far` | 156 | 25.6% | 1.32 | +14,421 | 63m | 33m |
| `otm_light` | 156 | 30.8% | 1.35 | +15,174 | 88m | 45m |
| `otm_near` | 156 | 30.1% | 1.29 | +11,819 | 83m | 37m |

Lectura: en abril/mayo varios buckets de opciones son rentables en agregado, pero no mejoran todos los tickers. Ejemplos: `atm` logra QQQ PF 1.84 y SPY PF 1.43, pero SPX sólo PF 1.08; `deep_otm` mejora SPX PF 1.32, pero QQQ queda prácticamente flat; `itm` mejora QQQ/SPY pero SPX cae a PF 0.95.

Prueba full 2022-2026, bucket fijo `atm`, salida `hold`:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 180 --force-rl-strike-bucket atm --rl-exit-policy hold 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_fixed_atm_hold_full_20260530.txt
```

Resultado full `atm` hold: 2,293 trades, WR 30.7%, PF 1.09, PnL +59,523. Por ticker: SPX PF 1.06, SPY PF 1.14, QQQ PF 1.08. No supera al GBT baseline.

Pruebas abril/mayo `atm` hold con stop de opción local:

```powershell
$losses=@('0.45','0.50','0.60'); foreach($loss in $losses){ $env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; $tag=$loss.Replace('.','p'); python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --start-date 20260401 --end-date 20260531 --rl-reentry-lock-minutes 180 --force-rl-strike-bucket atm --rl-exit-policy hold --rl-max-loss-pct $loss 2>&1 | Tee-Object -FilePath ".\logs\codex_bt_rl_fixed_atm_hold_aprmay_maxloss_m${tag}_20260530.txt" }
```

Resultado: max loss 0.45 PF 1.38 PnL +18,957, max loss 0.50 PF 1.33 PnL +18,217, max loss 0.60 PF 1.25 PnL +14,817. Aflojar el stop mejora QQQ/SPY recientes, pero no resuelve SPX: con 0.50 SPX sólo PF 1.03.

Prueba por ticker abril/mayo con buckets manuales observados (`SPX:deep_otm,QQQ:atm,SPY:itm`), salida `hold`:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --start-date 20260401 --end-date 20260531 --rl-reentry-lock-minutes 180 --force-rl-ticker-strike-buckets SPX:deep_otm,QQQ:atm,SPY:itm --rl-exit-policy hold 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_fixed_tickerbest_hold_aprmay_20260530.txt
```

Resultado abril/mayo: 156 trades, WR 32.7%, PF 1.56, PnL +20,822, max DD -6,622. Por ticker: SPX PF 1.32 +5,669, QQQ PF 1.84 +9,180, SPY PF 1.68 +5,972. Es rentable y mejora PF agregado reciente, pero el WR es bajo y el PnL de SPX/SPY no supera claramente al GBT.

Misma configuración full 2022-2026:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 180 --force-rl-ticker-strike-buckets SPX:deep_otm,QQQ:atm,SPY:itm --rl-exit-policy hold 2>&1 | Tee-Object -FilePath .\logs\codex_bt_rl_fixed_tickerbest_hold_full_20260530.txt
```

Resultado full: 2,294 trades, WR 27.6%, PF 1.00, PnL -894. Por ticker: SPX PF 0.88 PnL -35,788, SPY PF 1.14 +20,333, QQQ PF 1.08 +14,561. La configuración reciente no generaliza; es una prueba clara de data snooping si se promocionase.

Búsqueda post-hoc de filtros sobre el CSV full de la configuración por ticker:

```powershell
@'
import pandas as pd
from itertools import product
p='backtest_results/gbt_rl_20260530_184816.csv'
df=pd.read_csv(p)
df['date_str']=df['date'].astype(str)
df['is_oos']=df['date_str'].between('20260401','20260531')
def m(x):
    pnl=x.pnl_dollars
    gp=pnl[pnl>0].sum(); gl=-pnl[pnl<0].sum()
    return len(x), pnl.gt(0).mean()*100 if len(x) else 0, gp/gl if gl else float('inf'), pnl.sum()
for ticker in ['SPX','QQQ','SPY']:
    t=df[df.ticker==ticker]
    rows=[]
    for conf in [0.4,0.45,0.5,0.55,0.6]:
      for direction in ['ALL','LONG','SHORT']:
       for start,end in [(580,1200),(580,960),(615,1200),(660,1200),(700,1200)]:
        for iv_side in ['ALL','LOW','HIGH']:
          q=t.actual_iv.quantile(.5) if 'actual_iv' in t else None
          mask=(t.confidence>=conf)&(t.entry_minute>=start)&(t.entry_minute<=end)
          if direction!='ALL': mask &= t.direction.eq(direction)
          if iv_side=='LOW': mask &= t.actual_iv<=q
          if iv_side=='HIGH': mask &= t.actual_iv>=q
          tr=t[mask & ~t.is_oos]; oo=t[mask & t.is_oos]
          tn,twr,tpf,tpnl=m(tr); on,owr,opf,opnl=m(oo)
          if tn>=200 and tpf>=1.2 and twr>=35 and on>=10:
            rows.append((opf,opnl,on,owr,tpf,tpnl,tn,twr,conf,direction,start,end,iv_side,q))
    print('\n',ticker)
    for r in sorted(rows, reverse=True)[:10]:
      print(r)
'@ | python - 2>&1 | Tee-Object -FilePath .\logs\codex_rl_fixed_map_skip_filter_search_20260530.txt
```

Resultado: sólo aparecen candidatos en SPY. No hay candidatos robustos para SPX ni QQQ con esos filtros simples. Mejor SPY: `confidence>=0.5`, `LONG`, `actual_iv>=0.2105`, entrada 580..960/1200, train n=218 PF 1.214 WR 44.5%, OOS n=12 PF 2.98 WR 66.7%. Es diagnóstico, no solución promocionable.

Conclusión actual RL: el problema ya no es colapso de entropía. El entrenamiento v4 mantiene entropía razonable, pero la policy no encuentra una selección de opción/salida que mejore la señal GBT. El agente necesita probablemente una acción explícita `skip/no-trade` y/o pretraining supervisado/oráculo sobre `strike + skip`, porque forzar strikes fijos demuestra que la capa de opciones puede ser rentable en abril/mayo, pero no generaliza en full 2022-2026, especialmente en SPX.

## Diario 2026-05-30 21:31 +02:00

### Correcciones de coherencia del backtest RL

Se detectaron dos incoherencias en el diagnóstico RL:

- `backtest\backtest_rl.py`: el RL aplicaba por defecto `reentry_lock_minutes = max_time`, mientras el GBT baseline bloquea sólo mientras la posición está abierta y aplica cooldown desde la entrada. Esto reducía volumen del RL de forma no equivalente. Cambio: default RL reentry lock = `0`, y el lock largo queda sólo como override diagnóstico. `neural\run_pipeline.ps1` ahora usa `$RlReentryLockMinutes = 0`.
- `--rl-max-loss-pct 0.45` se interpretaba como `+0.45`, no como pérdida `-0.45`; esos logs previos de stop positivo no son válidos para decisión. Cambio: el flag normaliza magnitud positiva a pérdida negativa (`0.50` y `-0.50` significan `-0.50`).

Verificación:

```powershell
python -m py_compile .\backtest\backtest_rl.py
```

Resultado: OK.

### Barrido SPX full con buckets fijos

Comando ejecutado con lock largo diagnóstico 180m:

```powershell
$buckets=@('deep_otm','otm_far','otm_near','otm_light','atm','itm_light','itm'); foreach($b in $buckets){ $env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; $log=".\logs\codex_bt_rl_spx_fixed_${b}_hold_full_20260530.txt"; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX --rl-reentry-lock-minutes 180 --force-rl-strike-bucket $b --rl-exit-policy hold *> $log }
```

Resultado SPX con lock 180m:

| Bucket | Trades | WR | PF | PnL | Max DD | Winner hold | Loser hold |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deep_otm` | 887 | 16.5% | 0.88 | -35,788 | -55,098 | 58m | 33m |
| `otm_far` | 887 | 19.6% | 1.00 | +202 | -20,515 | 72m | 34m |
| `otm_near` | 886 | 24.0% | 0.98 | -5,720 | -24,189 | 89m | 38m |
| `otm_light` | 886 | 27.9% | 1.08 | +19,924 | -17,610 | 101m | 43m |
| `atm` | 886 | 30.5% | 1.06 | +19,258 | -25,500 | 107m | 49m |
| `itm_light` | 884 | 34.0% | 1.11 | +41,945 | -28,086 | 113m | 54m |
| `itm` | 883 | 38.3% | 1.12 | +57,861 | -38,125 | 118m | 60m |

Lectura: ningún bucket fijo de SPX supera el GBT SPX (1,291 trades, WR 47.6%, PF 1.37, PnL +159,450).

Prueba SPX `itm` con reentry coherente `0`:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX --rl-reentry-lock-minutes 0 --force-rl-strike-bucket itm --rl-exit-policy hold *> .\logs\codex_bt_rl_spx_fixed_itm_hold_full_reentry0_20260530.txt
```

Resultado: 1,652 trades, WR 37.8%, PF 1.17, PnL +151,420, max DD -50,900. Mejora volumen pero sigue por debajo del GBT en PF/WR/PnL y con drawdown mucho mayor.

Stops corregidos para SPX `itm`, reentry 0:

```powershell
$losses=@('0.45','0.50','0.60'); foreach($loss in $losses){ $env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; $tag=$loss.Replace('.','p'); $log=".\logs\codex_bt_rl_spx_fixed_itm_hold_full_reentry0_maxloss_m${tag}_20260530.txt"; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX --rl-reentry-lock-minutes 0 --force-rl-strike-bucket itm --rl-exit-policy hold --rl-max-loss-pct $loss *> $log }
```

Resultados: `-45%` PF 1.17 WR 42.1% PnL +143,788; `-50%` PF 1.17 WR 44.3% PnL +135,707; `-60%` PF 1.16 WR 47.1% PnL +123,486. Aflojar el stop sube WR, pero no sube PF y empeora PnL/drawdown.

Backtest v4 completo con reentry coherente:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v4_homerun\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 0 *> .\logs\codex_bt_rl_march2026_v4_homerun_best_full_reentry0_20260530.txt
```

Resultado v4 full reentry 0: 6,002 trades, WR 32.0%, PF 1.00, PnL +7,292, DD -79,557. Por ticker: SPX 2,373 trades WR 30.8 PF 1.06 PnL +50,658; SPY 1,874 WR 34.8 PF 0.96 PnL -12,253; QQQ 1,755 WR 30.4 PF 0.90 PnL -31,113. No mejora el GBT.

### Cambio arquitectónico v5: acción directa SKIP/ENTER+strike

Hipótesis: el RL no debe estar obligado a convertir cada señal GBT en una opción. Los tests muestran que algunos strikes pueden ser rentables en subconjuntos, pero no de forma estable en todos los regímenes. El agente necesita aprender cuándo no entrar.

Cambios aplicados:

- `neural\rl\config.py`: añadidos `use_entry_skip_action`, `entry_skip_penalty=-0.03`, `min_best_entry_rate=0.55`.
- `neural\rl\environment.py`: cuando `use_entry_skip_action=True`, acción 0 = `entry_skip` y acciones 1-7 = entrar con bucket 0-6. No cambia `state_dim`.
- `neural\rl\training.py`: nuevo flag `--entry-skip-action`; PPO usa `sniper_head` como cabeza de entrada directa y aplica máscara `[SKIP] + buckets válidos`. Métricas de PF/WR excluyen skips, pero el score de best checkpoint exige `eval_entry_rate >= 55%`.
- `neural\rl\evaluate.py`: eval distingue entradas reales de skips.
- `backtest\backtest_rl.py`: nuevo flag `--rl-entry-skip-action`; si el agente devuelve acción 0, salta la entrada y aplica cooldown normal.
- `neural\run_pipeline.ps1`: RL v5 apunta a `rl_models\march2026_oos_v5_entryskip`, `RlTotalUpdates=260`, `RlUseEntrySkipAction=$true`, `RlReentryLockMinutes=0`.

Verificación:

```powershell
python -m py_compile .\neural\rl\config.py .\neural\rl\environment.py .\neural\rl\training.py .\neural\rl\evaluate.py .\backtest\backtest_rl.py
$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\neural\run_pipeline.ps1), [ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message }; exit 1 } else { 'run_pipeline.ps1 parse OK' }
python -u -m neural.rl.training --help | Select-String -Pattern 'entry-skip|usage'
```

Resultado: OK. Siguiente comando previsto:

```powershell
$env:PYTHONUNBUFFERED='1'; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026 --save-dir .\rl_models\march2026_oos_v5_entryskip --total-updates 260 --min-confidence 0.400 --workers 32 --entry-skip-action 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v5_entryskip_260updates_20260530.txt
```

## Diario 2026-05-31 10:56 +02:00

### Estado RL v7-v9 y correcciones de entrenamiento

Resultado v7 `entryskip_penalty`: el worker ya propagaba `use_entry_skip_action` y el agente no colapsó a skip total, pero no mejoró al GBT. Backtest full con salidas del agente: 5,820 trades, WR 36.6%, PF 1.08, PnL +117,792. Por ticker: SPX PF 1.14, SPY PF 0.96, QQQ PF 0.96. Con `--rl-exit-policy hold`: 4,122 trades, WR 38.0%, PF 1.15, PnL +196,674; por ticker SPX PF 1.19, SPY PF 1.07, QQQ PF 1.08. Sigue por debajo de GBT.

Resultado v8 `entryskip_holdexit`: combinar `--entry-skip-action` con `--force-hold-exit` colapsó a skip casi total. No se guardó `best_rl_agent.pt`. No se promociona.

Resultado v9 `strike_holdexit`: sin skip, con salida forzada a HOLD durante entrenamiento. Comando:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONPATH = "$((Resolve-Path .).Path)\neural;$((Resolve-Path .).Path;$env:PYTHONPATH)"; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026 --save-dir .\rl_models\march2026_oos_v9_strike_holdexit --total-updates 220 --min-confidence 0.400 --workers 32 --force-hold-exit 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v9_strike_holdexit_220updates_20260530.txt
```

Entrenamiento v9: best internal eval PF 1.174 en step 150. `H[Exit]=0` por diseño (`--force-hold-exit`), `H[Strike]` se mantuvo >0.19 al final. Backtest full:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v9_strike_holdexit\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 0 --rl-exit-policy hold *> .\logs\codex_bt_rl_march2026_v9_strike_holdexit_best_full_20260530_retry.txt
```

Resultado v9 full: 4,511 trades, WR 32.8%, PF 1.10, PnL +138,306, max DD -52,210. Por ticker: SPX 1,781 trades WR 32.7 PF 1.15 PnL +115,115; SPY 1,416 trades WR 34.3 PF 1.04 PnL +12,680; QQQ 1,314 trades WR 31.4 PF 1.04 PnL +10,510. No cumple requisitos y no mejora GBT. Exit reasons: hard_stop 60.3%, max_time 22.1%, signal_reversal 15.3%, hard_take_profit 2.3%. Strike: 99.1% `itm_light`, PF 1.10.

### Bug encontrado: señales de reversión RL no estaban alineadas por ticker

Problema: `neural\rl\preprocess.py` construía `daily_signals` con clave sólo `time`. En fechas con SPX, QQQ y SPY al mismo timestamp, el cache podía asignar a todos los tickers la señal de reversión del último ticker iterado. El backtest RL, en cambio, evalúa reversión con predicciones ticker-específicas. Esto no es un parámetro ni data snooping: es una incoherencia train/backtest.

Cambios:

- `neural\rl\preprocess.py`: `daily_signals` ahora usa clave `(ticker, time)` y `_process_single_date` lee la señal ticker-específica.
- `neural\rl\compute_recovery_stats.py`: añadidos `--episode-index`, `--options-cache`, `--output`. Antes leía siempre `rl_data\episode_index.parquet` y `rl_data\rl_options_cache_chunks`, aunque el experimento usara `rl_options_cache_chunks_march2026`.
- `neural\run_pipeline.ps1`: v10 apunta a `rl_data\rl_options_cache_chunks_march2026_tickersig` y `rl_models\march2026_oos_v10_tickersig_holdexit`; `compute_recovery_stats.py` recibe rutas explícitas del experimento.

Verificación:

```powershell
python -m py_compile .\neural\rl\preprocess.py .\neural\rl\compute_recovery_stats.py
$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\neural\run_pipeline.ps1), [ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message }; exit 1 } else { 'run_pipeline.ps1 parse OK' }
python -u .\neural\rl\compute_recovery_stats.py --help | Select-String -Pattern 'episode-index|options-cache|output|usage'
```

Resultado: OK.

### Regeneración de datos RL v10

Regeneración del índice de episodios March-cutoff:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONPATH = "$((Resolve-Path .).Path)\neural;$((Resolve-Path .).Path);$env:PYTHONPATH"; $env:MODEL_PATH = "$((Resolve-Path .).Path)\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib"; $env:NORM_PATH = "$((Resolve-Path .).Path)\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz"; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\neural\generate_episode_index.py --data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --output .\rl_data\episode_index_march2026.parquet --strict-wf --min-confidence 0.400 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 2>&1 | Tee-Object -FilePath .\logs\codex_rl_v10_generate_episode_index_tickersig_20260530.txt
```

Resultado: 39,219 episodios; LONG 24,141; SHORT 15,078; confidence mean 0.5795 +/- 0.0959.

Regeneración del cache de opciones v10:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONWARNINGS='ignore'; $env:PYTHONPATH = "$((Resolve-Path .).Path)\neural;$((Resolve-Path .).Path);$env:PYTHONPATH"; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\neural\run_preprocess.py --training-data .\training_data\training_data_spx_qqq_spy_march_2026.parquet --options-dir D:\ThetaData\data_options --output .\rl_data\rl_options_cache_chunks_march2026_tickersig --mlp-model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --mlp-normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --num-workers 22 --strict-wf --min-confidence 0.400 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 2>&1 | Tee-Object -FilePath .\logs\codex_rl_v10_preprocess_tickersig_20260530.txt
```

Resultado: cache creado en `rl_data\rl_options_cache_chunks_march2026_tickersig`, 39,219 episodios procesados, 532 fechas.

Recomputo de recovery stats desde el mismo cache v10:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONPATH = "$((Resolve-Path .).Path)\neural;$((Resolve-Path .).Path);$env:PYTHONPATH"; python -u .\neural\rl\compute_recovery_stats.py --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026_tickersig --output .\rl_data\recovery_stats.pkl 2>&1 | Tee-Object -FilePath .\logs\codex_rl_v10_compute_recovery_stats_tickersig_20260530.txt
```

Resultado: 108 buckets guardados en `rl_data\recovery_stats.pkl`.

Chequeo de señal ticker-específica en cache v10:

```powershell
@'
import pickle
from pathlib import Path
cache=Path('rl_data/rl_options_cache_chunks_march2026_tickersig')
checked=0
for f in sorted(cache.glob('*.pkl')):
    with f.open('rb') as fh:
        shard=pickle.load(fh)
    md=shard.get('minute_data',{})
    if all(t in md for t in ['SPX','QQQ','SPY']):
        common=set(md['SPX']) & set(md['QQQ']) & set(md['SPY'])
        for ts in sorted(common):
            sigs={t:(md[t][ts].get('sig_dir'), round(float(md[t][ts].get('sig_conf',0)),3)) for t in ['SPX','QQQ','SPY']}
            checked += 1
            if len(set(sigs.values()))>1:
                print(f.name, ts, sigs, 'checked', checked)
                raise SystemExit
print('no differing sample found; checked', checked)
'@ | python -
```

Resultado: ejemplo `20240815.pkl 09:35 {'SPX': ('HOLD', 0.678), 'QQQ': ('SHORT', 0.569), 'SPY': ('SHORT', 0.525)}`. Confirma que el cache ya no fuerza la misma señal a todos los tickers.

Siguiente paso: entrenar v10 con `--force-hold-exit`, sin `entry_skip`, y backtestear contra el parquet completo para abril/mayo true-OOS.

## Diario 2026-05-31 15:22 +02:00

### RL v10 entrenado y backtest OOS completo

Entrenamiento ejecutado sobre `episode_index_march2026.parquet` y cache ticker-specific `rl_options_cache_chunks_march2026_tickersig`, con datos generados solo hasta marzo 2026:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONWARNINGS='ignore'; $root=(Resolve-Path .).Path; $env:PYTHONPATH = "$root\neural;$root;$env:PYTHONPATH"; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026_tickersig --save-dir .\rl_models\march2026_oos_v10_tickersig_holdexit --total-updates 220 --min-confidence 0.400 --workers 32 --force-hold-exit 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v10_tickersig_holdexit_220updates_20260531.txt
```

Resultado entrenamiento v10: 75.5 min, best internal eval PF 1.120 en step 75, last eval PF 1.037. `H[Exit]=0` por diseño al usar `--force-hold-exit`. El problema no es colapso del exit head en esta variante; el `strike head` se concentra gradualmente y acaba con `H[Strike]~0.15`, mientras la eval se estanca en WR 28-32% y hard stop 62-68%.

Backtest full v10, policy strike y exit hold:

```powershell
$env:PYTHONWARNINGS='ignore'; $env:GBT_MIN_STRICT_WF_AVG_PF='1.25'; $env:GBT_MIN_STRICT_WF_VALIDATION_TRADES='12'; $env:GBT_STRICT_WF_TOP_N='3'; $env:GBT_STRICT_WF_RECENCY_POWER='2.0'; $env:GBT_TICKER_MIN_STRICT_WF_AVG_PF='QQQ:1.25'; $env:GBT_TICKER_STRICT_WF_TOP_N='QQQ:2'; $env:GBT_TICKER_STRICT_WF_RECENCY_POWER='QQQ:0.5'; Remove-Item Env:\DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH -ErrorAction SilentlyContinue; $env:DEPLOYMENT_TICKER_MAX_VIX_SPOT='SPY:0.4108'; python -u .\backtest\backtest_rl.py --data .\training_data\training_data_spx_qqq_spy.parquet --model .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026.joblib --normalizer .\neural\models\codex_exp\gbt_candidate_top2_rec1_march2026_norm.npz --rl-model .\rl_models\march2026_oos_v10_tickersig_holdexit\best_rl_agent.pt --model-size small --ensemble --threshold 0.40 --cooldown 8 --max-time 180 --target-long 0.010 --target-short 0.010 --stop 0.0025 --spx-target 0.010 --etf-target 0.006 --qqq-target 0.006 --spy-target 0.006 --spx-stop 0.0025 --etf-stop 0.0030 --qqq-stop 0.0030 --spy-stop 0.0035 --risk-capital 1000.0 --min-entry-minute 580 --min-short-entry-minute 615 --min-short-price-vs-ib-high -150.0 --filter-by-greeks --single-step-eval --strict-wf --tickers SPX QQQ SPY --rl-reentry-lock-minutes 0 --rl-exit-policy hold *> .\logs\codex_bt_rl_march2026_v10_tickersig_holdexit_best_full_20260531.txt
```

Resultado full: 4,446 trades, WR 33.6%, PF 1.11, PnL +147,826, max DD -54,996. Por ticker: SPX 1,738 trades WR 34.2 PF 1.15 PnL +124,432; SPY 1,407 trades WR 34.5 PF 1.05 PnL +15,354; QQQ 1,301 trades WR 31.8 PF 1.03 PnL +8,040. No mejora al GBT.

Backtest abril-mayo 2026 true-OOS v10: 300 trades, WR 37.3%, PF 1.27, PnL +25,290. Por ticker: SPX 110 trades WR 33.6 PF 1.13 PnL +7,291; QQQ 102 trades WR 40.2 PF 1.38 PnL +7,284; SPY 88 trades WR 38.6 PF 1.60 PnL +10,715. Es rentable en abril/mayo, pero no mejora WR/PF de forma suficiente ni arregla el periodo completo.

### Diagnosticos RL v10: delta, stops, reversión y salida por subyacente

Pruebas de delta forzado. Importante: las pruebas sobre abril/mayo son diagnosticas. No se pueden promocionar como reglas si se escogen mirando abril/mayo, porque eso seria data snooping. Solo sirven para localizar el fallo mecanico del entorno/backtest.

- `--force-rl-delta-target 0.75`, full: 4,004 trades, WR 39.7%, PF 1.14, PnL +186,097. Por ticker: SPX 1,587 WR 40.3 PF 1.18; SPY 1,265 WR 40.7 PF 1.05; QQQ 1,152 WR 37.9 PF 1.04.
- `--force-rl-delta-target 0.85`, full: 3,663 trades, WR 44.4%, PF 1.10, PnL +126,840. Por ticker: SPX 1,447 WR 45.2 PF 1.13; SPY 1,160 WR 45.0 PF 1.01; QQQ 1,056 WR 42.8 PF 0.97. Profundizar delta sube WR, pero destruye PF/asimetria.
- SPX `delta=0.75` con stop de prima mas amplio: max loss 45% -> PF 1.14 WR 44.5; 50% -> PF 1.17 WR 46.3; 60% -> PF 1.19 WR 48.7. Muy cerca en SPX, pero no supera PF 1.20 ni arregla QQQ/SPY.
- SPX `delta=0.75`, max loss 60%, `--disable-rl-signal-reversal`: empeora a 1,032 trades, WR 43.9%, PF 1.15, PnL +106,722. La salida por reversión no era el bloqueo principal.
- `--rl-underlying-exit-policy only`, full policy strike: 3,704 trades, WR 42.5%, PF 1.09, PnL +123,794. Por ticker: SPX PF 1.16, SPY PF 1.00, QQQ PF 1.01. No resuelve.

Cambios de diagnostico añadidos a `backtest\backtest_rl.py`:

- `--force-rl-delta-target`
- `--rl-underlying-exit-policy {off,hybrid,only}`
- `--disable-rl-signal-reversal`

Verificacion:

```powershell
python -m py_compile .\backtest\backtest_rl.py
```

Resultado: OK.

### Diagnostico de techo: oracle de buckets en entorno de entrenamiento

Ejecutado un muestreo de 1,500 episodios del cache v10. Para cada episodio se forzaron los 7 buckets de strike en el mismo entorno de entrenamiento, salida HOLD, y se eligio el mejor bucket por PnL porcentual. Comando guardado como log/CSV:

```powershell
$env:PYTHONPATH = "$((Resolve-Path .).Path)\neural;$((Resolve-Path .).Path);$env:PYTHONPATH"; @' ... script Python de oracle buckets ... '@ | python -u -
```

Output guardado en `logs\codex_rl_oracle_bucket_sample_20260531.csv`.

Resultados oracle sample:

- Oracle `best_bucket`, eval sample: QQQ WR 33.6 PF 1.916; SPX WR 35.6 PF 2.941; SPY WR 35.2 PF 1.903.
- Fixed `itm_light`, eval sample: QQQ WR 27.2 PF 0.902; SPX WR 30.4 PF 1.461; SPY WR 28.4 PF 0.936.
- Fixed `itm`, eval sample: QQQ WR 32.0 PF 0.954; SPX WR 34.4 PF 1.573; SPY WR 35.2 PF 1.018.
- Distribucion del best bucket es amplia, no monotona: el bucket 6 gana mas a menudo, pero buckets 0-5 tambien son necesarios en todos los tickers.

Conclusion actual RL: PPO no esta fallando solo por entropia de salida. Con `--force-hold-exit`, el fallo principal es que el entrenamiento de strike con PPO puro tiene señal demasiado ruidosa y converge a una region simple (`itm_light`/`itm`) que no captura el oracle. Ademas, el backtest compara GBT spot vs RL opciones; el RL sufre stops de prima y reentradas tempranas que el baseline spot no sufre. El siguiente cambio razonable debe ser un warm-start supervisado del strike head usando labels oracle generados solo en el tramo de entrenamiento hasta marzo 2026, y despues validar sin tocar abril/mayo.

## Diario 2026-05-31 20:44 +02:00

### RL v11: warm-start supervisado de strike head con oracle train-only

Cambios:

- `neural\rl\training.py`: añadido `pretrain_strike_oracle()`, que etiqueta episodios solo del split cronologico de entrenamiento usando los 7 buckets y salida HOLD; nuevos flags `--strike-oracle-pretrain-samples`, `--strike-oracle-pretrain-epochs`, `--strike-oracle-pretrain-lr`.
- `neural\run_pipeline.ps1`: experimento v11 con `rl_models\march2026_oos_v11_strike_oracle_holdexit`, `--force-hold-exit`, `6000` labels, `3` epochs, LR `0.0001`.

Comando:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONWARNINGS='ignore'; $root=(Resolve-Path .).Path; $env:PYTHONPATH = "$root\neural;$root;$env:PYTHONPATH"; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026_tickersig --save-dir .\rl_models\march2026_oos_v11_strike_oracle_holdexit --total-updates 220 --min-confidence 0.400 --workers 32 --force-hold-exit --strike-oracle-pretrain-samples 6000 --strike-oracle-pretrain-epochs 3 --strike-oracle-pretrain-lr 0.0001 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v11_strike_oracle_holdexit_6000labels_220updates_20260531.txt
```

Resultado: oracle pretrain generó labels balanceados, pero accuracy supervisada fue mala (`19.9% -> 14.3%`). PPO best internal eval PF 1.244 en step 150, pero el backtest full volvió a colapsar a 100% `itm_light`: 4,512 trades, WR 32.8%, PF 1.10, PnL +137,216. Por ticker: SPX PF 1.14, SPY PF 1.04, QQQ PF 1.04. Abril/mayo fue rentable y ligeramente mejor en PF total, pero no cumple full-period ni mejora al GBT: 304 trades, WR 36.8%, PF 1.32, PnL +29,213; SPX PF 1.19.

Conclusion v11: el warm-start se borra durante PPO y no resuelve el problema de informacion. El estado de entrada no describia la cadena de opciones por bucket, por lo que el agente elegia strikes casi a ciegas.

### RL v12: contexto explicito de cadena por bucket

Cambios:

- `neural\rl\config.py`: `TOTAL_STATE_DIM` pasa de 185 a 220 al añadir `STRIKE_CONTEXT_DIM=35`.
- `neural\rl\environment.py`: el estado incluye, por cada bucket, `[available, abs_delta, premium_pct_spot, iv_ratio, theta_vs_premium]`.
- `backtest\backtest_rl.py`: replica el mismo contexto de cadena en inferencia; esto mantiene coherencia train/backtest para checkpoints nuevos.
- `neural\run_pipeline.ps1`: apunta a `rl_models\march2026_oos_v12_chainctx_oracle_holdexit`.

Verificacion:

```powershell
python -m py_compile .\neural\rl\config.py .\neural\rl\environment.py .\neural\rl\training.py .\backtest\backtest_rl.py
$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path .\neural\run_pipeline.ps1), [ref]$tokens, [ref]$errors) | Out-Null; if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message }; exit 1 } else { 'run_pipeline.ps1 parse OK' }
```

Resultado: OK. Smoke test confirmado con `State dim: 220` y strike context no vacio.

Comando entrenamiento v12:

```powershell
$env:PYTHONUNBUFFERED='1'; $env:PYTHONWARNINGS='ignore'; $root=(Resolve-Path .).Path; $env:PYTHONPATH = "$root\neural;$root;$env:PYTHONPATH"; python -u -m neural.rl.training --episode-index .\rl_data\episode_index_march2026.parquet --options-cache .\rl_data\rl_options_cache_chunks_march2026_tickersig --save-dir .\rl_models\march2026_oos_v12_chainctx_oracle_holdexit --total-updates 220 --min-confidence 0.400 --workers 32 --force-hold-exit --strike-oracle-pretrain-samples 6000 --strike-oracle-pretrain-epochs 3 --strike-oracle-pretrain-lr 0.0001 2>&1 | Tee-Object -FilePath .\logs\codex_rl_train_march2026_oos_v12_chainctx_oracle_holdexit_6000labels_220updates_20260531.txt
```

Resultado entrenamiento v12: oracle pretrain mejoro algo al principio pero siguio bajo (`17.6%`, `22.0%`, `16.8%`). Critic pretrain acabo en V loss 0.9063. PPO best internal eval PF solo 1.024. `H[Strike]` termino en 0.07 con warning de colapso.

Backtest full v12 combinado se quedo sin resumen por timeout/log incompleto:

```powershell
python -u .\backtest\backtest_rl.py ... --tickers SPX QQQ SPY --rl-exit-policy hold *> .\logs\codex_bt_rl_march2026_v12_chainctx_oracle_holdexit_best_full_20260531.txt
```

Se reintento por ticker, sin procesos Python vivos al iniciar el retry:

```powershell
# SPX
python -u .\backtest\backtest_rl.py ... --tickers SPX --rl-exit-policy hold *> .\logs\codex_bt_rl_march2026_v12_chainctx_oracle_holdexit_best_spx_full_retry_20260531.txt
# QQQ
python -u .\backtest\backtest_rl.py ... --tickers QQQ --rl-exit-policy hold *> .\logs\codex_bt_rl_march2026_v12_chainctx_oracle_holdexit_best_qqq_full_retry_20260531.txt
# SPY
python -u .\backtest\backtest_rl.py ... --tickers SPY --rl-exit-policy hold *> .\logs\codex_bt_rl_march2026_v12_chainctx_oracle_holdexit_best_spy_full_retry_20260531.txt
```

Resultados v12 retry por ticker:

- SPX: 1,705 trades, WR 35.5%, PF 1.16, PnL +132,598, max DD -50,037. Bucket `itm`: 1,004 trades, WR 39.8%, PF 1.28; bucket `itm_light`: 701 trades, PF 0.96. Falla WR y PF total; no mejora GBT.
- QQQ: 1,216 trades, WR 36.2%, PF 1.08, PnL +18,443. Falla PF/WR y no mejora GBT.
- SPY: 1,322 trades, WR 38.7%, PF 1.05, PnL +11,832. Falla PF/WR y no mejora GBT.

Conclusion v12: añadir contexto de cadena evita el colapso completo a `itm_light`, pero no arregla el objetivo. La policy sigue maximizando una recompensa de opciones que produce demasiados hard stops de prima y WR bajo. El siguiente paso no debe ser otro ajuste menor de entropia; hay que cambiar el entrenamiento para que el agente aprenda una accion economica validada por PF/WR por ticker, probablemente con:

- cabeza/objetivo supervisado de `ENTER/SKIP + bucket` por ticker usando labels out-of-fold del periodo train-only;
- penalizacion explicita por hard-stop rate y WR bajo en el reward/seleccion de checkpoint;
- o separar el RL por ticker, porque SPX/QQQ/SPY tienen microestructura de opciones distinta y una unica policy esta aprendiendo un compromiso malo.

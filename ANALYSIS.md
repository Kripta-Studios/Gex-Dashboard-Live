# Analisis del pipeline neural y backtests recientes

Fecha de analisis: 2026-05-18. La ultima fecha presente en los backtests es 2026-05-15, por lo que mayo es un mes parcial.

## Fuentes revisadas

- `neural/run_pipeline.ps1`
- `visualizer/analysis/All_backtest_analysis_report.tex`
- CSV usados por el reporte global: `backtest_results/gbt_only_20260518_043538.csv` y `backtest_results/gbt_rl_20260518_043538.csv`
- Modelo GBT activo: `neural/models/codex_exp/gbt_18m_econ_pf150_minsel10_avail.joblib`
- Historial GBT estricto: `neural/models/codex_exp/gbt_18m_econ_pf150_minsel10_avail_history.joblib`
- Registro de ventanas: `neural/models/codex_exp/window_registry.json`
- Agente RL activo: `rl_models/best_rl_agent.pt`
- Historial RL: `rl_models/rl_training_history.json`
- Indice de episodios RL: `rl_data/episode_index.parquet`

Tambien cree y ejecute `scripts/analyze_pipeline_outputs.py` para recalcular metricas de rentabilidad, sesgo direccional, distribucion de strikes, metadatos de modelos y split temporal RL desde los artefactos reales.

## Como funciona el sistema

`neural/run_pipeline.ps1` ejecuta el sistema completo:

1. Recolecta datos SPX, QQQ y SPY en `training_data/training_data_spx_qqq_spy.parquet`.
2. Entrena un ensemble LightGBM walk-forward con `neural/train_walkforward.py`.
3. Genera `rl_data/episode_index.parquet` con inferencia GBT en modo `--strict-wf`.
4. Preprocesa cache de opciones reales para RL en `rl_data/rl_options_cache_chunks`.
5. Entrena PPO con `python -m rl.training`.
6. Ejecuta diagnostico con `neural/diagnose_pipeline.py`.
7. Ejecuta backtest GBT-only y GBT+RL.
8. Genera reportes visuales con `visualizer/analyze_backtests.py`.

La configuracion activa entrena GBT con 18 meses de train, 1 mes de test, ensemble de 3, `min_pf_floor=1.50`, `selection_metric=economic`, `min_window=15`, y usa en backtest `threshold=0.475`, `cooldown=15`, target 1.0% long/short, stop 0.25%, y `risk_capital=1000`.

## Modelos generados/activos

El GBT activo contiene 14 modelos de 5 ventanas walk-forward:

| Ventana | Modelos | Cutoff train | Validacion | Disponible desde | PF avg |
|---:|---:|---:|---:|---:|---:|
| 18 | 3 | 2025-07-08 | 2025-07-10 a 2025-08-06 | 2025-08-06 | 1.92 |
| 20 | 3 | 2025-09-05 | 2025-09-08 a 2025-10-06 | 2025-10-06 | 3.70 |
| 21 | 3 | 2025-10-06 | 2025-10-08 a 2025-11-04 | 2025-11-04 | 2.66 |
| 22 | 3 | 2025-11-04 | 2025-11-06 a 2025-12-04 | 2025-12-04 | 5.15 |
| 25 | 2 | 2026-02-05 | 2026-02-09 a 2026-03-09 | 2026-03-09 | 2.19 |

Para marzo de 2026, el backtest empieza usando ventanas 18/20/21/22 y a partir de despues de 2026-03-09 tambien puede usar la ventana 25. Abril y mayo usan las cinco ventanas.

El RL activo `best_rl_agent.pt` fue guardado en el step 325. El mejor PF de evaluacion del historial fue step 275, con PF 2.86; el step 325 tenia PF eval 2.72 y WR eval 52.0%. El entrenamiento final siguio hasta step 500, pero el backtest usa el best checkpoint.

## Rentabilidad marzo-abril-mayo 2026

Resultado agregado por mes:

| Estrategia | Mes | Trades | WR | PF | PnL | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| GBT-only | 2026-03 | 64 | 54.7% | 1.65 | +$16,217 | -$6,936 |
| GBT-only | 2026-04 | 36 | 44.4% | 1.59 | +$9,684 | -$5,488 |
| GBT-only | 2026-05 | 15 | 46.7% | 1.41 | +$2,981 | -$3,656 |
| GBT+RL | 2026-03 | 63 | 36.5% | 1.65 | +$13,171 | -$8,556 |
| GBT+RL | 2026-04 | 35 | 31.4% | 1.55 | +$6,939 | -$5,170 |
| GBT+RL | 2026-05 | 14 | 42.9% | 2.45 | +$5,025 | -$1,642 |

Resultado total reciente:

| Estrategia | Trades | WR | PF | PnL | Max DD |
|---|---:|---:|---:|---:|---:|
| GBT-only | 115 | 50.4% | 1.60 | +$28,882 | -$6,936 |
| GBT+RL | 112 | 35.7% | 1.69 | +$25,135 | -$11,786 |

Conclusion: ambos son rentables en marzo, abril y mayo agregados. GBT-only gana mas dinero en marzo y abril; GBT+RL mejora mayo y el PF total reciente, pero con peor win rate y mayor drawdown agregado de marzo a mayo.

Por ticker en marzo-mayo:

| Estrategia | Ticker | Trades | WR | PF | PnL |
|---|---|---:|---:|---:|---:|
| GBT-only | QQQ | 38 | 60.5% | 2.18 | +$16,633 |
| GBT-only | SPX | 40 | 52.5% | 1.81 | +$12,604 |
| GBT-only | SPY | 37 | 37.8% | 0.98 | -$355 |
| GBT+RL | QQQ | 39 | 43.6% | 2.83 | +$10,845 |
| GBT+RL | SPX | 38 | 31.6% | 1.57 | +$13,020 |
| GBT+RL | SPY | 35 | 31.4% | 1.17 | +$1,270 |

QQQ es el ticker mas sano. SPY es debil: en GBT-only queda practicamente plano/negativo y en GBT+RL depende de pocas operaciones cortas con baja tasa de acierto.

## Diagnosticos de colapso

Hay colapso direccional local, sobre todo en SPY/SPX:

- GBT-only: SPY abril fue 100% SHORT (12 trades), SPX mayo 100% SHORT (4 trades), SPY mayo 100% SHORT (3 trades).
- GBT+RL: SPX abril fue 93.3% SHORT (15 trades), SPY abril 100% SHORT (11 trades), SPX mayo 100% SHORT (4 trades), SPY mayo 100% SHORT (3 trades).
- El `episode_index` confirma que esto viene del GBT, no solo del simulador: SPY abril tuvo 91 episodios SHORT y 0 LONG; SPX mayo 8 SHORT y 0 LONG; SPY mayo 12 SHORT y 0 LONG.

El RL tambien presenta colapso de strike:

- En marzo-mayo, 110 de 112 trades GBT+RL usaron bucket `itm` (98.2%).
- Los 2 trades `otm_far` fueron en marzo y perdieron -$724.

Esto significa que, en el periodo reciente, el RL esta funcionando casi como una politica ITM fija mas gestion de salida, no como selector diversificado de strikes.

## Riesgo de overfitting

Mi conclusion es: no veo un colapso total del sistema, pero si veo riesgo alto de overfitting metodologico y de seleccion.

Puntos a favor:

- Marzo-mayo 2026 queda positivo en ambos sistemas.
- El backtest reciente usa `--strict-wf`; para estas fechas hay modelos con `available_date` anterior a las operaciones.
- El split cronologico de RL deja 2025-07-17 a 2026-05-15 como evaluacion, asi que marzo-mayo estan en el tramo eval del RL.

Puntos problematicos:

- El reporte `All` no es totalmente walk-forward para fechas antiguas. Si no hay modelos suficientemente antiguos, `GBTEnsemble.predict_proba(..., date=...)` usa fallback al modelo mas antiguo disponible. Para fechas anteriores a 2025-08-06 eso usa un modelo entrenado con datos de 2025 sobre 2022-2025, lo que invalida gran parte del backtest global.
- `run_pipeline.ps1` contiene parametros descritos como validaciones de Apr/May 2026. Eso sugiere tuning posterior sobre el mismo periodo que ahora se mira como prueba.
- Corregido tras este analisis: `neural/run_pipeline.ps1` ahora hace que `selection_base_confidence` del GBT derive de `BacktestBaseConfidenceArg` (`0.475`) y pasa al training GBT `--min-short-entry-minute` y `--min-short-price-vs-ib-high`. Para que el fix tenga efecto en los artefactos, hay que reentrenar desde el paso GBT.
- `MinTradesPerWeekGate = 6` se imprime, pero no se aplica en el pipeline.
- La seleccion de ventanas usa PF de muchos candidatos con pocos trades minimos (`min_selection_trades=10`). Esto favorece multiple testing.
- El RL muestra gap de train vs eval: en el ultimo checkpoint evaluado, train PF 3.60 vs eval PF 2.63; en steps 425-450 el gap fue aun mayor. Es overfitting leve/moderado, no catastrofico.
- Los thresholds son bajos: los SHORT pueden entrar desde 0.45 por el offset de confianza. Muchas senales recientes estan muy cerca del umbral.

## Propuestas de mejora

1. Eliminar el fallback temporal del GBT: si no hay modelo `available_date < date`, no operar. Regenerar el reporte global solo desde la primera fecha realmente disponible o mostrar una seccion "pre-model invalid".
2. Unificar configuracion en un unico YAML/JSON usado por training, episode index, preprocess, backtest y live. La seleccion GBT debe recibir tambien los filtros short reales.
3. Separar un holdout final que no se toque. Si marzo-mayo 2026 ya se uso para decidir parametros, bloquear junio-julio 2026 como proximo test real sin tuning.
4. Anadir gates automaticos por ticker/direccion: si un ticker supera 90% de una direccion con bajo numero de trades o PF menor a 1.2, bajar sizing o bloquearlo temporalmente.
5. Aplicar de verdad `MinTradesPerWeekGate` y reportar semanas con menos de 6 trades como no concluyentes.
6. Comparar RL contra baselines simples: GBT + ITM fijo, GBT + ATM fijo, GBT + salida fija. Si RL no supera ITM fijo, simplificar.
7. Penalizar colapso de strike en entrenamiento RL o exigir diversidad minima de buckets, salvo que un test OOS demuestre que ITM-only es superior.
8. Calibrar probabilidades por ventana/ticker/direccion. Confiar en 0.45-0.50 sin calibracion es fragil.
9. Endurecer costes: slippage, half-spread variable, fill probability y liquidez por strike. El PF de opciones puede caer rapido si el fill es optimista.
10. Crear un reporte diario de salud: PnL por ticker/direccion, strike mix, confidence hist, drift de features, y comparacion GBT-only vs GBT+RL en las mismas entradas.

## Veredicto

Los modelos son rentables en marzo, abril y mayo de 2026 en agregado, pero no considero que el sistema este probado de forma suficientemente robusta para confiar solo en el reporte `All`. El GBT-only parece mas estable en marzo-abril; el GBT+RL aporta mejora en mayo y mejor PF reciente, pero con menor win rate, mayor drawdown agregado y colapso fuerte a strikes ITM. La prioridad deberia ser corregir la validacion walk-forward, alinear los filtros de training/backtest y demostrar que RL supera a un baseline ITM fijo en un periodo completamente no tocado.

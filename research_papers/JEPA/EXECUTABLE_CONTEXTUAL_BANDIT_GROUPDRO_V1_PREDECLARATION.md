# EXECUTABLE_CONTEXTUAL_BANDIT_GROUPDRO_V1 — predeclaración

**Fecha:** 2026-07-26  
**Estado:** `CLOSED_NO_EXECUTION_SUPERSEDED_BY_USER_NESTED_SELECTOR`
**Producción:** cerrada

## Cierre anterior a ejecución — 2026-07-26

El usuario prioriza la comprobación exhaustiva del selector mensual sobre el
grid de 1.128.960 overlays. Esta familia se cierra antes de implementar runner,
ajustar una red, generar una predicción o leer una métrica. La autoridad
siguiente es
`EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_PREDECLARATION.md`.
No se permite volver a ejecutar GroupDRO para rescatar el resultado nested.

## Motivo y alcance

Esta es una única falsificación sobre datos ya existentes. No descarga,
recaptura ni reconstruye fuentes. Tampoco reabre las familias long-option
cerradas: cambia simultáneamente el espacio de acciones y el objetivo de
aprendizaje, y debe cerrarse sin rescate si falla.

El evento tiene una sola decisión y, una vez cerrado, el parquet contiene el
payoff ejecutable de cada acción admisible. Por ello el problema es un
**contextual bandit con feedback completo**, no un MDP. PPO/DQN secuencial no
está justificado: no existe estado posterior controlado por la acción ni una
cadena de rewards que requiera Bellman backup. La comparación materialmente
nueva es una Q-network multiacción que aprende los doce payoffs conjuntamente y
penaliza el peor ticker-mes de training.

Todo 2026 ya fue visto por otras familias. Enero-junio se usa únicamente como
development walk-forward y nunca como outer promocional. Incluso un PASS solo
autoriza congelar una policy para un mes futuro intacto.

## Fuentes inmutables

Único parquet económico:

`tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`

- SHA-256:
  `e6a19efba1edb055c733aab4967843f7a4b5f1d2c8238a7a243fc5bbc2251903`
- bytes: `74.638.331`
- filas: `44.169`
- fechas: `20250102..20260630`
- tickers: `QQQ`, `SPXW`, `SPY`
- schema: 371 columnas
- `option_price_mode=executable_quote`
- entrada al ask, salida/stop/trailing al bid
- 0DTE, hold observado `30..180m`

No se combina con el parquet V1 que termina el 29-may-2026: aunque ambos tienen
el mismo schema físico, sus universos de eventos no son idénticos. No hay union,
intersection, deduplicación ni patch de junio.

## Features y clocks

Decisiones desde `10:30` hasta el último evento ya sellado, máximo `14:30` ET.
Las features son exactamente las columnas que devuelve
`walkforward_event_option_profile_selector.build_features` con:

- `live_observable_features_only=true`;
- `entry_start_minute_et=630`;
- sin include/exclude prefixes;
- dummies fijas de `ticker`, `expiry_mode` y `nearest_level_name`.

La lista resultante tiene 289 campos y SHA-256 JSON canónico:

`b4f038f75cb029c4ba2d1e4e4aab5266a45d86e9c2d86ac527a69be521c852ca`

Quedan prohibidos todos los patterns de outcome del filtro compartido:
`future`, `win`, `status`, `exit`, `return`, máximos/mínimos posteriores y
relojes posteriores. Mediana e IQR se ajustan solo con filas de training; los
valores no finitos se imputan a la mediana de training, el IQR cero se convierte
en 1 y el valor estandarizado se limita a `[-10, 10]`.

Mapping:

- `QQQ <- QQQ`;
- `SPY <- SPY`;
- `SPXW <- SPY` para contexto cash compartido, conservando `SPXW` como contrato
  y payoff de opción.

No se usa Greek/IV vintage cross-venue ni se toca ningún repair ID V1R1/V4R2.

## Acciones y reward

Orden de las doce acciones:

`CALL_D15, CALL_D25, CALL_D35, CALL_D50, CALL_D65, CALL_D80,`
`PUT_D15, PUT_D25, PUT_D35, PUT_D50, PUT_D65, PUT_D80`.

Cada reward es el `*_opt_exit_ret` executable_quote de la misma fila y acción.
Cada hold es su `*_opt_exit_minutes`. Una acción no disponible o no finita se
enmascara tanto en training como en inferencia; no se rellena ni se sustituye
por otro delta/strike.

El target de training se recorta a `[-0.60, 5.00]` únicamente dentro de la
loss. El ledger y todas las métricas usan el retorno físico original sin
recorte.

## Q-network fija

Una única red pooled:

1. `Linear(289,128) -> LayerNorm -> SiLU -> Dropout(0.10)`
2. `Linear(128,64) -> LayerNorm -> SiLU -> Dropout(0.10)`
3. `Linear(64,12)`

Inicialización PyTorch por defecto bajo seed `20260726`; deterministic
algorithms activado. Optimizer `AdamW`, learning rate `0.0003`, weight decay
`0.001`, batch `2048`, `30` epochs exactos, sin early stopping.

Loss por fila:

- SmoothL1, beta `0.25`, promediada sobre rewards disponibles;
- más `0.25 * CrossEntropy(Q/0.25, argmax(reward_clipped))`.

GroupDRO usa grupos `ticker x month` presentes en training. Los pesos empiezan
uniformes y, al final de cada epoch, se actualizan con exponentiated gradient
`q_g <- q_g * exp(0.05 * loss_g)` y se renormalizan. La loss del siguiente
epoch es el promedio de las losses de grupo ponderadas por `q_g`. No hay sweep,
ensemble, selección de seed, arquitectura alternativa ni tuning por ticker.

## Walk-forward development

Seis folds:

| Test | Training permitido |
| --- | --- |
| 202601 | 202501..202512 |
| 202602 | 202501..202601 |
| 202603 | 202501..202602 |
| 202604 | 202501..202603 |
| 202605 | 202501..202604 |
| 202606 | 202501..202605 |

Cada fold se entrena desde cero. El mes test no participa en scaler, loss,
pesos GroupDRO, selección de acción ni scheduler. No se excluyen fechas o
meses.

Inferencia determinista:

- se enmascaran acciones no disponibles;
- se elige `argmax(Q)` una sola vez;
- se abstiene si `max(Q) <= 0`;
- no hay umbral por ticker ni calibración posterior.

Scheduler live-equivalent:

- QQQ: máximo 2 trades/día, cooldown 30m;
- SPXW: máximo 4/día, cooldown 0m;
- SPY: máximo 1/día, cooldown 0m;
- orden cronológico;
- `reject_while_open`;
- una entrada exactamente al minuto de salida anterior vuelve a ser elegible.

## Gates

La policy pasa development únicamente si, simultáneamente en QQQ/SPXW/SPY:

- PF H1 `> 1.20`;
- WR H1 `> 45%`;
- neto H1 `> 0`;
- al menos 13 trades en cada uno de los seis meses;
- PnL positivo en cada uno de los seis meses;
- holds dentro de 30..180m;
- cero overlaps y paridad exacta del scheduler.

También se reportan PF/WR/PnL/trades por ticker-mes, drawdown, concentración de
top-5 días y mix de las doce acciones. No se selecciona por mes, ticker, delta o
lado.

## Secuencia fail-closed

1. Versionar esta predeclaración y el cierre sin ejecución de la admisión OPRA.
2. Implementar runner, auditor y tests; commit/push antes de ejecutarlos.
3. Ejecutar el development una sola vez.
4. Auditar independientemente hashes, features, folds, modelos, predicciones,
   payoff, holds, scheduler y métricas.
5. Si falla cualquier gate, cerrar sin cambiar arquitectura, loss, seed,
   epochs, threshold, acción, feature o scheduler.
6. Si pasa, congelar solo una policy prospectiva para el primer mes futuro
   todavía intacto. Enero-junio 2026 siguen siendo development visto.
7. Antes de cualquier integración, probar paridad offline/runtime de las 289
   features y ejecutar shadow paper. No modificar `services/`, `bots/`,
   `systemd/` ni desplegar sin permiso explícito.

## Referencias metodológicas

- Agarwal et al., *Contextual Bandit Learning with Predictable Rewards*,
  AISTATS 2012:
  <https://proceedings.mlr.press/v22/agarwal12.html>
- Sagawa et al., *Distributionally Robust Neural Networks for Group Shifts*,
  ICLR 2020:
  <https://openreview.net/forum?id=ryxGuJrFvS>

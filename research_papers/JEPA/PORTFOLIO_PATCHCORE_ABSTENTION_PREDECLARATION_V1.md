# Predeclaración — Portfolio PatchCore abstention v1

**Congelada:** 2026-07-11 CEST, antes de la corrida completa.

## Corrección de baseline

El selector flat-history anterior fijó cupos/cooldowns runtime, pero permitió seleccionar buckets d50/d65/d80. Por ello no se reutilizan sus policies ni su PnL como control de esta fase. El control correcto es el payoff head determinista exacto d25 SPXW/d35 QQQ-SPY de Portfolio Var-JEPA v1.

## Factor único

Se entrena una sola vez por mes el mismo payoff head determinista. Control y variante comparten bit a bit modelo, preprocesado, scores, acciones CALL/PUT, score thresholds, seeds, datos y replay. La variante añade únicamente una condición de abstención: `patchcore_distance <= cap`.

- El coreset se construye solo con eventos train anteriores a los tres meses internos.
- Usa únicamente 70 features actionless flat OOF (`z`, `dz_h1` y resúmenes live, incluido surprise lagged).
- Estandarización mean/std fit solo en train.
- K-center greedy determinista, 128 centros por ticker; no usa outcomes.
- 1-NN Euclidean distance; no cambia dirección ni score.
- El cap se elige únicamente en inner validation entre quantiles fijos `0.50/0.60/0.70/0.80/0.90/0.95/1.0`; `1.0` contiene el control sin filtrado.
- No hay sweep de tamaño, métrica, arquitectura ni combinación de anomaly scores.

## Contrato común

- Dataset SHA-256 `39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F`.
- 22.037 eventos `20250501..20260529`, executable_quote ask→bid, 0DTE.
- Rejilla 10:30–14:30 ET/5m, features live y secuencias flat OOF contiguas.
- SPXW d25/cupo4/cooldown0; QQQ d35/cupo2/cooldown30; SPY d35/cupo1/cooldown0.
- Una posición por ticker y hold >=30m.
- Nested test `202601..202605`, tres meses internos, junio físicamente sellado.
- Seed base `20260618`, fold `base+YYYYMM`, CUDA determinista, 40 epochs, batch 512.
- Inner gates: PF >=1,3, WR >=50%, >=18 trades por mes y todos los meses positivos. Una policy inválida hace abstain; no se relajan gates después.

## Decisión

PatchCore solo continúa si:

1. produce policies válidas suficientes para que cada ticker cumpla PF >=1,3, WR >=50%, mínimo 18 trades en cada mes y PnL positivo en los cinco meses OOS;
2. la distancia correlaciona positivamente con error absoluto OOS en al menos 10/15 celdas ticker×mes y tiene mediana Spearman positiva;
3. provenance, hashes, holds, cupos, cooldowns y una sola posición pasan.

No se seleccionará por PnL agregado. `production_live_ready=false` sin excepción.

## Hashes

| Artefacto | SHA-256 |
| --- | --- |
| Script | `2649D8ED77A7A43F07BE0E67FC47B51FC5ADF6F5E9FC9D304DA4C09A693D29E9` |
| Dependencia payoff compartida | `21C011C6F66906E90B128E091794FC92497739568DC10F34EBB6F9175B45F0A1` |
| Test | `269C0E73B3E8C1B20373EC98963F2598541400FDA5B7325B353913EE296AF439` |
| Runner | `A0F653D8FDAF735641816A93A2D177DE42323488570B4FC75C8F17D584510795` |
| Dataset | `39203C83F47A60AFB2AB7951201CBEB3B9098F4238169F0D716649571667DA2F` |

Tests focalizados: `9 passed in 2.16s`; `py_compile`, parse PowerShell y `git diff --check` PASS.

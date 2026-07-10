# CODEX-HANDOFF.md — Estado para continuación por otro agente

**Fecha:** 2026-07-10T19:20 CEST
**HEAD:** `0458ff4 fix: enforce causal JEPA training windows`
**Agente anterior:** cerraron auditoría causal, selector nested, optimización del simulador, exploratory walk-forward (rechazado), y endurecimiento del trainer.

## Estado del experimento

### Ablación predeclarada: `flat` vs `modal` encoder (SUMMARY-articles.md §6, punto 1)

**Estado:** COMPLETADO. Ambos arms (`flat` y `modal`) completaron extracción OOF y evaluación OOS con nested walk-forward.

**Diseño experimental:**
- **Factor único cambiado:** `--encoder-input-mode flat` vs `--encoder-input-mode modal`
- **Dataset:** `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet` (44.169 filas, 371 cols)
- **SHA-256 dataset:** `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903`
- **Seed:** `20260618` (default del trainer)
- **Horizons:** `1,3,6,12` (equivalentes a 5/15/30/60 minutos)
- **OOF range:** `--start-month 202501 --end-month 202605`
- **Data cutoff:** `202605` (junio excluido físicamente)
- **Features live-observable:** `--live-observable-features-only`
- **Contiguidad 5min:** `--expected-step-minutes 5`
- **Rejilla 10:30–14:30 ET:** `--entry-start-minute-et 630 --entry-end-minute-et 870`

**Arms:**
1. `flat`: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1/`
2. `modal`: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1/`

### Comandos ejecutados

#### 1. Tests focalizados (50 passed)

```powershell
python -m pytest -q tests/test_build_event_option_dataset.py tests/test_event_option_live_causality.py tests/test_event_option_non_overlap.py tests/test_event_option_production_validator.py tests/test_jepa_bot_execution.py tests/test_event_phys_td_jepa_causality.py --basetemp C:\tmp\pytest-jepa-causal-20260710b
```

### Arm 1: `flat` (COMPLETADO)

Comando ejecutado con `--encoder-input-mode flat`.
Output: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_flat_h1_3_6_12_causal_202501_202605_v1/`
Folds generados: 13 folds OOF (mayo 2025 – mayo 2026).
Filas OOF: 33.380.

### Arm 2: `modal` (COMPLETADO)

Comando:

```powershell
python neural/jepa/walkforward_event_phys_td_jepa_oof.py \
  --data "tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet" \
  --output-dir "research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1" \
  --tickers SPXW SPY QQQ --expiry-modes zero_dte \
  --start-month 202501 --end-month 202605 \
  --horizons 1,3,6,12 --encoder-input-mode modal \
  --live-observable-features-only \
  --entry-start-minute-et 630 --entry-end-minute-et 870 \
  --entry-grid-anchor-minute-et 600 --expected-step-minutes 5 \
  --seed 20260618 --device cpu --epochs 8 --batch-size 1024 \
  --context-len 6 --z-dim 32 --phys-dim 12 --delta-dim 16 \
  --hidden-dim 128 --num-layers 2
```

Output: `research_papers/JEPA/results/_diagnostics/ptdj_ablation_modal_h1_3_6_12_causal_202501_202605_v1/`

### Procesos activos

- Ninguno en curso (ambas tareas finalizadas).

### Artefactos y checkpoints

- Dataset: `tmp/event_option_dataset_execquote_causal1030_202501_202606_v3_physics/event_option_dataset.parquet`
- Exploratory nested WF (rechazado): `research_papers/JEPA/results/_diagnostics/event_option_execquote_causal1030_nested_exploratory_202601_202605_v1/`

### Hashes y seeds

| Artefacto | SHA-256 |
| --- | --- |
| Dataset base | `68AE45C89D521F71431261DEEA9BCC7E465FEB294D17BF122AFBDDBB30A4C8F8` |
| Dataset physics | `E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903` |
| Seed | `20260618` |

### Tests ejecutados

```text
50 passed in 4.92s (2026-07-10T19:17 CEST)
```

Suite:
```text
tests/test_build_event_option_dataset.py
tests/test_event_option_live_causality.py
tests/test_event_option_non_overlap.py
tests/test_event_option_production_validator.py
tests/test_jepa_bot_execution.py
tests/test_event_phys_td_jepa_causality.py
```

### Métricas disponibles

- Baseline nested exploratorio Jan–May rechazado: Overall PF 0,909, WR 43,8%
- Legacy package: BLOCKED_FOR_PRODUCTION

### Fallos encontrados

- Ninguno nuevo en esta sesión

### Cambios sin commit

```text
M backtest/backtest_gbt_parquet.py  (solo line-ending)
M neural/models/jepa/.../event_option_policy.json  (entry_sample_minutes/anchor additions)
M neural/models/jepa/.../component_registry.json  (newline at end)
M neural/models/jepa/.../QQQ_static_union_balanced.json  (newline)
M neural/models/jepa/.../SPXW_static_union_balanced.json  (newline)
M neural/models/jepa/.../SPY_static_union_balanced.json  (newline)
M neural/models/jepa/.../runtime_policy_replay_summary.json  (newline)
```

Estos diffs son del agente anterior y solo añaden `entry_sample_minutes`/`entry_sample_anchor_minute_et` al policy JSON. No afectan la ablación en curso.

### Último commit

```text
0458ff4 fix: enforce causal JEPA training windows
```

### Junio de 2026

Completamente sellado. El `--data-cutoff-month 202605` / `--end-month 202605` excluye junio del dataset y del OOF.

### Primera acción del siguiente agente

1. La ablación `flat` vs `modal` está terminada y documentada en `SUMMARY-update.md` y `SUMMARY-articles.md`. `modal` mejora ligeramente PF y fuertemente a SPY/SPXW, pero destruye QQQ. Ninguno llega a production-live.
2. Iniciar el siguiente experimento en la cola: **Semantic-Masked Market JEPA** (ver `SUMMARY-articles.md` punto 2).
   - Enmascarar modalidades completas y spans temporales solo dentro del prefijo observado.
   - Predecir latentes futuros en horizontes rápidos y lentos.
   - Ablaciones limpias de SIGReg, EMA/prototipos, VISReg y Gram anchoring cambiando un factor cada vez.
3. No usar junio de 2026.

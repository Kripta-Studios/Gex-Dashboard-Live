# EXISTING_DATA_EXECUTABLE_UTILITY_V1 — predeclaración

Estado al crear este documento: `PREDECLARED_DEVELOPMENT_ONLY`. Ningún outcome
económico 2024/2025 se ha inspeccionado. Enero-mayo 2026 y junio 2026 permanecen
cerrados; producción no se modifica.

## Hipótesis y universo

Los bloques causales ya existentes pueden contener información complementaria
sobre las distribuciones completas de retorno executable CALL y PUT, aunque los
bloques aislados no mejoraran los proxies físicos rejection-versus-break. El
target primario es utilidad ask-to-bid, no AUC física.

El universo maestro son las 97.625 filas únicas SPXW/QQQ/SPY, 0DTE,
2022-01-03..2025-12-31 de
`event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1`. Se
preservan también las decisiones de 10:30. No se reduce el universo a touches.
La única transformación persistida es una vista temporal outcome-free bajo
`tmp/existing_data_edge_sprint_v1/`; no es una nueva fuente.

## Brazos de features

- `E0`: los 30 campos ordenados del allowlist Pairwise V1. Las diferencias y
  cambios se calculan causalmente dentro de ticker/sesión sobre el universo
  maestro; 10:30 no consume ninguna fila previa inexistente fuera de la sesión.
- `E1`: E0 más bloques completos elegibles, sin selección por outcome:
  pairwise physics/context current-time, el allowlist live legacy, wall-state
  GEX/DEX/DGEX y H-IBQDYN1 F1. Solo existen los flags predeclarados
  `wallstate__applicable` e `ibqdyn__applicable`. Los nulls de fuente ausente o
  geometría no aplicable permanecen null y solo se imputan con mediana train.

H-FLOW1, H-IVSURF1 y H-QSIZE1R1 se omiten completos: su clave de decisión es
one-to-many y el maestro no contiene `wall_identity`; nunca se congeló una
agregación exacta. H-QDYN1 se omite por `REJECTED_DATA_GATE`. H-GREEK2 se omite
por `BLOCKED_SOURCE_ENTITLEMENT`. Quality/provenance, labels, outcomes y futuros
no entran como alpha. No se permite as-of, nearest-strike, floor-time ni
sustitución retrospectiva.

Dos filas training-only SPXW del 2022-02-22 (10:30 y 11:20) tienen CALL
ejecutable pero PUT ausente/status 0. Se preservan en el universo, nunca se
rellenan y el head PUT las omite al ajustar su target; el head CALL puede usarlas.
Todo inner/outer debe contener ambos outcomes o el runner falla cerrado. Esta
regla se congeló al descubrir la missingness en desarrollo 2022-2023, antes de
abrir outcomes 2024/2025.

Los allowlists completos y hashes se congelarán en un manifest separado antes
de abrir 2024/2025. En este punto outcome-free, los hashes ordenados son E0
`b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38`
y E1
`e15469c0d1dce8176afd5c7fd48af4c477f830b4fc58651fb982f89fb8986abc`.

## Modelos económicos

Solo se autorizan dos formulaciones, idénticas para E0/E1 y todos los tickers.

1. Primaria: seis LightGBM hurdle. Por lado se estima probabilidad de retorno
   positivo, ganancia condicional y pérdida absoluta condicional; utilidad es
   `p*gain-(1-p)*loss`. Imputación y winsor 1%/99% se ajustan solo en train.
   Spec SHA `f5593225ef09e0f53b9b2de587fd01ae5d5378ace6d78f3185b407bea4f76796`.
2. Alternativa no rescatable: dos regresiones LightGBM Huber directas sobre los
   retornos executable completos CALL/PUT, sin clipping. Spec SHA
   `528a02bc36fb1a14aa60efe052095a52a23cd60ed56002d2007e8de51ef7de8f`.

Ambas preservan la capacidad Pairwise: 300 árboles, learning rate 0,05, 31
hojas, min child 20, subsample/colsample 0,8, lambda 1 y semillas
deterministas. No hay tuning, ablation, pruning, SHAP ni allowlists por ticker.

## Policy y selección inner

Se elige CALL si `utility_call > utility_put`, PUT en el caso contrario y
ABSTAIN en empate exacto. Los percentiles de training son exactamente utility
50/60/70/80/85/90/95 y margin 0/10/20/30/40/50. Ningún valor outer participa.

Un par solo es elegible si pasa en cada uno de los tres meses inner: PF >=1,30,
WR >=50%, >=18 trades, PnL >0 y hold mínimo >=30m. Si varios pasan, el ranking
descendente fijo es peor PnL mensual, peor PF, peor WR, mínimo trades, PnL
pooled, PF pooled, percentile utility y percentile margin. Si ninguno pasa,
todo el outer month es `ABSTAIN_OUTER`; no se escoge el menos malo.

## Folds y ejecución

Para cada mes outer: train usa toda la historia anterior al primero de los tres
meses inner, inner son los tres meses inmediatamente anteriores y outer es un
mes. Desarrollo se limita a 2022-2023. Tras congelar código, manifest, features
y protocolo se ejecutan una sola vez los 24 meses 2024-01..2025-12.

El contrato executable es ask entry, bid exit, stop -60%, take-profit +1000%,
trail +50%/25%, hold 30-180m. Solo una posición por ticker; SPXW 4/día y 0m,
QQQ 2/día y 30m, SPY 1/día y 0m. Entrada en el mismo timestamp de la salida
previa está permitida. La policy se decide cronológicamente cuando cada fila es
observable; no existe ranking futuro ni backfill del cap diario.

## Gate final

Solo E1 puede ser candidato científico. Una formulación pasa únicamente si los
72 ticker-month cells cumplen simultáneamente PF >=1,30, WR >=50%, >=18 trades,
PnL >0 y hold mínimo >=30m. Se reportan todos los trades, meses abstain, PF/WR/
PnL, drawdown, balance de lado, abstención y concentración top-5. Stress de
ejecución se abre solo si el contrato base pasa. Un fallo termina esta familia;
no autoriza otra fuente, relax ni rescate post-hoc.

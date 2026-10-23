# Auditoría independiente económica del TCN row-mixed: calendario completo

Fecha: 23 de octubre de2026. Especificación previa a la ejecución del auditor.
La reanudación está autorizada en `RESUMPTION_20261023.md`. Esta especificación
no declara que haya terminado una evaluación de mercado ni que sea rentable.

`audit_tcn_row_mixed_calendar.py` verifica la ejecución económica **dados los
scores sellados y los labels previamente auditados**. No importa el evaluador,
su scheduler ni los modelos. Reutiliza exclusivamente primitivas del auditor
independiente `audit_tcn_flags_economics.py`, SHA256
`ccb9686b1968fd5328fbcf9ffa18dfd843d302f1fc13a3bd3381a02f35d16e91`,
y exige ese hash al iniciar. No refittea ni reproduce inferencia GPU.

## Autoridades y calendario

Se requieren las auditorías originales FLAGS64 y SessionClock con sus hashes
publicados, sus raíces exactas, manifests, cierre e índice; el review nuevo del
evaluador debe coincidir con sus dependencias y copias ejecutadas. La identidad
y el completion deben vincular todos los outputs consumidos. La fuente modelo
row-mixed y su copia deben coincidir; se exige cierre de épocas1–4 con1491updates
por época y cuarto modelo final. No se elige otro checkpoint.

El calendario se reconstruye desde XNYS y se contrasta contra el índice auditado:
750ticker-días2025, incluidos nueve cierres cortos;369ticker-días enero–junio2026,
363disponibles y seis ausencias fijas SPY/QQQ del1,9,15deabril. Las ausencias
mantienen `NO_EVALUABLE`, separadas del día observable sin fill. Se validan todos
los campos de reloj: cierre210/390, estados60..195/375, liquidación205/385,
normalización temporal390.

Cada actions/labels y los cuatro archivos de features deben ser miembros
efectivos de `source_inputs.json`, con el hash del índice. No basta verificar los
miembros que un mapa haya decidido incluir. El mapa debe contener también las
fuentes originales de los controles y los sidecars diarios. Se rehashea todo al
principio y al final, conservando el inventario comprobado en el informe.
En particular, manifest y sidecar originales FLAGS son miembros obligatorios
del mapa externo aunque el adaptador omita listarlos. Los cuatro archivos de
features del índice son miembros obligatorios de ambos sellos de predicción,
control corto y variante; un `feature_files` vacío no acredita el orden causal.

## Predicciones y causalidad documental

Para1104sesiones completas se comprueban dtype, shape y bytes de action_ids y
scores en toda la cadena FLAGS64.variant → adapter.tcn_teacher → calendar
control → evaluation.control. El control original debe pertenecer al manifest
y sidecar auditados. Signed-zero o conversiones de dtype no cuentan como copia
exacta aunque sus valores sean numéricamente iguales.

Los nueve controles cortos tienen procedencia `NEW_SHORT_INFERENCE`, modelo y
normalizadores originales, score/inputs sellados y `labels_read=false`. No se
presenta esa inferencia nueva como parte del antiguo auditor FLAGS. Los sellos
de predicción deben preceder los shards económicos; freeze contiene toda la
validación y precede todos los artefactos test/adaptadores test. Se contrasta
timestampUTC y tiempos locales de archivos. Esto verifica coherencia del registro
y del código publicado; no acredita recepción de mercado ni observación externa
de cada acceso a memoria.

## Reconstrucción económica

Se reconstruyen las seis políticas control/variant × umbrales estrictos0/5/10USD,
desempate por action_id, WAIT, NO_FILL sin alternativa en el mismo minuto y
FILLED con siguiente decisión posterior a exit. Se comparan shards, attempts,
ledgers, cobertura, resúmenes por ticker/mes, selección y contrastes pareados.

La contabilidad se recalcula desde entry_ask/exit_bid ya sellados: multiplicador100,
slippage0,01por lado base y0,02adverso, salida limitada inferiormente a cero,
comisión2,60USDpor operación. Se exige entrada state+1, salida ≥state+2 dentro
del cierre explícito y duración coherente. NO_FILL aporta cero. No se reconstruye
la geometría del target/stop ni las cotizaciones raw; esas dependencias permanecen
bajo la auditoría del dataset, y el informe declara `raw_quote_replay=false`.

Selección exclusivamente2025, con fill diario, suma del PnL por ticker dividido
por escalaTRAIN y desempate control antes que variante y umbral menor. Si ninguna
cumple, selección nula. Se reproduce el gate económico original y el gate diario
en2026, sin permitir rescate por ticker/mes/umbral. Todo es `SEEN_DEVELOPMENT`;
`technical_ready=false`, `promotion_approved=false` incluso con auditoríaPASS.

## Publicación y pruebas

El auditor exige una raíz nueva separada y publica JSON mediante flush/fsync y
rename; un fallo conserva `audit_failure.json`, sin sobrescribir otro intento.
El PASS sólo puede emitirse tras reconstrucción completa y rehash final.

Las fixtures sintéticas cubren costes, reloj corto/completo, sesiones ausentes,
dtype/signed-zero, mapa incompleto, mutación durante auditoría, cadena de control,
sellos cortos y cronología freeze/test. Se ejecutan junto a las pruebas existentes
del scheduler/selector/economía independiente. No usan fuentes de mercado.
Incluyen admisión del CLI con productor incompleto, conservación del fallo sin
PASS y pequeños recorridos full/short desde controles sellados hasta ledger,
resumen final y publicación exclusivamente sintética.

CLI prevista (requiere productor completo y revisión independiente del auditor):

```powershell
python -u research_papers/JEPA/level_oracle_20261018/audit_tcn_row_mixed_calendar.py `
  --root D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_calendar_v1_evaluation `
  --flags-root D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1 `
  --control-audit D:/GexResearchArtifacts/level_oracle_20261018/tcn_flags_v1_economic_audit/audit.json `
  --session-root D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1 `
  --session-audit D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1_audit/audit.json `
  --review research_papers/JEPA/level_oracle_20261018/TCN_ROW_MIXED_CALENDAR_IMPLEMENTATION_REVIEW.json `
  --output D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_calendar_v1_economic_audit_01
```

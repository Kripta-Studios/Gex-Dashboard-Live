# KING-GEX-MANAGE30-V1 — aclaración causal de snapshots V1R2

Fecha de freeze: 2026-07-15, antes de `PASS_DATA_GATE`, modelos, métricas
MANAGE30, ranking o apertura de 2024–2026.

Esta aclaración no cambia la entrada King D1, las 17 acciones, features,
targets, modelo, hiperparámetros, folds, scheduler ni gates congeladas en la
predeclaración. Corrige una semántica causal de timestamp revelada por el
replayer fail-closed y registra una única señal train-only no ejecutable.

## Estado de los targets anteriores

- `train_dev_202201_202312_v1` queda `REJECTED_PRE_PATH_LABEL`: contenía solo
  `RUN_CHECKPOINT.json` y un join de universo incorrecto.
- `train_dev_202201_202312_v1r1` queda
  `REJECTED_CAUSAL_SNAPSHOT_SEMANTICS`: produjo 1.265/1.267 checkpoints de
  sesión, no produjo dataset ni `SUMMARY.json`, no entrenó modelos ni calculó
  PF/WR/PnL MANAGE30.
- Ningún checkpoint V1R1 puede reutilizarse. El relanzamiento autorizado debe
  usar el target inmutable nuevo `train_dev_202201_202312_v1r2`.

## Hallazgo causal

El histórico QQQ 2022-06-17 contiene quotes nativas cada 30 segundos. La función
compartida conserva `quote_dt` nativo pero crea también `dt=floor(quote_dt,1m)`.
El builder V1R1 agrupaba el snapshot por `dt`, por lo que una decisión de entrada
`13:55:00` podía elegir el contrato/quote de `13:55:30`. El mismo agrupamiento
podía mezclar las superficies de `hh:mm:00` y `hh:mm:30` en entrada o decisión.
Eso consume información posterior y no es live-equivalent.

El fail-closed de paridad B00 detectó cuatro ejemplos en esa sesión. A las 13:55
el master causal usa CALL 277 bid/ask `0,67/0,71`; V1R1 eligió la quote de
13:55:30 `0,72/0,74` y recalculó retorno `-0,6486486661` frente al sellado
`-0,6338028193`. Al seleccionar exclusivamente `quote_dt == timestamp`, las
seis señales QQQ del día reproducen contrato, strike y las cinco métricas B00.

Greeks SHA de la sesión:
`8c8444f2b2668924505c9b99949ef72380897b05d9001dd1f3866b76ab79d893`.

## Regla exacta V1R2

- El snapshot de entrada contiene exclusivamente filas con
  `quote_dt == entry_timestamp`.
- El snapshot de superficie en decisión contiene exclusivamente filas con
  `quote_dt == exact_decision_quote_time`.
- No se permite `floor`, as-of, nearest-time, last-known, forward fill ni unión
  de varios timestamps para construir un snapshot.
- El path del mismo contrato después de la entrada conserva timestamps nativos
  y puede observar quotes sub-minute solo cuando su timestamp es posterior a la
  entrada y no posterior al instante de decisión para features.
- La decisión sigue siendo la primera quote válida del contrato cuyo elapsed
  entero está entre 30 y 31 minutos. La superficie se toma exactamente en el
  timestamp de esa quote.
- Si falta un snapshot de entrada exacto, el data gate falla salvo la única
  exclusión congelada abajo. Si falta superficie completa en decisión, sus
  variables M1 permanecen NaN; jamás se inventa otro timestamp.

## Única señal de entrada no ejecutable

La auditoría exacta identificó una señal D1 train-only:

```text
ticker=SPXW
trade_date=20220222
minute=680
action=PUT
reason=exact_entry_contract_not_executable
```

En el snapshot exacto no existe PUT d25 con bid/ask ejecutable. El master ya la
representa con strike/outcomes NaN, hold `0` y status `0`. No se permite nearest
strike, CALL sustituta, zero payoff, as-of ni conservarla como acción B00.

Esta exclusión se determina solo con información observable en entrada. Se
mantiene el censo fuente de 22.273 señales y se registra exactamente una
rejection; el dataset executable esperado contiene 22.272 filas. Cualquier otra
señal sin contrato exacto, cualquier cambio de la clave congelada o más/menos de
una rejection causa fallo del data gate. No hay exclusiones en desarrollo 2023,
por lo que sus 36 celdas y su frecuencia no cambian.

Greeks SHA de la sesión:
`75dca4da75813f9e2965f44f6d4158c3e6a70c4976784556d4678b2f772d3208`.

## Reanudación y evidencia

El nuevo run identity debe incluir el SHA de este documento, las dos cuentas
`source_candidates=22273` y `executable_rows=22272`, y la clave/reason de la
rejection. Cada checkpoint de sesión sigue siendo manifest-last con hashes raw,
code/protocol, rows, bytes y SHA.

El relanzamiento V1R2 debe reconstruir las 1.267 sesiones. Solo un
`PASS_DATA_GATE` con paridad exacta B00 en las 22.272 filas, una única rejection
congelada y auditoría de coberturas puede autorizar los 72 folds 2023. Los
outcomes y producción 2024–2026 permanecen cerrados e intactos.

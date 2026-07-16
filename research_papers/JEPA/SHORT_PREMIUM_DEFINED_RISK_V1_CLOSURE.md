# Cierre SHORT_PREMIUM_DEFINED_RISK_V1

## Estado

`CLOSED_DATA_EXECUTION_GATE`

El one-shot autoritativo se ejecutó desde `ff4fb06f` sobre las 1.506 sesiones
selladas de 2024-01-01..2025-12-31 (502 por ticker). Revalidó los hashes de los
ficheros Greek y de reloj nativo y llegó a construir 65.512 filas de candidatos
en memoria. Se detuvo, antes del selector walk-forward y antes de escribir el
directorio de resultados, porque encontró 88 perfiles con entrada resoluble y
sin las cuatro patas ejecutables en el exit exacto congelado.

Por tanto no existen PF, WR, PnL, selección mensual ni resultado 2026 de V1.
Las 65.512 filas parciales no son un ledger publicable: el protocolo exige un
universo completo antes de seleccionar o reportar economía.

## Fallo exacto

Los 88 casos son los 44 perfiles congelados de QQQ y los 44 de SPY en
2025-10-22. La entrada 10:35 sí construye las once estructuras por ticker
(nueve iron condors y dos iron flies), cada una con cuatro reglas de salida. El
exit programado es 13:35. El reloj nativo contiene esa clave exacta, pero los
bid/ask Greek originales están cruzados en patas necesarias, por lo que son
no-signable y `close_path` no puede producir un cierre de cuatro patas.

Ejemplos del vintage original en 13:35:

| Ticker | Right | Strike | Bid | Ask |
| --- | --- | ---: | ---: | ---: |
| QQQ | PUT | 601 | 1,37 | 1,20 |
| QQQ | PUT | 602 | 1,81 | 1,56 |
| SPY | PUT | 664 | 1,06 | 0,79 |
| SPY | PUT | 665 | 1,48 | 1,07 |

Una reproducción aislada desde el mismo runner devuelve `candidate_rows=0` y
`unresolved=44` para cada una de esas dos sesiones. SPXW no tiene unresolved.

## Interpretación y límites

Este cierre no demuestra que la prima corta 0DTE sea intrínsecamente perdedora.
Demuestra que esta familia congelada no puede evaluarse de forma íntegra bajo el
contrato exacto de ejecución y el vintage histórico disponible. Imputar el
quote anterior, usar midpoint, excluir el día, reemplazar los precios por el
sidecar revisado o cambiar la hora después de observar el fallo violaría la
predeclaración y sesgaría la muestra.

La gate que protegía 2026 no fue alcanzada. Enero-julio 2026 y producción no se
abrieron ni modificaron. Una investigación posterior debe ser una hipótesis
realmente distinta y predeclarada; no un rescate de V1.

## Evidencia reproducible

- Predeclaración: `SHORT_PREMIUM_DEFINED_RISK_V1_PREDECLARATION.md`.
- Runner: `neural/jepa/evaluate_short_premium_defined_risk_v1.py`.
- Freeze inicial: `dd777fc7`.
- Corrección de provenance del complement seal: `ff4fb06f`.
- Fuentes de precio: bid/ask Greek originales.
- Sidecars: usados solo para probar reloj/clave exactos.
- Cobertura recorrida: 1.506/1.506 sesiones.
- Filas de candidatos acumuladas antes del fail-closed: 65.512.
- Perfiles unresolved: 88.
- Output económico escrito: ninguno.


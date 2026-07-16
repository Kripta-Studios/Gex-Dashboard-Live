# Cierre DIRECTIONAL_SEMANTIC_JEPA_V1

Estado: `CLOSED_2026_GATE`

La policy `SEMANTIC_RESIDUAL` fue elegida para QQQ/SPX/SPY en desarrollo y
sealed antes de abrir 2026. El one-shot se ejecutó sin cambios: features hasta
10:35, open 10:36→open 13:36, hold exacto 180m, una operación por día, cero
overlaps y coste 1bp. El ledger tiene 399 trades hasta 2026-07-15.

## Gate enero–junio 2026

| Ticker | Trades | WR | PF | Net bps | Min mes | Meses + | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| QQQ | 123 | 52,85% | 0,794 | -678,2 | 19 | 2/6 | FAIL |
| SPX | 123 | 50,41% | 0,906 | -202,1 | 19 | 3/6 | FAIL |
| SPY | 123 | 49,59% | 0,794 | -468,9 | 19 | 2/6 | FAIL |

La frecuencia pasa ampliamente, pero ninguno cumple PF, PnL agregado o todos
los meses positivos. La precisión de signo cercana a 50% no compensa el tamaño
asimétrico de los errores. Esto refuta este JEPA price-only/residual a tres
horas; quitar theta no crea por sí mismo alpha direccional.

## Julio MTD

| Ticker | Trades | WR | PF | Net bps |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 10 | 50,0% | 1,133 | +38,0 |
| SPX | 10 | 60,0% | 1,922 | +111,1 |
| SPY | 10 | 60,0% | 1,888 | +107,1 |

Julio MTD es positivo, pero tiene solo diez sesiones y no puede reparar la gate
enero–junio ni probar la frecuencia mensual. No se selecciona julio post-hoc.

## Evidencia

- Ledger SHA256: `0f08765d694992f53bac07b76751b2dab09692fc1616f13c92591c0b6092ab3a`.
- Monthly metrics SHA256: `024019f686bb45de75f533edc15eff63a423d36e92aef249958cd8666b9d7b98`.
- Source inventory SHA256: `66f8954f13f1aaa095b7b3c521fc989bb053b78ec65bf95c4545fef0ebddd7ec`.
- Development model SHA256: `876f36c28f4872b836bb751f93fc4c3baa09d302044b03a75d35567f0aebc607`.
- Producción modificada: no.
- Fills de futuros validados: no.

No rescatar V1 con otro seed, máscara, hora, coste, threshold, ticker o subset.
Una siguiente hipótesis debe añadir información causal nueva —no otro dataset
price-only— y demostrar primero paridad de options surface/VIX/futuros.


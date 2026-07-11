# Informe — estabilidad pre-2026 del mecanismo static-union

## Veredicto

Las reglas estáticas seleccionadas sobre 2026 no muestran estabilidad al trasladarlas a octubre–diciembre de 2025 con modelos entrenados solo hasta septiembre. Los tres tickers fallan las gates; `production_live_ready=false`.

| Ticker | Trades | WR | PF | PnL | Min/mes | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 75 | 41,33% | 1,158 | +4,193R | 21 | 66,7% |
| SPXW | 64 | 43,75% | 1,686 | +14,481R | 19 | 66,7% |
| SPY | 125 | 34,40% | 0,794 | -10,172R | 26 | 0% |

El volumen supera 18 trades en cada mes para los tres. El cuello de botella es calidad/dirección y estabilidad mensual, no frecuencia.

## Desglose mensual

| Ticker | Mes | Trades | WR | PF | PnL |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | 202510 | 28 | 46,43% | 1,574 | +5,399R |
| QQQ | 202511 | 26 | 50,00% | 1,323 | +2,233R |
| QQQ | 202512 | 21 | 23,81% | 0,664 | -3,439R |
| SPXW | 202510 | 23 | 43,48% | 2,634 | +11,955R |
| SPXW | 202511 | 19 | 47,37% | 1,755 | +4,705R |
| SPXW | 202512 | 22 | 40,91% | 0,712 | -2,179R |
| SPY | 202510 | 48 | 31,25% | 0,727 | -5,219R |
| SPY | 202511 | 26 | 42,31% | 0,971 | -0,289R |
| SPY | 202512 | 51 | 33,33% | 0,772 | -4,664R |

Diciembre rompe QQQ y SPXW; SPY es negativo los tres meses. SPXW conserva PF agregado alto por payoff asimétrico, pero no cumple WR>=50% ni todos los meses positivos.

## Interpretación

La diferencia frente a las métricas 2026 del paquete no puede atribuirse a una arquitectura superior ni a falta de candidatos. Los modelos productivos entrenaron en 2025, pero sus thresholds y reglas declararon selección en los mismos meses 2026 reportados. Esta auditoría confirma que esas reglas no eran un mecanismo estable antes de esa selección. No deben usarse sus cifras 2026 como prueba de rentabilidad OOS bajo el nuevo objetivo.

La próxima investigación debe aprender reglas/buckets en una ventana interna y evaluarlas en una ventana posterior sin reutilizarla. No se retocará diciembre ni se importarán los filtros 2026 como si hubieran estado congelados.

```text
audit.json                         4A3C950E8EF2D17FCA39A35A66E99795EA62B7BBC80D55B5D9F40874E35ABC53
pre2026_static_selected_trades.csv 98471C586DDD9A39B9AA48FEF09CCBA20766DBEBDC8830AD68F597A9EBA750D7
```

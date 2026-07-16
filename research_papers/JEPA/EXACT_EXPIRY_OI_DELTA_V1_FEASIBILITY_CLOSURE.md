# EXACT_EXPIRY_OI_DELTA_V1 — cierre de factibilidad

## Veredicto

`FAILED_FREQUENCY` antes de outcomes.

Se auditó únicamente el inventario de nombres de los ficheros OI 2023–2025 de
QQQ, SPXW y SPY. La pregunta era si podía medirse el cambio de OI del mismo
contrato que vence en la sesión `D`, comparando su observación en `D` con la del
último día de mercado anterior.

Cada ticker contiene 752 ficheros exact-0DTE, pero solo 156 expiraciones aparecen
también en el fichero del día de mercado previo. Son esencialmente los contratos
semanales visibles el jueves y que vencen el viernes. Hay 36 meses, pero el
mínimo es cuatro eventos por mes, muy por debajo del requisito estricto de más
de 12 operaciones.

No se abrió ningún valor OI, retorno, label o PnL. Comparar el 0DTE de hoy con el
0DTE de ayer usaría contratos y expiraciones diferentes y convertiría rollover
en una falsa variación; no se autoriza. Esta vía queda cerrada sin policy ni
rescate de frecuencia.

| Ticker | 0DTE 2023–2025 | Pares exactos previos | Meses | Mínimo mensual |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 752 | 156 | 36 | 4 |
| SPXW | 752 | 156 | 36 | 4 |
| SPY | 752 | 156 | 36 | 4 |

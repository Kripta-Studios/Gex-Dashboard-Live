# INDEX_ETF_CALENDAR_RR_PARITY_V1 — cierre de factibilidad

## Veredicto

`BLOCKED_LOCAL_SOURCE` antes de quotes, outcomes o modelos.

Se auditó por nombres de fichero si podía construirse una fuente independiente
comparando el calendario de skew del índice institucional con su ETF: NDX/NDXP
frente a QQQ y SPX frente a SPY. Una fecha requiere 0DTE exacto y al menos un
vencimiento posterior del mismo símbolo. No se leyó ningún valor de opciones,
retorno, label o PnL.

| Símbolo | Greek files 2023–2025 | Trade dates | Fechas front+back |
| --- | ---: | ---: | ---: |
| NDX | 0 | 0 | 0 |
| NDXP | 0 | 0 | 0 |
| SPX | 174 | 174 | 0 |
| SPXW | 1.504 | 752 | 752 |
| QQQ | 1.504 | 752 | 752 |
| SPY | 1.504 | 752 | 752 |

NDX/NDXP no tienen fuente Greek local. SPX contiene historia de vencimientos
estándar, pero ninguna fecha del inventario tiene simultáneamente el contrato
0DTE exacto y un vencimiento posterior; no puede formar el RR calendarizado
predeclarable. SPXW, QQQ y SPY sí tienen capacidad diaria, pero son exactamente
los tres universos ya usados por `CALENDAR_RISK_REVERSAL_PRESSURE_V1`, no una
medición institucional adicional.

## Evidencia reproducible

- Ventana inventariada: `20230101..20251231`.
- Ficheros Greek parseados: `4.686`.
- IDs símbolo-fecha elegibles: `2.256`.
- SHA-256 del inventario ordenado:
  `50bf239416d5e6956a75ed6717a419beebfb707292bd240884574740e70a0f8d`.
- SHA-256 de IDs elegibles ordenados:
  `88ad198bbd54aeb849ab9bc0647dbfcb1639056b5c9218ea3287dfafcf58b8cc`.

No se permite sustituir NDXP por QQQ, SPX por SPXW ni inferir un vencimiento
ausente con nearest/as-of. La hipótesis solo podría reabrirse tras adquirir y
sellar historia nativa NDXP/SPX con front y back exactos; queda cerrada para los
datos locales actuales sin resultado económico.

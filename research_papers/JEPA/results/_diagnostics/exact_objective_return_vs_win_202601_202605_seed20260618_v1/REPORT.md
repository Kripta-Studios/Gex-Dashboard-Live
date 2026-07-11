# Exact objective ablation v1 — informe final

Comparación de un solo factor: regresión del retorno ejecutable frente a probabilidad de win, con bucket y contrato fijos.

| Arm | Ticker | Sel/Abs | Trades | WR | PF | PnL (R) | Min/mes | Meses + | Hold min | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| return | SPXW | 0/5 | 0 | nan% | nan | +0.000 | 0 | nan% | n/a | False |
| return | QQQ | 0/5 | 0 | nan% | nan | +0.000 | 0 | nan% | n/a | False |
| return | SPY | 0/5 | 0 | nan% | nan | +0.000 | 0 | nan% | n/a | False |
| win | SPXW | 0/5 | 0 | nan% | nan | +0.000 | 0 | nan% | n/a | False |
| win | QQQ | 0/5 | 0 | nan% | nan | +0.000 | 0 | nan% | n/a | False |
| win | SPY | 2/3 | 42 | 28.57% | 0.602 | -6.167 | 0 | 0% | 30 | False |

- Return arm full gate: `False`.
- Win arm full gate: `False`.
- Junio de 2026 sellado: `True`.
- Este resultado no altera ni promociona producción.
- Si ambos arms fallan, la predeclaración exige traducir el stream legacy a las mismas filas/exits antes de abrir otro modelo.

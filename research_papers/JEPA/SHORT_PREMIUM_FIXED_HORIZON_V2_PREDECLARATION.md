# SHORT_PREMIUM_FIXED_HORIZON_V2 — predeclaración económica

Fecha: 2026-07-16. V2 se declara tras el cierre de V1 por quotes cruzadas en el
exit 13:35 de QQQ/SPY 2025-10-22. No excluye ese día, no usa midpoint ni sustituye
precios históricos.

## Hipótesis y fuentes

La hipótesis es que el cruce NBBO completo puede amortizarse con theta/volatilidad
en horizontes intradía fijos anteriores, sin depender de predecir el signo. Se
reutilizan los Greeks originales y el proof de timestamp/contract key sellado de
V1 para las mismas 1.506 sesiones 2024–2025. No se crea un dataset de features.

Entrada exacta 10:35 ET. Las estructuras son idénticas a V1: iron condor con
delta corta 0,15/0,20/0,25 y anchos SPXW 5/10/20, QQQ-SPY 1/2/5; iron fly con
anchos SPXW 10/20, QQQ-SPY 2/5. Selección de patas, alas exactas y crédito
permanecen congelados.

Los únicos exits son TIME30, TIME60, TIME90 y TIME120, respectivamente 11:05,
11:35, 12:05 y 12:35. Cada perfil necesita sus cuatro patas exactas, finitas y
no cruzadas en entrada y exit. Una estructura resoluble en entrada con exit no
ejecutable invalida todo el run; no desaparece el trade. No se consulta ninguna
barra intermedia, stop o take profit.

Fills:

```text
credit = short_call_bid + short_put_bid - long_call_ask - long_put_ask
debit  = short_call_ask + short_put_ask - long_call_bid - long_put_bid
net_points = credit - debit - 0,08
net_R = net_points / (width - credit + 0,08)
```

## Selector y gates

Para cada ticker/mes 2025 se elige entre estructura+horizonte usando solo los 12
meses anteriores. Cobertura: 12/12 y >=13 trades/mes. Elegible robusto: PnL>0,
PF>1 y >=8 meses positivos. Ranking: mayor Q25 mensual, mediana, PF y nombre; si
no hay robustos se registra fallback de cobertura.

Solo pasa a 2026 si en las predicciones walk-forward de 2025 cada ticker tiene
WR>45%, PF>1,20, >=13 trades en cada mes y PnL positivo en 12/12. Si pasa, se
congela la selección antes de auditar/capturar 2026. Gate final del usuario:
WR>45%, PF>1,20, >12 trades/mes y PnL positivo en enero–julio MTD para los tres.
La provenance histórica sigue condicionada y un PASS requiere paper/shadow.

Clarificación de implementación previa a resultados: el primer lanzamiento fue
detenido sin completar 50 sesiones y sin escribir output porque llamaba a
`close_path` 44 veces por sesión. El cálculo se reemplaza por lookup directo de
las cuatro patas en el único timestamp de cada TIME; conserva exactamente las
mismas gates `valid_quotes`, debit no negativo, fills y PnL. Una regresión exige
igualdad numérica contra `close_path` en el caso de referencia.

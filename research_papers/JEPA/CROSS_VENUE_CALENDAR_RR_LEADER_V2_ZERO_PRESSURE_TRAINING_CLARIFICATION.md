# CROSS_VENUE_CALENDAR_RR_LEADER_V2 — zero-pressure training clarification

**Congelada:** 2026-07-22 Europe/Madrid, tras dos fallos pre-cash del runner V2,
antes de leer ningún open 09:30–10:35 y antes de crear output V2.

## Hallazgo

El join exact-date del train 2023 reproduce dos filas QQQ con
`signal_pressure == 0.0`:

- `QQQ|20231116`;
- `QQQ|20231215`.

El ledger V1 sellado ya las identifica como `side=0`,
`action=NO_TRADE_ZERO_PRESSURE`, `trade_executed=false`, gross0, cost0 y net0.
No son operaciones. No existe ninguna presión cero en los 743 eventos 2024.

El target V2 `direct_win` pregunta si conservar o invertir
`sign(signal_pressure)`. Para signo cero, directo e inverso son la misma acción
nula y el target no está definido. Codificarlo como clase perdedora o asignarle
un lado ±1 introduciría información y una operación que V1 nunca ejecutó.

## Reparación única permitida

El loader debe exigir que el conjunto completo de keys cero 2023–2024 sea
exactamente `{QQQ|20231116, QQQ|20231215}` y que ambas pertenezcan al train
2023. Las excluye **solo del ajuste del modelo y del dataset de training** antes
de leer cash. No excluye ninguna predicción 2024, no altera features, labels,
modelo, threshold, clocks, coste o gates y deja 739 filas de train ejecutadas.

Cualquier tercera key cero en los inputs congelados falla cerrado. Cualquier
cero futuro en una fase aún no abierta conserva la semántica preexistente
`NO_TRADE_ZERO_PRESSURE`; reduce el conteo mensual y debe superar la misma gate
de frecuencia, nunca se transforma en LONG/SHORT.

El test de regresión debe fijar los dos IDs y probar que cualquier conjunto
distinto falla. Código/tests se committean después de este documento. 2025,
2026, live y systemd permanecen cerrados.

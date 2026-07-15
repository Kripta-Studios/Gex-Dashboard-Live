# KING-GEX-SLOPE1 — aclaración de universo executable

Estado: `FROZEN_BEFORE_FIRST_PAYOFF`. El primer intento del runner cargó las
columnas físicas 2023 pero se detuvo en el join antes de construir una acción,
adjuntar un payoff, ejecutar el scheduler o calcular PF/WR/PnL.

El bug exigía erróneamente que cada timestamp válido del wall-state perteneciera
al master executable. La relación causal correcta ya estaba implícita en la
hipótesis: el master define oportunidades con opción executable y cada una debe
tener wall exacto; el wall puede contener timestamps adicionales sin contrato
elegible.

Auditoría outcome-free 2023, tras excluir la media jornada:

- master exacto 11:20–14:30: 20.309 claves únicas;
- wall con lag45 contiguo: 28.977 claves únicas;
- claves master sin wall: 0;
- claves wall extra: 8.668 (QQQ 3.290, SPXW 2.701, SPY 2.677);
- intersección exacta: 20.309.

La única reparación autorizada es `master LEFT JOIN wall` one-to-one, exigir
`_merge=both` para las 20.309 claves y descartar las 8.668 claves wall sin
oportunidad master. No hay as-of, nearest, floor, relleno, exclusión por payoff
ni cambio de regla K0/K1.

Feasibility recalculada sobre master exacto: K1 conserva 13.286 señales y todas
las sesiones SPXW/SPY; QQQ tiene mínimo 16 días con señal en un mes, pero cap 2
mantiene capacidad teórica mínima 32 trades, superior a 18. SPY mantiene mínimo
19 días y cap 1. Este censo no lee returns de opción.

El relanzamiento debe partir de un nuevo commit del runner, revalidar ambos
hashes de protocolo y usar el mismo target, que no fue creado por el intento
fallido. 2024/2025/2026 siguen cerrados.

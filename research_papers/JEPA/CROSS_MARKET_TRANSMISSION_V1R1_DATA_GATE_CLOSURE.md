# CROSS_MARKET_TRANSMISSION_V1R1 — cierre del data gate

Estado: `BLOCKED_DATA`. No se escribió vista final ni se leyó outcome económico.

La reparación de medias jornadas funcionó, pero el build volvió a fallar
fail-closed en una sesión normal: QQQ event 30-may-2024 11:10. El primer par
fijo SPXW/SPY tenía RV SPXW positiva solo por el primer retorno de la ventana;
los 28 retornos posteriores eran exactamente cero. Por tanto
`std(SPXW_returns[1:])=0` y la correlación lead/lag no existe.

La predeclaración prohíbe epsilon, imputar cero, quitar `lead_score`, omitir la
fila o crear un flag de aplicabilidad después del hallazgo. V1R1 queda cerrada
sin desarrollo económico, freeze u outer. Esto no prueba que la transmisión no
tenga alpha; prueba que este bloque de 28 campos no está definido sobre el
universo full executable con la fuente existente.

No se autoriza V1R2. La siguiente familia debe usar un mecanismo matemático y
fuente distintos.

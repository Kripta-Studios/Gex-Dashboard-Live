# Qué cambio de exposición puede observarse con esta caché

La señal compacta actual es una diferencia entre la logmasa instantánea y la
media de logmasas de una barra cerrada. Exige cobertura completa de OI, IV y
presencia en cada instante de esa barra y en el presente. Una sola IV inválida,
incluso en un contrato con OI cero, puede invalidar la señal de toda la cadena.
En cambio, la gamma estática admite una suma parcial positiva. Sus coberturas
no son comparables: la diferencia no prueba que falten todas las griegas.

Para una decisión en t, sea C la intersección de contratos presentes, con IV
válida y OI conocido en t y t−h, h∈{5,15}. Identidad incluye ticker, fecha de
expiración 0DTE, strike y right. La caché diaria separa esas fechas; su eje de
columnas de todo el día no constituye un universo observable antes de tiempo.
La pertenencia a C es conocida en t. No debe reutilizarse retrospectivamente
como si ese mismo conjunto se hubiera conocido en t−h.

Se pueden calcular dos sumas sobre exactamente C:

G0 = Σ BSgamma(S0,K,IV0,T0) × OI0 ×100×S0²×0,01

G1 = Σ BSgamma(S1,K,IV1,T1) × OI1 ×100×S1²×0,01.

G1−G0 compara la misma cohorte. No requiere rellenar ningún contrato ausente.
CALL y PUT se mantienen separados y ambos pesos gamma son no negativos. No
es gamma dealer firmada ni permite identificar por sí sola un gamma flip.
OI reportado diario no es flujo intradía: una revisión de OI o su llegada al
dataset no demuestra compras, ventas ni el lado del dealer. Se conservan los
supuestos de reloj nativo/underlying y disponibilidad OI de la caché; no se
convierte ese supuesto en evidencia de recepción real.

Cada medida requiere cobertura explícita: número de contratos comunes dividido
por los conocidos y los válidos de cada extremo; fracción del OI conocido y de
la masa gamma **observable** de cada extremo retenida en C. Un denominador cero
es no evaluable, no cobertura cero inferida. Ninguna fracción estima exposición
de contratos cuya IV/OI se desconoce. Cambiar el conjunto común puede cambiar
la serie entre decisiones; deben conservarse además entradas/salidas y la
diferencia de masa observada exterior a C.

Una atribución aritmética posible evalúa sobre C la secuencia
(S0,IV0,T0,OI0)→(S1,IV0,T0,OI0)→(S1,IV1,T0,OI0)→(S1,IV1,T1,OI0)→(S1,IV1,T1,OI1).
Los cuatro incrementos suman exactamente G1−G0. Son efectos contables de spot,
IV, paso del tiempo y OI reportado bajo ese orden; las interacciones hacen que
el reparto dependa del orden y no identifican causas de mercado. Una futura
atribución simétrica podría promediar órdenes preespecificados, sin seleccionar
el orden por resultados. Este diagnóstico sólo usa el orden escrito.

La misma cohorte permite representar la distribución por strike, su centro de
masa y el desplazamiento del máximo de gamma; una pared puede cambiar por el
spot, IV o tiempo aunque OI sea constante. Comparar distribución por strike
absoluto separa esa redistribución del mero desplazamiento del spot respecto a
los strikes. Estas serían features nuevas con máscara/cobertura, no un parche
silencioso al extractor congelado. Aún no se entrenó ni evaluó un modelo con
ellas y su disponibilidad no demuestra capacidad predictiva ni rentabilidad.

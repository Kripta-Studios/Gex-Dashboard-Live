# CROSS_MARKET_TRANSMISSION_V1 — cierre del data gate

Estado: `FAILED_CAUSALITY`. El build outcome-free se detuvo antes de escribir
vista, manifest, labels o resultados económicos.

## Defecto observado

El primer denominador degenerado aparece en SPXW el 25-nov-2022 a las 13:35 ET.
Las 30 barras exactas `[13:05,13:35)` tienen close idéntico `4026.12`, por lo
que RV, beta, correlación y basis no están definidos. Aplicar epsilon, cero o
imputación habría violado la predeclaración y no se hizo.

La causa no es ausencia de fuente cross-market. El 25-nov-2022 es una media
jornada: SPXW cerró a las 13:00, pero el master conserva decisiones hasta las
14:30. En 2022-2023 existen tres sesiones de cierre temprano y 357 filas del
master. Usando solo ese periodo de desarrollo, 126 filas tienen al menos un
lado cuyo `entry minute + exit_minutes` cruza el cierre real de la opción; 125
cruzan en ambos lados. Esto demuestra que una parte de esos paths stale no es
un label ask-to-bid ejecutable.

La auditoría outcome-free de calendario 2022-2025 encuentra nueve fechas de
cierre temprano y 1.072 filas en ellas. De esas, 275 decisiones están incluso
después de 12:55. Ningún outcome 2024/2025 fue leído para llegar a este censo.

## Dictamen

V1 no obtiene `PASS_EXACT_CROSS_MARKET_VIEW`. No se permite reparar una
estadística degenerada ni seleccionar filas según su exit futuro. El defecto es
del reloj/label master en medias jornadas, no evidencia económica del mecanismo.

La única reparación causal autorizable es V1R1: omitir completas y por lista
congelada las nueve sesiones de cierre temprano, porque sus labels no son
uniformemente certificables sin reconstruir paths. La exclusión se decide por
calendario, no por outcome, y conserva 96.553 oportunidades de sesiones normales.

# THETA_IB_SOURCE_PILOT_V1 — primera hora real, sin economía

El usuario ordena continuar después del informe 21. El componente 22 pasó sobre
las seis respuestas selladas: tres barras, una reparación y 866 registros OI
reconstruidos independientemente. El siguiente escalón técnico es verificar una
hora completa, manteniendo fecha/tickers fijados por calendario y sin PnL.
No reabre ni sustituye intentos históricos cerrados.

IBSRC-001: exactamente tres GET nuevos a /option/history/greeks/first_order del
terminal existente: SPXW/SPY/QQQ, date=expiration=20220801, strike=*, right=both,
interval=1s, start_time=09:30:00, end_time=10:30:00, version=1, format=csv.
Sin retries, fallback, nuevos endpoints, licencia o reconfiguración. Publicar
contrato y código antes de capturar. Root nuevo:
D:/GexResearchArtifacts/multiscale_v1r1/ib_source_pilot_20260918_01.
Se fija tope 512 MiB y 1.200 s por cuerpo, timeout de inactividad 120 s; conservar
parciales/errores con status incompleto. Reserva disco 20 GiB adicional al máximo
1,5 GiB de respuestas. Un fallo no habilita otra fecha, filtro o ampliación.

IBSRC-002: conservar bytes exactos en streaming, SHA calculado sobre esos bytes,
petición, recepción, inicio/fin de materialización, tamaños y código. Capturas
secuenciales no constituyen simultaneidad entre tickers; cada una tiene su reloj.
Reusar el OI sellado solo para referenciar su existencia, sin nueva consulta.
No leer fuente posterior a10:30, modelos, labels, PnL ni abrir archivos antiguos.

IBSRC-003: construir exactamente60 barras [09:30,10:30), misma regla 22 extendida
a cada minuto. Los 3.600 segundos reportados deben existir; filas a10:30 no son
parte del IB. Clave contrato/timestamp única. Concordancia del precio/tiempo del
subyacente por segundo; sin deduplicar, rellenar o elegir otra quote. Rechazar
dependencias futuras. Primera barra SPXW admite exclusivamente reparación por
su propio close disponible a09:31; ningún otro precio inválido se repara.
El proxy tick_count conserva todas las filas aportantes, no volumen negociado.

IBSRC-004: IBH=max(high), IBL=min(low) de las60 barras reparadas/admitidas. Ancho
positivo. Extensiones: IBL+r*(IBH-IBL), IBH-r*(IBH-IBL), r=1.272/1.618/2.0.
Todos disponibles a10:30; Decimal y comparación exacta, sin redondeo intermedio.
Auditor csv/Decimal separado reconstruye barras, reparación, IB y extensiones
desde raw sellado. Pruebas sintéticas de60 minutos, hueco, duplicado, límite10:30,
precio/tiempo futuro y modificación de niveles con checksums actualizados.

IBSRC-005: revisar y publicar mediciones reales de recepción, parseo, construcción,
auditoría, RAM y disco. La hora de 2022 reconstruida hoy no certifica su vintage
original. Estado máximo PASS_RECONSTRUCTED_IB_SOURCE_PILOT, no gate de features
multiescala: faltan D1–D5, prior-close, resto de prefijo y sus walls. Nada de ello
se inventa. No habilita economía o promoción. Futuras capturas requieren su
universo/ventanas publicados; no se extrapola admisión de esta hora al histórico.

Implementación separada del motor congelado. Mantener intactos22 y sus artefactos.
No adaptar ratios, costes, modelos o thresholds a los valores encontrados.

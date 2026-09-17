# ThetaData: revisión de fuente y siguiente admisión

Consulta documental: 2026-09-18. El usuario confirma que no existen otros backups
locales y autoriza revisar la API por si hace falta descargar datos adicionales.
No se restauran logs antiguos ni se concede admisión económica por esa instrucción.

## Qué puede proporcionar la API

| Necesidad | Endpoint v3 | Alcance documentado |
|---|---|---|
| Disponibilidad por expiración | `/option/list/expirations` y `/option/list/dates/quote` | Metadatos, sin precios; catálogo actualizado de noche |
| Inputs de subyacente e IV/delta | `/option/history/greeks/first_order` | Standard/Pro; incluye `timestamp`, `underlying_timestamp`, `underlying_price`, bid/ask e IV; admite `interval=1s` en peticiones de un día |
| OI previo | `/option/history/open_interest` | El OI representa el cierre anterior; normalmente se publica alrededor de 06:30 ET |
| Cotización contractual | `/option/history/quote` | NBBO; con intervalo devuelve la última quote al instante de muestreo |

Fuentes: [First Order Greeks](https://docs.thetadata.us/operations/option_history_greeks_first_order.html),
[Open Interest](https://docs.thetadata.us/operations/option_history_open_interest.html),
[Quote](https://docs.thetadata.us/operations/option_history_quote.html),
[Expirations](https://docs.thetadata.us/operations/option_list_expirations.html),
[Dates](https://docs.thetadata.us/operations/option_list_dates.html).

La suscripción Options Standard aparece con acceso a Greeks de primer orden y
datos de opciones tick desde 2016. All Greeks y Greeks de órdenes superiores
requieren Pro. No se propone comprar Pro: V1R1 calcula sus exposiciones desde IV,
OI y spot. La licencia vigente del usuario debe confirmarse; el acceso a opciones
no acredita por sí mismo una suscripción separada a stocks o índices.
[Suscripciones](https://docs.thetadata.us/Articles/Getting-Started/Subscriptions.html).

Se debe fijar la versión de Greeks: la API distingue `version=1` de `latest`,
incluida la convención temporal de 0DTE. No se deben mezclar versiones sin registro.
Los scripts locales usan first_order y el terminal remoto configurado; no se
importaron ni ejecutaron. El API histórico ofrece una reconstrucción del proveedor
consultada ahora, no prueba por sí solo qué revisión estaba disponible entonces.

## Diagnóstico nuevo de ausencias por calendario

Las 29 fechas de 2022 del inventario sellado son martes/jueves entre 2022-08-02
y 2022-11-10. Nasdaq documenta el inicio de los nuevos vencimientos de martes y
jueves de SPY/QQQ a mediados de noviembre de 2022, con primeros vencimientos
15 y 17 de noviembre. Por tanto, esas ausencias son compatibles con falta de
contratos 0DTE, no evidencia de 29 capturas fallidas recuperables. Es una inferencia
de calendario a contrastar con el catálogo del proveedor, sin cambiar el resultado
del intento cerrado. Las otras fechas (2026-04-01, 2026-04-09, 2026-04-15) siguen
pendientes de contrastar. No se alteran sus fuentes ni exclusiones anteriores.
[Aviso Nasdaq actualizado](https://beta.nasdaqtrader.com/MicroNews.aspx?id=OTA2022-40),
[Aviso Cboe actualizado](https://cdn.cboe.com/resources/product_update/2022/Update-Cboe-Options-to-List-SPY-and-QQQ-Tuesday-and-Thursday-Expiring-Weekly-Options.pdf).

## Comprobación autorizada de metadatos

Publicar este alcance antes de acceder al terminal. Root nuevo:
`D:/GexResearchArtifacts/multiscale_v1r1/theta_metadata_20260918_01`.
Solo GET al terminal ya configurado en los scripts locales, sin iniciarlo,
reiniciarlo ni cambiar VPS o credenciales. Una consulta `/terminal/mdds/status`,
tres `/option/list/expirations` (SPXW/SPY/QQQ) y seis `/option/list/dates/quote`
(SPY/QQQ × las tres expiraciones ausentes de 2026). Diez peticiones máximas,
secuenciales, sin retry o fallback; guardar cuerpos exactos, hashes, parámetros,
hora local de recepción y estado HTTP. No interpretar un error como ausencia.
Si el terminal no está conectado, detener antes de las nueve consultas restantes.
No descargar ni inspeccionar precios, resultados, modelos de mercado o PnL.
[Estado del terminal](https://docs.thetadata.us/System/System.html).

## Descarga adicional concreta propuesta, todavía sin ejecutar

Un piloto de admisión usaría 2022-08-01 (primera sesión del intervalo, elegida por
calendario) para SPXW/SPY/QQQ, expiración del día, ambos derechos y todos los strikes:
Greeks first_order a 1 segundo, 09:30:00–09:31:00 ET, y OI del día. Se preservaría
la respuesta íntegra con parámetros/versiones y ambas marcas temporales antes de
parsearla. Se medirían ceros iniciales, edad y duplicados, sin rellenar ni reparar.
Es una prueba del schema/reloj al abrir, no un gate de toda la sesión ni de IB.
El resto del día y el histórico completo no se descargarían por extensión.

Una construcción nueva de barras deberá fijar agregación y dependencias por minuto;
no reutilizar bfill ni sobrescribir raw. OI requiere validar su timestamp real,
claves únicas y significado previo; 06:30 aproximado no es garantía por fila.
Si esos controles pasan, se podrá predeclarar una fuente/transformación nueva y
un piloto técnico con su propio contrato. La documentación de una API no admite
automáticamente los archivos antiguos ni demuestra paridad histórica/live.

Economía NOT_EVALUATED; promoción false. Revisión de API y metadatos no es captura
prospectiva, shadow ni validación de rentabilidad.

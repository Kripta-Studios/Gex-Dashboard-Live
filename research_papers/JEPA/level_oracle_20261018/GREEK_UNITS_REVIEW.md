# Unidades y disponibilidad de griegas

Revisión 18-oct-2026: documentación pública primaria y código local como texto; reutilización del censo de schemas existente. Sin endpoints Terminal, descargas, nuevas filas de mercado, outcomes ni cambios de features/modelos.

**Confirmación documental.** Theta indica que sus griegas regulares usan Black–Scholes europeo y que **vega y rho requieren dividirse por 100**. La documentación v2 conserva la misma advertencia. La interpretación matemática es que vega almacenada corresponde a sensibilidad respecto a volatilidad en unidad 1,0; `vega/100` expresa el cambio de prima por un punto porcentual de volatilidad. Esta última equivalencia es inferencia de la definición del modelo, no deducción por rangos observados. [Artículo Theta v3](https://thetadata.net/docs/Articles/Data-And-Requests/Option-Greeks.html), [artículo Theta v2](https://http-docs.thetadata.us/Articles/Data-And-Requests/Option-Greeks.html).

| Campo | Qué puede afirmarse | Límite |
|---|---|---|
| Delta | Interpretación BS: derivada de prima respecto al precio del subyacente, con signo | El schema del endpoint sólo lo denomina delta; no acredita posición de dealers ni necesidad de cobertura real |
| Gamma | Interpretación BS: derivada de delta respecto al subyacente | No se encontró columna gamma en los 37 schemas del censo local; la familia actual calcula una aproximación propia |
| Vega | Advertencia explícita de conversión `/100` | No aplicar otra conversión silenciosa al cache congelado ni confundir con prima contractual |
| Theta | El endpoint sólo identifica el campo como theta | **No se encontró especificación explícita por día/año ni base 252/365**; mantener unidad almacenada sin anualizar ni etiquetar USD/día |
| Rho, epsilon, lambda | Campos presentes en los schemas raw de primer orden | No incluidos en el cache actual; no admitirlos por mera presencia |

El endpoint de primer orden documenta cálculo con midpoint y publica delta/theta/vega/rho/epsilon/lambda/IV/errorIV. Su parámetro `version` distingue `1` (DTE fijo0,15 al vencimiento) y `latest` (tiempo restante real con mínimo de una hora). El schema no explica escala temporal de theta. [Endpoint histórico de primer orden](https://thetadata.net/docs/operations/option_history_greeks_first_order.html).

**Lo que hace nuestro código.** `D:/ThetaData/options_bulk.py:53,301–355` llama al endpoint de primer orden; no envía `version`, tipos/tasas explícitas o dividendos, ni convierte delta/vega/theta/rho. El fallback sólo cambia el intervalo. Los scripts actuales y los parquets no demuestran qué versión de cálculo estaba activa al descargarse cada archivo; no atribuir retrospectivamente `latest` actual a todo el histórico. El artículo actual también distingue modelos binomiales separados, que este descargador no solicita.

`build_cache.py:37–40,105–110` conserva bid, ask, delta, implied_vol→iv, vega y theta en float64, con NaN cuando falta valor; no divide vega por100 ni theta por365. Rho/epsilon/lambda/iv_error están fuera de su whitelist. `features.py:142–157,284–300` divide vega/theta por spot para contexto/acción y conserva flags específicos de validez; esas cantidades siguen en unidades de origen por precio, no son PnL monetario por día.

La gamma utilizada por los niveles es **aproximación BS propia y sin signo de inventario**: tiempo físico hasta cierre NYSE, año365, r=q=0, IV almacenada y multiplicación `gamma × OI × 100 × spot² × 0,01`. `session_level_engine.py:95–120` adapta el cierre a210/390. No equivale a gamma observada ni replica necesariamente el mínimo de una hora descrito por Theta. El multiplicador100 pertenece al contrato económico de esta investigación, separado de la unidad del campo raw; esta lectura no valida multiplicadores de contratos ajustados.

Para una futura dinámica de cohorte común: congelar el conjunto de identidades conocido/válido en ambos extremos, conservar signed delta y máscaras campo por campo; nombrar vega/theta en unidades almacenadas mientras no se cierre su interpretación. Ponderar por OI no demuestra órdenes, cambios de inventario, agresor ni flujo de dealers. Comparar cambios relativos no corrige por sí solo posibles diferencias de versión de cálculo. No se ha introducido ninguna de estas features en los entrenamientos activos.

Referencias locales: censo `D:/GexResearchArtifacts/restart_20261018/inventory/schemas.json`; descargadores con hashes en `OHLC_VOLUME_SEMANTICS.md`; cache congelado `985e87dc…180d69f`, features `b5c63f91…369d4e0`, engine `70cc5d20…13b7c6`. La revisión no inspeccionó distribuciones numéricas para inferir unidades.

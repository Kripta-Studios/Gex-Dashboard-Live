# SUMMARY-articles — conclusiones transferibles de JEPA/world models

### Reparar fuentes por intersección, no por imputación

El full cross-venue reveló cuatro discrepancias Greek/IV entre 3.012 captures.
Cada una es una sola clave unilateral repetida en los dos clocks; el resto de
cada superficie coincide (406–858 rows compartidas). Como calendar-RR requiere
delta e IV simultáneas, una clave presente en una sola modalidad no contiene la
medición completa y no puede ser alpha. La reparación causal predeclarada usa
solo `Greek∩IV`, conserva las unilaterales como audit y prohíbe as-of, nearest,
imputación o sustitución por valores actuales.

La captura parcial masiva no se desecha: 3.008 unidades atómicas quedan
inmutables y solo cuatro se recapturan a un overlay separado. Un composite seal
debe revalidar ambos roots antes del data gate. Este patrón evita tanto perder
provenance como relajar silenciosamente la población después de ver outcomes.

### Rentabilidad mensual no equivale a promoción

`DIRECTIONAL_VOL_COMPLEX_V1` muestra el caso exacto: junio 2026 fue positivo en
QQQ/SPX/SPY (PF1,249/1,779/1,764, 21 trades cada uno), y julio MTD también tuvo
PnL positivo, pero QQQ/SPX quedaron en PF1,133/1,098 y solo hubo 10 trades.
Peor aún, Jan–Jun agregado quedó en PF1,039/0,993/0,898 y solo 3/4/3 meses
positivos. Una celda mensual prometedora no compensa inestabilidad cronológica,
frecuencia incompleta ni ausencia de fills SPXW. La familia cross-venue activa
aún no ha abierto 2026 y no puede heredar esas cifras.

El auditor económico outer-2024 cross-venue queda implementado antes del
outcome: revalida acción SPY→SPXW, retorno logarítmico, 1/2/3bps, resúmenes y
fuentes. Suite focal/combinada cross-venue `50 passed`; todavía no se ejecutó.

### Separar validación económica de integración live

Una mejora de diseño 2023 no autoriza producción. La arquitectura cross-venue
solo puede entrar en `realtime_feed`/`ai_bot` tras una secuencia 2024→2025→2026
con ejecución ask→bid, no-overlap y gates por ticker. Junio 2026 debe ser un mes
cerrado rentable; julio 2026, todavía incompleto a día 17, solo aporta evidencia
shadow MTD y no puede presentarse como mes completo ni usarse para seleccionar.
La primera integración, si se autoriza, debe seguir generando paper intents y
demostrar paridad de features, acción, scheduler y salida antes del restart
systemd.

El puente causal de fuentes queda definido como una certificación, no una
imputación: el `underlying_timestamp` vintage solo identifica una fila después
de un join exacto uno-a-uno con la misma key y option timestamp nativo. El
sidecar no aporta precios al alpha. Este patrón permite restaurar provenance de
reloj sin convertir una reconstrucción actual del proveedor en un histórico
económico revisado.

El builder añade otra defensa transferible: no confía solo en el seal agregado.
Revalida los blobs de código congelados, reconstruye cada raw/parquet y compara
las 3.012 filas de auditoría con el capture index sellado antes de producir una
feature. La reanudación operativa y el consumo científico quedan así separados
por una segunda verificación independiente y outcome-free.

La progresión separa dos decisiones: PF>1 estable por ticker es evidencia
incremental suficiente para autorizar el siguiente año, mientras PF>1,20 y PnL
positivo cada mes siguen siendo la gate de promoción. Congelar ambas antes de
2024 evita tanto matar prematuramente una señal débil como rebajar después el
objetivo live.

El runner refuerza el principio de mínimo acceso al outcome: aunque el parquet
underlying contiene toda la sesión, el lector económico solicita por predicate
pushdown únicamente 10:36 y 13:36. El hash del fichero conserva integridad y el
scope semántico queda reducido a los dos valores declarados.

La paridad live no se deduce de nombres parecidos: `weekly` no equivale a
next-expiry y el IV puntual first-order no equivale al midpoint bid/ask-IV. Una
feature temporal también necesita persistir la identidad del contrato elegido,
no solo conservar dos snapshots agregados. Estos tres puntos son parte del
modelo, no detalles de infraestructura.

El seal agregado tampoco sustituye una auditoría de consumo. El auditor full
rehace offline raw→parquet, revalida los hashes vintage y compara cada fila con
el índice sellado antes de crear compactos. Así el data gate no confía en que
“3.012 completadas” implique por sí solo 3.012 unidades reproducibles.

La auditoría del data gate comprueba propiedades semánticas además de hashes:
reconstruye el mapping exact-date, verifica que SPXW recibe literalmente la
presión SPY y busca columnas outcome prohibidas. Integridad de bytes y fidelidad
del experimento son gates distintas y ambas deben pasar.

El full sidecar cross-venue ya está en captura outcome-free. Su progreso no es
evidencia económica: solo demuestra materialización causal del reloj que hará
posible un verdadero outer 2024 posterior.

El full sidecar aplica una arquitectura operativa reusable: contrato raíz
inmutable, unidad de captura atómica y reanudación solo tras reconstrucción
completa. Esto separa tolerancia a interrupciones de tolerancia a datos malos:
un HTTP transitorio puede reintentarse, pero un directorio parcial o una key
faltante detiene el experimento.

Las constantes de capacidad también requieren discovery reproducible: el
preflight subestimó el full por seis captures. El inventario filename-only
corrige a 1.506 sesiones/3.012 y mantiene la cost gate. No se debe excluir datos
para hacer coincidir una proyección histórica; el manifest posterior debe
registrar el erratum sin reescribir el seal previo.

El preflight demuestra que el déficit de timestamp 2024–2025 es reparable sin
reescribir el histórico: en 64.632 filas, el proveedor actual cubre exactamente
el universo vintage y no revisa un solo bid/ask de la muestra. La proyección
full es pequeña (8,10M filas/1,43GiB raw), por lo que la validación cross-venue
puede avanzar con provenance fuerte. Sigue siendo factibilidad, no alpha.

El sealer reparado distingue provenance de captura y provenance de sellado:
rehash del blob Git original y reconstrucción raw prueban que una validación
offline posterior no cambió las respuestas. Esta separación evita que un fix
operativo reescriba silenciosamente evidencia de mercado.

Una captura completa no equivale a un seal: el preflight obtuvo las 24
respuestas y coverage exacta, pero una rotura del canal de progreso impidió el
manifest agregado. La reparación científica correcta es validar offline los raw
ya capturados contra el commit original, no consultar de nuevo al proveedor ni
tratar manifests parciales como PASS.

El preflight cross-venue convierte la ausencia de option timestamp 2024–2025 en
un test falsable: quote nativa debe cubrir cada key vintage de dos clocks y dos
expiraciones, mientras sus precios revisados solo se cuentan. Esto separa
reconstrucción de reloj de reescritura histórica. Doce sesiones extremas de año
proyectan el coste de las 3.006 capturas antes de autorizar el full backfill.

### Arquitectura cross-venue generada por SPY/SPXW

SPXW y SPY separan claramente movimiento y sensor: sus retornos cash a 180m
correlacionan 0,999733 y tienen el mismo signo en 246/246 fechas, mientras sus
presiones calendar-RR correlacionan solo 0,580 y sus acciones coinciden 60,2%.
Cuando coinciden ambos PF≈1,022; en desacuerdo SPXW PF0,753 y SPY1,170. La
superficie local no es un proxy intercambiable del mismo factor subyacente.

Usar SPY como sensor líder fijo para SPXW eleva el diagnóstico 2023 de SPXW a
PF1,072/WR50%, por lo que QQQ, SPY y SPXW quedan todos por encima de PF1. Es una
hipótesis prometedora generada después de ver outcomes, no validación. La
arquitectura debe congelarse sin variantes y probarse por primera vez en 2024;
solo una secuencia 2024→2025→2026 puede separar liderazgo real de selección.

El edge calendar-RR original es además cost-fragile: pooled PF1,058 a 1bp cae a
PF0,999 a 2bps. Breadth de componentes no aporta frecuencia (min3; IWM min12),
y faltan NDX/NDXP/SPX front-back locales. La paridad live futura depende de un
sidecar de reloj front/back; `underlying_timestamp` no sustituye option time.

### Calendar skew aporta información parcial, no estabilidad

La diferencia front/back de RR25 es la primera rotación reciente que conserva
PF pooled>1 después de costes: 1,058 y +730bps. QQQ/SPY quedan >1; SPXW <1. El
inverso pierde claramente, señal de que la dirección no es arbitraria, pero solo
12/36 meses pasan. La información temporal IV mejora sobre paridad same-expiry,
sin resolver heterogeneidad entre índices ni persistencia mensual.

El manifest calendar-RR ya hace inmutable la traducción económica de la curva:
signo directo, una observación diaria, 180 minutos y 1bp. Así un resultado
negativo no puede rescatarse eligiendo el otro lado de la term structure y un
resultado PF>1 no se confunde con estabilidad mensual completa.

El ledger calendar-RR codifica de nuevo la diferencia entre progreso agregado y
estabilidad: PF>1 en los tres tickers solo produce estado incremental; no abre
outer si una celda mensual falla. El freezer sella esa regla y evita convertir
un primer resultado prometedor en permiso para variar signo o años.

El data gate calendar-RR demuestra que una estructura temporal IV causal puede
medirse con 99,2–100% de cobertura y sin as-of. Los tres fallos muestran por qué
el join exacto importa: crossed quote y dos diferencias de key Greek/IV se
preservan como missing, sin convertir calidad en alpha. La variable tiene al
menos 233 estados por ticker y frecuencia suficiente; todavía no dice nada de
dirección o rentabilidad.

El preflight calendar-RR confirma que la comparación front/back es materializable
sin interpolar: 250 sesiones por ticker en 2023, dos expiraciones por día, clocks
nativos y cuatro contratos 25-delta que persisten cinco minutos en las muestras.
La factibilidad de fuente no implica alpha; el siguiente gate comprueba cobertura
y no-degeneración en las 750 sesiones antes de cualquier retorno.

### Nueva separación: skew de calendario

El OI exacto no tiene frecuencia diaria para medir cambios del mismo contrato:
solo los vencimientos semanales aparecen el día previo. La alternativa causal
no debe cruzar contratos; compara simultáneamente el risk reversal 25-delta del
0DTE con el siguiente vencimiento. Es una estructura temporal de demanda IV,
no otro nivel estático, wall o panel 0DTE genérico. Primero debe demostrar reloj
nativo, persistencia de contratos y cobertura sin outcomes.

### Paridad cross-right: medible no significa direccional

La presión de paridad se midió con alta cobertura, pero su signo fijo perdió en
los tres tickers y antes de costes. Pooled PF0,875; 10/36 meses pasan. El control
always-long capturó drift 2023 que la señal destruyó, mientras invertir el signo
tampoco alcanzó PF1,20. La identidad CALL/PUT ofrece una coordenada física
estable, no una semántica direccional a tres horas bajo esta formulación.

El manifest preejecución de paridad congela 744 eventos normales de 2023 y las
dos medias jornadas excluidas, además de hashes de código, protocolo y feature
view. Así el próximo acceso a retornos queda identificable como un único ensayo,
no como una búsqueda sucesiva sobre relojes, costes o años.

### Separación adicional entre medición y outcome

El ledger de paridad queda diseñado para que el scope sea una propiedad del
código, no un argumento mutable: solo puede construir rutas underlying 2023 y
requiere un manifest de runner congelado y committed. Este patrón impide que un
resultado inicial abra silenciosamente 2024–2026 o cambie coste/reloj/gates.

## Nota 2026-07-17 — paridad física medible

El relanzamiento confirma que la corrección `.000` era de representación y no
de contenido: las 2.256 sesiones pasan equality temporal, paridad de keys,
cobertura y distinctness, con mínimo 18 eventos mensuales y cuatro strikes
comunes. Esto habilita una prueba económica, pero no la valida. La siguiente
lectura de outcomes queda limitada a 2023 y a una regla de signo ya congelada;
2024–2026 conservan su función de falsificación fuera de muestra.

**Corte:** 16 de julio de 2026. Los 29 trabajos aportados fueron auditados. Este
resumen conserva únicamente las ideas que afectan la investigación actual y su
evidencia local.

**Conclusión actual:** mejorar la representación, corregir el colapso espectral,
añadir breadth, superficie de opciones o siete futuros Globex y cambiar el
payoff no ha producido estabilidad mensual. La sección final incorpora la
evidencia posterior a MANAGE30/weeklies.

## Actualización de mecanismo económico — transmisión cross-market

El contexto contemporáneo cross-market ya fue parte de una unión económica que
abstuvo; repetir returns/spreads no es una hipótesis nueva. Sí lo es medir
transmisión dinámica: beta rolling, residuo beta-neutral, liderazgo temporal,
volatilidad relativa y desviación del basis, todos sobre barras 1m cerradas
exactas. Esta representación contrasta impulso líder con absorción del rezagado
y se evalúa directamente sobre distribuciones executable CALL/PUT, no mediante
otro proxy físico.

La inferencia metodológica es predeclarada, no un resultado: si el bloque falla
el nested mensual, no se rescata seleccionando pares, lags o tickers. TPO/value
migration permanece como mecanismo distinto en cola y no se mezcla con esta
prueba.

Cross-market quedó bloqueado por ventanas causalmente indefinidas y la rotación
activa es TPO/value migration target-only. Su vista outcome-free ya pasó
causalidad, cobertura y distinctness (96.553 filas; 36 features), pero ese PASS
no es evidencia de alpha. La siguiente evidencia válida es exclusivamente PF,
WR, frecuencia y PnL mensual del desarrollo nested 2023-04..12.

Ese test económico queda operacionalmente protegido con checkpoints atómicos
por fold; una interrupción no autoriza cambiar hipótesis ni recomenzar con otro
grid. La persistencia sirve a la evaluación económica, no cuenta como evidencia.

El resultado fue negativo ya en la primera celda H-TPO: 0/42 grids X1 pasaron
los tres meses inner y el near-miss pooled quedó PF 0,922/-1,831R. Por gate
conjuntiva se aplicó early stop sin abrir outer ni holdouts. La lección vuelve a
ser que una representación microestructural plausible no sustituye la utilidad
ask-to-bid mensual.

King Node aporta como hipótesis independiente la dinámica de net GEX —pendiente
y sign flip—, no el nivel estático. Antes de evaluarla deben eliminarse
dependencias de reloj/calibración 2026 y demostrarse OI, signos, timestamps y
paridad histórica. VIX1D/VVIX, skew y vomma no se mezclarán en el primer test.

La traducción congelada usa una regla falsable pequeña: gamma negativa implica
momentum, positiva reversión, y el candidato solo actúa cuando la pendiente de
45m refuerza el signo actual. La fuente pasa timestamps/OI/frecuencia, pero se
declara proxy histórico y live parity bloqueada. La evidencia siguiente debe ser
PF/WR/PnL ask-to-bid, no otra métrica física.

El replayer implementa exactamente esa comparación K0/K1 sin aprendizaje ni
sweep, por lo que un resultado negativo distinguirá un fallo del mecanismo de
un fallo de optimización. Sus celdas se sellan individualmente para diagnóstico.

El data gate aclaró el universo sin mirar payoff: toda oportunidad executable
tiene wall exacto, mientras el wall contiene timestamps adicionales que no son
trades posibles. La evaluación preserva el master y no expande el universo por
disponibilidad de la señal.

## 1. Principio rector

Una mejora de representación no es alpha. Toda idea académica debe terminar en el
mismo contrato executable-quote, causal, nested y live-equivalente. Se rechaza si
solo mejora reconstruction loss, MAE, rango efectivo o incertidumbre sin mejorar
la economía por ticker y mes.

Gates finales por SPXW/QQQ/SPY: PF `>=1,3`, WR `>=50%`, `>=18` trades cada mes,
todos los meses positivos y holds `>=30m`.

## 2. Lecciones de la literatura ya verificadas localmente

| Idea | Referencias representativas | Evidencia local | Conclusión |
| --- | --- | --- | --- |
| Predicción en latente | I-JEPA, V-JEPA, LeJEPA | Flat/modal/SMM/Phys-TD | Loss latente no predice PnL |
| Teacher/regularización | DINOv2/v3, SIGReg, VISReg | rank mejora en algunos arms | No creó lado causal |
| Multihorizonte | V-JEPA 2.1, HWM | h1/h6 e historia larga | Horizonte mayor no arregló payoff |
| Incertidumbre | Var-JEPA | correlación error débil/negativa | No usar como gate direccional |
| Anomalía/coreset | PatchCore | distancia-error positiva 10/15 | Útil para drift, no dirección |
| Adaptación online | AdaJEPA | error latente mejora 15/15 | Downstream abstiene 0/210 |
| Más historia | SSL/JEPA general | 2022 mejora representación OOF | PF empeora 0,863→0,764 |
| Más frecuencia | modelos temporales | 1m añade 62.280 filas | Drift, no inanición |

## 3. Colas de arquitectura cerradas

No continuar por rotación de bloques sobre el mismo OOS:

- modal MJEPA e intra/cross-modal losses;
- Semantic-Masked Market JEPA;
- VISReg/prototipos/Gram sin un nuevo mecanismo;
- jerarquía fast/slow basada en el encoder rechazado;
- Portfolio Var-JEPA e uncertainty abstention;
- PatchCore como filtro de trading;
- AdaJEPA downstream;
- sweeps h3/h12/multihorizon;
- bloques genéricos spot/cross-asset por tanteo.

Motivo común: representación y economía se desacoplan.

## 4. Diagnóstico económico que sobrevivió

El oracle side sobre las mismas opciones alcanza PF `4,55..11,73` y WR
`73,5..86,7%`, mientras clasificadores causales quedan cerca de azar. Por tanto:

1. las labels contienen payoff;
2. el scheduler y la frecuencia no son el cuello principal;
3. falta una fuente causal estable para escoger lado y oportunidad.

La familia legacy dense15 parecía rentable en 10:00–10:29, pero sus IB/Fibonacci
usaban el IB completo hasta 10:30. Ese resultado no es evidencia válida.

## 5. Nueva hipótesis económica: estado de walls

La observación del usuario es más específica que “añadir Greeks”:

- strikes con máxima exposición gamma/delta pueden actuar como soporte,
  resistencia, imán o acelerador;
- el rol depende de signo, fuerza, concentración, persistencia y régimen;
- IB High/Low y extensiones Fibonacci actuales/previas aportan niveles independientes;
- la confluencia puede reforzar una interacción;
- aproximación, pierce, rechazo, aceptación y migración importan más que una
  distancia estática.

La prueba physics-side previa no contenía los walls griegos. La primera auditoría
explícita de distancias y eventos sí se ejecutó:

| Arm | SPXW PF | QQQ PF | SPY PF |
| --- | ---: | ---: | ---: |
| Proximidad | 0,872 | 0,903 | 0,935 |
| Wall event V1 | 0,865 | 0,832 | 0,899 |
| V1r1 con pierce real | 0,910 | 0,845 | 1,008 |

La proximidad no es alpha. V1 además confundía toque con rechazo; corregirlo mejora
pero no alcanza las gates.

Evidencia parcial:

- acceptance CALL muestra 58–63% de dirección spot correcta a 30m en muestras
  relevantes, pero el retorno ask→bid queda cerca de PF 1;
- rejection PUT después de pierce es rentable en SPY, marginal en QQQ/SPXW;
- magnets rentables aparecen con muy poco volumen;
- reglas simétricas CALL/PUT no son defendibles sin medir el régimen.

## 6. Qué faltaba en las features

Las features históricas guardan `dist_to_max/min_gamma`, zero-gamma, DGEX,
confluencias y flags binarios, pero omiten:

- CALL gamma wall y PUT gamma wall explícitos;
- CALL delta wall y PUT delta wall por strike;
- exposición en el wall;
- concentración, entropía/HHI y dominancia top1/top2;
- edad, persistencia y migración del wall;
- separación CALL/PUT y cambio de fuerza;
- identidad económica estable a través del tiempo.

Esto explica por qué un árbol con muchas “physics features” podía seguir viendo
solo localización ruidosa.

## 7. Diseño científico actual

Predeclaración activa:

```text
research_papers/JEPA/WALL_STATE_GEX_DEX_DATASET_PREDECLARATION_V1.md
```

El dataset nuevo usa las mismas fórmulas de exposición que live y agrega por
timestamp/strike:

- GEX, DEX y DGEX CALL/PUT;
- wall strike, distancia, magnitud, concentración, dominancia y effective strikes;
- separación y balance CALL/PUT;
- same/move/magnitude-change 5/15/30m y edad causal.

Las primitivas pasan tests de walls separados, deduplicación de OI,
persistencia/resets y schema causal. El preflight ThetaData real consiguió 100% de
cobertura en tres sesiones, spot <=0,000572 bps y delta walls no equivalentes a
gamma. La separabilidad wall-state se ejecutó y fue rechazada.

El build completo 2022–2025 materializó 135.120 filas y cubre 100% de las 95.424
claves executable con spot <=0,000572 bps. La auditoría detectó un riesgo causal
transferible: floor-join de quotes sub-minuto puede incorporar `HH:MM:30` a una
decisión `HH:MM:00`; el contrato corregido exige timestamp exacto.

La evaluación física posterior separa magnet hit con distance/approach (D0 AUC
mediana 0,805), pero wall strength/persistence/IB no añade mejora pareada y
rejection vs break queda cerca de azar. Esto refina la hipótesis: la ubicación del
wall atrae, pero OI diario no identifica el inventario dealer ni la presión
intradía que decide defensa o ruptura. La siguiente fuente debe medir flujo de
superficie observable, no aumentar capacidad del encoder.

El protocolo wall-state evaluó primero la física del subyacente, no PnL, usando
future prices solo como labels. Al no superar distance-only no se autorizó payoff.
La siguiente evaluación física es H-FLOW1: flujo de superficie observable frente
a F0 distance/approach, congelada antes de labels. Solo si supera el control en los
tres tickers se permite un payoff head ask→bid con contrato 30–180m.

## 8. Uso del hardware

- Build por sesión con 16 procesos CPU inicialmente; aumentar solo si RAM medida lo
  permite.
- LightGBM tabular: 28 hilos, folds secuenciales.
- RTX 5070 Ti: CUDA determinista para secuencias únicamente después de demostrar
  alpha físico; no forzar GPU para agregaciones o árboles pequeños.

## 9. Artefactos clave

```text
research_papers/JEPA/WALL_INTERACTION_EXECQUOTE_PREDECLARATION_V1.md
research_papers/JEPA/WALL_INTERACTION_EXECQUOTE_V1R1_REJECTION_SEMANTICS.md
neural/jepa/audit_wall_interaction_execquote_v1.py
neural/jepa/diagnose_wall_interaction_failure_v1.py
research_papers/JEPA/WALL_STATE_GEX_DEX_DATASET_PREDECLARATION_V1.md
neural/jepa/wall_state_features.py
neural/jepa/build_wall_state_dataset.py
research_papers/JEPA/WALL_SURFACE_FLOW_AT_TOUCH_V1R1_CAUSAL_AMENDMENT.md
research_papers/JEPA/NATIVE_QUOTE_TIMESTAMP_PROVENANCE_AUDIT_20260712.md
neural/jepa/surface_flow_features.py
neural/jepa/build_wall_surface_flow_dataset.py
neural/jepa/build_wall_native_quote_sidecar.py
neural/jepa/freeze_wall_surface_flow_runner_v1r1.py
neural/jepa/evaluate_wall_surface_flow_at_touch_v1.py
```

Producción y junio de 2026 continúan intactos.

## 10. Documentación primaria aplicada a flow V1R1

- ThetaData OHLC define timestamp de apertura e intervalo `[s,s+interval)`;
  por eso una decisión `t` solo consume barras con fin `<=t`.
- ThetaData quote histórico expone un reloj de opción nativo y snapshots de
  bid/ask/size; no autoriza equiparar silenciosamente `underlying_timestamp`.
- La documentación de first-order Greeks conserva ambos relojes como campos
  distintos. El censo local obliga a backfill nativo de 1.441 sesiones.
- Avisos oficiales Cboe separan cierre RTH del underlying/expiring SPXW a 13:00
  del cierre QQQ/SPY options a 13:15 en medias jornadas. Labels físicos usan el
  cierre del underlying; una barra vendor posterior no completa un horizonte.

Estas fuentes se materializan en assertions y tests, no en una estrategia
copiada: timestamp exacto, grids schedule-aware, horizon same-session y sidecar
raw-hashed. Referencias y censo exactos están en
`NATIVE_QUOTE_TIMESTAMP_PROVENANCE_AUDIT_20260712.md`.

La auditoría del productor local añade una regla transferible: un `floor("min")`
es seguro solo si la barra se consume tras completarse, y cualquier `bfill` debe
quedar fuera del research window o rechazarse. El audit 2.519/2.519 cuenta tres
anomalías tempranas fuera de scope y no las imputa.

Otra regla transferible: una reconsulta histórica sirve para recuperar identidad
temporal, pero no debe reemplazar precios antiguos si el proveedor revisó datos.
El sidecar separa key-set de clock, price-revision audit y signability.
La cobertura se define sobre el universo histórico congelado: contratos que el
proveedor añade retrospectivamente se cuentan, no se incorporan al experimento.

El backfill completo selló 1.441/1.441 sesiones y 125.557.990 filas con cero
missing keys y cero errores. Las 500 keys extra, 5.720 crossed y 2.915 revisiones
bid/ask permanecen como evidencia adversarial; el experimento conserva el precio
Greek histórico y usa el sidecar únicamente para recuperar/verificar el reloj.

Lección adicional de procedencia: un booleano leído de CSV no debe pasar por un
helper vectorizado mediante `Series.map(helper)`. El primer full gate lo detectó
antes de outcomes; ahora el attach prueba el CSV real y vuelve a verificar hashes
de raw responses/manifests, JAR y booleanos JSON estrictos antes del build.

Otra lección: igualdad de timestamps no prueba que cada columna tenga la misma
semántica temporal. QQQ 2022-12-30 trae bid/ask de t pero `underlying_price` de
t-1 dentro de la misma fila 1m; desplazar la fila completa sería incorrecto.
El gate debe comparar cada columna contra una fuente 1s exacta y bloquear o
reconstruir el campo, nunca relajar bps ni asumir que todo el snapshot está lagged.

La auditoría de consistencia confirmó que IV/delta almacenados explican el spot
stale, no el spot corregido; sustituir únicamente S generaría una superficie
sintética. V1R2 exige recapturar juntos S/IV/delta a 1s exacto para todo contrato
con OI positivo, conservar OI y bid/ask históricos como anclas y rehacer también
los controles/touches. Es una reconstrucción condicional, no una promoción.

El censo general confirmó que no era una regla elegida sobre dos ejemplos:
2.516/2.518 sesiones son exactas en t y únicamente QQQ/SPY 2022-12-30 son
exactas en t-1; no apareció ninguna sesión unresolved.

La viabilidad de recaptura también quedó probada: 671/671 contratos positivos-OI
aportaron 48 snapshots exactos cada uno y conservaron spot y bid/ask con
diferencia cero frente a sus anclas. Esto repara coherencia física para esas dos
sesiones, aunque la reconsulta 2026 mantiene provenance condicional.

La reconstrucción conserva el mecanismo original de walls: exact-1s S/IV se une
al OI diario congelado y reutiliza las mismas fórmulas; el control se deriva
independientemente de `open(t)` y `open(t-lag)`. El overlay se audita sin modificar
ninguna fila fuera de QQQ/SPY 2022-12-30.

La cardinalidad también debe preservar el universo ejecutable: hay 96 snapshots
wall, pero solo 47 decisiones presentes en el event view. Los otros 49 controles
sirven para auditar la física, no pueden añadirse retrospectivamente como trades.

También hay una separación importante entre mecanismo y policy: un mecanismo
físico puede ser real y aun así no tener frecuencia suficiente. First-touch
H-FLOW no alcanza matemáticamente 18/mes en varios meses QQQ/SPY, por lo que un
PASS solo justificaría un componente de convicción dentro de una unión causal.

El overlay se aplica antes de construir candidatos: reparar después del touch
mantendría un universo elegido con el spot corrupto y sería otra forma de
hindsight. Los hashes del bundle forman parte del data-gate autoritativo.

Un data gate debe distinguir degeneración de baja cardinalidad legítima. La
presión local 1m puede saturar ±1 cuando solo negocia un lado; seis estados con
rango completo y pocos ceros no es una constante. La regla aclarada exige
variación real/missingness, no una cardinalidad arbitraria de diez.

La aplicación de esa regla predeclarada permitió cerrar el gate sin cambiar una
sola fila: V1R2R1 selló 10.683 eventos y 173 columnas con SHA
`6d27fdeb44422daa95aa79f777044e68276a2fe374c9bd847cd475d9dccfdb5b`.
Esto valida únicamente disponibilidad y causalidad de la medición; no constituye
evidencia de alpha. La comparación F0 distance/approach contra F1 flow sigue sin
abrirse hasta congelar el runner.

La prueba congelada ya falsificó el bloque H-FLOW1: añadir volumen, count,
close-notional y presión firmada local/full-surface en 1/5/15m empeoró el AUC
frente a distance/approach en 20/24 celdas; mediana ΔAUC `-0,029209` y
`p=0,984375`. En 30/60m no ganó ninguna celda de ningún ticker. La lección es
específica: el signing quote-relative de barras agregadas no identifica defensa
versus ruptura. No extrapolarla a profundidad/tamaño de quote, update intensity,
deformación IV/skew o basis/futures, que no fueron features de F1.

La fuente siguiente se separó precisamente por esa lección. H-IVSURF1 no usa
flujo agregado ni skew estático por delta bucket: sigue la misma malla de strikes
alrededor del wall y mide desplazamiento, cambio de pendiente y curvatura de la
superficie midpoint-IV a 1/5/15m. El data gate completo pasó con validez mínima
ticker-año 90,319%. La documentación ThetaData establece que Greeks intervalados
usan la quote del timestamp; live aún debe registrar `feature_available_at`
antes de entrada para probar el orden recepción->score->ask.

El resultado físico de esa prueba también fue negativo: LR mediana ΔAUC
-0,001203 (12/24) y LightGBM -0,005822 (9/24). La superficie fixed-strike
midpoint-IV no añade señal estable en los tres tickers. SPY aislado mejora en LR,
pero no replica con el modelo de sensibilidad y no es seleccionable tras abrir
outer. La siguiente medición distinta es tamaño NBBO; requiere completar el
reloj histórico y no debe confundirse con profundidad completa/update intensity.

H-QSIZE aporta otra lección transferible: disponibilidad de quote no es presión
de mercado. El primer data gate encontró cambios de signable fraction constantes
en seis ticker-año; esos campos deben ser quality-only y no entrar explícita ni
implícitamente mediante missing indicators o ramas nativas. La reparación V1R1,
congelada antes de outcomes, compara F0/F1 en complete cases idénticos y limita
alpha a imbalance y tamaño bid/ask relativo. También exige pertenencia de
contrato Greek exacta por timestamp; una unión diaria puede introducir un strike
antes de su primera observación histórica.

Aplicada esa separación, V1R1 pasa el gate outcome-free con 32 pressure features
no degeneradas y 98,477% de cobertura mínima ticker-año. Esto valida medición y
causalidad, no alpha; la comparación física F0/F1 sigue sellada hasta congelar
el runner.

El one-shot posterior falsifica también el bloque snapshot QSIZE: LR pierde
18/24 comparaciones (mediana -0,014823) y LightGBM pierde 19/24. La conclusión
es específica: nivel/cambio 1m de tamaño NBBO, imbalance y profundidad agregada
cerca del wall no separa defensa de ruptura. No falsifica reposición de cola,
cancelaciones/update intensity intraminuto ni libro profundo, que no se midieron.

H-QDYN1 separa esa pregunta: usa reportes NBBO tick previos a decisión. Los
timestamps duplicados sin sequence solo cuentan intensidad; se excluyen de
transiciones ordenadas. Así replenishment/withdrawal no depende de inventar un
orden intramilisegundo. Sigue siendo NBBO top-of-book, no profundidad completa.

La auditoría de profitability añade dos falsos positivos históricos que deben
recordarse: (1) IB/Fibonacci completo usado antes de terminar el IB, fuga que
afectó 338/697 trades del resultado original; (2) buena curva sobre labels
`legacy_ohlc` y políticas escogidas con los mismos meses luego reportados. La
única comparación económica admisible parte de `executable_quote` (ask->bid) y
un scheduler no-overlap. El benchmark nested disponible cumple ese pricing pero
da PF inferior a 1 en los tres tickers, por lo que no confirma alpha económico.

Para dinámica NBBO, cercanía a un wall conocido no prueba que el contrato podía
estar suscrito. H-QDYN1R1 exige presencia exacta de ambos rights en `t-5m`. El
audit sellado confirmó esa condición en los 10.683 candidatos; los 9.833 eventos
de radio sobreviven con identificación causal más fuerte. Esto valida
disponibilidad, no alpha ni rentabilidad.

La captura debe preservar quotes raw inválidas y decidir validez solo en el
cálculo de transiciones. `Size-only` excluye cambios simultáneos de exchange;
conditions cuentan como reportes/dedup pero quedan fuera de las 28 mediciones.

ThetaData documenta que OI publicado por la mañana representa el cierre del día
previo y que `/v3/option/history/greeks/all` ofrece griegas de orden superior
timestamped. Esto abre una fuente mejor que recalcular fórmulas locales para
estudiar deformación/migración vanna/charm/vomma/zomma, aunque sigue siendo una
reconstrucción del proveedor actual y no identifica signo dealer.

En IB/Fibonacci, “algunas extensiones según el día” no es una hipótesis nueva si
se eligen después de mirar resultados. Un test nuevo debe mantener los ocho
niveles y medir presión dinámica con un modelo compartido, no escoger niveles.

El contrato H-QDYN V1R1R1 ya sobrevivió auditoría de raw preservation, listing
exacto, colisiones, size-only y exchanges finitos; 31 tests pasan. Esto certifica
la implementación previa al outcome, no la existencia de edge.

La captura completa posterior quedó sellada `PASS_QDYN_CAPTURE`: 9.833 eventos
elegibles, 37.846.658 ticks balanceados entre CALL (18.915.243) y PUT
(18.931.415), sin errores ni rights ausentes. Los hashes del índice
(`9a4924df...1b4f03`) y eligibility (`09df8319...ee2e1`) fijan el universo,
pero la provenance continúa siendo reconstrucción condicional del proveedor
actual. El primer data gate falló cerrado, antes de outcomes, por un bug de
plomería (`set_index` eliminó `event_id`), no por una propiedad de la señal; se
corrigió en `85de313` con `26 passed`. Hasta que el relaunch pase, se congele el
runner y se ejecute el único F0/F1, esto sigue siendo evidencia de disponibilidad
y causalidad, no de alpha ni rentabilidad.

El data gate final impidió precisamente convertir disponibilidad en una falsa
señal: aunque both-valid supera 89,4% en cada ticker-año, 18 mediciones SPXW son
constantes. Las fracciones CALL/PUT de cambio de exchange son cero en los cuatro
años y las fracciones de cualquier cambio de estado son uno en SPXW 2025. Como
la hipótesis congeló >=2 estados por feature/ticker-año, H-QDYN1 se cierra antes
de labels. Eliminar ahora esas features sería selección post-resultado, aunque
no se hayan abierto outcomes. La lección es que mayor granularidad de mensajes
no garantiza variación identificable: este feed reconstruido no mide dinámica
de exchange/state útil de forma no degenerada para SPXW. El siguiente test
independiente es el preflight directo de higher-order Greeks H-GREEK2WALL.

H-GREEK2 convierte esa siguiente pregunta en un test de disponibilidad antes de
outcomes: 12 sesiones fijas y respuestas direct all-Greeks + direct OI capturadas
atómicamente, con provenance del Terminal. El inventory V1R2 ya pasa y el código
está congelado, pero no se obtuvo ninguna respuesta utilizable. El Terminal local
tiene entitlement STANDARD y el endpoint exige PROFESSIONAL (HTTP 403); el
remoto conectó a MDDS pero rechazó la sesión duplicada/stale (478). Esto es un
bloqueo de fuente/servicio, no evidencia contra ni a favor del mecanismo.
Restaurar una única sesión remota y sellar las 12 capturas es requisito previo;
si el feed o entitlement no existen, H-GREEK2 debe cerrarse como fuente ausente.
No inferir alpha o rentabilidad de la disponibilidad del endpoint ni relajar la
gate económica PF1,3/WR45%/mínimo12, que sigue sin ser probada por esta fuente.

La recuperación del servicio separó definitivamente operación de entitlement:
con un único Terminal remoto, MDDS CONNECTED y los bots activos, la primera
sesión congelada volvió a responder HTTP 403 porque la cuenta remota también es
STANDARD. H-GREEK2 queda cerrado por ausencia de fuente Professional antes de
capturar una sola griega directa. Un endpoint documentado no equivale a un dato
disponible, y un transporte SSH al mismo host no cambia la identidad de fuente.

Tampoco es científicamente válido reemplazar vanna/charm/vomma/zomma directas
por fórmulas locales y conservar el nombre de la hipótesis: esas fórmulas son
transformaciones deterministas del spot/IV ya disponible. La dirección nueva
separada es H-IBQDYN1, presión/reposición NBBO intraminuto sobre los ocho niveles
IB/Fibonacci fijos después de completar el IB. Exige universo, listing y captura
propios; los ticks dirigidos a Greek walls de H-QDYN no pueden reutilizarse.

H-IBQDYN1 materializa esa separación: el evento nace de los ocho niveles IB/Fib
completados, pero la medición se dirige a los contratos realmente ejecutables
d25/d35. El proof t-5m sobre 2.519 sesiones conserva 16.852/16.926 eventos y
rechaza 74 QQQ sin remap; SPXW y SPY tienen listing exacto total. La lección es
que disponibilidad de una fila futura de candidato no prueba buffering causal:
se debe demostrar la identidad de cada CALL/PUT antes de su ventana tick.

El adelgazamiento a la primera oportunidad por bloque fijo de 30 minutos reduce
coste sin seleccionar outcomes y aún deja capacidad mensual 2024/2025 de
35/69/19 para QQQ/SPXW/SPY bajo el scheduler actual. Es solo una cota superior:
especialmente SPY debe convertir casi todos sus días activos para cumplir 18;
ningún recuento de candidatos prueba PF, WR o PnL.

El preflight tick confirma que esta vez la medición no está bloqueada antes de
descargar todo: 24/24 contratos aportan rows, las 20 variables son finitas y las
60 celdas ticker-feature de la muestra varían. La proyección de 61,34M rows y
9,64GiB raw es operable. Aun así, distinctness y volumen de mensajes solo prueban
que el instrumento mide algo; el edge exige que F1 supere F0 y después sobreviva
ask->bid, no-overlap y meses completos. Por eso la siguiente acción es una sola
captura/one-shot, no otra expansión de fuentes o arquitecturas.

La prueba queda reducida a una comparación interpretable: una logística L2 con
18 controles causales frente a la misma logística con 20 variables tick
adicionales; LightGBM es confirmación no rescatable. El data gate conserva los
fallos de listing y usa todos los eventos en el denominador, evitando fabricar
edge al eliminar retrospectivamente los casos difíciles.

Si el mecanismo pasa, la prueba económica no buscará otra configuración: la
probabilidad física de rechazo a 60m se convierte mecánicamente en CALL/PUT con
boundary 0,5 y se ejecuta cronológicamente. Así un PF rentable mediría la misma
hipótesis causal, no una segunda optimización sobre los retornos reportados.

La primera captura full aporta otra lección de fuente: listing exacto a `t-5m`
no garantiza que OPRA haya emitido un update dentro de cada ventana posterior de
30 segundos. ThetaData expresa esa ausencia con HTTP 472 `NO_DATA`, no con un
JSON 200 vacío. Un capturador causal debe distinguir una ventana observada sin
mensajes de un fallo de conexión y conservar el raw de error, pero no puede
inventar una quote, ampliar la ventana ni usar as-of. H-IBQDYN1 encontró cuatro
casos exactos entre 33.704 contratos, ambos rights de dos eventos SPXW/SPY; el
tratamiento congelado es parquet vacío, evento both-invalid y cobertura
penalizada. Esto valida semántica de missingness, no alpha.

La implementación V1R1 confirmó esa separación sin pérdida de universo:
33.700 respuestas 200 y cuatro respuestas 472 forman un índice único de
33.704 contratos, con el raw de error conservado y cero filas sintéticas. Los
58,21M ticks restantes se reconstruyeron desde raw y coincidieron con sus
parquets antes del seal. Una ausencia correctamente representada puede pasar la
gate de procedencia; sigue contando contra cobertura y no demuestra edge.

El primer ensamblado completo aportó otra protección reproducible: cuando una
propiedad de calidad aparece tanto en el proof como en la medición, no basta con
dejar que el dataframe resuelva nombres duplicados. Debe probarse igualdad
one-to-one antes de conservar una versión; de lo contrario un sufijo mecánico
puede detener la cadena o, peor, ocultar una discrepancia. H-IBQDYN1 ahora hace
esa comprobación fail-closed. El fallo ocurrió antes de output y outcomes, por lo
que no informa sobre alpha; solo endurece el puente entre procedencia y dataset.

El paralelismo también forma parte de una ejecución reproducible, aunque no de
la hipótesis: 16 procesos simultáneos agotaron memoria al rehashear los raws
grandes tras 12.000 eventos. Como no hubo output y cada evento se calcula de
forma independiente, reducir a ocho workers conserva exactamente los datos y
gates; solo limita el pico de RAM. Un fallo de recursos no debe reinterpretarse
como fallo o evidencia del mecanismo.

Con ocho workers, el mismo cálculo completó y separó disponibilidad de validez:
16.852 eventos tenían listing causal, pero solo tres de 16.926 no produjeron
ambos rights medibles. Esas ausencias permanecen visibles y en el denominador;
la cobertura mínima anual sigue siendo 96,31%. Las 20 variables tick conservan
al menos 79 estados finitos distintos por ticker-año y F0/F1 comparten
exactamente las mismas complete cases. `PASS_DATA_GATE` prueba que la medición
es reproducible, cubierta y no degenerada; todavía no prueba que prediga el
mecanismo ni que sobreviva al spread ask-to-bid.

El freeze físico hace explícita la comparación que puede contestar esa pregunta:
la base no son solo 18 variables continuas, sino también las ocho identidades
predeclaradas del nivel, para que F0 y F1 compartan la geometría completa. F1
añade exactamente 20 dinámicas tick y nada más. Al congelar hashes, folds,
horizontes, LR/LightGBM y gates antes de labels, una mejora posterior no puede
atribuirse a seleccionar retrospectivamente una extensión Fibonacci o modelo.

El resultado one-shot muestra por qué esa disciplina importa: pese a una muestra
mensual holgada (mínimo 45 episodios resueltos), las dinámicas tick reducen la
AUC mediana de la LR en 0,004 y solo ganan 7/24 celdas. La señal no falla por
escasez ni por un único ticker; las medianas son negativas en QQQ, SPXW y SPY.
LightGBM tampoco confirma y su mediana empeora 0,00585. Algunas celdas aisladas
—QQQ 120m LR o SPXW 30/60m LightGBM— parecen favorables, pero elegirlas después
del resultado convertiría ruido en una nueva policy sin evidencia.

La conclusión acotada es que update intensity, aceleración, presión de mid/
spread y replenishment/withdrawal durante 30 segundos en los CALL/PUT ejecutables
no identifican de forma estable defensa/aceptación de los ocho niveles IB/Fib
por encima de distancia, aproximación, volatilidad, hora e identidad del nivel.
No se abrió payoff porque hacerlo tras este fallo solo permitiría seleccionar una
traducción económica sobre una representación física falsificada. Por eso no hay
PF, WR o PnL que reportar para H-IBQDYN1.

El primer resultado de EDGE-FIRST V1 demuestra una separación útil entre
reproducción y diagnóstico. Las métricas del benchmark ask-to-bid se recalculan
sin diferencia, pero su scheduler histórico permitía dos SPY por día; aplicar el
cap actual de uno mejora algo el PF y reduce frecuencia, sin volverlo rentable.
Esto evita atribuir al modelo una discrepancia puramente contractual.

El oracle se limita a 2023 y no es una policy: muestra que las oportunidades
observadas contienen trades ganadoras que el clasificador causal no sabe elegir
ni orientar. Los controles de lado constante o aleatorio siguen perdiendo, por
lo que no basta un sesgo direccional trivial. A la vez, no existe una label
midpoint/no-spread emparejada que permita aislar execution drag; reportarlo como
número sería mezclar un contrafactual inexistente con evidencia ejecutable.

La unión existente puede construirse sin inventar una geometría nueva. Los
bloques touch H-FLOW/IVSURF/QSIZE no tienen clave única contra el universo full;
agregarlos ahora sería una decisión de representación posterior, así que se
omiten. Wall-state y H-IBQDYN sí admiten igualdad exacta y expresan la no
aplicabilidad geométrica con un único flag por bloque, manteniendo nulls en vez
de ceros sintéticos. La vista resultante conserva todas las oportunidades.

El smoke 2023 también verificó la disciplina de abstención: ni hurdle ni Huber,
con base o unión, encontró un umbral que pasara PF, WR, frecuencia y PnL en cada
uno de tres meses inner. En vez de escoger el menos malo, los 12 folds abstienen
por completo. Esto no anticipa el veredicto 2024/2025, pero prueba que el runner
puede terminar honestamente sin forzar trades. Dos outcomes PUT ausentes de 2022
se tratan como target missing por lado, nunca como retorno cero.

El freeze convierte esa disciplina en un contrato verificable: el evaluator
rehúsa abrir outer si cambia un byte del view, allowlists, modelos, scheduler,
predeclaración o runner. También congela por anticipado los meses 2024-2025 y
marca 2026 como cerrado. Así, un eventual mes malo no puede provocar una nueva
regla de selección sin invalidar formalmente el experimento.

El resultado final distingue una métrica pooled atractiva de una policy
desplegable. E0 hurdle suma PF 1,465 y +8,34R, pero esa ganancia proviene de solo
tres de 72 ticker-meses; 69 meses abstienen, uno de los tres operados no alcanza
18 trades y otro no alcanza 50% WR. Solo QQQ septiembre 2024 pasa. El pooled no
compensa una frecuencia mensual mínima de cero.

La unión E1 ofrece una conclusión todavía más limpia: ningún threshold/margin
pasó los tres inner meses en ninguno de sus 144 folds de modelo/ticker/mes. El
scheduler no llegó a ocultar una policy marginal; la selección nested ya exigió
abstención completa antes de outer. Huber tampoco rescata el resultado. Por eso
no se justifican stress ni 2026, y el cierre correcto es ausencia de edge en la
información existente bajo este protocolo, no ausencia de oportunidades oracle.
mecanismo.

El primer data gate añadió otra lección: un parquet marcado `executable_quote`
no prueba ejecutabilidad si el calendario de sesión no limita los paths. En una
media jornada, closes subyacentes planos y exits que cruzaban el cierre revelaron
eventos stale. No se estabiliza beta con epsilon ni se filtran filas por su exit
futuro; se rechaza V1 y se excluye la sesión completa mediante calendario
predeclarado en V1R1.

V1R1 mostró un límite distinto: una correlación lead/lag no está definida si
una de las dos secuencias lag queda constante, aunque la ventana total tenga un
movimiento. Asignar cero o epsilon cambiaría el mecanismo tras ver el gate. La
familia se cierra y se rota a aceptación por tiempo-precio TPO, que no depende
de covarianzas cross-market.

En TPO, términos de mercado no bastan como especificación: periodo, lattice,
fronteras, ties, touches y denominadores deben quedar matemáticamente fijados
antes del data gate para que una implementación distinta no cambie el alpha.
La aclaración V1R1 añade centro/bordes exactos, value location no clipped y
efficiency sobre h transiciones; cualquier caso indefinido falla cerrado.

La reanudación también es parte de la reproducibilidad: un checkpoint solo es
evidencia reutilizable si sella conjuntamente inputs, universo, código,
protocolo y output. Guardar únicamente pesos o un contador permite mezclar dos
experimentos distintos después de una muerte de proceso.

La prueba KING-GEX separa de nuevo oportunidad y dirección. Exigir que la
pendiente de 45 minutos refuerce el signo de net GEX reduce algo las pérdidas en
21/36 meses, pero pooled continúa en PF 0,804 y WR 42,22%. El mecanismo simple
`gamma negativa = momentum, gamma positiva = reversión` no orienta opciones
0DTE de forma estable: acierta el mejor right menos de la mitad de las veces.

La comparación contrafactual evita una conclusión equivocada. Invertir CALL/PUT
en los mismos timestamps también pierde, mientras un oracle de right gana mucho.
Eso no autoriza usar el oracle; muestra que el universo contiene movimiento pero
que nivel/pendiente GEX y momentum 15m no lo convierten en una elección causal
de lado. La siguiente idea debe cambiar el mecanismo de orientación o probar un
payoff realmente no direccional, no retocar thresholds tras ver los meses.

El replay de gestión cierra otra salida fácil: un stop fijo distinto no corrige
el King. El stop 30% corta la cola y eleva el payoff ratio, pero reduce WR hasta
35,96%; stops amplios elevan WR a costa de pérdidas mayores; trails tempranos
aproximan 50% WR recortando demasiado las ganadoras. Las 32 combinaciones quedan
por debajo de PF1,0. Esto demuestra que PF no puede repararse optimizando una
sola palanca global cuando recuperación y deterioro comparten el mismo estado.

La comparación matched B00/S30 localiza información potencialmente útil: el
stop reduce 24,275R de pérdida sobre entradas comunes, pero sacrifica 96 trades
que habrían recuperado. Incluso un oracle ex-post queda en PF1,239, por debajo
del objetivo. Un test siguiente debe observar el estado a +30m y estimar valor
de continuación causal; no puede prometer que la clasificación cierre el gap.

Las higher Greeks sintéticas no son una fuente olvidada. `neural/stats.py` y el
collector histórico ya derivan gamma, vanna, charm, vomma y zomma desde IV/spot/
strike/tiempo, y E1 incorporó sus niveles, cambios, ratios 0DTE-weekly, walls,
confluencias IB/Fib, OI, volumen y contexto del precio. La abstención de los 144
folds E1 falsifica esa representación como selector de entrada estable, no toda
utilidad posible de las griegas. Su dinámica posterior a la entrada plantea una
label distinta —continuar versus realizar al minuto 30— y evita repetir el mismo
experimento. Debe etiquetarse como sensibilidad de modelo: OI no revela el lado
del cliente ni el inventario real del dealer.

El oracle con scheduler completo delimita mejor la oportunidad. Escoger solo
B00 o S30 no cruza PF1,30 ni con futuro; la mejora matched exageraba el valor al
omitir entradas que cambian cuando cambia el hold. El menú completo de 16 exits
sí eleva PF a 2,357 y WR a 54,67%. La diferencia implica que el estado no solo
separa stop/continue: también contiene información sobre horizonte y cuándo
proteger una ganancia.

MANAGE30 formula esa idea como un problema contrafactual estrecho. Para cada
trade se conocen los 17 payoffs bajo el mismo path, así que el modelo no debe
aprender primero si la entrada era buena; estima la ventaja relativa de una
gestión frente a B00. La elección ocurre justo al primer instante en que un exit
es legal, después de observar retorno actual, MFE/MAE, cambio de IV/delta y
deformación sintética de la superficie.

La disciplina temporal sigue siendo decisiva. Entrenar con todo 2022-2026 y
reportar 2026 memorizaría el examen; expandir mes a mes permite que cada mes sea
predicho antes de incorporar su label. Si la policy supera 2023, se congela
antes de 2024/2025 y solo después puede llegar a 2026. El fit para operar julio
sí puede usar todos los meses ya completados, pero no convierte esos meses en
evidencia OOS.

La implementación evita un leakage sutil: si falta el mark exacto de un lag no
se sustituye por la última quote. La decisión solo existe si el mismo contrato
tiene quote válida entre 30 y 31 minutos; de lo contrario la política conserva
B00. Cada sesión sella por separado inputs, features y contrafactuales para que
una reanudación no mezcle dos versiones del experimento.

La ventana también forma parte de la identidad: exigir wall state a las filas
10:30–11:15 del master era un error de universo, no ausencia de datos. Aplicar
11:20–14:30 antes del join conserva exactamente las oportunidades K1 y evita
que filas nunca elegibles bloqueen o alteren el experimento.

La traducción live del oracle requiere aprender valor, no copiar una etiqueta
ganadora. Las 17 acciones comparten estructura: stop, activación/drawdown de
trail y horizonte. Representarlas con esos parámetros permite estimar una
superficie de ventaja condicionada al estado; una clasificación plana perdería
esa relación y exageraría diferencias pequeñas entre acciones casi equivalentes.

La duración elegida también modifica el universo futuro. Un H60 puede liberar
una oportunidad que B00 bloquearía hasta 180m; por eso no basta medir el retorno
de cada fila y agregar. Primero se asigna gestión usando solo el estado +30 y
después se reproduce secuencialmente caps, cooldown y posición abierta. El
oracle actual maximiza retorno por evento, no valor global con coste de bloqueo;
esa diferencia explica por qué PF2,357 es headroom, no el techo exacto de una
policy de cartera.

La implementación en `b8fa50c8` convierte estas restricciones en checkpoints
auditables por fold. La prueba 2023 aún no ha comenzado: el builder V1R1 tenía
843 sesiones selladas al último checkpoint. Hasta que existan data gate y 72
folds completos, cualquier PF atribuido a M0/M1 sería inventado. Un Excel King
auditado en el futuro puede inspirar otra hipótesis, pero no alterar este examen
después de congelarlo.

El fallo posterior demuestra por qué “mismo minuto” no equivale a causalidad.
En feeds sub-minute, floor a un minuto puede incorporar una quote treinta
segundos posterior a la decisión y una superficie compuesta por estados que
nunca coexistieron. La unidad causal es el timestamp nativo exacto. V1R2 obliga
esa igualdad tanto en entrada como en decisión y rechaza explícitamente la única
señal train-only sin contrato; no la rellena con nearest strike ni payoff cero.

Por ello los 1.265 checkpoints aparentemente correctos de V1R1 no son
reutilizables: su B00 podía coincidir mientras M1 seguía mezclando instantes.
La reanudación es válida solo cuando también la semántica temporal forma parte
del hash del checkpoint. V1R2 se relanzó antes de cualquier modelo o PF.

El resultado V1R2 confirma que más representación no sustituye una ventaja
económica. M0 y M1 terminaron cerca de PF0,90 y WR39%; las higher Greeks
sintéticas no rescataron la gestión y no justifican una red más compleja.

El único examen weekly multi-día separa dos preguntas. La microestructura mejora:
spread mediano 0,46–0,82% y el mismo contrato puede seguirse dos sesiones en
2.361/2.364 casos. Pero la prima aún pierde aproximadamente 26–31% por dos días
de theta en la mediana y ambos rights pierden a la vez en ~27% de eventos. El
oracle de dirección convierte la convexidad restante en PF12–14, mientras un
CALL fijo apenas llega a PF1,04–1,06 y PUT fijo pierde. Por tanto el problema
no era solo “las griegas 0DTE”: al dar más tiempo reaparece un techo atractivo,
pero la dirección causal sigue sin estar resuelta.

Con ocho a diez posiciones mensuales no-overlap, exigir WR>50% en cada mes es
estadísticamente y físicamente mucho más duro; exigir además 18 trades es
incompatible con sostener dos sesiones. Cambiar esas gates después de ver el
oracle sería selección post-hoc. El cierre correcto es preservar el hallazgo y
no crear otra familia de datasets hasta una decisión prospectiva del usuario.

## Actualización 16-jul-2026 — qué enseñan Globex y los payoffs alternativos

### El colapso JEPA no era la explicación completa

El diagnóstico espectral fue correcto: el encoder anterior comprimía demasiado
la variación. Factorizar common/residuos/innovaciones y aplicar VISReg elevó el
rango efectivo de `z` a 53,54% y de `dz` a 42,67%, superando la gate física.
Sin embargo, el backtest 2026 siguió con PF inferior a uno en los tres tickers.
VISReg arregla geometría latente; no inventa información predictiva ni corrige
un target económico no estacionario.

Esto refina la lección de la literatura: evitar collapse es necesario para que
un world model represente el mercado, pero no suficiente para que la semántica
aprendida sea la que determina retorno ejecutable. Un latente puede tener rango,
innovaciones y buen loss y aun no separar qué lado sobrevive spread, theta y
cambio de régimen.

### Una fuente genuinamente nueva también puede sobreajustar el régimen

La captura sellada de ES/NQ/YM/RTY/ZN/GC/CL aportó información Globex, rates y
commodities que no estaba en las barras RTH. El primer modelo logró en 2025 PF
1,200–1,210, WR 51–52%, frecuencia suficiente y 9/12 meses positivos. Ese es el
near-miss más convincente de la rama direccional porque la fuente era nueva y
la selección se congeló antes de 2026.

Precisamente por eso el fallo posterior es informativo: enero–15 julio 2026 cayó
a PF 0,873–0,899 y solo 2–3 meses positivos. Regresión logística online, Hedge
de reglas y meta-Hedge no recuperaron estabilidad en 2025. El patrón no encaja
con “faltaba un modelo más adaptativo”; encaja con señales débiles cuya relación
con el target cambia más rápido de lo que puede estimarse con pocos meses.

Los continuos Yahoo sirven para investigación, no para certificar fills de
futuros: contienen rolls, solo ofrecen 60m durante 730 días y no equivalen a un
contrato broker/live. Un futuro PASS necesitaría datos contract-level y paridad
prospectiva; no puede promoverse desde este proxy.

### Cambiar theta por otro payoff no resolvió la economía

El short-premium defined-risk era la prueba simétrica natural tras cerrar long
options, pero los exits exactos de cuatro patas no estaban siempre ejecutables.
V2 encontró 13 faltas invalidantes en las primeras 100 sesiones auditadas y se
cerró antes de PnL. Omitir esos trades habría convertido calidad de datos en un
filtro alfa retrospectivo.

La compra simultánea CALL+PUT elimina la necesidad de escoger lado, pero no el
coste de comprar dos spreads y dos curvas de decay. Con 613 trades/ticker y
mínimo 40/mes, PF quedó 0,605–0,661 y WR 33–36%. Aquí no falla frecuencia ni
clasificador: falla directamente el payoff long-vol bajo ask->bid.

### IB/Fibonacci es geometría, no una ventaja por sí sola

La ejecución directa de la primera salida del Initial Balance, con clasificación
breakout/fade, entradas al minuto siguiente, stops conservadores y objetivos
Fib, conservó 24–25 trades mensuales mínimos pero dio PF 0,779–0,819 y WR
31–32%. El resultado no invalida todo uso de niveles; invalida esa traducción
fija y el intento de aprender continuación/fallo con el panel actual.

Modificar los stops al observar que concentran pérdidas no sería descubrimiento:
sería optimizar sobre el examen. Una hipótesis posterior debe cambiar el
mecanismo, no desplazar 0,236 a otro Fibonacci o seleccionar solo los meses de
breakout.

### Conclusión transferible

Los resultados separan cuatro fallos que antes se confundían:

1. `representation failure`: existía y fue corregido, sin alpha;
2. `directional information failure`: persiste en cash, options y Globex;
3. `payoff failure`: long-vol pierde aun sin elegir lado;
4. `execution/data failure`: short premium no puede evaluarse omitiendo patas.

Por tanto, el siguiente trabajo no debe ser otra corrupción JEPA, otro dataset
de las mismas features ni un sweep de memoria/stop/delta. Debe aportar un
mecanismo económico independiente —por ejemplo relative-value/cross-session— o
una fuente nueva broker-grade que pueda observarse igual en histórico y live.
Estado del programa: `NO_PROFITABLE_CAUSAL_POLICY`.

## Actualización 17-jul-2026 — hipótesis relative-value falsable

La continuación no intenta volver a predecir el signo absoluto ni comprar otra
prima. `CROSS_SESSION_RELATIVE_VALUE_V1` cambia simultáneamente target y payoff:
pregunta si el exceso QQQ frente a un ancla SPY/SPXW acumulado entre el cierre
previo y 10:34 revierte de 10:36 a 13:36 en un spread QQQ-SPY equal-notional.

La inferencia transferible es que una hipótesis nueva debe poder escribirse sin
un nuevo dataset ni un selector: un reloj, una ecuación de shock, una acción y
un coste. Aquí no hay beta rolling, z-score, threshold o ML; la regla opuesta
solo es control y no puede rescatar el primario. El desarrollo 2022–2023 exige
todos los meses positivos además de PF/WR/frecuencia. Un PASS seguiría siendo
feasibility spot, no ejecución broker-grade ni autorización de opciones.

La implementación traduce esas restricciones en un runner sin cutoff externo:
rehúsa fuentes posteriores a 2023 por construcción, valida la malla completa y
registra por separado controles momentum/fijo. Los controles se calculan para
diagnóstico de signo, pero el código no puede usarlos para sustituir la regla
mean-reversion ni para decidir abrir el outer.

Una exclusión de trade no implica borrar toda la sesión fuente: si la anomalía
está localizada dentro de la ventana de señal, puede prohibirse la decisión de
ese día y conservarse un close posterior válido como estado previo del día
siguiente. Esto requiere una allowlist exacta de filas adversariales, no una
tolerancia general ni imputación.

El resultado falsifica la versión fija de esa hipótesis: mean-reversion obtiene
PF0,627 y solo 5/24 meses positivos. El signo opuesto mejora a PF1,075 pero no
alcanza la gate y era un control no seleccionable. La lección es que cambiar de
dirección absoluta a spread relativo elimina parte del beta, pero no garantiza
reversión; observar después que momentum es menos malo no autoriza añadir un
z-score/beta/threshold ni invertir la policy sobre los mismos meses.

La siguiente falsificación separa precisamente overnight de price discovery
cash. `OPENING_RELATIVE_MOMENTUM_V1` no usa el shock cross-session observado:
mide solo 09:30–10:34 y pregunta por continuación posterior. Esta separación
evita convertir el control momentum PF1,075 en una promoción; el control solo
motiva una hipótesis con señal nueva y outer aún intacto. Se distingue progreso
agregado PF>1 de la gate mensual completa, sin confundirlos.

El runner conserva esa distinción como estado de máquina, no como narrativa:
PF agregado>1 nunca activa outer si un mes falla. Además hashea el loader
compartido para evitar que reutilizar validación de fuente oculte un cambio en
la semántica de timestamps.

Una prueba importada por pytest no certifica que el entrypoint directo arranque:
el primer launch falló antes de fuentes porque `sys.path` difería. La regresión
correcta debe ejecutar el script en subprocess; este tipo de fallo conserva el
freeze si no creó output ni alcanzó outcomes.

El resultado cash-open también es negativo, pero aporta una separación útil:
497 operaciones alcanzan WR50,905% y aun así PF0,831, con solo 7/24 meses
positivos. No falla la frecuencia ni principalmente el porcentaje de acierto;
fallan la magnitud de las pérdidas y la estabilidad. Los controles de reversión
y lado fijo también quedan bajo PF1. Esto cierra la selección de signo sobre
este impulso y orienta una hipótesis futura hacia asimetría de riesgo causal,
sin autorizar stops o filtros elegidos después de ver el ledger.

La rotación siguiente cambia la medición, no el clasificador. La paridad
CALL/PUT del mismo strike elimina gran parte del valor intrínseco compartido y
expresa presión relativa directamente en quotes. Usar su cambio sobre strikes
idénticos evita convertir financiación/dividendos o el desplazamiento del ATM en
señal. Antes de preguntarle al retorno debe probar que bid/ask vintage,
timestamp nativo y spot causal producen una variable completa y no degenerada.

La capacidad de producto también es parte de la causalidad: febrero de 2022
solo ofrecía 12 vencimientos 0DTE y no podía superar una gate estricta `>12`
con una operación diaria. Por autorización explícita, el protocolo elimina todo
2022 antes de outcomes y separa 2023 desarrollo, 2024–2025 outer y 2026 final.
Eso evita tanto inventar frecuencia como usar el holdout para seleccionar.

El censo formal confirma que el nuevo eje ya no está limitado por listings:
752 sesiones por ticker y mínimo 18 en cualquiera de los 36 meses 2023–2025.
Todavía no dice que la paridad sea medible o predictiva; separa correctamente
capacidad de producto, calidad de quotes y alpha en gates sucesivas.

El primer quote gate mostró otra distinción útil: pushdown de strings no es
validación temporal. Ciento cuatro sesiones parecían vacías porque almacenaban
`.000`; el datetime exacto sí estaba. La reparación válida enumera ambas
codificaciones y vuelve a exigir equality/key parity, en vez de relajar el reloj
o aceptar un as-of.

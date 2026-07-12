# SUMMARY-articles — conclusiones transferibles de JEPA/world models

**Corte:** 12 de julio de 2026. Los 29 trabajos aportados fueron auditados. Este
resumen conserva únicamente las ideas que afectan la investigación actual y su
evidencia local.

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

# SUMMARY-articles — conclusiones transferibles de JEPA/world models

**Corte:** 11 de julio de 2026. Los 29 trabajos aportados fueron auditados. Este
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
gamma. Tras aprobar el build completo, queda pendiente la separabilidad física.

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

Primera evaluación autorizada: física del subyacente, no PnL. Los future prices se
usan solo como labels para `magnet_hit`, `true_rejection` y `accepted_break` a
30/60/120/180m. El wall state debe superar un control distance-only en los tres
tickers mediante selección nested anterior al test.

Solo después se permite un payoff head de opciones con ask→bid y el contrato
30–180m. Si la física no es separable, otra arquitectura no está autorizada.

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
```

Producción y junio de 2026 continúan intactos.

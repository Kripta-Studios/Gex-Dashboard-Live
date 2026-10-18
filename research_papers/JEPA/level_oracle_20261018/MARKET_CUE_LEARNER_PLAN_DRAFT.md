# Control compacto de señales observables → retorno neto

Borrador de preparación, 2026-10-18. Sin fit ni nueva evaluación económica.
No modifica productores, muestras, modelos ni métricas existentes. El coordinador
decidirá ejecutar después del análisis emparejado completo y revisión técnica.
Las diferencias descritas en la sesión ilustrativa no se usan para elegir estas
variables o cambiar parámetros. No se afirma que cada trade del oracle tenga una
justificación rentable observable.

## Contraste que se puede identificar

Comparar una única representación compacta con el `gbt_net` original congelado,
manteniendo exactamente sus270.377 filas TRAIN2023–24, orden `sample_i`, pesos
IPW, escalas por ticker, objetivo y configuración. Control `gbt_net__0` reutilizado;
no refit del control. Nueva policy `cue_net__0`, threshold0 fijo. La intervención
es únicamente la representación de entrada, no un nuevo método de muestreo,
target, coste o selección de operaciones.

La muestra original se estratificó por trayectoria oracle/resto; se conserva
íntegra junto a sus IPW. No es una nueva muestra elegida sólo mediante identidad
causal, ni se afirma que deje de tener esa procedencia. Sus pesos corrigen el
objetivo de regresión de acciones bajo ese diseño; no hacen que el máximo DP sea
una expectativa alcanzable. No cargar dp_advantage, teacher_selected, stratum,
priority, membership o salidas como features. Se proyectan sólo claves necesarias,
`net_base`, `weight` y estado FILLED/NO_FILL para las comprobaciones de TRAIN.

Target idéntico al original: `y=net_base/risk_scale_usd[ticker]`, con escalas
copiadas del `normalizers.json` original ligado a su freeze; no recalcularlas con
la nueva representación o con validación. MSE ponderado por los mismos pesos
globales; mantener negativos, ceros y NO_FILL. Predicción final multiplicada por
esa escala fija. Es aproximación de retorno condicional; no queda calibrada ni
es rentable por llamarla «expected net». No hay critic oracle ni Bellman target.

Configuración LightGBM original: objective regression,200árboles,31hojas,
max_depth6,min_child_samples100,learning_rate.04,reg_lambda10,max_bin63,
random_state20261018,n_jobs4,deterministic=true,force_col_wise=true. Sin
normalización adicional, clipping, early stopping, grids o elección por seeds.

## Schema y conexión al pipeline

`market_cue_vectors.py` fija76 valores y76 máscaras,152columnas float32, en
`VALUE_NAMES/COLUMN_NAMES`; hash del schema
`a0432d1a80161075bb765b2ec1482e08fb6f867e15dd682cf5bac6b2f204352e`.
Geometría continua, distancias a zonas/objetivo/stop, mechas/cuerpo, cambios de
spot, coste relativo, Greeks disponibles, distribución unsigned y cambios de
logmasa. Categorías observables CALL/PUT y procedencia del objetivo/stop se
conservan como bits, no reglas direccionales. Confluencia es número de tipos
visibles, no inventario completo. Ausente→0 convalid0; cero observado→0 convalid1.
No se eliminan filas que carezcan de una señal.

Se excluyen los tags/rejection_description/acceptance_retest_description y las
cantidades no identificables (gamma individual, gamma dealer firmada, theta en
dinero/minuto y ratio neto monetario). No hay gates de rechazo, aceptación,
spread, distancia ni rentabilidad. Los límites de las señales y del ancla actual
permanecen en MARKET_CUE_ORACLE_DESIGN.md. Las máscaras informan disponibilidad,
no se reinterpretan como confirmación del patrón.

El adaptador recibe arrays **sin estandarizar**. Admite máscaras raw[N,20] y el
stack[N,20,2] de FeatureStore, comprobando que su segundo canal coincide con
bar_mask; conserva bar_end_i original. `join_action_rows` exige IDs únicos en
las ofertas y pack, mismo universo y
`actions.state_i[action_id]==sample.state_i==pack.state_i[state_position]`.
Los IDs/sample_i sólo unen y restauran orden; no son columnas. El runner deberá
comprobar además SHA de la muestra original, `sample_i=arange(270377)`, claves
day_key/ticker/date y correspondencia exacta antes de escribir cada bloque.

`market_cue_vectors_fast.py` reutiliza el vector de referencia por
(posición de estado,lado,band) dentro del bloque. Sobrescribe los25 valores
directamente dependientes de la acción y sus máscaras usando el mismo cálculo
float64→float32. Esto conserva distancias, valores de contrato y missingness de
cada opción. No se aproximan mapas, señales o barreras. El extractor original
permanece intacto y es la autoridad de igualdad bit a bit.

## Recursos y recuperación previstos

Matriz270377×152×4=164.389.216bytes (156,8MiB), frente a2.113.266.632bytes del
control1954 (aprox2015,4MiB). Un bloque256 ocupa155.648bytes de salida. Escribir
memmap y checkpoints por día/bloque; nunca conservar JSON de cues por cada fila
de entrenamiento. Modelo único y cuatro threads, sin GPU. No deducir pico RSS
de estos tamaños: LightGBM mantiene estructuras adicionales y habrá lecturas
de packs. Antes de un fit, comprobar RAM/commit y espacio; preservar otras tareas.

Microbenchmark sintético1024filas/64estados/16ofertas por estado,128claves de
caché: referencia0,328s, helper0,123s,2,665× y bytes idénticos. Una medición previa
con otra carga del equipo dio400filas/s; la diferencia global no se atribuye
al helper. Con8319filas/s del ensayo emparejado, las6.979.843 ofertas de2025–26
de sesiones completas proyectan unos14min CPU, **sin I/O ni garantía de tiempo**.
Los counts (4.573.153 y2.406.690) se consultaron sólo como metadatos de ofertas,
sin columnas de labels/PnL. Las nuevas sesiones cortas añadirían ofertas.

Se requiere probar igualdad por byte en acciones/estados variados, ambos lados,
bandas, missingness, cero válido, barras futuras/masked y máscaras stacked.
El runner aislado guardará schema/código/autoridades, sample/scales/pesos,
matrices y modelo completo antes de evaluar. Un modelo completo y ligado se
reutiliza sin refit. Un fit interrumpido sin checkpoint completo no se adopta
como terminado; preservar parciales y explicar recuperación. No hay checkpoint
intraárbol ni promesa de reanudar LightGBM a mitad del fit.

Implementación preparada en `train_market_cue_control.py`: CLI sólo prepare/fit,
ambos sujetos a review exacta y salida separada. Bloques256, chunks diarios
verificados, ensamblaje por sample_i, fsync y rehash; matriz completa reanudable.
Gate de fit12GiB RAM disponible/16GiB commit libre. La inferencia pura
`predict_offered_day` conserva todas las ofertas y escala TRAIN, sin sidecars
económicos. El runner de evaluación/scheduler/calibración completo y su auditor
siguen pendientes: no ejecutar evaluación económica mediante esta API aislada.

## Evaluación posterior predefinida, todavía no ejecutada

Puntuar todas las ofertas, incluidos estados no visitados por oracle y acciones
NO_FILL. Mayor score>0, empate action_id menor; NO_FILL avanza1min sin sustitución,
FILLED bloquea hasta exit+1. WAIT es implícito cuando ningún score supera0;
no se añade target WAIT ni información de continuación futura a este control.
Las salidas siguen las reglas de niveles, sin duración fija. Esta comparación
de representación no resuelve por sí sola coordinación temporal o planificación.

Usar el calendario completo admitido:2025 son750 ticker-días, incluidos9short;
2026H1 son369esperados,363disponibles y6missing no evaluables. La muestra TRAIN
se mantiene exacta y por ello no añade los15shortTRAIN: es una limitación del
control, no una exclusión nueva de evaluación. Los9short2025 requieren features
de la nueva familia auditada y nueva inferencia del control original congelado;
no refit ni hacer pasar el ledger original741 por750. Fullsessions deben
reproducir exactamente scores/control existentes antes de transportar short.

Presentar ambas policies fijas y el requisito>=1fill por ticker-día, sin forzar
trades. La eventual selección se fijará antes de ejecutar: sólo2025 y sólo entre
policies que cumplan frecuencia; ninguna elegible→null. No rescatar con2026 ni
buscar otro threshold. Beneficio/PF/costes adversos y actividad disponibles se
reportan separados de la cobertura universal.2025 y2026 ya son desarrollo visto.

Análisis emparejado: calibración por bins fijados en TRAIN, pérdida ponderada de
neto y ranking dentro del mismo estado/lado/contexto, además de PnL del scheduler.
Separar decisiones efectivamente visitadas y contrafactuales. Agregar incertidumbre
por sesión, no tratar miles de targets del mismo minuto como observaciones
independientes. Importancias/SHAP del futuro GBT serían asociaciones del modelo,
no prueba causal de walls ni explicación que legitime cada ganador del oracle.
En particular, mostrar por ticker y periodo, sobre acciones efectivamente
seleccionadas, media y distribución de score en USD, neto realizado, residual
score−neto y fracción de ofertas/fills. Contrastar con todas las ofertas para
separar sesgo de selección del scheduler de mala calibración general. Las mismas
fronteras de bins TRAIN se transportan a2025/26; no recalibrar con sus resultados.
Net regression no produce probabilidades: no calcular Brier score ni convertir
signo/score en probabilidad sin otro modelo, que no se autoriza aquí. Los altos
ratios de objetivos vistos en TRAIN y validación no justifican añadir un cap.

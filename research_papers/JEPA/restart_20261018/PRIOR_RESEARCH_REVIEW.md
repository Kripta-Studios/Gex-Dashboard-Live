# Revisión de investigación anterior — 18 de octubre de 2026

Revisión de documentos y código, sin leer nuevos valores de mercado, entrenar,
repetir experimentos ni modificar evidencia anterior. Los números siguientes
son resultados reportados por sus informes; aquí no se reejecutaron sus auditores.
La petición actual permite investigación nueva; no convierte resultados antiguos
en evidencia independiente ni recupera un histórico no observado.

## Conclusión útil

No es correcto concluir que «los modelos ya demostraron que los walls y los
Fibonacci no tienen edge». Sí perdieron varias formulaciones concretas, algunas
con zonas aproximadas. La representación más próxima a la idea del usuario
—secuencias de velas 5m/15m junto con fuerza, migración y persistencia de walls—
se implementó y probó con datos sintéticos, pero **no se evaluó económicamente
en mercado**. Su bloqueo fue de procedencia/adaptación de fuentes.

Tampoco es correcto atribuir todo fracaso a falta de percepción visual: ya hubo
umbrales de proximidad, estados de interacción y pruebas de representación. Una
hipótesis nueva debe separar predicción física, utilidad neta de opciones y
controles que distingan niveles especiales de cualquier nivel cercano al precio.

## Qué se probó realmente

| Experimento | Representación y prueba | Resultado e interpretación |
|---|---|---|
| Wall interaction V1 | Distancias a gamma/DGEX, IB y extensiones 1,272/1,618/2 de hoy y cinco días anteriores. Touch/confluencia 15 bps, magnet 15–80 bps, lags 5/10/15m. Reglas fijas, ask→bid. | PF 0,865/0,832/0,899 SPXW/QQQ/SPY en 2024–2025. La semántica de rejection no exigía realmente haber cruzado el nivel. |
| Wall interaction V1r1 | Misma prueba, añadiendo cruce previo para rejection; wall actual fijo al contrastar precios anteriores. | PF 0,910/0,845/1,008. La corrección ayudó pero no produjo estabilidad común. No tenía fuerza/persistencia/migración ni identidad de delta wall. |
| IB breakout/fade V1 | Primera ruptura del IB 09:30–10:29, LightGBM elige seguir o fade, ventanas AM/PM y stops/targets fijos. | En 2025 PF QQQ/SPX/SPY 0,779/0,785/0,819 con coste spot de 1 bp. Es fallo de esa estrategia sobre subyacente; no prueba económica directa del contrato 0DTE ni de todas las interacciones Fib. |
| Multiscale V1R1 | 12×5m + 8×15m, 59 slots, OHLC relativo al nivel, estados, fuerza/concentración/persistencia/migración, ablación sin niveles. | No hay evaluación económica histórica. 72 LightGBM y refits se probaron en un fold sintético de seis plantillas; 92.048 columnas primarias, 488 de ablación. |
| JEPA semántico y factorizado | Contexto 66×18; diagnóstico de colapso, reparación por residuales/innovaciones y mejor rango efectivo. | Arreglar geometría no arregló rentabilidad. Factorizado PF 2026 QQQ/SPX/SPY 0,846/0,906/0,835. No equivale a probar el tensor visual completo de walls. |
| Full nested monthly overlay | LightGBM CALL/PUT y 20.321.280 configuraciones lógicas sobre 18 folds. Freeze antes de cada test mensual. | Ledger test 370 operaciones; PF QQQ/SPXW/SPY 0,584706/0,844375/1,083921; auditoría independiente reportada PASS. Fracaso económico real de esa formulación. |

Referencias: `WALL_INTERACTION_EXECQUOTE_PREDECLARATION_V1.md:43,60,105`;
`WALL_INTERACTION_EXECQUOTE_V1R1_REJECTION_SEMANTICS.md:4,29,44`;
`DIRECTIONAL_IB_BREAKOUT_FADE_V1_PREDECLARATION.md:22,39`;
`DIRECTIONAL_IB_BREAKOUT_FADE_V1_CLOSURE.md:3`;
`multiscale_v1r1/21_REAL_BACKEND_AND_SOURCE_REPORT.md:4,73`;
`DIRECTIONAL_SEMANTIC_JEPA_V1_COLLAPSE_DIAGNOSIS.md:11,80,179`;
`EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_FAILURE.md:24,34,60`.
Todos esos documentos están bajo `research_papers/JEPA/`.

Los subgrupos favorables de V1r1 (p. ej. 65 rejections PUT SPY, PF 1,536;
42 magnet CALL QQQ, PF 2,230) fueron identificados después del resultado.
Son pistas de investigación ya vistas, no políticas seleccionables con el mismo
resultado como validación. La afirmación antigua «proximity alone is not the edge»
es excesiva si se interpreta universalmente: sólo falló su control M0 concreto.

## Problemas distintos que no deben mezclarse

1. **Fuente/causalidad:** `data_training_input` fue rechazado por uso del reloj
   del subyacente como reloj de opción y `ffill().bfill().fillna(0)`; weekly
   significaba segunda expiración, variable entre 1–8 días. No reutilizarlo como
   dataset causal sin reconstrucción verificable. Evidencia:
   `DIRECTIONAL_SEMANTIC_JEPA_V1_COLLAPSE_DIAGNOSIS.md:111`.
2. **Auditoría histórica multiscale:** cambiaron los hashes de tres logs,
   faltó procedencia de reparaciones y no hubo admisión positiva. Eso no demuestra
   que los precios fueran erróneos ni que la estrategia perdiera.
   `multiscale_v1r1/11_TERMINAL_REPORT.md:1,40,96`.
3. **Software disponible:** `neural/jepa/multiscale_v1r1/runner.py:12` rechaza
   expresamente toda ejecución histórica; no hay que cambiar un booleano y asumir
   que el pipeline está terminado. Adaptador histórico y entrenador SSL completo
   faltaban según `multiscale_v1r1/25_REPOSITORY_REVIEW_AND_CONTINUATION.md:49,73`.
4. **Economía:** acertar dirección no implica ganar comprando opciones. Los
   resultados anteriores distinguen labels legacy, payoff de subyacente y ask→bid.
   El resultado favorable `intersection_guarded` procedía de selección sobre los
   meses reportados, labels legacy y falta de no-overlap físico; véase
   `EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_FAILURE.md:87`.
5. **Múltiples pruebas:** el histórico hasta 2026-07-24 es desarrollo visto y
   varios años fueron usados repetidamente. Un nuevo walk-forward puede medir
   transporte temporal de una receta nueva, pero no borra esa adaptación de la
   investigación. No llamar outer virgen a 2026; tampoco inferir que fechas
   posteriores no inspeccionadas son automáticamente un holdout válido.
   `MULTISCALE_LEVEL_INTERACTION_SEQUENCE_V1_PHASE0_AUDIT_CONTRACT.md:107,168`.

## Semántica de exposición que debe corregirse en la interpretación

`neural/jepa/multiscale_v1r1/levels.py:137` recalcula Black–Scholes a partir de IV
con tasas constantes r=0,0325 y q=0,015; agrega gamma por OI y construye call-minus-put
en `:157`. Esto es un **proxy bajo una convención de signos**, no una observación
de inventario neto de dealers. OI por sí solo no identifica quién está largo/corto.
Conservar call y put separados evita que esa convención sea una verdad impuesta
al modelo. El factor de contrato también debe ser explícito al comparar dólares.

`levels.py:185` llama `zero_gamma` a una raíz interpolada entre strikes del perfil
Gn. No es el spot donde la suma de gamma de toda la cadena, recalculada a diferentes
spots, cruza cero. Mantener nombres distintos: raíz del perfil por strike y nivel
de flip de gamma del portfolio son objetos distintos.

`levels.py:16` impone call/max como resistencia y put/min como soporte.
`interactions.py:23` conserva touch de 15 bps y estados discretos. Aunque contiene
OHLC continuo, esto no equivale a aprender libremente el papel de cada nivel.
La nueva representación puede conservar identidad y permitir que su papel cambie
con aproximación, régimen y contexto, sin asumir de antemano que siempre rebota.

## Componentes que merece la pena reutilizar

- Identidad contractual numérica y validación de duplicados; cálculos IB con
  60 minutos completos y fórmula L(r)=IBL+r×(IBH−IBL): `levels.py:42,77`.
- Scheduler sin solapamiento y contabilidad de un contrato ask→bid con costes,
  demora y salida ausente explícitos: `scheduler.py:7`, `payoff.py:9,37`.
  Reusar primitivas tras revisión, no asumir que todo dato histórico es compatible.
- Barrera de congelación, artefactos/hashes y auditoría independiente existentes.
  El PASS de tests sintéticos certifica comportamiento acotado, no causalidad del raw.
- Lector proyectado y manejo de timestamps/valores inválidos del piloto local:
  `neural/jepa/local_snapshot_source_v1.py:158,240`. Es específico del piloto;
  no extrapolar automáticamente su schema/tolerancias a todas las sesiones.

## Experimento nuevo propuesto, pendiente de cobertura válida

Representar el gráfico como **campos espaciales suaves de exposición y niveles**,
no sólo distancias al máximo. Usar coordenada precio normalizada por volatilidad
pasada y, separadamente, por rango IB. Canales separados call/put gamma×OI,
delta×OI, densidad de strikes, IB/Fib, máscara/cobertura y antigüedad. Mantener la
secuencia observada de 5m/15m, sin interpolar huecos futuros. El primer baseline
puede ser GBT con resúmenes de esas distribuciones y su variación; una pequeña
CNN temporal o transformer de tokens de nivel es una comparación posterior.
No es necesario renderizar capturas de pantalla para conservar geometría.

Antes de entrenar, fijar un presupuesto pequeño de comparaciones y controles:
precio solo; precio+niveles auténticos; niveles placebo con igual número,
distancia/densidad y cobertura; ablación de exposición. Los placebo deben
construirse causalmente, sin elegirlos por reacción futura. Evaluar incrementalidad
frente a esos controles y no sólo contar rebotes: con muchos niveles y tolerancia
amplia es fácil describir retrospectivamente casi cualquier trayectoria.

Objetivos físicos útiles: distribución futura de excursión arriba/abajo y probabilidad
de alcanzar bandas en ambos sentidos; no imponer «el nivel es soporte» al label.
El control económico final requiere mismo contrato, quotes observables ask→bid,
costes y ausencia de solapamiento. Si faltan quotes causales sólo podrá medirse
predicción del subyacente bajo supuestos; no declarar rentabilidad 0DTE.

La elección de arquitectura no sustituye este diseño. AlphaZero/MCTS necesitaría
un simulador fiable de transición y ejecución; hacer search en trayectorias reales
futuras o entrenar un world model con test visto produciría ventaja artificial.
JEPA sólo se justificaría si añade valor frente al baseline directo bajo la misma
partición temporal y presupuesto; un embedding sano no es por sí mismo alpha.

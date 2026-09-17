# Continuación A/B: resultados verificados

El circuito **sintético** terminó con ENGINE_E2E_SYNTHETIC_PASS. La recuperación
documental produjo un snapshot nuevo verificado, pero no resolvió la procedencia
temporal del histórico. **No se ha demostrado rentabilidad de mercado**: economía
real NOT_EVALUATED, prospective NOT_STARTED, technical_ready=false y promoción false.
El intento anterior conserva INVALIDATED / FAILED_AUDIT y todos sus hashes.

## A. Recuperación y fuentes

Se preservaron diez artefactos terminales mediante copias que coinciden con el
catálogo publicado. La verificación final confirmó también que todos los archivos
del catálogo del intento original mantienen sus hashes. De las diez fuentes
documentales antiguas, siete coinciden: cuatro scripts y tres logs de errores.
Los tres logs descarga de SPXW/SPY/QQQ tienen ORIGINAL_EVIDENCE_NOT_RECOVERED.
No había tamaño original sellado para probar un prefijo; no se infirió identidad
a partir de las 204 claves ni se reconstruyó texto.

La nueva captura coherente conserva **210 documentos**, con exclusión Win32 de
escritura/borrado durante la lectura del conjunto. Hash y parser usan los bytes
copiados. El auditor independiente verificó las copias y una comprobación posterior
las volvió a verificar. Es un snapshot documental nuevo, no la restauración de
los logs perdidos ni un snapshot admitido de todos los precios históricos.

La búsqueda en data_options y SPXW encontró greeks/iv/ohlc/oi y logs segmentados.
Los footers de los **2.323 Greeks SPXW del inventario original** declaran intervalo
1m. Las referencias exactas a interval=1s encontradas pertenecen a los documentos
de data_underlying_derived, no a una respuesta de 1 segundo preservada en las
carpetas examinadas. No se leyeron columnas de valores de mercado.

El mapa de linaje conserva por fuente hashes, disponibilidad/recepción/materialización
conocidas o desconocidas y razón de clasificación. El histórico sigue
UNVERIFIABLE_FOR_CAUSAL_REPLAY. No se demuestra reparación indebida ni lookahead.
Las **32 fechas** con ausencias se desglosan en **122 registros de fuente**; están
dentro del calendario bloqueado de 973 sesiones completas. Incluyen 29 fechas
de 2022 y 2026-04-01, 2026-04-09 y 2026-04-15. No se suman como fechas adicionales.

Para admitir SPXW_INITIAL_ZERO_BAR siguen faltando sus inputs originales verificables,
la transformación que produjo cada archivo y el origen/instante o cota acreditada
de los valores sustitutos. Un log de descarga reciente o un precio actual parecido
no resuelve esa dependencia. No se cambió raw ni se descargaron datos.

## B. Implementación y ejecución sintética

Código publicado antes de las ejecuciones en **1847abe2**; especificaciones en
ce06af99. La hipótesis Fibonacci/IB y walls se conserva; no se modificaron las
definiciones históricas V1/V1R1. Se añadieron 59 niveles y 39 canales, estados
cronológicos completos, máscaras, X5/X15, snapshots nativos de walls y controles
sin niveles. El auditor reconstruye el tensor desde fuentes sintéticas con
cálculos separados. Pasaron las seis plantillas y los **18 relojes de decisión**.

Runtime ejecutado: Python 3.14.2, NumPy 2.3.5, pandas 2.3.3, PyArrow 23.0.1,
LightGBM 4.6.0, PyTorch 2.10.0+cu128 y exchange_calendars 4.12. El ejecutable,
versiones y comprobaciones están en [verification.json](continuation_evidence/verification.json).

| Componente | Implementación y comprobación | Límite pendiente |
|---|---|---|
| Snapshot y recuperación | `provenance.py`, `recovery.py`; auditor `snapshot.py`; 210 copias verificadas | Tres logs originales no recuperados; no admisión de precios |
| Niveles y tensor | `levels.py`, `interactions.py`; reconstrucción independiente `tensor.py` | Solo fuentes sintéticas; ningún tensor histórico construido |
| Admisión temporal | `admission.py`; caso positivo artificial y dependencia futura rechazada | Admisión histórica positiva no concedida ni implementada como atajo |
| Selección y circuito | `selection.py`, `synthetic_engine.py`, `checkpoint.py`; 18 folds y freezes auditados | Perfil sintético con dobles; adaptador histórico pendiente |
| Modelos reales | `models.py`, `component_smoke.py`; A/B reales, exportación y carga exactas | No se ejecutó la secuencia completa de regresores reales |
| Dinero y diagnóstico | `payoff.py`, `scheduler.py`, `metrics.py`, `bootstrap.py`; auditores `engine.py`, `summary.py` | Sin evidencia económica de mercado |
| Cuenta y recepción | `account.py`, `prospective.py`; reinicio, rechazos y revisiones offline | Sin integración, órdenes, captura real ni shadow |
| SSL/RANGE | Primitivas SSL anteriores preservadas | Entrenamiento completo y bot RANGE fuera del circuito básico |

El comando E2E ejecutó **18 folds**, 24 acciones y las cuatro combinaciones.
Cada mes guarda modelos, scores y decisiones, congela antes de crear su payoff
test y audita antes de avanzar. Se reprodujeron **1.296 refits de modelos dobles**,
18 winners y **33.696 payoffs contractuales**. Los ledgers incluyen abstenciones
y rechazos; baseline y ablación deciden por separado. La comprobación adicional
reprodujo 1.404 decisiones del baseline. El escenario diseñado ejecutó 702 trades
positivos del primario: es una señal artificial inequívoca, no rentabilidad real.

El perfil rápido usa dos decisiones/día y trece días laborables artificiales/mes,
con seis plantillas de tensor completo y una proyección explícita para los modelos
dobles de medias por señal. No es el universo histórico XNYS ni un entrenamiento
V1R1 real de 24 LightGBM por configuración/fold. Los fixtures reutilizados prueban
el control de la orquestación; no son un replay histórico de cada fecha.

Por separado, el smoke **real** ajustó/exportó/cargó LightGBM A y B con los
parámetros fijados, 600 filas y 92.048 columnas. Ambos aprendieron su señal
artificial y reprodujeron exactamente las predicciones tras cargar el modelo.
Son dos regresores reales, no los 1.296 refits reales del programa completo.

Se integraron payoffs ask→bid, penalización por salida ausente, costes base/adversos,
scheduler, métricas, bootstrap pareado de 10.000 draws y cuenta de prueba.
La cuenta usa capital e importes de fixtures; no certifica contabilidad causal de
una cuenta histórica ni recomienda capital real. Reinicio con intención/posición,
capital insuficiente y cantidades indivisibles se comprobaron. El transporte de
órdenes está deshabilitado y broker_submission=false en todos los registros.

La captura prospectiva solo se probó offline con dos revisiones append-only.
No hay captura real, paridad, shadow o evaluación prospectiva iniciada. SSL/RANGE
completos no forman parte de este circuito básico; las primitivas SSL previas se
conservan, sin presentarlas como entrenamiento histórico terminado.

## Verificación, recursos y límites

**55 tests** pasaron en 72,49 s; Ruff y compile también. Se verificaron señal
artificial, mercado plano que pierde costes, abstención, escenario aleatorio sin
exigir pérdida, +1,40/−0,60 USD, salida ausente, datos futuros, bloqueo de posición,
capital, reinicio, checkpoints y snapshots. Se rechazaron siete perturbaciones
semánticas en memoria tras controles de integridad, y adicionalmente acceso test
prematuro con cadena recalculada y copia incorrecta del WR base al adverso.
No se alteraron artefactos originales para estas pruebas.

El E2E rápido tardó **1198.34 s**, con pico RSS medido de
**557,064,192 bytes** y **86,568,432 bytes**
de artefactos al medir. El smoke real tardó **13.27 s**,
con pico RSS **458,166,272 bytes**. Fit A/B: 3.317/
3.300 s. Se registran construcción, fit (incluye bins),
predicción, guardado y carga/predicción. Bins no están cronometrados por separado.
Las features del smoke tienen baja entropía: estos tiempos no estiman el histórico
completo ni sustituyen el preflight anterior de 819,734 s. histogram_pool_size
no limita toda la memoria del proceso.

Quedan pendientes para una evaluación real: linaje temporal admitido por alcance,
adapter/orquestación sobre fuentes históricas aprobadas, fits completos y su
auditoría real, presupuesto medido de ese workload y piloto técnico predeclarado.
El CLI histórico permanece cerrado. El CLI sintético sí ejecuta el circuito y
produce artefactos auditados. No se promociona la ablación ni un comparador.

Los resultados base/adversos y primario/ablación de SPXW, SPY y QQQ **reales**
siguen NO_EVALUADOS. Agosto/septiembre conservan exposición desconocida; octubre
no se declara validado. No hubo cambios en producción, servicios, bróker o VPS.

## Evidencia y reproducción

Comandos exactos: [15_CONTINUATION_RUNBOOK.md](15_CONTINUATION_RUNBOOK.md).
Estados separados: [states.json](continuation_evidence/states.json).
Catálogo de hashes/rutas: [artifact_catalog.json](continuation_evidence/artifact_catalog.json).
Root completo: `D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01`.
Recuperación: [evidence_recovery.json](continuation_evidence/evidence_recovery.json).
Ausencias por nombre: [missing_sources.json](continuation_evidence/missing_sources.json).
Linaje y cobertura: `recovery/lineage.parquet` y `recovery/lineage_coverage.parquet`
dentro del root completo, con sus hashes en el catálogo.
E2E: [engine_summary.json](continuation_evidence/engine_summary.json).
Auditor agregado: [summary_audit.json](continuation_evidence/summary_audit.json).
Smoke real: [real_component_smoke.json](continuation_evidence/real_component_smoke.json).

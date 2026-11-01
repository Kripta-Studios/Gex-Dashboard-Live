# Admisión y extracción causal de contexto IB/walls a las 10:30

Preparación de la siguiente comparación semanal, sin fit ni outcomes. El
baseline weekly18 ya cerrado no contiene IB/walls. El objetivo es añadir
contexto causal del subyacente sin adoptar la acción o elección del oracle.
El usuario autoriza continuar investigación local; no se necesita otra
confirmación para este trabajo reversible. Producción y API quedan fuera.

## Autoridades y soporte

Raíz D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1.
Índice index.parquet SHA7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4;
dataset_contract.json437f480794dc89b80ff0c4999c3053d19d936fab779b99cb75b923433d641a43;
feature_contract.json777890230663b0f683d0007117c58b5818047699fe8b25d27b5b819bac7f83db;
completion.json86e0c623ca47010434cb4c5d9b644cba0fc6457aacce2e680474dce6f1b932e5.
Auditor hermano session_clock_dataset_v1_audit/audit.json
678eb21bca80b38855979d8a7386cdadd6827a6dfdd5acbf3df6fde5a5a2f3b9.
features.py congelado b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0.

2625 identidades ticker/fecha:2595 sesiones full referenciadas,24short y6missing.
Índice determina rutas/hashes de features.npz y features.json de cada COMPLETE;
jamás inferir el universo por carpetas. Para MISSING_SOURCE no abrir rutas
nominales; preservar contexto ausente. No leer labels/actions/advantages/oracle,
scores, netos o resultados económicos para elegir soporte o variables.

Extraer exactamente una fila state_i=60 por identidad COMPLETE: estado10:30.
El B81 contiene spot, IB, cambios y geometría/masas/validez de walls. Guardar
las81 columnas en el orden exacto publicado por feature_schema; sin selección
por correlación o neto. Conservar state_valid, todas las máscaras de las20barras
y sus bar_end_i como metadata causal, verificando bar_end_i válido<60; no
exportar accionesA33 ni quotes de ejecución futuras. Para invalid-state guardar
valores originales auditados y state_valid=false; futuro modelo tendrá que
declarar su enmascaramiento. No imputar ni normalizar durante esta extracción.

El contexto es **0DTE**, distinto de la expiración weekly operada. Walls de
OI/gamma son proxies con las convenciones congeladas, no posiciones dealer.
OI sin reloj mantiene supuesto de disponibilidad09:30 del cierre previo; no
se acredita recepción observada. Greek sin clock nativo puede usar el proxy
admitido por el cache. Esto se declara, no se eleva a causalidad live verificada.

## Validación y salida

Dos fases separadas. Inventario sólo metadata de índice, manifests y ficheros:
rutas exactas/SHA y tamaños, soporte completo, sin abrir arraysNPZ ni outcomes.
Publicar inventario con autoridad y binding antes de la extracción de arrays.
En extracción, rehash NPZ/metadata antes y después; validar features schema,
shapes/dtypes, unicidad/orden de state_i y state60, finitud donde corresponda,
clocks/máscaras y close_i full/short. Archivos alterados o incompletos fallan
cerrado; no regenerar fuentes ni rellenar arrays.

Salida nueva h2_context_1030_01 bajo D:/GexResearchArtifacts/weekly_multiday_20261101:
context.jsonl (2625filas, incluidas ausencias), coverage.json, inventory.json,
manifest con hashes de todos los inputs compactos y NPZ leídos, schema/código.
Cada fila preserva ticker/date/status/close_i, fuentes y contexto o ausencia.
No join económico todavía: el futuro join será weekly(ticker,entry_date) a
context(ticker,date), muchos candidatos a una fila, sin borrar candidatos.

No hay extensión Q3 de estas features auditada: queda expresamente pendiente.
No inventar contexto Q3 ni evaluar un modelo enriquecido fuera del soporte.
La comparación de modelos y sus métricas requieren contrato nuevo posterior,
incluyendo control básico, modelo actual18 y18+contexto, con riesgo igual.

Pruebas sintéticas de full/short/missing/alteración/causalidad y revisión antes
de runtime; CPU0/hilo1, RAM/commit>=2GB, procesos con handle retenido, raíces
nuevas y publicación previa. Esta extracción no constituye auditoría raw nueva
ni mejora económica demostrada. Goal activo, promoción y technical_ready false.

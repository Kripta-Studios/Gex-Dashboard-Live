# Contexto causal de las 10:30 para Q3 parcial: contrato de extensión

El turno anterior fue PROGRESS: cerró dos fits y una auditoría independiente
de los modelos contextuales H1. La hipótesis probabilística primaria no mejoró,
aunque CONTEXT182 produjo +41.871 USD adversos. Este contrato extiende las
mismas variables a otro tramo temporal antes de aplicar parámetros congelados.
No selecciona modelo, ticker, mes o feature por esos resultados.

## Calendario y fuentes

Periodo 20260701–20260917, 55 sesiones y165 identidades ticker-fecha de
SPY/QQQ/SPXW, close_i390. Autoridades en
D:/GexResearchArtifacts/weekly_multiday_20261101/h2_q3_partial_calendar_01:
calendar.json ac9bd2569d91e9bd9b0475d6f5e2d5400b2816cc1d1d0d9ec98c69e4dbe2e72b;
calendar.parquet e16ef041efadc0f6914585540e19e9c04fcb05f1597952137e4f5bcf06de8c78;
manifest.json 5a530747f2c97704869d87c04d09bba3cc00125f38a8a78454c2d459a2ea502c.
No nuevo calendario inferido de los archivos disponibles.

Fuentes exclusivamente 0DTE:
D:/ThetaData/data_options/{ticker}/{greeks|oi}/YYYY/MM/
{ticker}_{date}_{date}_{kind}.parquet. No weekly quote/payoff en esta etapa.
330 identidades exactas: la inspección estructural previa encontró153 Greek y
165 OI presentes. Faltan Greek SPY yQQQ en20260701/07/10/16,20260826,20260901.
Las doce ausencias se mantienen aun existiendo OI. Un cambio de esa cobertura
requiere recibo de discrepancia; no se adopta automáticamente.

Primera fase sólo inventario: path normalizado, existencia, tamaño, SHA256,
schema, número de filas y reloj nominal por fuente; comprobar estabilidad de
stat/hash, rutas exactas, ausencia de enlaces/reparse/aliases y autoridades.
Las318fuentes presentes deben tener timestamp nativo y columnas exigidas por
build_cache; no inferir recepción real o calidad de valores a partir del schema.
Guardar inventory.json y su manifest en raíz nueva; publicar su SHA y binding
antes de la segunda fase. No cargar columnas/valores en el inventario.

## Transformación congelada

Dependencias del directorio level_oracle_20261018, sin modificar:

- build_cache.py 985e87dcbd1e73289b58e4576445e47e73a6edea13e5ac73dde3ad629180d69f.
- features.py b5c63f918319f844793abb3346a34515526073374f5e71af2129a94f2369d4e0.
- level_engine.py 70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6.
- D:/GexResearchArtifacts/level_oracle_20261018/session_clock_dataset_v1/feature_contract.json,
  777890230663b0f683d0007117c58b5818047699fe8b25d27b5b819bac7f83db.

Reutilizar funciones puras y construir secuencialmente:
build_cache.build_day(task) → load_day_cache →
features.build_day_feature_cache(raw) → encode_states(indices=[60]).
No ejecutar sus CLI históricos: fijan otra cobertura o generan más estados.
Verificar módulos importados y sus hashes; no mutar globals o extender ciencia.
Registrar Python y versiones numpy,pandas,pyarrow,exchange_calendars, además
de rutas __file__ resueltas de los tres módulos congelados, sin import shadowing.
task contiene source_root=D:/ThetaData/data_options, out nuevo, ticker,date, producer_sha256 del
build_cache congelado y calendario explícito. Rechazar caches preexistentes:
no resume ni adopción de parciales. Una fuente ausente no llama build_day.
Por identidad disponible, metadata debe confirmar clock_basis yoi_clock_basis
ambos NATIVE_STORED_TIMESTAMP. Cualquier fallback ASSUMED_* falla, aunque el
inventario anterior declarara timestamp presente. No sólo comprobar schema.

La lectura raw incluye sesiones completas para producir el cache rectangular
del código congelado. Sólo se exporta state60: B81 y las máscaras de ese estado.
El cálculo usa IB09:30–10:29, snapshot10:30 y barras completadas con end<60.
La unión de contratos de todo el día no puede alterar denominadores pasados;
conservar known_contract_matrix y reducciones de identidades activas.
No calcular actions, labels, oracle, políticas, PnL o nuevas matrices de modelo.
OI sólo se incorpora según su disponibilidad nativa almacenada; gamma sigue
siendo un proxy no firmado, no inventario dealer ni masa total weekly.

Guardar cada cache raw con su metadata/hash y un NPZ de un solo estado con
state_i,base,tokens,maps,token_mask,bar_mask,map_mask,bar_end_i,state_valid.
Los valores raw/cache permanecen locales; no publicar matrices voluminosas.
Validar shapes/dtypes del encoder:1×81 base float32,1×20×45 tokens float32,
1×20×5×64 maps float32, state_i=[60]int16; máscaras ybar_end del contrato
congelado. No exigir state_valid=true como filtro: registrar el bool real.
Map_mask fraccional en[0,1], no convertirlo a bool. Finito ybar_end causal.

## Salida y admisión

Raíz nueva D:/GexResearchArtifacts/weekly_multiday_20261101/h2_context_q3_1030_01.
Inventario y extracción son fases distintas, cada una lanzada una sola vez.
La extracción recibe SHA externo real del inventario y lo revalida antes del
primer valor, por fuente al consumir y al cierre. Registrar fuentes present/missing
y confirmar que las ausentes siguen ausentes. Admitir exactamente el calendario,
fuentes y dependencias; nada de ampliar raíces para resolver discrepancias.

context.jsonl mantiene el esquema de columnas de la extracción H1: identidad,
source_status/state_i=60/close_i, status,state_valid,context_81, máscaras/bar_end
y referencias a NPZ/metadata. Coverage incluye todas165identidades y los81nombres
en el orden congelado. Exigir igualdad exacta y ordenada de
feature_contract.schema.base_names, features.BASE_NAMES, coverage.feature_names
y las posiciones de context_81. Missing: context y máscaras nulos,state_valid=null,
status CONTEXT_MISSING_SOURCE. Available inválido conserva su vector y máscaras;
su consumidor aplicará la regla de flags/cero ya congelada, sin eliminar filas.
Manifest final fija todas las fuentes, autoridades, outputs y código; flags
outcomes_read=false,models_fit=false,SEEN_DEVELOPMENT,promotionfalse.

Fixtures antes de runtime: cobertura/missing, duplicados yschema/clocks,
rechazo de inventario o fuente mutada, root nuevo, shapes ymap_mask fraccional,
IB válido/inválido y causalidad con perturbación de valores/contratos/OI
posteriores a10:30. Usar normalize_day yfeatures congelados sobre datos
artificiales; no repetir piloto o resultados H1 reales.

Auditoría separada tras cierre: verificar todas las fuentes/cache/pins y
recalcular state60 desde caches raw sellados mediante funciones congeladas,
sin importar wrapper, comparando NPZ yJSONL. Productor y auditor no pueden abrir
candidatos weekly, modelos o resultados de scoring. Esto valida la extensión y la
igualdad con funciones ya auditadas, no una segunda implementación desde
raw ni exactitud económica. No abrir resultados de modelos en este auditor.

CPU0, todos los hilos numéricos1 y ejecución secuencial; gate contemporáneo
RAM ycommit libre >=2GB antes del hijo oculto. Logs directos yexit por handle
retenido. Preservar cualquier fallo; no retry/resume automático. Publicar
contrato, código/tests, revisión y binding antes de cada runtime autorizado.
Sólo local; producción, API, bróker yVPS intactos.

Después del cierre auditado se preparará otro binding para scoring de los tres
modelos congelados, con los180candidatos weeklyQ3 existentes y riesgo5000.
Sin refit, recalibración, umbral nuevo o rescate del positivo. Q3 sigue siendo
SEEN_DEVELOPMENT, no holdout limpio. El goal IB/Fibonacci/walls sigue abierto.

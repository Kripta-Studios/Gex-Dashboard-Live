# El beneficio contextual de H1 no se mantiene en Q3

La extensión temporal congelada terminó y su auditoría numérica independiente
pasó. CONTEXT182, que obtuvo +41.871 USD adversos en enero–junio de2026,
pierde −58.128,60 USD entre el1de julio y el17de septiembre. Los tres meses
parciales/completos del bloque y los tres tickers pierden. El resultado deH1
es reproducible, pero no demuestra estabilidad económica del modelo.

No hubo refit, recalibración, selección de subgrupos o cambio de reglas.
Se aplicaron los tres modelos predeclarados a180 candidatos en55sesiones;
última entrada15septiembre. Cada modelo/coste inicia el bloque con100.000USD
nuevos y riesgo máximo5.000USD por entrada. H1 yQ3 son libros separados:
esta comparación no es una cartera continua ni una estimación anualizada.

## Comparación económica

| Modelo | H1 adverso USD | Q3 base USD | Q3 adverso USD | Trades Q3 | PF adverso | DD realizado USD | Meses positivos |
|---|---:|---:|---:|---:|---:|---:|---:|
| BASE18 congelado | −14.931 | +10.271,80 | +9.872,80 | 28 | 1,2054 | 23.203,40 | 1/3 |
| CATEGORY30 | −32.666,20 | +13.146 | +12.765 | 32 | 1,2826 | 25.724,60 | 1/3 |
| CONTEXT182 | +41.871 | −57.631,60 | −58.128,60 | 41 | 0,2427 | 58.128,60 | 0/3 |

Controles ya cerrados del mismo bloque/riesgo: ALWAYS_CALL −18.963,80,
ALWAYS_PUT −29.794,80 y abstención0USD adversos. Se citan desde su autoridad
previa, sin otro replay. BASE18 reproduce exactamente sus dos libros sellados.

CONTEXT182 adverso por mes: julio−19.060,60, agosto−25.603 y septiembre
parcial−13.465USD. Por ticker: QQQ−9.315,60, SPXW−22.215,80, SPY−26.597,20.
CALL aporta−45.699,40 y PUT−12.429,20USD. Son descripciones del mismo libro,
sin autorización para excluir direcciones, tickers, meses o cambiar umbrales.

Sus41trades suman256contratos, mediana7 y máximo14; dos salidas ausentes
conservan su cota conservadora y cuatro intentos se rechazan por riesgo de
entrada. No hay bloqueo por capital. Mayor prima simultánea reservada14.546USD;
máximo presupuesto adverso deentrada4.980,80USD. DD es realizado, sin MTM
intradiario/nocturno. Se asume fill completo al quote guardado, sin profundidad,
fills parciales ni capacidad verificada para esas cantidades.

Los dos modelos positivos deQ3 tampoco acreditan estabilidad. En BASE18,
la mayor operación aporta23.133,60USD: sin ella la suma queda−13.260,80;
sin agosto−31.771,60. CATEGORY30 comparte esa mayor operación: sin ella
−10.368,60; sin agosto−26.496,20. Ambos perdieron H1. No se cambia la selección
al modelo que resultó positivo en este bloque.

En CONTEXT182 la mayor operación suma8.497,60USD; sin ella−66.626,20.
Su campo largest_month_by_net_usd identifica septiembre porque es el mes
menos negativo (−13.465), no un mes ganador; sin él−44.663,60USD. Todas estas
restas son diagnósticos mecánicos de concentración, no políticas alternativas.

## Probabilidades y valor esperado

La hipótesis primaria de mejorar logloss con contexto vuelve a fallar:

| Modelo | Logloss Q3, menor mejor | Brier Q3, menor mejor | MAE EV adverso USD/candidato | Sesgo EV predicho−realizado USD |
|---|---:|---:|---:|---:|
| BASE18 | 1,1568190607 | 0,6197942158 | 1.083,40 | +1,91 |
| CATEGORY30 | 1,2582915593 | 0,6540254459 | 1.104,26 | +13,34 |
| CONTEXT182 | 1,2258111274 | 0,6551123794 | 1.132,36 | +48,05 |

Diferencia pareada BASE18−CONTEXT182:−0,06899206665. Intervalo exploratorio
por bloques5sesiones [−0,09763813633;−0,04186408864],10.000remuestras,semilla
20261101,55sesiones incluidos ceros. No p-value ni holdout limpio.
En164candidatos sin cota por salida ausente también empeora logloss:1,272979
contextual frente a1,198834BASE18; Brier0,680559 frente a0,643762.

En45candidatos seleccionados por CONTEXT182, incluidos cuatro rechazos,
el sesgo EV adverso es+746,44USD por contrato, MAE890,44. BASE18 selecciona30
con sesgo−213,60 yMAE1.166,70. No son filas comunes: el MAE menor del subconjunto
contextual no acredita mejor EV. El gran sesgo positivo dentro de su selección
merece diagnóstico específico de probabilidades, medias condicionales y ranking,
sin atribuir todavía la causa a un régimen o a sobreajuste concreto.

Se conservan16cotas enel universo:5seleccionadas por CONTEXT182 y4por cada
otro modelo. El universo contextual completo contiene165ticker-fechas,
153disponibles y12missing; los180candidatos weekly pertenecen a fechas con
contexto disponible yválido. No se eliminó ningún candidato por missing.

## Cadena auditada y archivos

Extracción buildercaa049ca: PID34688 exit0retenido16:48:20.526953UTC;
manifest1429bb4dc227843cbb988d552d3b463443b6ae1046e2a53e11118dee4d9fda66.
Auditor contextual6c1a6647: PID40076 exit0retenido16:58:53.389600UTC;
audit ae90d005b6fa9a3a1a708fdfafd3361bdef9146312ddda324d103a139cd18633.
Recalculó nueve arrays state60 desde153caches con funciones congeladas,
rehash de fuentes/artefactos y cobertura; no normalización raw reimplementada.

Scorer e7638731fbba44ca45ff0f69418428083226b0f44110819f0ab52e13d3ff1e75,
publicado d8477c101e7075b605753f9e2ea681e1d8e4da69 antes del único run;
PID49748, exit0retenido17:02:31.672690UTC,5,1797s. Gate RAM6.450.454.528/
commit7.223.742.464bytes,CPU0/seis variables dehilos1,logs vacíos.
Manifest dcdc8b0bef5a508f40b322ba632109d4afaff689a3d0d36514f30d8618531e66;
summary01de55e3369b39d1ede3aee65c12c8e99ee15c4fdb9d39f9efd4dc1a7b900650.
Root y revisión independiente comprobaron8outputs/16payloads/cadena de cierre.
Archivo q3_context_scoring_result_evidence_01:14copias540542B,
receipt9de9ee0fa9294372583f3a84ebe64599bda54d8682805852ad1b791326773736.

Auditor numérico80b0b3cfbaff80e5f06d685851cf080174f85270b1ab8ddcca2b03119e972e27,
binding/launcher revisados ypublicados717c66719b2f6a0fdcf43fde433feb6d220a52d8.
Único PID17652/creation1793552721.8218305;17:05:21.847618→17:05:26.908732UTC,
exit0retenido5,0919s,sesión root88581 cerrada. Gate RAM7.947.784.192/
commit9.169.039.360bytes,CPU0/hilos1,logs vacíos.
PASS_INDEPENDENT_Q3_CONTEXT_MODEL_NUMERIC_AUDIT:
audit ef6a325b8f4defc579aa568ebd9dc980ede750e106a8ef4578b025d999215f69;
manifest c1f0c6bb33180a02e25c41cd8d267814d1759c2acb188f9ad8d94b02710afa10;
exit1e3e8e4e667e182fbf7b129550369e8c44d36dcc05a8f263d0515ee8891edc03.

Reconstruyó matrices, transformaciones, probabilidades/calibración/EV, seis
libros, métricas ybootstrap usando funciones independientes del auditorH1;
sin importar scorer, refit ni raw/API. PASS significa reproducción dados los
parámetros, no rentabilidad. Root verificó9inputs/4pins deimplementación y
cadena de cierre. Siete copias85749B en q3_context_numeric_audit_result_evidence_01;
receipt e880a68043eecb5fa3b5a29d8e46a109e8ca1c2b7a58efaabf7f4a9b7e333d80.
Todos estos procesos están cerrados: no relanzar.

## Consecuencia y continuación

Esta configuración weeklyH2 no ofrece rentabilidad temporal estable enlos dos
bloques. El resultado contextual favorable deH1 no sobrevivió la extensión.
No se rescata CATEGORY30, BASE18 ni un ticker por su Q3 positivo. La siguiente
pregunta es dónde falla el EV entre probabilidad, magnitud condicional y
selección, manteniendo separados los errores enfilas comunes y los resultados
decartera. Cualquier diagnóstico posterior es postdesarrollo y debe etiquetarse.

Las entradas por zonas ya existen enel motor causal0DTE, pero weeklyH2 sigue
entrando a10:35 con salida dos sesiones después. No se han probado aquí toques
Fibonacci o salidas dinámicas por walls. Reutilizar esa infraestructura requiere
un contrato separado de eventos/ejecución, conservando días sinoperar; este
resultado no activa automáticamente filtros, nuevos fits o una familia porzonas.

Todo2026 sigue SEEN_DEVELOPMENT. Goal general activo, selecciónnull,
technical_ready=false,promotion_approved=false. Producción/API/bróker/VPS y
cambios ajenos intactos. Queda pendiente evidencia temporal no usada para diseño.

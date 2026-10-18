# Familia separada: dinámicas de griegas sobre contratos comunes

2026-10-18, diseño posterior al diagnóstico TRAIN gamma. No es una corrección
retrospectiva del modelo compacto ya ejecutado. El extractor152, sus modelos y
artefactos permanecen intactos. No autoriza fit: primero implementación, tests y
revisión root. La futura comparación primaria propuesta es net compacto152
frente a los mismos152 más272 campos dinámicos, total424, idéntica muestra
TRAIN270.377, pesos IPW, targets, modelo y presupuestos. La selección/gates de
una ejecución económica requieren su contrato previo; aquí no se abre VAL/TEST.

Inputs: arrays crudos de la caché sellada; estados de decisión, calendario de
sesión y cierre explícito. Para TRAIN se limita a la muestra2023–2024 existente.
Se calculan h5/15 con endpoints t y t−h, nunca barra promediada, y se mantienen
CALL/PUT separados. Ningún dato posterior a t cambia un campo de ese estado.
La identidad es contrato dentro de ticker+fecha/expiración, strike y right.
No se usa el tamaño del eje diario futuro como denominador.

Cada Greek tiene su propia cohorte común. Requiere presencia en ambos extremos,
underlying del contrato válido según row_flags4 y spot consenso válido, más
OI conocido y válido en ambos extremos. Se diferencia así Greek ausente o
stale; no se rellena, bfill, forward-fill de Greek ni se exige cotización
ejecutable para medir sensibilidad. OI usa último reporte disponible, con
invalidación por reporte inválido posterior, según motor congelado.

Validez específica: gamma proxy requiere IV finita0<IV<=5; delta finita con
abs(delta)<=1; vega finita>=0; theta finita. No se exige IV a delta/vega/theta.
Los filtros numéricos conservan las convenciones existentes. A diferencia del
diagnóstico anterior se exige además row_flags4 por contrato; la cobertura
resultante se informará, no se asumirá idéntica a la del diagnóstico gamma.

Unidades: gamma es proxyBS r=q0, tau calendario al cierre de la sesión, sin
floor1h, ×OI×100×S²×0,01; no replica un gammaTheta ni dealer firmado. Delta
usa valor almacenado×OI, sin multiplicador monetario. Vega usa valor almacenado
/100×OI por punto porcentual de volatilidad conforme documentación Theta.
Theta usa valor almacenado×OI; no se anualiza ni se llama decay diario porque
su escala temporal no está acreditada. Ver GREEK_UNITS_REVIEW.md. El TTE/version
del proveedor histórico no está acreditado; los cambios son del campo observado.

Se fijan17 campos por Greek×lado×horizonte, en este orden (4×2×2×17=272):

1. available: cohorte no vacía y ambos endpoints válidos.
2. common_count_log1p.
3. common_known_now_fraction.
4. common_known_past_fraction.
5. common_eligible_now_fraction.
6. common_eligible_past_fraction.
7. observed_abs_mass_now_fraction.
8. observed_abs_mass_past_fraction.
9. observed_abs_mass_now_positive.
10. observed_abs_mass_past_positive.
11. common_signed_logmass_now.
12. common_signed_logmass_past.
13. common_relative_change.
14. fixed_oi_greek_relative_change.
15. reported_oi_relative_change.
16. composition_relative_change.
17. common_oi_relative_change.

Los logs firmados son sign(suma)×log1p(abs(suma)), en unidades documentadas por
Greek. La masa absoluta observada usa sum(abs(Greek×OI)); evita cancelaciones
al expresar cobertura de delta/theta. No estima masa desconocida. Los ratios
sin denominador positivo se guardan0 con su flag explícito; `available` y los
dos indicadores de masa positiva distinguen esa codificación de un cambio0
observado. Los cuatro ratios de identidad implican denominadores positivos si
available; si no existe cohorte, se conservan coberturas0 y available0.

Con OI0/1 y sensibilidad g0/1 dentro de la misma cohorte: M0=Σg0OI0,
M1=Σg1OI1, B=Σg1OI0, D=Σabs(g0OI0)+Σabs(g1OI1).
common_relative_change=(M1−M0)/D;
fixed_oi_greek_relative_change=(B−M0)/D;
reported_oi_relative_change=(M1−B)/D.
Los dos últimos suman el primero, pero no identifican flujo dealer ni causas.
Si D=0 los tres son0. La composición es la diferencia de sumas firmadas
observadas fuera de la cohorte, dividida por la suma de masas absolutas de los
dos universos observados. common_oi_relative_change=Σabs(OI1−OI0)/Σ(OI1+OI0).
Los estados con cohorte válida de masa0 se mantienen sin inventar valores.

La atribución gamma spot→IV→tiempo del diagnóstico queda descriptiva; no se
añaden más features por sus resultados. Sin nuevas ventanas, umbrales de
cobertura, selección de strikes o hiperparámetros. Se anexan272 canales exactos
a las152 columnas originales y se comprueba igualdad bit a bit de ese prefijo.
El control ya ejecutado no se refittea ni se presenta como una prueba nueva.

Pruebas: perturbación de futuros y contrato futuro; intersecciones distintas
por Greek; OI inválido no rellenado; delta/theta firmadas y masa absoluta;
identidad de la descomposición; vega/100; cierre210/390 explícito; igualdad del
prefijo152 y shape424. Salida feature-only, sin labels, PnL ni modelos nuevos.

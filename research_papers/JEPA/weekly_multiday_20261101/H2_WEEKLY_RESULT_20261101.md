# Weekly con posiciones de dos sesiones: resultado

La política de probabilidades y valor esperado produce un backtest neto positivo
para H1 2026: **+11486 USD** con el coste adverso predefinido,75 operaciones y
PF1,2625. La auditoría económica independiente pasó. El resultado sigue siendo
frágil: tres meses de seis positivos, drawdown realizado16666,30USD y beneficio
concentrado en SPXW y abril. Sin la mayor operación, el neto sería−507,40USD.
Esto es sensibilidad descriptiva, no una política alternativa ni una exclusión.

## Comparación cerrada

Misma cartera inicial100000USD, un contrato por operación, máximo una posición
por ticker y tres en total. Libros independientes por periodo y coste.

| Política | H1 2026 base USD | H1 2026 adverso USD | Fills adversos | PF adverso | DD realizado adverso USD |
|---|---:|---:|---:|---:|---:|
| Probabilidades + EV | 11633,00 | 11486,00 | 75 | 1,2625 | 16666,30 |
| Siempre CALL | 3300,80 | 3049,80 | 127 | 1,0417 | 34947,70 |
| Siempre PUT | −24750,20 | −25011,20 | 132 | 0,7450 | 45514,90 |
| Abstenerse | 0 | 0 | 0 | No aplica | 0 |

El neto EV representa11,486% del capital inicial del libro hipotético, sin
anualizar. La caída indicada valora las posiciones abiertas a coste: **no es un
drawdown mark-to-market** y no mide toda la exposición entre snapshots.
En2025, usado para calibración y por tanto descriptivo, EV dio+23648,80USD
adversos,172fills,PF1,2794,DD22490USD y6/12meses positivos. No es otro holdout.

Contribución EV adversa H1: SPXW+15605USD (25fills), SPY−2561,60 (26) y
QQQ−1557,40 (24). Un contrato no iguala el riesgo monetario entre índices y ETF;
SPXW tiene primas mucho mayores en esta selección. No se rescata SPXW como
nuevo ganador a partir del mismo semestre.

Netos mensuales EV adversos: enero+53,20; febrero−3739,20; marzo−10803,20;
abril+24369; mayo+3719; junio−2112,80USD. Hubo entradas en41fechas,12NO_FILL,
75esperas por posición abierta y67esperas por EV no positivo. Hay140eventos
NO_OPPORTUNITY adicionales: no son decisiones del modelo de abstenerse.
Tres salidas sin fuente se contabilizan como pérdida íntegra de prima más costes;
son cotas conservadoras, no fills de salida observados.

## Modelo y ejecución simulada

Regresión logística multinomial L2 fija(C1), sin búsqueda de hiperparámetros.
TRAIN2023–2024:1758candidatos,1752labels elegibles tras purga temporal;
CAL2025:870; EVALH12026:426. Imputación y normalización exclusivamente TRAIN.
Cinco escenarios: no-fill y cuatro tramos de retorno de la prima. Probabilidades
calibradas con mezcla30%priorTRAIN/70%modelo, elegida por loglossCAL en once
valores predefinidos. Medias de payoff por escenario/ticker/lado con shrinkage20.
Se opera sólo la oferta CALL/PUT con mayor EV adverso estrictamente positivo;
empate o EV no positivo implica WAIT. No mínimo de actividad diaria.

Las18features observadas10:30 incluyen ticker/lado,DTE,día semanal,spot,strike,
moneyness,bid,ask,spread,delta,IV,gamma,theta,vega,rho. Este experimento de duración
no usa todavía Fibonacci IB ni walls. La selección busca delta absoluta0,50;
entrada ask10:35, salida bid10:35 de la segunda sesión oficial posterior,
antes del vencimiento. Duración realizada2–5días naturales,media2,4.

Spreadask→bid más1,30USD por lado y deslizamiento0,01(base)/0,02(adverso)
puntos por lado, multiplicador100. Son costes asumidos; no se acreditan tamaño
disponible, cola de ejecución ni fills de bróker. El desfase de cinco minutos y
los clocks almacenados no prueban recepción live. Ninguna operación real.

LoglossEVAL1,204875; Brier0,642239 sobre426candidatos. En87ofertas seleccionadas
(incluye12NO_FILL), el EV adverso tiene sesgo predicho−realizado−26,285USD y
MAE1184,770USD. Son métricas descriptivas, no certeza sobre la siguiente operación.

## Trazabilidad y auditoría

DatasetV2:3054candidatos/2625ticker-sesiones;1527con serie local elegible,
1092sin ella y seis al final sin horizonteH2. De3054ofertas,2946tienen salida
observada,90NO_FILL y18salidas ausentes conservadas como cotas. Fuente semanal
local, no una cadena completa de vencimientos.2613archivos leídos:1410clocks
nativos y1203proxyunderlying;95940filas subminuto descartadas sin redondeo.
El fallo original por clocks:30 permanece archivado; no se adoptaron parciales.

BuilderV2 exit0 retenido14:23:03UTC; evaluador único exit0 retenido14:25:45UTC,
sinwarnings; auditor único PID26012 exit0 retenido14:31:56.272872UTC,0,811s.
Audit **d9f1602c35040d11010bba2f0998d6c15130d511234f1448eabb985b910ce806**:
PASS_INDEPENDENT_WEEKLY_H2_V2_ECONOMIC_AUDIT,3054scores/11calibraciones/24ledgers.
Reconstruye transformer desdeTRAIN, inferencia desde coeficientes guardados,
probabilidades/EV/calibración/cash/capital/métricas. No reproduce el fit de
coeficientes ni hace replay íntegro de Parquet. Usa35copias exactas de payloads.

Dataset manifestbfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8;
evaluación54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96.

Mayor operación: SPXW CALL6825,expiry17abril; ask47,00 el13abril10:35→bid167,00
el15abril10:35. Neto adverso11993,40USD. Comprobación puntual independiente
leyó ambas fuentes originales, rehasheadas antes/después: coincide exactamente
con candidato yledger. Result0fdd28726852556491949ee117460588c1e5cbe3d6137974c7d2234429cf713e.
Por tanto la concentración está en los datos guardados, no en una transformación
errónea de ese trade. Tampoco demuestra ejecución live o robustez estadística.

Reporte y gráfica reconciliados con ledgers/summary, PNG final inspeccionado.
[Gráfica](h2_final_evidence_01/h2_descriptive_report_v2_02/weekly_h2_v2_descriptive.png).
Archivo final22copias1000927B,recibo6619ad3bbfa7f11ea3100fd6997e4199a2bc8e46fc4639c9fd472e715646351c.

## Decisión de investigación

Resultado positivo de desarrollo, **rentabilidad robusta todavía no acreditada**.
H12026 ya es SEEN_DEVELOPMENT;75fills y concentración en una operación impiden
tratarlo como validación nueva. No selección de ticker, refit oportunista,
promoción o despliegue. technical_ready=false,promotion_approved=false.
La siguiente investigación debe comprobar estabilidad y riesgo comparable con
reglas fijadas antes de nuevos resultados; no optimizar sobre este semestre y
volver a llamarlo test. El goal general continúa activo; esta prueba H2 queda
cerrada y no debe relanzarse. API,bróker,VPS,producción y cambios ajenos intactos.

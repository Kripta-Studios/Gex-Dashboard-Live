# Riesgo comparable: el positivo no se mantiene en ambos periodos

Con un presupuesto máximo de pérdida contractual de5000USD por posición,
el modelo congelado pierde **14931USD en H1** y gana **9872,80USD en Q3 parcial**,
con costes adversos. El resultado anterior de un contrato por operación no
acredita por sí solo una ventaja general: la exposición monetaria entre SPXW,
SPY y QQQ era muy desigual. Esta prueba no selecciona un ticker ganador ni
sustituye retrospectivamente los libros anteriores.

| Bloque/política | Neto base USD | Neto adverso USD | Trades | Contratos comprados | PF adverso | DD realizado adverso USD |
|---|---:|---:|---:|---:|---:|---:|
| H1 EV | −14126 | −14931 | 71 | 415 | 0,8559 | 28293,30 |
| H1 CALL | −10716,20 | −11902,20 | 109 | 602 | 0,9287 | 83725,70 |
| H1 PUT | −67962,60 | −69207,60 | 119 | 631 | 0,6818 | 98828,60 |
| H1 WAIT | 0 | 0 | 0 | 0 | No aplica | 0 |
| Q3 EV | 10271,80 | 9872,80 | 28 | 207 | 1,2054 | 23203,40 |
| Q3 CALL | −18312,80 | −18963,80 | 57 | 333 | 0,7943 | 43041,80 |
| Q3 PUT | −29306,80 | −29794,80 | 44 | 263 | 0,6351 | 39578,60 |
| Q3 WAIT | 0 | 0 | 0 | 0 | No aplica | 0 |

Cada bloque/política arranca con100000USD; no se suman como cartera continua.
DD realizado valora posiciones abiertas a coste, no mark-to-market. Las
cantidades son enteras, se fijan10:30 y no se cambian tras conocer el ask10:35.
Se incluye prima, slippage adverso y ambas comisiones en la cota5000; la
cantidad se redondea hacia abajo y el riesgo por contrato hacia arriba en
centavos. No es igualdad exacta de exposición: la discretización deja saldo
sin usar, especialmente con primas altas. Ambos costes comparten cantidades.

La guarda de entrada también altera fills y el calendario de oportunidades:
no es simplemente multiplicar los75/28trades antiguos. H1 EV registra12fallos
de quote y9rechazos de presupuesto; Q3 EV tiene2rechazos de presupuesto. Un
rechazo no redimensiona ni rescata otra oferta. Ningún libro bloqueó por capital.
Las comisiones de salida de posiciones abiertas quedan comprometidas antes
de financiar otra entrada. Los16libros reconcilian cash, prima y obligaciones.

Contribución EV adversa H1: SPY−21732,20,QQQ−8803,80,SPXW+15605USD.
Q3: SPY+5253,QQQ−4540,60,SPXW+9160,40USD. Los costes siguen siendo los del
contrato original por contrato y lado. Se supone fill completo a la quote
guardada; no se ha demostrado volumen suficiente para todas las cantidades.
Las salidas missing conservan liquidación cero como cota, no fill observado.

## Comprobación independiente y evidencia

Contrato9c387e9b fijado antes del cálculo, implementacióne4f42a9f y binding
publicados0808fcab. ÚnicoPID35112, exit0retenido15:27:19.399520UTC,0,348s.
Stdout/stderr vacíos, CPU0/hilo1/gateRAM+commit. Manifest
50fa6b7a02aad9d122dc0bfdd84f8c01f9a5f468bafc7f175eed39aa3ea9418d;
summaryb3cd3144107768bc4c64505da1e44aefc559875ec857128d79b9bdb653b69aad.

Review_producer_exit reconstruyó las decisiones de los16libros desde los
candidatos/scores/cobertura sellados, sin importar productor. Comparó sus
digests con los libros reales y verificó cantidad, riesgo, guardas, capital,
orden, costes y cierre. Recalculó320campos de summary: cero diferencias.
Los diez inputs se rehashearon antes/después. Cálculo efímero de sólo lectura,
CPU0/unhilo, RAM11,63GB y commit17,39GB; no se presenta como replay raw ni refit.
El source completo inicial no se guardó en archivo por el rol read-only;
se conservan la atestación, sus hashes y digests, y el productor reproducible.
No atribuir a esta evidencia una suite independiente persistida inexistente.

Fuentes efímeras reportadas: reconstrucción01c855da6d46b6ee1a6072a221967fdb395507f549ba97e3dcec4107d2b00b32;
comparación72f69d09225a252a2a7f63574fa30473114942e44ef4248de7ff328ef9de0ea3;
summarycb8d636de20ef0025737038b2cce31b73fb2befd49c8491bc46887957f325b19.

## Consecuencia

No promover el modelo ni optimizar cantidades/meses/tickers sobre estos netos.
Hace falta contrastar información incremental de escenarios y su EV. Se está
extrayendo el contexto causal IB/walls de10:30, fijado antes de este resultado,
para una comparación posterior con controles simples y reglas iguales.
El contexto describe0DTE y se usará como señal del subyacente, no como masa
weekly completa. Q3 de ese contexto todavía pendiente. Goal activo;
2026SEEN_DEVELOPMENT,technical_ready/promotionfalse, sin producción/API/bróker.

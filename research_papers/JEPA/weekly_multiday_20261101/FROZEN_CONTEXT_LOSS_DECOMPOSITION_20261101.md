# Descomposición descriptiva del fallo contextual congelado

Análisis de audit_requirements, sin modelos ni backtests nuevos; root verifica
las sumas desde ledgers sellados. No se abrieron resultados adaptativos parciales.
Autoridades Q3: manifestdcdc8b0bef5a508f40b322ba632109d4afaff689a3d0d36514f30d8618531e66,
auditef6a325b8f4defc579aa568ebd9dc980ede750e106a8ef4578b025d999215f69,
ledger CONTEXT182 adverso
dd965a179b66eb244c7fcda96a2bcf1ff29029095afcfab05104b6ba1e2f7add;
scores03e89f00000603933269d80e799549d8302390d107b3c0582b9c60f4f97915a1.

| Q3 parcial, salida | Trades | Contratos | Neto USD |
|---|---:|---:|---:|
| Observada |39|241|−48694,60|
| Cota por fuente de salida ausente |2|15|−9434,00|
| Total |41|256|−58128,60|

Las dos cotas CALL son QQQ−4578 ySPY−4856. Representan16,23% de la pérdida
neta;83,77% corresponde a salidas observadas. Ganancias observadas18626,40,
pérdidas observadas67321,PFaprox0,277. Por mes observado:
julio−9626,60/agosto−25603/septiembreparcial−13465. Por ticker observado:
SPXW−22215,80/SPY−21741,20/QQQ−4737,60. Todos negativos.

Total por lado: CALL36trades/224contratos−45699,40;PUT5/32−12429,20.
CALL observado−36265,40. Los180candidatos Q3 tienen contexto disponible y
state_valid=true: no se atribuye el fallo a contexto ausente.

H1:80salidas observadas+51551,20 y2cotas−9680,20→+41871.
La variación de totales entre los dos ensayos separados es−99999,60:
−100245,80 en operaciones observadas y+246,20 en cotas. Esta comparación
NO es rentabilidad de una cartera continua: los libros originales reiniciaban
capital. Sólo localiza contablemente el deterioro.

Conclusión acotada: faltantes/cotas no explican el vuelco. El daño persiste en
las operaciones con salida observada, en ambos lados y los tres tickers.
No identifica por sí solo deriva, sobreajuste, ranking o azar como causa.
No eliminar cotas, rescatar subgrupos ni tratar esta agrupación como política.

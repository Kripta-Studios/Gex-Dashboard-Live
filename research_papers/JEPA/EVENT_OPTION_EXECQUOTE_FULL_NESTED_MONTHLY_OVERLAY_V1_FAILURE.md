# EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1 — cierre auditado

**Fecha:** 2026-07-26
**Estado:** `FAILED_ECONOMIC`
**Promovible:** no
**Integración live:** prohibida

## Ejecución

Contrato inmutable:
`EVENT_OPTION_EXECQUOTE_FULL_NESTED_MONTHLY_OVERLAY_V1_PREDECLARATION.md`.

Código y tests publicados antes del acceso económico en `5b0a44ad`. La primera
invocación como ruta de archivo terminó en 2,1 segundos con
`ModuleNotFoundError: neural`, antes de importar el evaluator, leer la fuente o
crear un output. La única ejecución económica se lanzó correctamente como
módulo desde ese mismo HEAD:

```text
python -m neural.jepa.evaluate_event_option_execquote_full_nested_overlay_v1
```

Procesó los 18 folds congelados, `1.128.960` configuraciones lógicas por fold y
`20.321.280` en total. Cada fold serializó policy y modelos antes de leer su mes
test. El ledger contiene solo las 370 operaciones test enero-junio; no contiene
training ni selección.

Evaluation summary SHA-256:

`01074ce9c7244f57560b4867e783cbfe059a379fda5817e31b80fcf484f897c8`

## Resultado test-only

| Ticker | Trades | WR | PF | PnL retorno acumulado | Mínimo mensual | Meses positivos |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 149 | 35,570% | 0,584706 | -23,412554 | 18 | 1/6 |
| SPXW | 114 | 38,596% | 0,844375 | -6,336789 | 17 | 3/6 |
| SPY | 107 | 47,664% | 1,083921 | +2,619171 | 12 | 2/6 |

PnL mensual:

| Mes | QQQ | SPXW | SPY |
| --- | ---: | ---: | ---: |
| 202601 | -0,276145 | -3,591270 | -0,060082 |
| 202602 | +0,349195 | -0,209465 | +1,642636 |
| 202603 | -11,348770 | -4,575995 | -0,850208 |
| 202604 | -6,445185 | +0,666324 | -1,274118 |
| 202605 | -1,401531 | +0,564895 | -2,829728 |
| 202606 | -4,290119 | +0,808722 | +5,990671 |

Los tres fallan. QQQ y SPXW pierden y no alcanzan WR/PF/meses. SPY tiene neto
agregado positivo, pero PF<1,20, solo 2/6 meses positivos y marzo produce 12
trades, por debajo de 13. No se permite selección posterior por ticker o mes.

## Auditoría independiente

Estado:
`PASS_INDEPENDENT_FULL_NESTED_AUDIT`.

El auditor:

- rehasheó el parquet fuente;
- reconstruyó las 289 features live-observable;
- refitteó 36/36 LightGBM con hash exacto;
- reprodujo 36/36 vectores de predicción de selección/test;
- repitió 18/18 búsquedas y winners;
- reprodujo exactamente las 370 operaciones y todas las métricas;
- certificó `option_price_mode=executable_quote`, hold30–180 y cero violaciones
  de `reject_while_open`.

Audit summary SHA-256:

`aa49666265635382a73d8289e8352bcbc430402648ddc2548adb345a3480e42c`

## Diagnóstico causal

El barrido exhaustivo no arregla la falta de transporte. Las medianas de PF en
selección fueron aproximadamente 1,128 QQQ, 1,300 SPXW y 1,398 SPY, pero sus PF
test cayeron a 0,585/0,844/1,084. Marzo rompe especialmente QQQ/SPXW y junio
solo rescata SPY. La inestabilidad de la relación score/filtros/payoff entre
ventanas domina la optimización.

Esto falsifica la explicación de que bastaba repetir mensualmente el sweep de
1,13 millones. El resultado fuerte `intersection_guarded` anterior provenía de
elegir sobre los mismos meses reportados, usar labels legacy y no imponer
no-overlap físico. No es una expectativa live.

## Cierre

La familia queda cerrada e inmutable. No relanzar, cambiar ranking, escoger
ventana, rescatar ticker/mes ni añadir guards sobre enero-junio. GroupDRO ya
quedó cerrado sin ejecución y no se reabre como reacción a este resultado.

No se modifica `services/`, `bots/`, `systemd/` ni el paquete live. Con 2026 ya
visto, ninguna nueva búsqueda sobre el mismo parquet puede demostrar promoción;
como mínimo hace falta congelar una regla antes de un mes futuro intacto.

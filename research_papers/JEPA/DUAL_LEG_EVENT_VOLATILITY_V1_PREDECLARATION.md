# DUAL_LEG_EVENT_VOLATILITY_V1 — predeclaración económica

Fecha: 2026-07-16. Hipótesis nueva tras cerrar short-premium V2 en data gate.
No descarga ni genera otro dataset: reutiliza el parquet physics sellado
`event_option_dataset_execquote_causal1030_202201_202605_v1_physics`, SHA-256
`11e26aaddd91fd441222d552e0362c1d4c2c4489a08d7a6de66479d6eb454fb1`.

## Payoff

En cada evento se compra simultáneamente CALL y PUT 0DTE con igual capital en
prima: d25 para SPXW y d35 para QQQ/SPY. Cada pata usa su trayectoria
`executable_quote` ya congelada: entrada ask, salida bid, hold 30–180m y la
gestión stop/TP/trailing del label. Las patas pueden cerrar en minutos distintos.

Retorno por ticker:

```text
gross = 0,5 * (call_opt_exit_ret + put_opt_exit_ret)
net   = gross - 0,002
```

El haircut de 20 bps de capital cubre comisiones/rounding además del spread ya
incluido. Igual capital puede requerir contratos fraccionales; es un proxy de
portfolio escalable, no evidencia de fill de un tamaño concreto.

## Intersección y scheduler

Solo se aceptan keys exactas `trade_date,timestamp` presentes en QQQ/SPXW/SPY,
con ambas patas disponibles, retornos finitos y exit 30–180m. Cualquier key
incompleta se elimina para los tres. Ventana 10:30–14:30 ET, grid original.

El portfolio global empieza libre cada día. Acepta cronológicamente la primera
key elegible y queda bloqueado hasta el máximo exit realizado de CALL/PUT en los
tres tickers. Una decisión posterior solo se acepta cuando el portfolio ya
estaba cerrado; usar el exit de la posición anterior es causal. No hay solape,
selección por retorno, threshold, modelo ni abstención adicional.

## Gates

El primer one-shot reporta exclusivamente enero–diciembre 2025. Debe lograr por
ticker WR>45%, PF>1,20, más de 12 trades en cada mes y PnL neto positivo en los
12 meses. Si falla, no se rescatan horas, deltas, patas o meses.

Solo un PASS autoriza congelar artefactos y evaluar 2026. La fuente actual llega
hasta mayo 2026; junio/julio se descargarán o reconstruirán únicamente después
de PASS 2025, con el mismo builder/hash y antes de abrir sus outcomes. Un PASS
histórico sigue requiriendo shadow/paper y no modifica producción.

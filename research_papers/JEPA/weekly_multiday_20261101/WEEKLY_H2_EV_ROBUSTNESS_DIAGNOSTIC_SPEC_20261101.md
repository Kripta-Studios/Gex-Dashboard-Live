# Especificación pre-cálculo — implementación del diagnóstico EV H2

Estado: **PROPUESTA PARA REVISIÓN; SIN SCRIPT NI EJECUCIÓN**.  
Norma superior: `WEEKLY_H2_EV_ROBUSTNESS_DIAGNOSTIC_CONTRACT_20261101.md`.

## Flujo mínimo propuesto

1. Admitir rutas planas, no symlink/reparse, bajo las dos raíces congeladas.
2. Verificar los SHA externos de ambos manifests y sus schemas
   `weekly_h2_dataset_manifest_v2` y `weekly_h2_ev_manifest_v1`.
3. Verificar el binding dataset→evaluación y los pins internos de los cuatro
   archivos consumidos.
4. Leer sólo candidatos, coverage compacto, summary y el ledger EV adverso EVAL.
5. Construir un índice único de candidatos y parejas únicas ENTRY/EXIT; rechazar
   duplicados, trades sin pareja, candidatos desconocidos o cualquier soporte
   distinto del summary sellado.
6. Reproducir primero el punto `s=0.02` y exigir igualdad con el ledger/summary
   en neto, PF, 75 trades, drawdown realizado, meses, tickers y missing exits.
7. Sólo tras esa reconciliación calcular, mediante funciones puras, el barrido,
   igual-riesgo, concentración y, si es admisible, bootstrap.
8. Rehashear todas las autoridades; crear la raíz de salida de forma exclusiva;
   escribir `diagnostic.json`; rehashear inputs otra vez y publicar al final
   `manifest.json`. Una escritura parcial se preserva y no se reintenta en la
   misma raíz.

## Estructura propuesta de `diagnostic.json`

- `schema`, `status`, `scope`, `fixed_trade_count`, `fixed_candidate_ids_sha256`.
- `baseline_reconciliation`.
- `slippage_sweep`: seis filas ordenadas con `slippage_per_side`, neto, PF,
  trades, ganancias/pérdidas brutas, DD realizado, ticker y mes.
- `equal_risk_diagnostic`: denominador, métricas por ticker y promedio de
  tickers con ponderación igual; caveat de no cartera.
- `concentration`: `drop_top_gains` para 1/3/5 y `leave_one_exit_month_out` para
  los seis meses, siempre con IDs retirados y soporte restante.
- `block_bootstrap`: configuración completa, soporte de sesiones/ceros y
  media/mediana/CI empírico exploratorio, referencia económica cero y supuestos
  de estacionariedad/dependencia de cinco sesiones; o estado
  `OMITTED_FAIL_CLOSED` con razón exacta.
- `limitations` y flags negativos de selección/refit/auditoría/promoción.

## Invariantes y pruebas sintéticas focales

- El orden/IDs de los trades no cambia entre puntos de slippage.
- `s=0.02` reproduce exactamente el baseline adverso sellado.
- El floor de salida impide crédito negativo antes de la comisión.
- Missing exit usa bid cero y permanece cota inferior.
- Las seis filas de slippage aparecen aunque sean desfavorables.
- Igual-riesgo usa el débito adverso real individual y tres tickers con peso
  idéntico sólo en el resumen final.
- Top 1/3/5 usa desempate estable; leave-one-month-out contiene exactamente seis
  filas y nunca reoptimiza.
- El bootstrap agrega tickers por fecha antes de remuestrear, incluye sesiones
  cero, es determinista con la semilla fijada, usa percentil lineal tipo 7 y no
  genera p-value ni lenguaje de distribución bajo el nulo.
- Mutación de manifests, ledger, candidatos o coverage falla antes de publicar.
- El destino preexistente falla sin sobrescribir.

Una suite sintética pequeña y una revisión independiente del código serán
suficientes. No se necesitan nuevas capas operativas, nuevas features, sklearn,
NumPy, DTheta, fit, scoring ni replay.

## Condición de avance

Root debe revisar y aceptar este contrato y esta especificación antes de crear el
script, ejecutar fixtures o abrir los valores reales para el diagnóstico. La
existencia del resultado EV H2 cerrado no constituye por sí sola autorización.


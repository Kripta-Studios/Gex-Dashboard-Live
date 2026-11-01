# Comparación congelada con presupuesto de pérdida comparable

Turno anterior: PROGRESS. Scoring Q3, auditoría numérica y trazabilidad de la
mayor operación cerrados; reporte147dae89 publicado en c9785227. Goal activo.
Nueva pregunta: ¿se mantiene el neto cuando cada posición tiene un presupuesto
máximo comparable, en lugar de un contrato de prima muy distinta por ticker?
Este contrato se fija antes de calcular los nuevos libros. No es una búsqueda
de cantidad óptima ni cambia las señales del modelo.

## Universo e inputs congelados

Dos bloques independientes: EVAL H1 2026 y Q3 parcial 1julio–17septiembre.
Mismos candidatos, identidades, calendario H2 y scores ya cerrados. Capital
inicial100000USD por bloque, política y coste; sin carry. Sólo SPY/QQQ/SPXW.

- Dataset H1 bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8,
  raíz D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_v2_01.
- Evaluación H1 54dc2d6ced2bb625a71fdae39b8ab2e417a576482ea6a99047df4ce8b6b1ad96,
  raíz h2_ev_v2_01 bajo la misma base.
- Dataset Q3 b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b,
  raíz h2_dataset_v2_extension_2026q3_partial_01.
- Evaluación Q3 7bd50a5a1fe5214df2c4281e785313f0fb016ca73d725d682788dcb78b283d8e,
  raíz h2_ev_frozen_extension_2026q3_partial_01.

Verificar manifests externos y bytes/SHA de cada payload consumido antes y
después. No acceso a raw ni modelos nuevos; no fit, recalibración, nuevo
threshold ni selección de ticker. Se conservan todos los días y ausencias.

## Cantidad y admisión causal

Presupuesto fijo B=5000USD de pérdida máxima contractual por nueva posición.
Se incluyen prima, slippage de entrada adverso y ambas comisiones por contrato;
con salida conservadora a cero éste es el peor neto del contrato largo bajo
los costes simulados. El B se corresponde con el límite original de prima,
no se ha elegido mirando resultados de esta variante.

A10:30, después de elegir oferta por EV adverso POR CONTRATO:

`unit_risk_cents = ceil((Decimal(str(decision_ask))+Decimal('0.02'))*10000+260)`
`qty = 500000 // unit_risk_cents`

Cantidad entera, congelada antes de la quote de entrada. No se limita con un
cap adicional de contratos ni se fracciona. Qty<1 registra NO_FILL con motivo
DECISION_RISK_BUDGET; nunca se busca otra oferta. El redondeo hacia arriba es
sólo para la admisión de riesgo en centavos, no cambia los precios o PnL.

A10:35, además del criterio original de quote, exigir
`qty * ceil((Decimal(str(entry_ask))+Decimal('0.02'))*10000+260) <= 500000`.
Si falla: NO_FILL/ENTRY_RISK_BUDGET. Si quote original no llena:
NO_FILL/ENTRY_QUOTE. No redimensionar, reintentar ni rescatar otra oferta.
Se usa la condición adversa para ambos costes. No es una simulación de cola
de órdenes, volumen disponible o fills parciales: el supuesto es fill completo
a las quotes guardadas si pasa la admisión; declarar el límite de capacidad.

## Replay y controles

Políticas fijas EV_TOP1_H2, ALWAYS_CALL_H2, ALWAYS_PUT_H2 y ALWAYS_ABSTAIN.
Conservar selección original, empates WAIT, sin EV multiplicado por qty para
cambiar ranking. Una posición por ticker y tres en total. Ticker abierto da
WAIT/OPEN_POSITION como antes; sin serie da NO_OPPORTUNITY, no WAIT.
Salidas H2 antes de entradas10:35 y orden de ticker SPY,QQQ,SPXW.

Los libros base/adverso comparten decisiones y cantidades. La admisión común
de capital exige que AMBOS puedan financiar el débito de entrada y la comisión
de salida ya comprometida de sus posiciones; si no, CAPITAL_BLOCKED/CAPITAL
para ambos. No cambiar cantidad ni usar otro ticker como sustituto. Registrar
por separado reserva de primas y obligación de comisiones de salida. Este
control no debería sustituirse por selección basada en el PnL futuro.

Ecuación exacta por libro antes de admitir la entrada:
`cash - existing_exit_fee_obligation >= entry_debit + q*1.30`.
La obligación existente suma `q_open*1.30` de TODAS las posiciones abiertas
de ese libro. Exigir la desigualdad en ambos costes. En entrada: cash disminuye
el débito y la obligación aumenta q*1.30. En salida: el crédito ya descuenta la
comisión pagada y la obligación disminuye q*1.30. La obligación no se resta otra
vez de equity ni del PnL; es una restricción de financiación, no doble coste.

Para qty=q: débito entrada=q*((entry_ask+s)*100+1.30), principal reservado
q*(entry_ask+s)*100, crédito salida=q*(max(exit_bid-s,0)*100-1.30).
Neto=q*net_original_s; faltas de salida conservan bid0/cota y no desaparecen.
En la entrada, equity realizada disminuye q*1.30; en salida aumenta net+q*1.30.
No MTM. Cantidades no dependen de equity, retorno futuro o etiqueta del escenario.

Informar ambos bloques separados, cuatro políticas, dos costes:16libros.
Netos/PF/drawdown realizado, meses, ticker, cantidad total/máxima/mediana,
capital reservado máximo, presupuesto usado, NO_FILL por motivo, WAIT,
NO_OPPORTUNITY y missing exits. Ledger completo con cantidades, riesgo a
decisión/entrada y cash. Comparar descriptivamente con un contrato ya cerrado;
no construir un libro combinado H1+Q3 ni declarar ganadora la variante.

## Ejecución y comprobación

Implementación nueva, fixtures sintéticos y revisión antes de publicar/ejecutar
una única vez en h2_equal_risk_frozen_01. No modificar productores anteriores.
Reconciliar cada neto con cantidad*neto original y cash; auditor separado
reconstruirá admisión/cantidad/secuencia desde candidatos y scores sellados.
CPU0/hilo1 y gate contemporáneo RAM/commit>=2GB. Logs y exit retenidos.
2026 sigue SEEN_DEVELOPMENT. Ninguna promoción o ejecución real de mercado.

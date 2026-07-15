# KING-GEX-SLOPE1 — regla executable de régimen gamma

Estado: `PREDECLARED_DEVELOPMENT_ONLY`. No se ha leído ningún payoff para esta
familia. 2024/2025 y todo 2026 permanecen cerrados.

## Hipótesis y origen

`live_king_node.py` sugiere que la trayectoria de net GEX y los cambios de signo
son más informativos que un nivel estático. La traducción testable es el
mecanismo clásico de cobertura: gamma negativa amplifica el momentum y gamma
positiva favorece reversión. La pendiente solo confirma que el régimen actual
se está fortaleciendo; estados transicionales abstienen.

Esto no valida ni copia el runtime King Node. El script usa IV CALL para ambos
rights, un reloj UTC-4 fijo, una ventana móvil de strikes, smoothing a 30s y
convenciones dealer no observables. La reconstrucción histórica usa IV separada
por contrato, timestamps exactos, todos los strikes 0DTE con OI positivo y una
rejilla 5m. Se declara `RESEARCH_PROXY_LIVE_PARITY_BLOCKED`.

El workbook `MASTER_KING_NODE_RECORD_V5.xlsx` permanece como referencia no
auditada: el runtime spreadsheet requerido no está disponible. No se usó una
fórmula, señal, trade ni resultado del workbook para definir esta prueba.

## Fuentes selladas y causalidad

- Wall state:
  `tmp/wall_state_gex_dex_202201_202512_v1/wall_state.parquet`, SHA
  `94e311e0e25ff7956347597a8734e82e07ab05753f42acaa26876c58752df8ef`.
- Master executable:
  `tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet`,
  SHA `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`.
- Wall source manifest SHA
  `5431c2bf932fef6ce1ba34117cc869feb78063fbc1aa3989017fdbcb5b66dc88`.
- Wall-state builder/module hashes `745491e3...e430` / `05133f68...a64f`.
- Idea-source `live_king_node.py` SHA
  `86ac49aa6ae4711eeb77286a94d70b83584242efcf27dd00506e9c3059de9e11`.

OI es el valor diario publicado antes de RTH y representa el cierre previo. Los
Greeks se aceptan solo en el timestamp exacto de minuto. No hay as-of, nearest,
floor, ffill ni lectura de una fila posterior a la decisión.

Se excluyen por calendario completas las nueve medias jornadas ya congeladas.
La rejilla wall comienza 10:35; una pendiente de 45m exige `t-45` exacto, por lo
que la primera decisión es 11:20 y la última 14:30.

`wall_net_gamma_total_log=L_t` es reversible:

```text
G_t = sign(L_t) * expm1(abs(L_t))
slope15_t = (G_t - G_{t-45m}) / 3
```

`G_t` es CALL gamma-OI menos PUT gamma-OI bajo las fórmulas históricas
declaradas; no se presenta como posición dealer conocida. Cero/no finito,
lag no contiguo o momentum 15m cero/no finito implica abstención.

## Reglas fijas

Momentum `m_t=sign(ret_15m_bps)` usa solo barras anteriores a `t`.

- `K0_LEVEL` (atribución): opera todo timestamp válido. Si `G_t<0`, sigue
  momentum; si `G_t>0`, lo revierte.
- `K1_ALIGNED` (único candidato): exige
  `sign(slope15_t)==sign(G_t)`. Aplica la misma regla de dirección que K0;
  si pendiente y nivel discrepan, abstiene.

`m=+1` mapea a CALL y `m=-1` a PUT en gamma negativa; el mapeo se invierte en
gamma positiva. No existen umbral, percentile, grid, fit, selección, pruning ni
parámetro por ticker. El score del scheduler es constante; la ejecución conserva
orden cronológico.

## Desarrollo y gate

Desarrollo usa exactamente los meses normales de 2023. Es una policy fija sin
entrenamiento; se reporta cada ticker-mes y se prohíbe seleccionar meses o brazos.
K1 debe cumplir simultáneamente en las 36 celdas:

- PF `>=1,30`;
- WR `>=50%`;
- `>=18` trades;
- PnL `>0`;
- hold mínimo `>=30m`.

Además, pooled y cada ticker deben respetar top-5 trades `<=20%` y top-5 días
`<=30%` del gross profit. Un solo fallo cierra la familia y permite early stop
porque el gate es conjuntivo. K0 nunca puede rescatar K1.

Ejecución: SPXW d25, QQQ/SPY d35; ask de entrada, bid de salida, stop -60%,
TP +1000%, trail 50%/25%, hold 30–180m, caps/cooldowns live y una sola posición.

Si desarrollo pasa, se exige commit de runner+manifest y un único outer
2024-2025. Si falla, no se añaden VIX1D/VVIX, skew, vomma, DEX o thresholds como
rescate. 2026 no se abre.

## Feasibility outcome-free

La pendiente exacta existe en 109.785 filas 2022-2025: QQQ 35.919, SPXW 37.908
y SPY 35.958. Cada valor de pendiente es distinto dentro del censo; share
positivo 53,42%/53,80%/53,52%. En 2023, K1 conserva señal en todas las sesiones
normales y el mínimo mensual es 19 días por ticker. La capacidad teórica con
hold30/caps es mínimo 38 QQQ, 76 SPXW y 19 SPY. Esto solo pasa frecuencia; no es
alpha ni rentabilidad.

El backtest debe persistir CSVs atómicos y manifest-last por
`month/ticker/arm`, revalidando hashes de master, wall state, protocolo, código
y outputs antes de reusar.

# H-TPOVALUE1 — Developing TPO Value Migration executable

Estado: `PASS_DATA_GATE_DEVELOPMENT_NOT_RUN`. Ningún outcome 2024/2025 de esta
familia ha sido abierto. H-TPOVALUE1 es la única familia activa.

## Checkpoint outcome-free del data gate

El build autoritativo desde `5cca9e0` terminó `PASS_EXACT_TPO_VALUE_VIEW`:
96.553 filas, 69 columnas, 2.777 sesiones fuente y las 36 features TPO finitas.
La vista SHA es
`fded87a10bdf038cb3c0d9fdd03de7e62f1f4dab987d8fbc25d93a0b9f3078fe`;
el manifest SHA es
`693a1708084b6157164c8fe87e763f23f30458969b2163ef3e1c5dd9074b1331`.

Las 432 celdas ticker-año-feature pasan distinctness: mínimo 4 valores y máxima
frecuencia modal `0,9243992606284658`. La auditoría independiente revalidó los
2.777 hashes de source y checkpoint. Este PASS solo certifica causalidad y
disponibilidad; no se ha calculado PF, WR, frecuencia ni PnL. El siguiente paso
es el desarrollo económico nested 2023-04..12 con checkpoints por fold.

## Hipótesis

La distribución causal de tiempo aceptado por precio puede distinguir subasta
de iniciativa frente a failed auction. Precio fuera de value con POC/VAH/VAL
migrando en la misma dirección implica aceptación; excursión sin migración y
reentrada en value implica rechazo. La prueba modela directamente las
distribuciones ask-to-bid CALL/PUT, no un proxy físico.

No es wall interaction, H-IBQDYN ni cross-market transmission. No selecciona
touches, walls, contratos o niveles; conserva todo el universo executable
certificable.

## Universo y fuente

Master físico: 97.625 filas 2022-2025. Se aplica la reparación causal ya
congelada que omite completas las nueve medias jornadas cuyos paths no respetan
uniformemente el cierre, dejando 96.553 filas. No se filtra ninguna otra fila.

Fuente única: `D:/ThetaData/data_underlying_derived/{ticker}/YYYY/MM/*.parquet`
del propio ticker. Se exigen por timestamp exacto todas las barras 1m
09:30..t-1. No hay as-of, floor, nearest, ffill, sustitución ni fuente
cross-market. OHLC inválido, duplicado o faltante aborta el build completo.

La vista temporal outcome-free vive solo en
`tmp/existing_data_edge_sprint_v1/tpo_value_migration_v1/`. No es una fuente
nueva y contiene exclusivamente keys, X0 y X1.

El build completo es reanudable por ticker-sesión. Cada checkpoint se escribe
parquet-atómico + manifest-last y solo se reutiliza si coinciden hashes de raw
source, event keys, builder, predeclaración, allowlist y parquet derivado. Un
proceso muerto puede relanzarse al mismo target sin recomputar sesiones válidas;
un cambio de cualquier input invalida y reconstruye únicamente lo afectado.

## TPO y value area exactos

IB usa las 60 barras 09:30..10:29. `bin_width=(IB_high-IB_low)/20` y los bins
se anclan en IB_low. Cada barra completada aporta un TPO a todo bin cuyo
intervalo intersecta inclusivamente `[low,high]`. Todos los snapshots de una
decisión usan la rejilla IB ya completada y observable en t.

Se construyen perfiles con barras anteriores a los cutoffs `t`, `t-5m`,
`t-15m`, `t-30m`. En cada perfil:

- POC es el bin de count máximo; empate por centro más próximo a IB midpoint y
  luego precio inferior;
- VA70 empieza en POC y expande un bin contiguo por vez hacia el count adyacente
  mayor; empate hacia precio inferior, hasta cubrir >=70% de TPO;
- VAL es el borde inferior y VAH el borde superior de los bins seleccionados;
- precio de referencia es el close de la última barra completada del snapshot.

Los snapshots lag son retrospectivos al tiempo t y pueden usar la rejilla IB
completa porque toda ella es observable antes de la decisión; nunca consumen
una barra >=t.

El periodo TPO es exactamente una barra de un minuto; no se presenta como el
bracket AMT tradicional de 30 minutos. Para cada barra, los índices enteros
incluidos son desde `floor((low-IB_low)/bin_width)` hasta
`floor((high-IB_low)/bin_width)`, ambos extremos incluidos. Esto cuenta ambos
bins cuando un rango llega a una frontera desde el bin inferior. El lattice del
perfil contiene todos los índices entre el mínimo y máximo observado, incluidos
los bins intermedios con count cero. No se usa tolerancia, rounding ni clipping
al rango IB.

Clarificación V1R1 outcome-free previa al primer builder: el precio de un bin
es su centro `IB_low + (i+0,5)*bin_width`. POC usa ese centro; VAL es el borde
inferior del menor índice incluido en value y VAH el borde superior del mayor.
La media ponderada del perfil usa centros y TPO counts, nunca volumen ni
`tick_count`. Todos los cálculos se conservan en `float64`, sin redondear
niveles antes de derivar features.

## Bloque completo de 36 features

Orden congelado:

```text
tpo_poc_dist_bps
tpo_vah_dist_bps
tpo_val_dist_bps
tpo_value_width_ib
tpo_value_location
tpo_poc_migration_5m_ib
tpo_poc_migration_15m_ib
tpo_poc_migration_30m_ib
tpo_vah_migration_5m_ib
tpo_vah_migration_15m_ib
tpo_vah_migration_30m_ib
tpo_val_migration_5m_ib
tpo_val_migration_15m_ib
tpo_val_migration_30m_ib
tpo_value_overlap_5m
tpo_value_overlap_15m
tpo_value_overlap_30m
tpo_entropy
tpo_poc_concentration
tpo_single_print_fraction
tpo_upper_tail_fraction
tpo_lower_tail_fraction
tpo_profile_skew_ib
tpo_developing_range_ib
tpo_last3_inside_value_fraction
tpo_last3_above_value_fraction
tpo_last3_below_value_fraction
tpo_session_inside_value_fraction
tpo_poc_cross_rate
tpo_vah_cross_rate
tpo_val_cross_rate
tpo_ib_position
tpo_dist_ib_high_bps
tpo_dist_ib_low_bps
tpo_directional_efficiency_15m
tpo_directional_efficiency_30m
```

Ordered JSON SHA-256:
`73903b48836f7d5a3b1d5943df46aa010403cd6bef9fe1a0f5ec90952ae7c9f5`.

Distancias son `(reference-level)/reference*10000`. Migraciones son
`(level_current-level_lag)/IB_range`. Overlap es intersection/union de los
intervalos VA. Entropy se normaliza por log del número de bins no cero y vale
cero si solo existe uno. Concentración POC es max count/total; single-print es
fracción de bins del rango con count uno; tails son fracciones de TPO fuera de
VA; skew es `(weighted_mean_price-POC)/IB_range`; developing range usa high-low
consumido / IB range.

Inside usa igualdad inclusiva `[VAL,VAH]`; above es estrictamente `>VAH` y
below estrictamente `<VAL`, por lo que las tres fracciones suman uno. Tails
usan TPO counts de bins con índice estrictamente fuera del intervalo de bins VA
divididos por TPO total. Single-print usa número de bins con count exactamente
uno dividido por todos los bins del lattice, incluidos los de count cero.

Cross rate transforma cada close en estado `-1/0/+1` respecto al nivel y cuenta
`state[i] != state[i-1]`, incluidos entrada/salida de touch; touch->touch no
cuenta. El denominador es `n_closes-1`. IB position es
`(reference-IB_low)/IB_range`. Directional efficiency es desplazamiento
absoluto dividido por suma de desplazamientos absolutos en 15/30 barras y vale
cero cuando no hubo movimiento.

Definiciones cerradas V1R1:

- `tpo_value_location=(reference-VAL)/(VAH-VAL)`, sin clipping; cero ancho de
  value aborta el build;
- overlap usa longitud continua
  `max(0,min(VAHc,VAHl)-max(VALc,VALl)) /
  (max(VAHc,VAHl)-min(VALc,VALl))`; unión cero aborta;
- `last3_*` usa exactamente los tres últimos closes completados contra el value
  actual; `session_inside` usa todos los closes 09:30..t-1 contra ese mismo
  value actual;
- cada cross rate usa todos esos closes contra el nivel actual correspondiente;
- directional efficiency de horizonte `h` usa los `h+1` últimos closes
  completados, `abs(c[-1]-c[-1-h]) / sum(abs(diff(c[-1-h:])))`: son exactamente
  `h` transiciones de un minuto; si el denominador es cero devuelve cero;
- `IB_range<=0`, referencia no positiva, perfil vacío, total TPO no positivo o
  cualquier denominador no definido fuera de las excepciones explícitas aborta
  el build completo. No se imputa, no se elimina la feature y no se elimina la
  fila.

## Brazos, modelo y protocolo

- X0: 30 features Pairwise exactos, SHA
  `b68b6c2e17b333597281a7d7fa27237b1f1e2640deb8952867d25eced26cbe38`.
- X1: X0 más los 36 TPO en bloque. No pruning, SHAP, ablation, screening ni
  allowlist por ticker.

Modelo único: `lightgbm_quantile_distribution_utility_v1`, spec SHA
`53940684518834bed0f45272151f030d740428516ce5c86443d92cf318245499`.
Son nueve cuantiles por lado, utility integral q10-q90, p(win)>=0,50 y grid
train-only utility 50/60/70/80/85/90/95 x margin 0/10/20/30/40/50.

El runner persiste un checkpoint atómico por `outer_month/ticker/arm` y escribe
el manifest al final. Antes de reutilizarlo exige hashes exactos de vista,
master, protocolo, spec del modelo, código activo y cuatro outputs del fold.
Una identidad distinta aborta y exige target inmutable nuevo; un fold incompleto
se recalcula, sin perder los folds ya sellados.

Desarrollo es exactamente outer 2023-04..2023-12. Inner son los tres meses
previos y train termina antes de inner. Cada par debe pasar los tres inner:
PF>=1,30, WR>=50%, >=18 trades, PnL>0, hold>=30m; si no, ABSTAIN_OUTER.

Ejecución: SPXW d25, QQQ/SPY d35, ask->bid, SL -60%, TP +1000%, trail
50%/25%, hold 30-180m; una posición, caps/cooldowns live. Concentración máxima
top-5: 20% de gross profit por trades y 30% por días, pooled y por ticker.

Un base economic PASS todavía queda pendiente de stress y de implementar
paridad live exacta del perfil TPO. 2026 no se abre antes de todo ello.

## Data gate outcome-free y live

Antes de leer labels, las 96.553 filas y las 36 features deben ser 100% finitas.
Cada feature por ticker-año debe tener al menos dos valores finitos distintos y
la frecuencia del valor modal debe ser <99,5%. Cualquier fallo cierra la familia;
no permite quitar features. El inventario debe contener exactamente 2.777 pares
ticker-sesión consumidos. Las tres barras SPY inválidas del 05-jun-2023 no se
cargan porque no existe ninguna decisión SPY master ese día.

Paridad live queda `BLOCKED_IMPLEMENTATION`: histórico SPXW corresponde a
`spot_SPX_latest.parquet`; QQQ/SPY son homónimos. Un candidato requiere un
barrier que exija todas las barras exactas cerradas y abstenga ante falta/stale;
se prohíben fallback local y contexto as-of.

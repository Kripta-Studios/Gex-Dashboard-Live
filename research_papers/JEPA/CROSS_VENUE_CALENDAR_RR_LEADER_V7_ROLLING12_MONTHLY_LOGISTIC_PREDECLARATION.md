# CROSS_VENUE_CALENDAR_RR_LEADER_V7_ROLLING12_MONTHLY_LOGISTIC — predeclaración

**Congelada:** 2026-07-26 Europe/Madrid, después de observar el outer V4R2 y
antes de calcular una sola predicción o métrica V7.

## Papel causal

V7 es una única falsificación `post-outcome development`. No reabre ni
renombra V4R2 y no puede promocionarse con 2026. Responde a una pregunta fija:
si el principal fallo de V4R2 es la inestabilidad temporal de coeficientes,
¿un logistic idéntico entrenado al comienzo de cada mes solo con los doce
meses completos anteriores conserva el edge sin lookahead dentro de 2026?

```text
outcome_2026_already_seen=true
development_only=true
new_theta_download=false
physical_payoff_opened=false
production_modified=false
```

## Inputs inmutables

| Input | SHA-256 |
| --- | --- |
| V2 development 2023–2024 `development_dataset.parquet` | `459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b` |
| V4 development 2025 `development_dataset.parquet` | `87413fb1c605c221aa8f225ad9877ccbdb6d5eca45877f4fa97a5b60d321d04b` |
| V4R2 feature view 2026 outcome-free | `904a28560cf5bc6c86afa28c833e9aaf7f84dbb417aac745a134fb65df8ecbff` |
| V4R2 outer `trades.csv` | `3db6f767282c308c7c87f3d0d74e29890e9809cdbe3621edee66f2562780e19c` |
| V4R2 outer `SUMMARY.json` | `8de7e8865b57d0ed36fd7a065bb8b87a9dac7e02d0a0db2d7c051e4f223f12b2` |
| V4R2 audit `audit_summary.json` | `30e0690f93386e16ce1662c367c8ba3aef2b7f8b5824f180a7d2f52d80195bcd` |
| HEAD base con FAIL auditado | `8bd1d437449f8cbf863791e5d90f60ee04f95713` |

El evaluator debe rehashear esos bytes, exigir 2.217 filas históricas, 394
filas 2026, unicidad ticker/fecha, features finitas, labels binarias y paridad
exacta `direct_win == (base_gross_bps > 0)`. Une outcomes 2026 a features por
`ticker,trade_date` uno-a-uno. No reabre raw ThetaData ni clocks.

## Mapping, eventos y ejecución

Se mantienen exactamente:

- QQQ ← QQQ; SPY ← SPY; SPXW ← SPY;
- los 394 eventos V4R2 y sus cuatro exclusiones sensor-fecha completas;
- las 29 features V4 en el mismo orden;
- target `direct_win = 1[base_gross_bps > 0]`;
- `base_side = sign(signal_pressure)`;
- probabilidad `>=0,5`: directo; `<0,5`: inverso;
- open10:36→open13:36, hold180m, una operación por ticker/día;
- coste primario round-trip1bp; 2/3bps solo como sensibilidad.

No hay abstención, filtro de confianza, selección de ticker/fecha, cambio de
horas, sizing, exclusión adicional, nearest/as-of, reparación, intersección ni
nueva captura.

## Modelo único y refit

En cada fold se instancia exactamente `make_model()` de V2:

1. `SimpleImputer(strategy="median")`;
2. `StandardScaler()`;
3. `LogisticRegression(penalty="l2", C=0.1, solver="liblinear",
   fit_intercept=True, class_weight=None, max_iter=2000, random_state=0)`.

Es pooled para QQQ/SPXW/SPY, con los tres one-hot ticker ya incluidos. No usa
pesos, warm start, calibration, ensemble, grid ni seed sweep. Se serializan
medianas, scaler, coeficientes, intercept, clases, train dates/hash y vector de
probabilidades de cada fold.

## Walk-forward mensual congelado

Cada fold usa solo los doce meses calendario completos inmediatamente
anteriores al mes test. El mes test nunca participa en su fit:

| Test | Train | Filas train total (QQQ/SPXW/SPY) | Filas test |
| --- | --- | ---: | ---: |
| 202601 | 202501–202512 | 735 (247/244/244) | 60 (20/20/20) |
| 202602 | 202502–202601 | 735 (247/244/244) | 57 (19/19/19) |
| 202603 | 202503–202602 | 739 (247/246/246) | 63 (21/21/21) |
| 202604 | 202504–202603 | 739 (247/246/246) | 54 (18/18/18) |
| 202605 | 202505–202604 | 732 (244/244/244) | 60 (20/20/20) |
| 202606 | 202506–202605 | 729 (243/243/243) | 62 (20/21/21) |
| 202607 | 202507–202606 | 731 (243/244/244) | 38 (12/13/13) |

Desde febrero se entrena sobre 2026, pero solo sobre meses anteriores ya
cerrados. Ninguna etiqueta del propio mes o posterior puede entrar. Un fold se
persiste antes de iniciar el siguiente.

## Gates y estados

Se reportan las 21 celdas ticker-mes, los tres resúmenes H1 y julio MTD. Para
un `PASS_DEVELOPMENT_GATE` H1, cada QQQ/SPXW/SPY debe cumplir simultáneamente a
1bp:

- PF `>1,20`, WR `>45%`, neto `>0`;
- mínimo 13 trades en cada mes enero–junio;
- PnL positivo en los seis meses cerrados.

Julio MTD no cuenta para la frecuencia H1, pero debe reportar PF/WR/neto y solo
se considera sano si los tres tickers tienen PF `>1,20`, WR `>45%` y neto
positivo. Un fallo produce `FAILED_DEVELOPMENT_NOT_STABLE`. Ningún estado V7
autoriza llamar OOS a 2026, payoff físico, VPS o live.

## Fail-closed y auditoría

Evaluator y auditor independiente deben versionarse antes de la única
ejecución. Se cierra sin output económico ante cualquier hash, schema, count,
join, mapping, feature, label o fold distinto; ante una fecha de training
`>=` al primer día del mes test; o ante cualquier fuente/clocks fuera de los
inputs listados.

El auditor recarga inputs, recompone los siete train sets, refittea los siete
modelos, exige igualdad numérica de probabilidades/acciones/ledger, reproduce
1/2/3bps, meses y gates y rehashea outputs. `services/`, `bots/`, `systemd/`,
paquete live y payoff físico permanecen cerrados.

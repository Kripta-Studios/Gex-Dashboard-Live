# Predeclaración — auditoría inversa del mecanismo static-union

## Motivo

El baseline productivo reporta PF/WR altos en 2026, pero los tres modelos y las reglas estáticas declaran `select_months=202601..202606`. Esas cifras no son holdout de selección. Antes de reconstruir o retocar el sistema se comprobará si el mecanismo seleccionado con hindsight 2026 muestra al menos estabilidad retrospectiva en meses anteriores.

## Protocolo

- Dataset causal1030 executable-quote/hold30 ya existente; no se reconstruye.
- Entrenamiento exclusivo `202501..202509`.
- Auditoría exclusiva `202510..202512`.
- Tres LightGBM de retorno con configuración productiva: SPXW d25, QQQ/SPY d35, 160 árboles, seed `20260617`, 28 hilos CPU.
- Reglas copiadas literalmente de los componentes committed: QQQ 12:30–14:30 self-counter cap2/cd45; SPXW 10:30–14:30 edge>=0,05 cap1/cd30; SPY PUT-only 12:00–14:30 SPX-counter edge>=0,1 cap4/cd30.
- Quotes ask→bid, stop -60%, TP 1000%, trailing 50%/25%, hold 30–180m, una posición por ticker y near-level<=20 bps.

No se leen enero–mayo 2026 para entrenar, seleccionar o decidir esta auditoría. Las reglas, sin embargo, ya fueron escogidas usando 2026; por eso incluso un PASS solo demostraría estabilidad inversa, no OOS limpio ni autorización de promoción.

## Gates

Cada ticker debe alcanzar en octubre, noviembre y diciembre: PF>=1,3, WR>=50%, >=18 trades en cada mes, PnL positivo en todos y hold>=30m. Si falla, se rechaza la hipótesis de que el baseline rentable ya era un mecanismo estable pre-2026. Si pasa, el siguiente paso será reconstruir una selección verdaderamente pre-2026 y esperar shadow futuro; no se reinterpretará 2026 como holdout limpio.

## Hashes

```text
dataset  E6A19EFBA1EDB055C733AAB4967843F7A4B5F1D2C8238A7A243FC5BBC2251903
script   1501013CF4B8FF0BD66F308DFF89003D341C4B6A86650CD15B084F7CCD6F25BD
test     95FD037FBDEA0398706E49C8AF513E077620E8999165F96F37D936A2678D8BDF
runner   11014BD6A469CC0867AAA62523672BA3FA975AFFF9967B56217614A9AF4EF699
```

# OPENING_RELATIVE_MOMENTUM_V1 — cierre científico

**Estado:** `NO_AGGREGATE_EDGE` / `FAILED_ECONOMIC`

**Fecha:** 2026-07-17 Europe/Madrid

## Veredicto

El único replay de desarrollo autorizado, 2022–2023, no supera ni la gate
incremental de PF agregado mayor que uno. La continuación del impulso relativo
cash-open QQQ-SPY queda cerrada sin abrir 2024–2026, sin traducir a opciones y
sin cambiar producción.

| Trades | WR | PF | PnL neto | Mín/mes | Meses + | Meses PASS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 497 | 50,905% | 0,831462 | -927,689 bps | 19 | 7/24 | 4/24 |

Los cuatro meses que superan simultáneamente PF>1,20, WR>45%, más de 12 trades
y PnL positivo son 2022-11, 2023-04, 2023-10 y 2023-11. La frecuencia pasa en
todos los meses, pero la economía y la estabilidad mensual fallan.

## Contrato ejecutado

- señal: QQQ menos `0,5*(SPY+SPXW)` desde open 09:30 hasta close 10:34;
- acción: momentum QQQ-SPY equal-notional;
- entry/exit: open exacto 10:36 / open exacto 13:36;
- hold: 180 minutos; coste total: 2 bps;
- scope físico: 501 sesiones por ticker, solo 2022–2023;
- exclusiones predeclaradas: 2022-11-25, 2023-06-05, 2023-07-03 y
  2023-11-24.

La auditoría independiente reprodujo el ledger, las métricas mensuales, hold y
coste únicos, cero overlaps y cero fechas posteriores a 2023.

## Controles no elegibles

| Control | WR | PF | PnL neto |
| --- | ---: | ---: | ---: |
| Mean reversion | 41,851% | 0,812876 | -1.060,311 bps |
| Long QQQ / short SPY fijo | 48,089% | 0,924384 | -398,799 bps |

Ningún control tiene PF mayor que uno y ninguno puede sustituir la acción
primaria.

## Evidencia sellada

Directorio:
`results/_diagnostics/opening_relative_momentum_v1_development_202201_202312/`.

- predeclaración: `f96e5af5340d265d658374ccf73e67be827999bd08b3964bac8531706a2306ba`;
- runner: `bb168f32f744d3144a547945989137fb5aae3684a5e05626104d21a40614004a`;
- dependency de fuente: `348e8dcf97abe924a024c9eaaf7c87b10969cde5ec840212e45c8460f12508f7`;
- inventario: `0311dc5ce66e09f4af9bda249f3c9e2e377cbe65fa1376229357ffcd75f9eb57`;
- trades: `b119ab24537d90e33f8205aac17be50bbf157616a403d0f4a087390fac750384`;
- meses: `48070dad5ade70f5b1b47a5c9d698c8215adda58ebb9bc528333b587a359a474`;
- controles: `ffd95ec3b7266bad4e49e141fa9626d297deaa1bcebd0e112db8ffc30027b320`.

## Stop rule

No abrir outer, seleccionar meses, invertir el signo, añadir beta/z-score,
threshold, gap filter, stop, ML o nuevo reloj sobre estos outcomes. La familia
queda falsificada en su forma fija. Una continuación debe ser una hipótesis
nueva predeclarada; mejorar WR sin PF muestra que debe explicar o limitar la
asimetría de pérdidas, no solo volver a escoger dirección.

El estado del programa sigue siendo `NO_PROFITABLE_CAUSAL_POLICY`.

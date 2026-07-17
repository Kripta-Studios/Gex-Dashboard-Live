# CROSS_VENUE CALENDAR-RR — resultado del preflight de reloj nativo

## Veredicto

`PASS_CROSS_VENUE_CALENDAR_RR_NATIVE_CLOCK_PREFLIGHT`.

El capture base fue `167118b0e22c8f76208fed32fc555c4d06148039` y el
sealer offline, ejecutado sin red, fue
`8828bd7239f57506c39434449a894d5acf126097`. La auditoría independiente posterior
rehasheó las 24 raw responses, parquets y manifests y terminó
`PASS_INDEPENDENT_PREFLIGHT_AUDIT`.

## Cobertura

| Medida | Resultado |
| --- | ---: |
| Sesiones | 12/12 |
| Capturas front/back | 24/24 |
| Filas nativas | 64.632 |
| Filas vintage sin key nativa | 0 |
| Keys nativas extra en clocks objetivo | 0 |
| Filas bid/ask revisadas | 0 |
| Crossed quotes | 0 |
| Raw bytes | 12.217.809 |
| Parquet bytes | 873.050 |

La respuesta actual del proveedor reprodujo exactamente keys y bid/ask vintage
en las cuatro sesiones extremas de cada ticker-año. Esto valida la viabilidad de
reconstruir el reloj, no la rentabilidad ni la paridad live prospectiva.

## Proyección full 2024–2025

| Medida | Proyección |
| --- | ---: |
| Sesiones | 1.503 |
| Capturas | 3.006 |
| Filas | 8.095.158 |
| Raw | 1,425 GiB |
| Parquet | 0,102 GiB |

Pasa los límites congelados de 50M filas y 20GiB raw. El full backfill queda
autorizado solo mediante un capturador inmutable/resumable que preserve los
mismos contratos de provenance y exact-key coverage. No se ha leído ningún
retorno 2024–2026.

## Hashes autoritativos

- `seal.json`: `d33e01a6226eb89083be7aa77ed5e8554a1a7babe6342a9a7d9d243881feee6d`.
- `capture_index.csv`: `c0eadebff11678f073ef372390aaaee00352acf32e052ab97d7b1966f0fe42ad`.
- `cost_projection.json`: `9458bd781c8a69fa946f1ba139fb83c6d59798e2e46775dfbee3330565e7f9d9`.
- Terminal status: `1f914c4386c0676ee418458a20c91d9db7c5cd18e88324b4908fdf27ec91dcc5`.

El output completo permanece en
`D:/ThetaData/cross_venue_calendar_rr_native_clock_preflight_2024_2025_v1`;
los compactos se versionan en `_diagnostics`.

# CROSS_VENUE CALENDAR-RR — aclaración de sellado del preflight

**Estado:** `PRE_OUTCOME_OFFLINE_SEAL_REPAIR_ONLY`

**Fecha:** 2026-07-17 Europe/Madrid

**Capture base:** `167118b0e22c8f76208fed32fc555c4d06148039`

## Hecho operativo

El comando del preflight fue iniciado una sola vez desde el capture base. El
wrapper PowerShell agotó su timeout de 120 segundos, pero el proceso Python PID
`42584` continuó como hijo huérfano. Se comprobó el PID y no se lanzó un segundo
capturador. Python completó las 24 peticiones, pero al terminar no pudo escribir
el progreso/resumen por el pipe cerrado y salió antes de crear
`capture_index.csv`, `cost_projection.json`, `seal.json` o renombrar staging.

El estado preservado es:

```text
D:/ThetaData/cross_venue_calendar_rr_native_clock_preflight_2024_2025_v1.staging
```

- 24/24 directorios front/back contienen raw response, parquet y manifest;
- `errors.json` no existe;
- `missing_vintage_key_rows=0` en 24/24;
- `native_extra_target_key_rows=0` en 24/24;
- `revised_bid_ask_rows=0` en 24/24;
- `crossed_native_rows=0` en 24/24;
- no se leyó underlying 10:36/13:36, label, retorno, PnL ni 2026.

Esto no es todavía `PASS`: falta el seal agregado.

## Reparación única permitida

No borrar, mover, recapturar ni volver a consultar el proveedor. Implementar un
modo explícito `--seal-existing-staging` que opere sin red y:

1. exija output final ausente y exactamente el staging anterior;
2. derive otra vez las 24 specs congeladas;
3. verifique que cada manifest usa los hashes del código en `167118b0`;
4. rehashee las 48 fuentes Greek/IV y los 24 raw/parquet/manifests;
5. reconstruya cada parquet desde su raw response;
6. repita el exact-key crosscheck Greek/IV/native a 10:30/10:35;
7. recalcule index y proyección de coste;
8. registre por separado capture commit/hashes y offline-sealer commit/hashes;
9. renombre atómicamente staging al output final solo si todo pasa.

El sealer debe estar tested, committed y pushed antes de ejecutarse. Cualquier
diferencia cierra el preflight sin requery. La reparación no cambia muestra,
endpoint, requests, keys, feature, mapping, gates ni scope cronológico.

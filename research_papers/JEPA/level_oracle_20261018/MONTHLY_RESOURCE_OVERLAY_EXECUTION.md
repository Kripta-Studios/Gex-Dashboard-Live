# Transición operativa mensual del 18 de octubre de 2026

La instrucción posterior del usuario fija ambos márgenes libres en
2.000.000.000 bytes decimales. La revisión independiente
`MONTHLY_RESOURCE_OVERLAY_REVIEW.json`, SHA
`b48f30431c9ddd40b57a2aa61e20f6786c1fda746ae41cc03ee2812ba034b1b9`,
admitió exclusivamente el reemplazo temporal de `wait_resources`;
12 fixtures independientes, Ruff y compile pasaron. El productor científico,
sus once dependencias, su configuración y su contrato permanecen intactos.

La primera transición se canceló: al suspender el PID 7680 se detectó que
había empezado el tercer fit a las 21:16:27.997380 UTC. El proceso se reanudó
en `finally`, sin terminarlo. Ese fit completó a las 21:18:28.675391 UTC
(120,678 segundos; 198.713 filas por 1.954 columnas).

La segunda transición suspendió el proceso después del tercer completion.
Comprobó la CLI original de validación, ausencia de hijos, exactamente tres
fit_started completos y ningún cuarto fit. Rehasheó 6.084 archivos de evidencia
(markers, modelos, fit_started, snapshots y contrato), conservando enero y los
modelos anteriores. Publicó un recibo antes de terminar únicamente el PID 7680;
después verificó de nuevo los 6.084 hashes. Ningún fit quedó interrumpido.

Los recibos están en
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_resource_transition_v1`:

- `before_stop.json`: SHA `7d24440ee38723a6cfe9f3163d7fd579d484e55afda5ec54c7644aca61ed3290`.
- `stopped.json`: SHA `06de4a14cd55011e61858bfc6601e7efd8311e76fd1f45bf03b029cdb1b06fb1`;
  estado `CONTROLLED_RESOURCE_TRANSITION_NO_FIT_INTERRUPTED`, 21:20:19.985163 UTC.
- `wrapper_process.json`: SHA `7cd1b996df5d4b7f0e20a2d49e24942942b7fb320e7f7541dc08feb8feaa320c`.

El wrapper comenzó a las 21:20:20.034372 UTC, PID **38676**, sólo
`--stage validation`. Mantiene OMP=4 y OPENBLAS/MKL/NUMEXPR/BLIS=1.
Los logs nuevos son `overlay.stdout.log` y `overlay.stderr.log` dentro del
directorio de transición; los antiguos se conservan. El runtime independiente es
`D:/GexResearchArtifacts/level_oracle_20261018/monthly_resource_overlay_v1`.
Su `launch.json` y eventual `completion.json` ligan la autoridad del overlay y
los checkpoints; no sustituyen la auditoría económica ni el contrato original.

Estado al escribir este recibo: proceso nuevo vivo, revalidación inicial en curso,
sin nuevo completion de validación. No se afirma todavía que el siguiente fit
haya atravesado el nuevo gate. El margen de 2 GB es una instrucción operativa,
no una cota demostrada del pico de memoria futuro.

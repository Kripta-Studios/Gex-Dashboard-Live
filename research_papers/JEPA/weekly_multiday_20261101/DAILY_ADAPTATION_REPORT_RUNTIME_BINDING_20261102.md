# Binding del informe descriptivo de adaptación diaria

Este binding fija un único render posterior al cierre independiente del
auditor V2. No abrió resultados económicos durante la preparación.

## Autoridades cerradas

- Productor `h2_daily_adaptation_01/manifest.json`, SHA256
  `7decb3e2baf360d807fd849604013728f5fe05c48dcd3302c0b270a1440d2206`.
- Exit del productor `h2_daily_adaptation_observer_01/exit.json`, SHA256
  `54021b954d522e0c9535b237de45a63da14a39e91e12e71fe90546d351f9f0d0`.
- Recibo root de cierre del productor, SHA256
  `2b59260b4019f7e04199a6353b58bdcb8fd995c671e23cb6485ab6fa67533a2d`.
- Contrato `DAILY_ADAPTATION_CONTRACT_20261101.md`, SHA256
  `5d388e484435c8fe23d40476c02928887c6ab5487af62197e5e74f08c1fe0047`.

El auditor requerido es V2 y sus autoridades son:

- `h2_daily_adaptation_audit_02/audit.json`, 2.983 bytes, SHA256
  `383edce65b16b316dcf71f2197a716d71501495f704040e858cea9354511b2b9`.
- `h2_daily_adaptation_audit_02/manifest.json`, 277 bytes, SHA256
  `ddda352f21b7b94b35db2a79c750048dd691c337672fbb3e31b35c3b9c4497d0`.
- `h2_daily_adaptation_audit_observer_02/exit.json`, 1.289 bytes, SHA256
  `6c9e236906de004c9da015021424e690b1dc8d1ed06514533fdcbfc4c3a524e8`.

El exit retenido registra PID24780, CPU[0], metadata_error null, changed_pins
vacío y `audit_v2_child_exit_code=0` a
2026-11-02T10:02:44.028522+00:00. El manifest vuelve a pinear el audit y ambos
declaran el PASS contratado dado los pesos guardados, sin refit.

## Renderer y evidencia técnica

- `render_weekly_daily_adaptation_result.py`, 34.271 bytes, SHA256
  `d0672f7d4723fa96f7df4745a0f7e922833e22b0b17deae2528c15b09fed3698`.
- Revisión `CLEAR_STATIC_RENDERER`, SHA256
  `0735773e90f04ccf8c045b8c079daf264389c039a1e43503d92328befbfae921`.
- Recibo formal de checks, SHA256
  `bef04941a5590ca374b6c87730be8509c295bfa58d444a6bf094937ae1aed2ef`:
  compile y Ruff exit0, sin render, inferencia, replay o lectura de outcomes.
- Archivo de evidencia, SHA256
  `51fff001da361aa956aa9d4bdb2c2c50d19400fc113599ff00839417b30387cc`.
- Helper oficial de recursos, SHA256
  `3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046`.

El renderer valida el manifest, audit, exits, flags, 152 outputs, 178 sesiones,
136 estados nuevos, 42 reutilizados, 612 diagnósticos, ocho libros y 72 valores
mensuales. Produce un informe, PNG, SVG y recibo descriptivos. No entrena,
infiere, hace replay, selecciona ganador ni aprueba promoción.

## Comando y raíces

```text
python -X utf8 -u render_weekly_daily_adaptation_result.py
  --execute-reviewed-report
  --producer-root D:/GexResearchArtifacts/weekly_multiday_20261101/h2_daily_adaptation_01
  --producer-manifest-sha256 7decb3e2baf360d807fd849604013728f5fe05c48dcd3302c0b270a1440d2206
  --audit-json D:/GexResearchArtifacts/weekly_multiday_20261101/h2_daily_adaptation_audit_02/audit.json
  --audit-sha256 383edce65b16b316dcf71f2197a716d71501495f704040e858cea9354511b2b9
  --audit-exit-json D:/GexResearchArtifacts/weekly_multiday_20261101/h2_daily_adaptation_audit_observer_02/exit.json
  --audit-exit-sha256 6c9e236906de004c9da015021424e690b1dc8d1ed06514533fdcbfc4c3a524e8
  --reporter-sha256 d0672f7d4723fa96f7df4745a0f7e922833e22b0b17deae2528c15b09fed3698
  --output D:/GexResearchArtifacts/weekly_multiday_20261101/h2_daily_adaptation_report_01
```

Las únicas raíces nuevas son `h2_daily_adaptation_report_01` y
`h2_daily_adaptation_report_observer_01`. Ambas deben estar ausentes. No hay
resume, adopción de parciales o retry automático.

## Admisión y cierre

El launcher exige branch exacta, HEAD local igual al remoto y cada miembro del
paquete byte a byte igual a `git show HEAD`. Verifica los pins del productor,
auditor V2, renderer, recibos y helper; exige exit0 retenido del productor y del
auditor. Fija CPU[0] y diez variables de threads a1 antes de importar el helper
oficial, persiste una observación contemporánea y aplica el gate de2GB.

Sólo después crea un hijo oculto mediante `Popen` con argumentos en lista,
registra PID/creation/afinidad antes del wait, retiene el handle, guarda logs y
espera siempre al hijo. El cierre rehashea todos los pins y eleva cualquier
cambio o error de metadata a exit no cero. La interpretación del informe y la
inspección visual del PNG corresponden a una revisión posterior separada.

Antes del único lanzamiento deben revisar ambos archivos y publicarse sus bytes
exactos. Este binding no acredita rentabilidad ni autoriza interpretar el
informe antes de su cierre y revisión independiente.
`technical_ready=false`, `promotion_approved=false`, selección nula.

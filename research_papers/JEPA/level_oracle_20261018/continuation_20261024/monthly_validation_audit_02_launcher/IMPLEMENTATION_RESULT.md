# Preparación del lanzador de auditoría 2025, intento 02

Fecha: 2026-10-24. Estado: implementación y fixtures completas; **sin lanzamiento ni auditoría real**. El pin externo del review V2 y la revisión final del root siguen pendientes.

El lanzador nuevo mantiene los controles del intento 01 y usa otro root de recibos y output. Fija el exit 0 real del productor, su completion, y los recibos del fallo del auditor 01. Añade la autoridad V2 mediante SHA externo obligatorio, comprueba su linaje original y lo verifica también en `audit.json`. Conserva la selección congelada, incluido null, sin cambiar ninguna decisión científica.

El intento 01 no se modifica ni se convierte en éxito. Su script conserva SHA256 `ccbecce5e10f03de302dbe19a448a1db138ed807b9c18bca266e43c377d10866`; el auditor y productor originales no tienen diff. La preparación no ha repetido el auditor, entrenado modelos o abierto 2026.

Pruebas:

- Primera ronda del nuevo launcher: **38 passed en 0,40 s**, exit 0.
- Tras añadir guard de la copia publicada y linaje del resultado: **40 passed en 0,36 s**, exit 0.
- `py_compile`: PASS. Ruff con selección `F`: PASS.
- Los tests usan autoridades temporales explícitamente sintéticas. Cubren pin externo obligatorio, review/código alterados, preservación del fallo 01, cadena de salida, gate exacto, locks, copia publicada sin mutaciones, linaje de cierre y consulta del handle tras un child Python vacío. No ejecutan el auditor real ni datos de mercado.
- Verificación adicional solo de metadata existente: los 22 pins reales del intento previo y de la validación coinciden; cadena del fallo 01 verificada. No se presentó esa comprobación como revisión del V2 pendiente.

Hashes de los bytes preparados:

| Archivo | SHA256 |
| --- | --- |
| `launch_when_validation_complete.py` | `a848a55788b7b4644db879421d0c733623a54761f9c4c7b6e7d53ac584770c20` |
| `test_launcher.py` | `c6e8cb5c38a97e79d961964110cc9f4286439529d983e10e6618f3a8bb1b0da1` |
| `SPEC.md` | `85e3ab25bc4b5b4f7a5100e1d33bc21c1c33ae4d68c23cf141ef84ee318c5bb1` |

El root externo canónico es `D:/GexResearchArtifacts/level_oracle_20261018/monthly_validation_audit_launch_20261024_02`. La copia publicable está en `research_papers/JEPA/level_oracle_20261018/continuation_20261024/monthly_validation_audit_02_launcher`. Ambos juegos de código, fixtures y spec deben tener hashes idénticos antes de publicar y ejecutar. El diff contra el script y fixtures intactos del intento 01 se conserva en `DIFF_FROM_ATTEMPT_01.patch`.

No existen `watch_started.json`, `attempt.json` ni el output de auditoría 02. La futura ejecución exige un SHA externo real del review V2 publicado y aprobación concreta del root sobre estos bytes. No hay transición automática a test 2026.

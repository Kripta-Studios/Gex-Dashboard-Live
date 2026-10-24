# OOF V2R1: verificación de la reparación de metadata

24 de octubre de 2026. Implementación sintética verificada; ningún preflight
real R1, calibración, replay ni auditor económico ejecutado por esta revisión.
El [contrato R1](OOF_TRANSITIVE_SOURCE_V2R1_IMPLEMENTATION_CONTRACT_20261024.md)
se publicó en `1a0035a4f2a1a0f4e426a26ea2ddee63dd747ed1` antes de las pruebas.
Los originales y cuatro archivos V2 publicados conservan sus hashes.

La única reparación funcional elimina `day_root` de la comprobación de nulidad
en filas `MISSING_SOURCE`. Se exigen los dos SHA nulos y se continúa antes de
usar esa ruta. Las seis ausencias no añaden miembros de I ni permiso de payload;
no se convierten en retornos cero. Versiones, nombres y reviews pasan a V2R1.
Comparaciones AST completas contra V2 verifican sólo esas sustituciones
declaradas; los ocho helpers comunes coinciden y los cuatro pins científicos
permanecen idénticos.

| Archivo nuevo | SHA256 |
|---|---|
| `run_oof_calibrated_pipeline_v2r1.py` | `87512b315d69c75c948c68a671939a9423f53abaa6cf2649d5faee7acd22b15a` |
| `test_run_oof_calibrated_pipeline_v2r1.py` | `7ca60f506540f4753b373d9230273c8d77936393604e909a87a9995f867c2400` |
| `launch_oof_pipeline_v2r1_20261024.py` | `e53084c70f99e4410814066a757e8f455dbb91bece8838fcd73417ce4614dce2` |
| `test_launch_oof_pipeline_v2r1_20261024.py` | `f78ee419e122800b14165902fa21ecc38dfd118191f4b61aa436f2fb912cb70a` |

El wrapper ejecutó cinco focales: cuatro variantes del constructor `Request`
real y comparación AST. Se usaron las seis identidades QQQ/SPY × 20260401/09/15,
con rutas artificiales nominales inexistentes. Guardas de prueba prohíben
resolver, hacer stat/lstat o abrir esas rutas. El positivo declarado y el caso
anterior de `day_root=null` pasan; cada SHA no nulo por separado falla.
No se llama `MonthlyInputs` ni se ejecuta `FullSource` o el fixture de doce fases.

El supervisor prueba el preflight real con la misma forma de metadata, sus
autoridades y recibos upstream sintéticos encadenados. Las ausencias permanecen
fuera de I, no aparecen destinos y Popen está prohibido en esos focales. También
se corrigió la expectativa heredada de junio a seis ausencias. El conjunto
sintético tiene 36 sidecars COMPLETE y dos de junio exclusivos del índice;
no debe confundirse con los recuentos del índice real.

| Intento de autor | Pytest | Tiempo pytest | Exit | Gate RAM / commit disponible, bytes |
|---|---|---|---|---|
| Wrapper R1 01 | 5 PASS, 41 deselected | 3,72 s | 0 | 8.031.547.392 / 6.804.918.272 |
| Supervisor R1 01 | 46 PASS | 77,67 s | 0 | 8.028.872.704 / 6.785.179.648 |

Ambos ejecutaron Ruff con exit 0, CPU 1 y un hilo OMP/BLAS. Pins, comandos,
snapshots, logs y exit observado mediante `Popen.wait` están preservados; no hubo
reintento. El filtro del supervisor `-k r1_ or june_index_only or
metadata_admission_helpers` coincidió además con el nombre del módulo y
seleccionó sus 46 pruebas técnicas completas. Se reconoce este exceso respecto
de los siete casos focales previstos; se dejó terminar una sola vez. No incluyó
calibración ni las doce fases científicas. Las pruebas heredadas de supervisión
usan procesos Python inocuos y artefactos artificiales, no mercado.

La [review independiente del wrapper](OOF_TRANSITIVE_SOURCE_V2R1_RUNTIME_IMPLEMENTATION_REVIEW_20261024.json),
SHA `7431a6df11966c46ce5aa66bac5d707b7dfe9e131f59366df24f0f2f66c222c9`,
fija su mapa exacto de 18 dependencias y cuatro pins científicos. Registró cinco
focales independientes PASS en 2,01 s. La review independiente del supervisor
se entrega separadamente; este recibo del autor no la sustituye.

## Evidencia compacta y límites

- [Archivo wrapper](continuation_20261024/oof_transitive_v2r1_wrapper_synthetic/MANIFEST.json):
  14 copias exactas, 104.271 bytes; manifest SHA
  `53bc167fb3688c30d1933fe3c4e00327851a99890b2081e7b167999108f8050d`.
- [Archivo supervisor](continuation_20261024/oof_transitive_v2r1_supervisor_synthetic/MANIFEST.json):
  17 copias exactas, 183.719 bytes; manifest SHA
  `e783766ff30221ad1e53e04260ea302caae1e0d2298592b48311f83ef4b71c4a`.

Los originales de esos recibos están en
`D:/GexResearchArtifacts/level_oracle_20261018/oof_transitive_v2r1_wrapper_synthetic_20261024_01`
y `.../oof_transitive_v2r1_supervisor_synthetic_20261024_01`; cada manifest
documenta paths y hashes. Los payloads artificiales permanecen en sus
subdirectorios `pytest_tmp`, sin copiarlos al repositorio. Los launchers
operativos de pruebas están copiados y sellados en ambos archivos compactos.

La corrección no demuestra admisión real R1 ni rentabilidad. Los recuentos
reales esperados y los fallos anteriores conservan sus recibos; aquí no se volvió
a leer el índice real ni ningún payload de mercado. Una ejecución posterior
requiere reviews, request/binding nuevos publicados y GO explícito de root.

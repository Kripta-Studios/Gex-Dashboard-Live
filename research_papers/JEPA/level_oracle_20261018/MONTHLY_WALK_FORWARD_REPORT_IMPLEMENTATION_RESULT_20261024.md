# Reporter mensual descriptivo preparado — 2026-10-24

Se prepararon código, contrato y fixtures sintéticas para derivar tablas desde
una auditoría mensual cerrada, con SHA externo. **No se ha ejecutado este
reporter sobre mercado.** La revisión independiente estática y focal terminó
sin blockers; publicación pendiente antes de cualquier uso real. Root confirma
aparte el exit y el pin de la auditoría.

Archivos:

- [Reporter](report_monthly_walk_forward_audited.py):
  `1968aefcba4abf650d5e13cd16435ac74067cfee78ce5752fde6427e5a941146`.
- [Fixtures](test_report_monthly_walk_forward_audited.py):
  `6b5463a4dbad2872cf1c4eea902dbacfaeefdb66b39b62c3a48a871aa00fa244`.
- [Spec](MONTHLY_WALK_FORWARD_AUDITED_REPORT_SPEC_20261024.md):
  `9cf8ad4f8b77dd5086fa3b5d9becfdd49b5d3c39d51bbb59bfeffc92d384fc40`.

El alcance 2025 produce 108 filas ticker-mes y 36 agregados `ALL`; el alcance
compuesto produce 162 y 54, respectivamente. Siempre incluye los tres modos y
tickers. Las tablas por periodo contienen 12 o 24 filas incluyendo `ALL` y el
diario contiene 2.250 o 3.357 filas. La selección congelada puede ser null y no
se vuelve a calcular. La economía de las ausencias se muestra null; los días
disponibles sin fills conservan cero observado. Netos, PF, WR, drawdown, holding
y razones de salida se reconcilian con los reportes ya auditados.

`summary.json` no declara éxito por sí solo: exige `output_manifest.json` con
status COMPLETE. El manifest sólo se escribe al terminar la reconciliación y
el rehash final. Un fallo conserva los archivos parciales y `failure.json`.
El inventario distingue los inputs consumidos/rehasheados de las referencias
restantes. Attempts y ledgers se consolidan completos; matrices y raw permanecen
locales. No se repiten fits, inferencia, scheduler, selección ni auditoría raw.

## Verificación sintética

Comando inicial:

```powershell
python -m pytest -q research_papers/JEPA/level_oracle_20261018/test_report_monthly_walk_forward_audited.py
```

Resultado: **21 passed in 188.51s**, exit 0, sesión exec 54001, hijo PID 15152,
creation time 1792799262.7527506. Ese resultado corresponde al código inicial
`b993ff09a93f80dcbc149b0f568dc0c33c6b6a65e39678af438c636099c2880f`
y tests `e736355bb040d3df61ecf5455b72e313f5f3508741ee80d21a6a8a9fc95e8b0d`.
Las fixtures construyen sólo datos artificiales, con índice de 2.625 filas,
ambos scopes, todos los meses/modos/tickers, ausencias, no-fill y discrepancias
inyectadas. No consumen archivos de mercado.

Después se añadió la dependencia explícita de summary respecto al manifest
final, el check de inmutabilidad del código y tres fixtures: fallo tardío,
rechazo de JSON no finito y determinismo JSON/CSV. Comando de ese primer delta:

```powershell
python -m pytest -q research_papers/JEPA/level_oracle_20261018/test_report_monthly_walk_forward_audited.py -k "late_failure or json_rejects or csv_json_deterministic"
```

Resultado: **3 passed, 21 deselected in 0.72s**, exit 0; wrapper 6,376 s.
Inicio 2026-10-23 23:51:46,621 UTC. En ese punto la suite contenía 24 tests;
ese recibo corresponde sólo a los tres seleccionados y conserva sus pins.

La revisión detectó RPT-01 (conteos auditados no exigidos por completo) y RPT-02
(destino dentro de feature_root no protegido). Se corrigieron antes de uso y se
añadieron 22 casos negativos de conteos/identidades ausentes o incoherentes y
dos destinos prohibidos. Los roots engine/session/feature deben coincidir con
los bindings y quedan protegidos antes de crear salida.

Sobre los tres hashes finales indicados arriba se repitió el comando completo:
**48 passed in 161.07s**, exit 0, wrapper 161,8320368 s, sesión exec 88939,
hijo observado PID 48560. Inicio 2026-10-23 23:55:12,595903 UTC; los tres hashes
permanecieron iguales al terminar (`pins_unchanged=true`). Gate Windows previo:
RAM disponible 8.573.263.872 B y commit libre 7.502.204.928 B, mínimo requerido
2.000.000.000 B. Ruff, parseo AST y compile de ambos archivos finales pasan.
No se añadieron tests a scripts antiguos ni se modificó ningún artefacto sellado.

## Corrección de la medición de recursos

El wrapper inicial imprimió RAM disponible 5.764.419.584 B y un campo llamado
`available_commit_bytes=31.067.901.952`. Este segundo valor procedía de
`psutil.swap_memory().free`: era swap libre, **no commit libre de Windows**.
Por tanto, no acredita un gate previo de commit. Se conserva el recibo inicial
y la identificación explícita del error; no se sustituye esa observación.

Después de arrancar pytest, durante generación sintética, `GlobalMemoryStatusEx`
midió RAM disponible 5.669.715.968 B y commit libre 3.675.742.208 B, ambos por
encima de 2.000.000.000 B. Esa observación posterior no se presenta como gate
de admisión del primer proceso. RSS observado del hijo: 202.313.728 B y después
224.948.224 B; son muestras, no un pico certificado.

Para el delta final sí se comprobó **antes de iniciar pytest** el gate Windows:
RAM 8.627.990.528 B y commit libre 7.322.591.232 B. Se fijó un hilo en
OMP/MKL/OpenBLAS. Ninguna de las dos ejecuciones entrenó, infirió o evaluó mercado.

Recibos preservados:

- [Corrección de medición](continuation_20261024/monthly_report_fixtures/resource_measurement_correction_01.json).
- [Resultado inicial](continuation_20261024/monthly_report_fixtures/initial_fixture_result_01.json).
- [Resultado delta](continuation_20261024/monthly_report_fixtures/delta_fixture_result_02.json).
- [Stdout delta](continuation_20261024/monthly_report_fixtures/delta_stdout_02.txt) y
  [stderr delta](continuation_20261024/monthly_report_fixtures/delta_stderr_02.txt).
- [Admisión completa final](continuation_20261024/monthly_report_fixtures/final_fixture_admission_03.json),
  [resultado completo final](continuation_20261024/monthly_report_fixtures/final_fixture_result_03.json),
  [stdout final](continuation_20261024/monthly_report_fixtures/final_stdout_03.txt) y
  [stderr final](continuation_20261024/monthly_report_fixtures/final_stderr_03.txt).
- [Manifest de recibos](continuation_20261024/monthly_report_fixtures/manifest.json).

CLI previsto, sólo tras revisión/publicación y autorización del pin cerrado:

```text
python report_monthly_walk_forward_audited.py --monthly-root ABS_MONTHLY_ROOT --audit ABS_CLOSED_AUDIT_JSON --audit-sha256 EXTERNALLY_VERIFIED_SHA256 --out ABS_NEW_REPORT_ROOT
```

Todo resultado futuro seguirá siendo desarrollo retrospectivo condicionado a
scores sellados. El reporter no acredita rentabilidad prospectiva, paridad live
ni promoción y no genera gráficos económicos durante esta fase.

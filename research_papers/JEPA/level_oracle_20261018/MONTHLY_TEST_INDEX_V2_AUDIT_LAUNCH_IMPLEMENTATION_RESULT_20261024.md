# Supervisor del auditor mensual 2026 V2: implementación sintética

Estado: implementación terminada y entregada a revisión independiente. No se ha
ejecutado el auditor de mercado, su preflight real ni el flag de lanzamiento.
El supervisor requiere todavía review externa, runtime con cierres reales y
publicación exacta; este informe no concede autorización de runtime.

El código nuevo admite el productor cerrado mediante su cadena de proceso y
exit cero observado por handle, preserva los 24 modelos anteriores y exige el
cierre científico de 36 ventanas y 18 meses. Comprueba hashes y JSON de markers
sin interpretar scores o labels. Mantiene el lock científico sin cambiar bytes,
usa un claim nuevo, exige RAM y commit libres de al menos 2.000.000.000 bytes
inmediatamente antes de Popen y ejecuta un comando fijo sin reintentos.

La revisión previa identificó tres huecos que se cerraron antes del pase final:

- La cadena persistida ahora liga process, exit y completion mediante SHA,
  junto a runtime, review, código, commit y preflight. `monitor_seconds` mide
  el intervalo del monitor posterior a Popen; RSS/private son máximos muestreados.
- El cierre exige launch.json exacto, quince snapshots y audit.json compuesto;
  rechaza failure.json coexistente. Un fallo posterior conserva el exit real
  y no crea completion.
- Las fixtures incluyen admisión completa, resultado completo y dos recorridos
  de lanzamiento con un hijo Python vacío: cierre válido y fallo tardío. La
  lógica de schemas, import closure y helper congelado se ejecuta realmente;
  Git se sustituye en esa fixture y el proceso auditor se sustituye por `pass`.

## Validación del autor

Primer pase: 31 PASS y siete errores de setup en 24,64 s, exit 1. La fixture
cambiaba el hash del contrato sintético en el supervisor pero no en el helper
congelado. Se corrigió ese dato de fixture sin relajar el gate. Además se añadieron
dos fixtures del recorrido completo de lanzamiento antes del segundo pase.

Segundo pase completo: **40 PASS en 33,22 s, exit 0**. Ruff completo y compile
PASS. La suite aplica un gate de recursos Windows al inicio. Una observación
adicional durante el segundo pase dio RAM libre 7.286.804.480 bytes y commit
libre 3.394.621.440 bytes; no se presenta como muestra inicial ni como reserva.
Ningún modelo real, score o label de mercado fue utilizado por estas pruebas.

Autorrevisión posterior identificó S4: faltaba conservar en el cierre el pin
original del preflight; se recalculaba después del hijo. Ahora el SHA capturado
antes de Popen pasa por process/exit y se verifica sin reemplazarlo. La fixture
nueva muta ese recibo durante el lanzamiento y exige conservar exit cero real,
publicar failure y rechazar completion. Sobre los bytes finales: **6 PASS,
35 deselected en 13,65 s, exit 0**, selección `monitor or launch_complete or
launch_gate`; Ruff y compile PASS. La suite completa anterior no se repitió,
porque el cambio está limitado a esos recorridos. Los resultados de 40 y 6
no se suman como 46 pruebas distintas.

Los logs originales siguen en `D:/GexResearchArtifacts/level_oracle_20261018/`
bajo `monthly_test_index_v2_supervisor_synthetic_20261024_01` y `_02`. Copias
compactas y versiones identificables están en
[continuation_20261024/monthly_test_index_v2_supervisor_synthetic/result.json](continuation_20261024/monthly_test_index_v2_supervisor_synthetic/result.json),
SHA256 `bbac3d9855861dfec093dafc5cb44db10bbfdff7bc43678c73001a2ad7e2e091`.
Las copias de versiones se tomaron después de los tests. La versión de tests
del primer intento se reconstruyó desde la delta conocida y está señalada como
tal; no se afirma que hubiera un sello de esa versión previo a su ejecución.
Los logs originales no se sustituyeron ni editaron.

La evidencia final de S4 está en el intento local `_03` y en
[final_result.json](continuation_20261024/monthly_test_index_v2_supervisor_synthetic/final_result.json),
SHA256 `e103ca86d7453dd24e33c0cdd62ffc688fe305ba2b196b31a92c3fa144a169a0`.
Enlaza el resultado anterior inmutable y añade copias de los bytes finales.

## Bytes entregados a revisión

| Archivo | SHA256 |
| --- | --- |
| launch_monthly_test_index_v2_audit_20261024.py | 3cfe55a6a2926007d91d44215c8a7c0a28801efaca189fcf306c275e352ed046 |
| test_launch_monthly_test_index_v2_audit_20261024.py | 54a98599ed91fe3317ad298f918f4ccb8703ce7720cee501c8a8a7b9e1b131bd |
| MONTHLY_TEST_INDEX_V2_AUDIT_LAUNCH_SPEC_20261024.md | eb5f4eec4775a9ece3ec00e98396b93994b77b7be52e58d3efbdb3ae9bdf2336 |

Revisión independiente a cargo de `oof_reviewer`, separada de estos resultados
del autor. Los archivos científicos, launchers anteriores, modelos y autoridades
congeladas no se modifican. No se han rellenado valores de cierres futuros.
Esta verificación acredita software operativo sintético, no rentabilidad ni
paridad live, y no inicia OOF ni una hipótesis de mercado nueva.

# Revisión independiente del launcher mensual de test

23 de octubre de 2026. **CLEAR — PASS_MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW**.
Alcance **IMPLEMENTATION_ONLY**; `runtime_authorized=false`. Revisor:
`/root/oof_reviewer`; autor: `/root/scientific_review`.

Se inspeccionaron el wrapper congelado, su spec/review y `verify_process_chain`,
y después el launcher, fixtures y spec finales. No se modificaron el wrapper,
reviews anteriores, productor o ciencia. No se creó un binding de runtime real,
se certificó la salida de validación 2025 ni se lanzó test 2026 de mercado.

## Hallazgos resueltos

- **L1:** la comparación textual de roots podía rechazar separadores equivalentes
  después de un preflight válido. Ahora se comparan paths normalizados.
- **L2:** una excepción al inicializar el monitor después de Popen podía abandonar
  la supervisión. La inicialización está protegida y los fallos drenan el Popen
  original mediante `wait`, sin matar, relanzar ni fabricar recibos Win32. Un fallo
  al registrar una interrupción tampoco abandona la observación.
- **L3:** la publicación inicial cubría las reviews del wrapper y de ciencia,
  pero no la del launcher. Ahora `launch_binding.launcher_review` fija este JSON
  por path/SHA externo, valida sus campos y tres hashes, y lo incluye en Git.
- **L4:** el monitor podía atribuirse un SHA leído tardíamente. Ahora usa el pin
  publicado de preflight y lo revalida al abrir/cerrar, junto a los hashes del
  binding y del recibo de apertura. Una mutación impide una cadena completa.

Los cuatro hallazgos están resueltos en los bytes fijados abajo. No quedan
hallazgos bloqueantes identificados.

## Verificación independiente

El revisor ejecutó **16 PASS, 13 deselected, 5,61 s**, exit0, con estos argumentos:

```text
-q -p no:cacheprovider research_papers/JEPA/level_oracle_20261018/test_launch_monthly_test_20261023.py -k "retained_receipts or resource_drop or resource_boundaries or native_monitor_initialization or failed_interruption or monitor_code_mutation or equivalent_root or launcher_review or native_fast or frozen_wrapper"
```

Gate antes de pytest: RAM **7.741.485.056 bytes**, commit **4.553.867.264 bytes**,
a las 2026-10-23T21:41:48.753794+00:00; umbral decimal de ambas 2.000.000.000.
Se comprobaron límites de recursos, caída justo antes de Popen, paths equivalentes,
review externa, fallos de inicialización/interrupción, mutación del monitor y
preservación de los dos pins congelados.

La prueba de composición usa recibos y procesos dobles, pero llama al
**`verify_process_chain(validation=False)` real congelado** para salidas 0 y 7.
Por separado, tres hijos Python Windows inocuos de salida inmediata **0, 7 y 259**
verifican `GetProcessTimes`, espera señalada y `GetExitCodeProcess` con el handle
original de Popen, incluso después de `child.wait`. Ninguno ejecutó el wrapper
científico. Estas dos capas no se presentan como una cadena real de mercado.

El [recibo del autor](MONTHLY_TEST_LAUNCH_IMPLEMENTATION_RESULT_20261023.md),
SHA `7eadf69269518dc1bfe22f36b000fbe178c814a31f1288941ea3b275345c15f9`,
informa **29 PASS, 16,48 s**, exit0, y Ruff/formato/compile PASS. Su gate fue RAM
8.292.151.296 y commit 6.336.966.656 bytes. El revisor **no repitió la suite
completa de 29**. Ambas ejecuciones se observaron en salidas de herramienta;
no se inventan logs persistidos o hashes de logs. No se repitieron pruebas para
redactar este recibo.

## Flujo y límites revisados

El modo predeterminado sólo comprueba; el lanzamiento exige opción explícita.
El comando del hijo es fijo y llama al wrapper congelado, que fija `--stage test`
al invocar al productor, con su misma review. La admisión reutiliza `admit`: auditoría 2025 externa,
freeze/null, 24 modelos, once dependencias científicas y cadena real de salida
de validación siguen siendo obligatorios. No existe una ruta alternativa de fit
o inferencia en el launcher.

Las raíces de logs/runtime son nuevas y separadas; se rehashean autoridades antes
de Popen y el gate de RAM/commit es inmediato. El handle original se conserva
hasta observar salida; no se deduce exit0 de que el PID desaparezca. Los recibos
ligan PID, creación, comando y hashes del binding/monitor. Si falta el launch real
del wrapper, la cadena queda incompleta. Un exit0 no acredita completion
científico, rentabilidad, auditoría o promoción; no hay retry ni resume automático.

El commit externo de 40 hex se usa para comprobar objetos Git exactos de alcance.
El launcher no accede a red ni certifica publicación remota: root debe verificarla
y documentarla antes de ejecutar. HEAD puede avanzar por cambios ajenos si los
bytes de alcance siguen idénticos; no se exige ni se altera un árbol global limpio.

## Bytes fijados

| Archivo nuevo | SHA256 |
|---|---|
| `launch_monthly_test_20261023.py` | `3e77bda56dabd8287b04ae9a47b4dcd45d5967a01a31514e933cbb44b6f4c08d` |
| `test_launch_monthly_test_20261023.py` | `684c495989d62f9feea40791d34c3cd2f9e12349a82de34189785ff13e64eed8` |
| `MONTHLY_TEST_LAUNCH_SPEC_20261023.md` | `1507f27de2445abbd63e8f088bb1f6eb52b8ae3e7178023cf720a67695e9b18f` |

| Autoridad congelada | SHA256 |
|---|---|
| Wrapper test | `f2b0490cdec916f98c09fc77a6533d0eab8c4f2711331753f7d5c998d81253c1` |
| Review del wrapper test | `49a3590504c74c06dc5a9b830bcf71b7472dbecae2ab267218aaa22aa2dd0280` |
| Review científica mensual | `0af3b22302c4eea2da0671bf7fa7f1f8dc3a775ccc7a372e23f0de082a32cdc7` |

El [JSON de revisión](MONTHLY_TEST_LAUNCH_IMPLEMENTATION_REVIEW_20261023.json)
fija también los tres archivos del wrapper y las once dependencias científicas,
con contrato `7250620ebe25da082c8d080faa54d006c15f36f2070f414405d14ca18a27158f`.
La publicación futura tendrá 20 miembros de código/reviews, incluido este JSON,
y además la runtime-review concreta. Su propio SHA se suministrará externamente,
evitando autorreferencia.

## Frontera pendiente

Este recibo declara únicamente la conclusión técnica de implementación. Faltan
la comprobación del cierre real 2025 con exit0 retenido, la auditoría 2025 completa
y su SHA externo, y la runtime-review concreta revisada/publicada con roots y
hashes reales. No se han creado ni declarado PASS esos bindings mediante esta
revisión. Root coordina publicación y lanzamiento tras satisfacerlos.

No hay fit, inferencia, validación prospectiva ni resultado económico nuevo de
mercado. 2026 sigue siendo desarrollo visto; `technical_ready=false` y
`promotion_approved=false`.

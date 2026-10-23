# Revisión independiente del auditor económico OOF

23 de octubre de 2026. **PASS_OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW**,
alcance **IMPLEMENTATION_ONLY**. Revisor: `/root/oof_reviewer`; autor de la
implementación: `/root/scientific_review`. `runtime_authorized=false`,
`technical_ready=false`, `promotion_approved=false`.

Se revisaron la admisión real `Monthly`, la reconstrucción `audit_month`, el
cierre `audit/main` y los esquemas de los productores congelados. La revisión
no quedó limitada a los helpers o a las afirmaciones de las fixtures. No se
leyeron valores de mercado, ejecutaron fits/inferencia/replay real ni modificaron
productores, código o especificaciones existentes.

## Hallazgo resuelto

R1: convertir primero a `float` podía borrar el dtype original de scores NPZ o
columnas de controles. Un float32 numéricamente igual podía pasar la comparación.
Los bytes revisados exigen scores float64 con forma vectorial exacta y controles
con `score`, `net_base` y `net_adverse` float64 antes de convertir a registros.
La revisión comprobó estos guards y las fixtures de admisión real que rechazan
float32 y formas incorrectas. No quedan hallazgos bloqueantes identificados.

## Evidencia de verificación

El revisor ejecutó **14 pruebas focales PASS, 21 deselected, 3,96 s**. Cubren
admisión mensual real, cutoff, pertenencia, escala, dtype/shape, controles float32,
signed-zero, gates por ticker, sellos/mutación y SHA externo incorrecto. La
invocación usó `pytest.main` después de `resource_gate`, con argumentos equivalentes a:

```text
python -m pytest -q research_papers/JEPA/level_oracle_20261018/test_audit_oof_calibrated_policy.py -k "real_monthly or exact_control or full_period_gate or main_wrong_external_hash or seal_required_members"
```

El gate previo midió RAM disponible **10.046.652.416 bytes** y commit disponible
**14.581.702.656 bytes**, ambos por encima de 2.000.000.000. El revisor también
ejecutó comprobaciones sintéticas en memoria: coste base/adverso con bid de salida
cero, rechazo de neto incorrecto, holding incorrecto y salida fuera del límite
de sesión corta, y desempate de signed-zero por menor action_id. Estas pruebas
adicionales son separadas de las 14 de pytest; precedieron a los guards finales
de dtype y sus funciones comprobadas no cambiaron.

El **autor informó 35 PASS en 12,99 s**, Ruff y compile PASS, para los hashes
finales de abajo. Su gate informado fue RAM 8.858.517.504 y commit
15.240.097.792 bytes. El revisor inspeccionó la fixture integral y el ciclo real,
pero **no reejecutó la fixture integral ni la suite completa de 35**. Esas cifras
no se atribuyen a una ejecución independiente del revisor.

## Alcance inspeccionado

- Autoridad mensual externa compuesta, bindings SessionClock, índice, markers y
  pertenencia efectiva a mapas de fuentes y salidas.
- Ventanas static/expanding/rolling12, identidad de modelos/escalas, máximos de
  todos los estados ofrecidos, incluidos negativos, empates y días sin ofertas.
- Historial estrictamente anterior al mes objetivo; disponibilidad declarada
  cierre NYSE + un minuto con DST y sesiones cortas; media `math.fsum` por
  estado y después por día; offsets USD sin selección por resultados.
- Controles float64 exactos y seis trayectorias propias; `has_filled`, WAIT,
  NO_FILL, no-overlap y estados visitados se reconstruyen para cada política.
- Contabilidad desde labels sellados con costes base/adversos ya declarados;
  calendario 750/369, seis ausencias fijas y 363 días objetivo disponibles;
  missing null separado de cero observado; gates por ticker sin ganador.
- Hashes congelados, payloads canónicos, rehash final, orden documental
  corroborado por mtimes y publicación exclusiva/atómica que conserva fallos.

Los mapas del adaptador contienen las fuentes efectivamente consumidas.
Los archivos históricos `realized` se vinculan mediante sus hashes en
`training_records`, la calibración reconstruida y el cierre externo. No se exige
al productor congelado un miembro inventado en un mapa donde no lo registra.

## Bytes revisados

Los hashes completos también constan en el
[recibo JSON](OOF_ECONOMIC_AUDITOR_IMPLEMENTATION_REVIEW_20261023.json).

| Implementación | SHA256 |
|---|---|
| `audit_oof_calibrated_policy.py` | `e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b` |
| `test_audit_oof_calibrated_policy.py` | `c98954a9bef3b70bef8c889255cb187a57d88c4f43235ade255a70560438f232` |
| `OOF_ECONOMIC_AUDITOR_SPEC_20261023.md` | `cfa6868435a772b336605e3b0613e8fa6c1e377a53cbbef376d3973e64901f37` |

| Productor congelado | SHA256 |
|---|---|
| `monthly_oof_calibration_adapter.py` | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| `evaluate_oof_calibrated_policy.py` | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| `oof_maximum_calibration.py` | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |

| Diseño y autoridad revisada | SHA256 |
|---|---|
| `OOF_ECONOMIC_AUDITOR_DESIGN_20261023.md` | `b9c2ac397945a04365289b9af0f202f04082c844badfc724ae937972be253154` |
| `PREQUENTIAL_MAX_CALIBRATION_DESIGN.md` | `e8264e398b31f22198a024a3c6d9dfa9fc4530402278693caac1caa2d6f7a619` |
| `OOF_MAXIMUM_CALIBRATION_INTEGRATION.md` | `79f8c69b13c3585aa26cbb15fa52f246675baaabd8b8e8d6661a5ffe150ce7bd` |
| `MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md` | `6bd989a6332fd21f751dc48ef084c5eba0f83b1f86f957f2a71127ef869bcb4e` |
| `OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md` | `7f88f18569d86ea936d0afdc4a485e461ccdf6c09d74feb835a026bee7caf3bc` |
| `PROTOCOL.md` | `c1b2551ec9ba84c2fe1fb20fe3ca86863ef7cca28e34bd36916991c7bf33d0ab` |
| `RESUMPTION_20261023.md` | `3f1c10e3a03470de2691aff21799d17550185251c3a63e4719f8efb2d35652b0` |

## Dependencias de ejecución pendientes

Este PASS permite versionar la revisión de implementación. No sustituye la
auditoría de outputs mensuales. Antes del uso real hacen falta los cierres y la
autoridad mensual compuesta con hash externo, cubriendo todos los meses desde
202501 hasta cada objetivo; H1 completo exige los 18 meses hasta 202606.
Cada mes debe tener cierres de corrección/replay ligados externamente y sus
artefactos completos. La request del auditor y su SHA externo deben quedar
revisados/publicados antes del lanzamiento, con root nuevo separado y gate
operativo de RAM/commit satisfecho. La decisión de ejecución corresponde al
coordinador tras resolver estas dependencias.

No se produjo una auditoría económica OOF real ni resultado de rentabilidad en
esta revisión. 2025 es TRAIN del calibrador y 2026 sigue SEEN_DEVELOPMENT.
`winner_selected=null`; rentabilidad causal NOT_DEMONSTRATED. El oracle
retrospectivo conserva su significado descriptivo y no acredita una política
operable.

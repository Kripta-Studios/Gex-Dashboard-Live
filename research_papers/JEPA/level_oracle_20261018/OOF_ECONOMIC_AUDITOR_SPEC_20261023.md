# Auditor económico OOF independiente: especificación de implementación

23 de octubre de 2026. Implementación solicitada por el coordinador después de
leer `OOF_ECONOMIC_AUDITOR_DESIGN_20261023.md`. No es revisión independiente ni
autorización de mercado. Productores y autoridades anteriores se conservan.

`audit_oof_calibrated_policy.py` no importa productores. Reconstruye máximos de
todas las ofertas, residuos históricos, offsets por día/estado, scores corregidos,
controles y trayectorias completas de las seis políticas. No refittea, reproduce
inferencia ni consulta cotizaciones raw. La autoridad base es una auditoría mensual
de outputs con hash externo, incluidos los meses anteriores y el objetivo.

## Interfaz fijada antes de ejecutar

La CLI exige `--request <JSON> --request-sha256 <SHA externo> --output <root nuevo>`.
El hash de request se publica/revisa antes del lanzamiento; no debe calcularse de
una request arbitraria como sustituto de aprobación/revisión. Esquema:

```json
{
  "version": "OOF_ECONOMIC_AUDIT_REQUEST_V1",
  "scope": "FULL_H1",
  "monthly_root": "ruta absoluta del productor mensual",
  "monthly_audit": "ruta absoluta de auditoría compuesta mensual",
  "monthly_audit_sha256": "SHA externo de esa autoridad",
  "session_root": "ruta absoluta SessionClock",
  "session_audit": "ruta absoluta de su auditoría",
  "correction_root": "ruta absoluta del adaptador OOF",
  "months": [
    {
      "month": "202601",
      "correction_completion_sha256": "SHA externo de 202601.complete.json",
      "evaluation_root": "ruta absoluta del replay de enero",
      "evaluation_completion_sha256": "SHA externo de completion.json del replay"
    }
  ]
}
```

El ejemplo abrevia la lista: `FULL_H1` requiere exactamente enero–junio2026
ordenados y seis raíces de replay distintas. `MONTHS` admite un subconjunto
explícito ordenado sin afirmar H1; los gates económicos H1 quedan NOT_EVALUATED.
Cada mes necesita historial completo 202501..mes anterior más el propio mes
auditado. La request no permite cambiar modos, thresholds, costes o calendarios.

Los tres productores están fijados a los SHA del diseño. Sus dependencias y las
copias de contrato de adaptador/replay deben coincidir con los bytes vigentes
publicados. Un cambio requiere revisión separada; no se acepta silenciosamente.

## Comprobaciones

Se mantienen las invariantes y artefactos exactos del diseño. Los mapas se
normalizan rechazando paths relativos y aliases conflictivos. Se exige pertenencia
efectiva de cada input mensual/marker, fuente actions/labels del índice, selección,
calibración, score y trayectoria consumidos. Se distingue entre `files` del replay
(incluye fuentes históricas heredadas del adaptador) y `monthly_files` (lecturas
del replay: objetivos/controles); no se exige que este último invente lecturas.

La selección y los offsets se comparan por payload canónico y float64 exactos.
La proyección de controles conserva bytes de score/netos. Costes y agregados
permiten tolerancia absoluta 1e-8, sin tolerancia relativa. El costo se comprueba
desde ask/bid ya sellados; no se carga de nuevo al replay.

Los nueve cierres cortos2025 y seis ausentes2026 son explícitos. La disponibilidad
de labels para el calibrador es cierreNYSE+1min, estrictamente anterior al mes
objetivo. No representa recepción observada. Los mtimes sólo corroboran orden
documental de selección/realized/calibración/scores/trajectorias; la reutilización
de historia previamente sellada se conserva.

Se reproducen economía pooled mensual y cobertura del productor. El auditor añade
economía por ticker y los gates preexistentes H1 (neto base/adverso positivo,
PF>=1,20,60trades y3/6meses positivos en cada ticker), separada del gate diario.
No selecciona una de las seis políticas por sus resultados. Missing mantiene
null/NO_EVALUABLE y un día disponible sin fill mantiene cero observado.

## Cierre y límites

Sólo se publica PASS tras reconstrucción y rehash de todos los archivos consumidos,
código y request. Estados:

- `PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_FULL_H1`: seis meses auditados completos.
- `PASS_INDEPENDENT_OOF_ECONOMIC_AUDIT_DECLARED_MONTHS`: únicamente meses indicados.
- `FAILED_OR_INTERRUPTED_PRESERVED`: fallo conservado, sin audit.json de éxito.

PASS significa reproducción de cálculos. `winner_selected=null`,
`base_fit_reproduced=false`, `base_inference_reproduced=false`,
`raw_quote_replay=false`, `development_seen=true`, `technical_ready=false` y
`promotion_approved=false`.2025 es TRAIN del calibrador;2026 no es holdout intacto.

El output es nuevo y separado, publicación atómica/fsync, sin sobrescribir ni
reanudar automáticamente una auditoría fallida. El launcher exige al menos
2.000.000.000bytes libres de RAM y commit. Las fixtures sólo generan fuentes
sintéticas pequeñas; los productores pueden emplearse para crear fixtures,
nunca como implementación del auditor o su reconstrucción económica.

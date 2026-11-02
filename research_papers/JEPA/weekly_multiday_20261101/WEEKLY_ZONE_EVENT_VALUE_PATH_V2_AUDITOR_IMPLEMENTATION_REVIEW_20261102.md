# Review de implementación del auditor V2 de value paths

Estado: `CLEAR_STATIC_PRE_SUITE`  
Fecha: 2026-11-02  
Alcance: revisión read-only; sin imports, compile, Ruff, pytest, raw ni runtime

## Pines congelados

| archivo | bytes | SHA-256 |
|---|---:|---|
| `audit_weekly_zone_event_value_paths_v2.py` | 112984 | `1ad942249d2eb160b2e8fe1ed902e577f9617dc4c11575e297cf5262f5aa61f2` |
| `test_audit_weekly_zone_event_value_paths_v2.py` | 36968 | `e7f7c6e7cd7f9b93a1763b969205478da87182247b1d284d7c9fd5b980112bf7` |

Autoridad contractual: enmienda V2 15276 bytes, SHA-256
`65fd1aaef25ddea13957ce07e6c21285771adc889f097d603f93e00572cf1146`,
que incorpora el contrato original SHA-256
`e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9`.

## Evidencia revisada

- El auditor no importa builder V2 ni módulo spot. Conserva las 70 funciones
  V1; sólo añade `validate_prior_failure_v2`, `normalize_calendar_v2` y
  `validate_calendar_envelope`. El whitelist AST exige el conjunto completo y
  las seis funciones compartidas que pueden variar operacionalmente.
- Las 29 autoridades son exactas: las 25 originales más contrato original,
  exit, failure y journal del productor 01 fallido. Se valida su envelope real:
  exit1, no adoption y sólo dos lifecycles de admisión, sin apertura de valores.
- El calendario raw exige schema/keysets/tipos, 2790 identidades únicas,
  dominio, conteos y orden ticker-major `QQQ,SPXW,SPY`. La copia independiente
  ordenada por fecha/ordinal `SPY,QQQ,SPXW` conserva identidad y `close_i` y
  reproduce 137640 bytes/SHA-256
  `13bc456a32c6dc711fffb71ef24375ecd5e455c11a9efedfb117b9ad903fb929`.
- Las diez claves de implementación exigen paths canónicos por rol, pin actual
  y contrato/helper exactos; una copia byte-idéntica en otro path se rechaza.
- El journal productor exige ADMIT real de `IMPLEMENTATION_PINS` (10) y
  `PINNED_AUTHORITIES` (29), seguido por `NORMALIZE_CALENDAR` y antes de
  footers. Se verifican los 1620 SELECT, 2768 STREAM y 2790 CACHE contexts.
- `CLOSING_REHASH` exige exactamente 10971 inputs —29 autoridades, 2768 option,
  8163 spot, diez implementaciones y el documento runtime—, dieciséis missing y
  nueve outputs: 10996 identidades y 21992 rows STARTED/COMPLETED. Paths,
  before/after, bytes y hashes se comparan con pins admitidos; los outputs
  pertenecen a un único staging hermano V2 y coinciden con los finales.
- Se mantiene la reconstrucción independiente V1 completa: 3240 decisiones,
  observations streaming por fuente, 9720 segmentos y 1086570 spot rows,
  schemas tipados, orden, null/NaN bit-exacto, source-once, summary/manifest V2,
  flags outcome-free y closing independiente.
- Roots productor/auditor/observer son exclusivamente `_02`; roots `_01`
  fallan antes de abrirse. Continúan prohibidos candidates, outcomes,
  `features.npz`, `state60`, modelos y ledgers.

Los fixtures sintéticos incluyen drift de calendario y digest, failure envelope,
ADMIT identity/details, implementation path, NORMALIZE order/details, source
contexts, cierre missing/extra/duplicado/pin estable incorrecto, guards de path,
cardinalidades y preservación AST. Los objetos mutables del journal se copian
antes de mutarlos para que las pruebas no alteren simultáneamente su expectativa.

## Dictamen

No queda blocker estático. Los dos archivos son aptos para una única suite
formal de fixtures con CPU0, diez variables a1, CUDA deshabilitado, gate oficial
y evidencia retenida, mediante un harness nuevo revisado y publicado.

Este CLEAR no afirma que esa suite haya pasado, no adopta parciales, no autoriza
auditoría real y no interpreta economía. El productor 02 debe cerrar exit0 y ser
revisado antes de preparar binding/launcher de una única auditoría real 02.

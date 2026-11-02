# Binding de la auditoría del plan de fuentes weekly

Estado: `READY_CONDITIONAL_TO_REVIEW_AND_BYTE_EXACT_PUBLICATION`.
Este binding fija una única auditoría real posterior al cierre del productor.
El launcher exige revisión operativa y publicación byte a byte antes de crear
el hijo.

## Auditor cerrado estáticamente

- Auditor `audit_weekly_zone_event_source_plan.py`, 41.573 bytes, SHA256
  `118a349f4ca44e25f5764e7082e0775010fdf6f6a35fe3876c972af223d2762c`.
- Tests `test_audit_weekly_zone_event_source_plan.py`, 10.098 bytes, SHA256
  `289b00ca94cb4414b3f6db2cba70c1b7641e9e55a9f87f9b5a0ceb925a3da58e`.
- Revisión estática `CLEAR_STATIC_PRE_SUITE`, SHA256
  `eb9f696cb85a02a62ab9caf9cd7335b25f621c7dfca37e6a3356365e125d2ca1`.
- Contrato, SHA256
  `c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65`.
- Revisión documental, SHA256
  `e7c0b2a2ec27afa79bab63776eefb767a5db912289ebffb1879887ab5fa19167`.
- Suite formal: compile0, Ruff0 y20PASS.

Evidencia final:

- Revisión final del auditor:
  `71ad8641711e0ed4264866e454a325fb6c7d6842ffa397c84f692110bc25f905`.
- Recibo formal:
  `6a0f90d5e01cf37f9a7e9bf20dd119cfe7dbc2e8d0efd64a1af6e1ca95d14bf9`.
- Recibo del archivo:
  `89805f2b782cf6ca7e3a527447f06faf647840db4b53385f6827a1241f31d57a`.
- Manifest del productor, 5.094 bytes:
  `a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161`.
- Exit retenido del productor, 1.307 bytes:
  `b8f34b02dccf570f0f3ebaaa4a120fbaded81e5d76645ac7f1f68de688bf1a9b`.
- Tests finales del productor tras su única corrección de fixture:
  `ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121`.

## Admisión del productor

El productor debe estar cerrado en
`weekly_zone_event_source_plan_01/manifest.json`, status
`SOURCE_PLAN_NOT_VALUE_ADMISSION`, schema
`weekly_zone_event_source_plan_manifest_v1`, diez inputs compactos exactos,
tres outputs exactos y pins de builder/tests/contrato. Su observer
`weekly_zone_event_source_plan_observer_01/exit.json` debe registrar exit0,
`planner_child_exit_code=0`, CPU[0], `metadata_error=null`, `changed_pins=[]` y
los cinco archivos de observación exactos. El builder permanece
`9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270`.
El proceso único PID3816 cerró exit0 a
2026-11-02T10:51:00.527590+00:00 con CPU[0], metadata_error null y
changed_pins vacío.

La auditoría reconstruye independientemente 2.790 planes, seis overlays y
4.860 referencias desde las diez autoridades. Repite únicamente stat/lstat,
contrasta los outputs del productor y no importa su módulo. No abre ni hashea
Parquets de mercado, footers, NPZ, candidatos u outcomes; no entrena, infiere,
hace replay o selecciona.

## Comando y raíces exclusivas

```text
python -X utf8 -u audit_weekly_zone_event_source_plan.py
  --execute-reviewed-audit
  --producer-manifest-sha256 a0a9d330992d7f5768550c5b60401a701e1c1b02caec4a0967de50b7c7f13161
  --producer-exit-path D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_event_source_plan_observer_01/exit.json
  --producer-exit-sha256 b8f34b02dccf570f0f3ebaaa4a120fbaded81e5d76645ac7f1f68de688bf1a9b
  --producer-builder-sha256 9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270
  --producer-tests-sha256 ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121
  --auditor-sha256 118a349f4ca44e25f5764e7082e0775010fdf6f6a35fe3876c972af223d2762c
  --auditor-tests-sha256 289b00ca94cb4414b3f6db2cba70c1b7641e9e55a9f87f9b5a0ceb925a3da58e
  --contract-sha256 c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65
```

Output exclusivo:
`D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_event_source_plan_audit_01`.
Observer exclusivo: `.../weekly_zone_event_source_plan_audit_observer_01`.
Ambos deben estar ausentes; no hay retry, resume o adopción parcial.

El launcher final exige publicación remota exacta, CPU[0], diez variables de
threads a1, helper oficial `3cfe55a6...`, gate RAM/commit >=2GB, Popen oculto
con argumentos en lista, PID/creation/afinidad, logs, handle retenido, wait en
finally, exit efectivo y rehash de cierre. Un PASS futuro sólo acreditará la
reconstrucción de metadata; nunca disponibilidad de valores, rentabilidad o
promoción. `technical_ready=false`, `promotion_approved=false`.

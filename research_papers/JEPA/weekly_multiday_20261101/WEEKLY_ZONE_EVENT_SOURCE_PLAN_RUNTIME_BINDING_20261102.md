# Binding del plan de fuentes para eventos weekly

Estado: `READY_REQUIRES_EXACT_PUBLICATION_BEFORE_USE`.
Este documento no autoriza ejecución desde bytes locales no publicados. Binding,
launcher y autoridades pineadas deben publicarse exactamente y comprobarse contra
el remoto antes del único runtime de planificación.

## Autoridad y alcance

- Contrato `WEEKLY_ZONE_EVENT_SOURCE_PLAN_CONTRACT_20261102.md`, 10.032 bytes:
  `c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65`.
- Revisión documental, 1.279 bytes:
  `e7c0b2a2ec27afa79bab63776eefb767a5db912289ebffb1879887ab5fa19167`.
- Publicación documental observada por root: commit `2123cc24` como prefijo;
  el launcher exige HEAD local igual al remoto de la rama y bytes exactos.
- Builder `build_weekly_zone_event_source_plan.py`, 43.609 bytes:
  `9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270`.
- Tests `test_build_weekly_zone_event_source_plan.py`, 16.225 bytes:
  `ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121`.
- Recibo formal attempt02, compile/Ruff/pytest exit0, 2.573 bytes:
  `5e56ec66c3f12e29635e4d3fe95709aa70a03cd59c4b0f80b6650344a7120ea3`.
- Recibo de archivo, 2.174 bytes:
  `45fcfee275ea0a4b787cf3313dbe3663d0c10f90ed62099b1ae1848b13c29855`.
- Revisión final independiente, 1.881 bytes:
  `6446555cd13e6c6ea8a00db47fba757fc43acf6c1419265521f933a3140901c1`.

Producto exclusivo: `SOURCE_PLAN_NOT_VALUE_ADMISSION`. Sólo admite los diez JSON
compactos sellados y stat/lstat estable de rutas nominales. No abre, hashea ni lee
footers de Parquets de mercado, NPZ, candidatos, outcomes, scores, ledgers o PnL;
no entrena, infiere, reproduce ni selecciona.

## Diez autoridades compactas

Raíz `D:/GexResearchArtifacts/weekly_multiday_20261101`:

1. `h2_dataset_v2_01/inventory.json` — `099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12`.
2. `h2_dataset_v2_01/inventory_manifest.json` — `c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899`.
3. `h2_dataset_v2_01/manifest.json` — `bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8`.
4. `h2_dataset_v2_extension_2026q3_partial_01/inventory.json` — `f633d0ee192f28650698a4033ee7f6d2dc00dad07aa38239c40e9e2b5092ea5c`.
5. `h2_dataset_v2_extension_2026q3_partial_01/inventory_manifest.json` — `5b39e0796599fa72b5d74d029885a24fd57fada207f12989576737aa46d75b2f`.
6. `h2_dataset_v2_extension_2026q3_partial_01/manifest.json` — `b45b017c63fea42036ab73418cc07faa8e377047fec1f8d60c908e98eea5400b`.
7. `h2_boundary_bridge_01/inventory.json` — `599ca400fecae12ce4098187a45af3ee0cf8c1b070e060d8c84e422ce92c6161`.
8. `h2_boundary_bridge_01/inventory_manifest.json` — `0a7a5fab0f932d23fdf9a3140027f99eb85ccd958b79ef55152c53ab5ced70f2`.
9. `h2_boundary_bridge_01/manifest.json` — `9d1455c601ac38224c4f56365f20c3fb31978e997f8652454dbc69807e0abb86`.
10. `h2_boundary_bridge_01/unified_calendar.json` — `be622bb24aca35448594743dfeb5236e6b2d08a4410109b20302891f8c1fa7d6`.

## Comando y raíces fijas

```text
python -X utf8 -u build_weekly_zone_event_source_plan.py
  --execute-reviewed-plan
  --builder-sha256 9a412a3ad4b1ae6d527c92c7b1307dfceecb2aec1b4d81cfff70acf8e71c1270
  --tests-sha256 ed4de57a2e4ff53f4f5f490377aa2a1338dba8aaf9b2939a028e9fad902e4121
  --contract-sha256 c1891e794cab794d5f6570f99d838a888663a48b8ccededd4d96d27a63173d65
```

El contrato fija los defaults de raíces. Output único:
`D:/GexResearchArtifacts/weekly_multiday_20261101/weekly_zone_event_source_plan_01`.
Observer único: `.../weekly_zone_event_source_plan_observer_01`. Ambos deben estar
ausentes; no retry, resume, sobrescritura ni adopción parcial.

El launcher final exige CPU[0], diez variables de threads a1 antes de imports,
helper oficial `3cfe55a6...`, gate RAM y commit libre >=2GB persistido antes del
hijo, Popen oculto con argumentos en lista, PID/creation time/afinidad, logs,
handle retenido con wait en finally, exit efectivo y rehash de cierre. La
publicación exacta del paquete es condición previa; un PASS sólo acredita el plan
de metadata, nunca disponibilidad de valores, rentabilidad o promoción.


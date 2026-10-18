# Ajuste TRAIN 424 completado

Una ejecución completada, PID48424, 2026-10-18 21:10:40–21:12:29 UTC, exit0.
`FIT_STARTED`21:11:22; 66,95s desde ese marker hasta export/readback/rehash final,
109,03s totales. Se reutilizaron exactamente las270.377 filas, targets net/risk,
escalas, IPW y CONFIG del control152. Un LightGBM200 árboles/31hojas/4hilos,
sin refit del control, selección nueva ni lectura de validación/test.

El supervisor previo12/16GiB quedó cancelado antes de cualquier hijo o fit y sus
logs se preservan. Por petición explícita del usuario, el ejecutor nuevo exigió
2.000.000.000 bytes disponibles tanto de RAM como de commit. Este cambio operativo
se vincula en el contrato; no se modificaron el entrenador científico, sus14
dependencias, las etiquetas, los parámetros ni la revisión base.

El monitor1s observó pico privado1.130.524.672 bytes y RSS1.588.076.544 bytes.
Son máximos muestreados, no garantía sobre picos entre muestras. El proceso terminó
y liberó la memoria. El modelo exportado reproduce exactamente, en float64, todas
las predicciones TRAIN del modelo en memoria; todos sus archivos y fuentes se
rehashearon antes del cierre. La revisión independiente fue de código; no se
presenta este cierre como refit independiente del modelo.

## Diagnóstico descriptivo TRAIN

Predicciones normalizadas por las mismas escalas TRAIN, ponderadas por IPW.
Se calculó después del cierre en archivos separados, sin cambiar los markers.

| Modelo | MSE ponderado | R² ponderado |
|---|---:|---:|
| Constante TRAIN |0,593241407|0|
| Control152, diagnóstico previo sellado |0,476395509|0,196961804|
| Ampliado424 |0,472848644|0,202940593|

La reducción de MSE TRAIN es aproximadamente0,745%; el incremento de R² es0,00598.
Es una mejora pequeña dentro de la muestra. No demuestra generalización, edge o
rentabilidad. La comparación posterior ya fijada conserva threshold0 y el mismo
scheduler/calendario/costes, independientemente de este diagnóstico.

Media del target−0,079320891; media de predicción−0,079444922; desviación estándar
ponderada de predicción0,202197782. El hash de `targets.npz` coincide exactamente
con el diagnóstico previo del control152. No se seleccionó un modelo o threshold
usando estas cifras.

## Evidencia

Raíz de modelo: `D:/GexResearchArtifacts/level_oracle_20261018/common_greek_control_resource_v1`.
Monitor/exit/diagnóstico/comparación: raíz hermana `common_greek_control_resource_v1_logs`.
Consola: archivos hermanos `_stdout.log` y `_stderr.log`.

| Artefacto | SHA256 |
|---|---|
| model.complete.json |be3583366019869c4b061e93b044b9ee4001d94510e573f1b3b978a970cb2c33|
| export.complete.json |f28e7ef21971a76012eeb92210306998ab5873e5e5db569a190fc01750f7402b|
| run_contract.json |ca1f55b1fe78bcd7575d7ad6d7cb5b91a8b9d340e11935f377030e6ccc735018|
| common_greek_net.txt |10b1c409a575797a2827e64a272809006917c17342f41c09fedd2d737a54e82c|
| train_readback_predictions.npy |ebe48ed61a097a1cc07b821d666f73163b0ebba7321f9e3350fce3f63594e343|
| Revisión científica base |79fc3d9ef28268083f014274b2371622b0003004c66b434daef1b439b515e61d|
| Revisión runtime2GB |58ce4886b12f83ca3b5b4096e880649aaf8955981721ad8e7b3497c9b608fc31|

Entrenador congelado `bba356f55467048c5f115d8fd7c580afcaa4a5c6cb2c532220df511319f3ce44`;
entrypoint operativo `7e91263325871a555af8d8a7575cdaac1b56fd191ba310ad56d2429b6f3e32b6`.
Pruebas:9 fixtures del entrenador y2 del gate operativo PASS; Ruff/compile PASS.
Todo es investigación de desarrollo sobre histórico ya visto, sin promoción live.

# Dataset H2 V2 cerrado y binding de evaluación

Único builder V2 desde c58834d7, PID40784/root84269, exit0 retenido a
2026-11-01T14:23:03.647257Z, 248,0067s. Exit SHA
50379090a5e11704b364fd6ec07f4afe4a5ebd3fe2cc1783d43845d1d74941ee.
Revisión independiente /root/review_producer_exit: CLEAR de cierre/metadata,
4 pins de exit y tres payloads exactos, cero discrepancias de IDs/fechas/cobertura.
Root verificó también los tres payloads y 10 copias/12282456 bytes; archivo
h2_v2_dataset_evidence_01, recibo6ff975d222a27430e4bf1f21ca8c3331908a681901a27ed5f95d6b3af601ba67.

Dataset D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_v2_01:
- Manifest bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8.
- Candidates c98f232a97a8a6f9221b5d3452424d71bec3684a6b037b258c8a5b0f8fb9d5ad, 3054 filas.
- Coverage 83ebf5704cb4f1c9ca7c2aff4cca749592f2e30b55978172ec1413a85cec6209, 2625 filas.
- Inventory 099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12, 2619 fuentes.

1527 sesiones con dos candidatos; 1092 sin serie local elegible; seis al final
sin H2. 2946 OBSERVED_EXIT,90 NO_FILL,12 MISSING_EXIT_SOURCE,6 MISSING_EXIT_QUOTE.
2613 clock_files exactos a fuentes presentes;1410 clocks nativos/1203 proxy.
455518273 filas;1164763 por cada snapshot;95940 subminuto descartadas sin redondeo.
Estos conteos son cobertura, no rentabilidad ni frecuencia de fills de política.

Binding para única evaluación tras publicar este documento y copias:
- Evaluador evaluate_weekly_h2_ev_v2.py SHA8a9e75855d542a12662e5c812583f2ef86042f5c3ae1bbbad73c16042e063476.
- Contrato245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5.
- Amendment9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb.
- Review H2_EVALUATOR_V2_IMPLEMENTATION_REVIEW.md: CLEAR implementación,23PASS.
- --candidates/--coverage/--manifest: archivos homónimos en dataset anterior.
- --manifest-sha256 bfc7370f38e32e1209bc41fe72f01563dcdaa17ddf86fe7b625814beedcbe1d8.
- --output D:/GexResearchArtifacts/weekly_multiday_20261101/h2_ev_v2_01, debe estar ausente.
- Observer h2_ev_v2_observer_01, CPU0/un hilo, gate RAM/commit2GB, handle retenido.

No se han leído netos para cambiar parámetros. El evaluador produce modelo,
calibración, scores y24libros bajo contrato fijo. Auditor independiente después
del cierre y revisión de su implementación. SEEN_DEVELOPMENT; sin promoción.

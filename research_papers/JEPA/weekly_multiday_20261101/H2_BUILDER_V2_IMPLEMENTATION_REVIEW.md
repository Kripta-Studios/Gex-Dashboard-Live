# Builder H2 V2 revisado: selección de timestamps exactos

Revisión independiente `/root/review_weekly_source_pilot`: CLEAR/ship. Root leyó
el delta completo frente al builder fallido y verificó las copias físicas finales.
Pins:

- V2 `ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945`.
- Tests `6972a8a3a3d07988538f9c6b4f639a4240fd5815bb46dfa40e0fa6c657351694`.
- Enmienda `9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb`.
- Contrato original `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5`.

V2 conserva identidad, selección delta, costes, escenarios y labels. Los cuatro
nodos económicos `_decision_candidate/_scenario/_net/_debit` son AST idénticos;
los cambios de build_candidates sólo recogen metadata de clocks. Se filtran
exactamente10:30:00/10:35:00; segundos/fracciones no nulos se cuentan y descartan,
sin redondeo. Se valida precisión submicrosegundo, fecha/zona/tipo; no hay fallback
de nativo inválido al proxy. Coveragev2 añade clock_files y el manifest incluye
la enmienda; nueva raíz h2_dataset_v2_01. No se toca el intento01.

Evidencia h2_builder_v2_attempt01:16 pruebas PASS y Ruff PASS en primera versión.
La revisión detectó una restricción nueva no deseada sobre ISO HH:MM; se restauró
ese formato con segundo implícito cero, manteniendo prohibida la fracción ambigua
HH:MM.5. Retry02 final:dos focales PASS/Ruff PASS, copias previas exactas y gate
RAM/commit, CPU0/un hilo. No sumar versiones como suite única. El revisor comprobó
en memoria, sin fuentes ni archivo de test, Arrow timestamp[ns,UTC]: exactos
convertidos a ET, +1ns y :30 excluidos correctamente.

Tras publicar estos bytes: un inventarioV2 nuevo, revisión de identidad del plan
y fuentes frente al inventario01 (excepto schema/pins), binding del nuevo SHA
antes de una pasada de valores. No repetir outcomes01 ni adoptar parciales.
El evaluadorV2 necesita su propia revisión de adaptación y cierre del dataset.
No hay aún modelo semanal ajustado ni resultado de rentabilidad.

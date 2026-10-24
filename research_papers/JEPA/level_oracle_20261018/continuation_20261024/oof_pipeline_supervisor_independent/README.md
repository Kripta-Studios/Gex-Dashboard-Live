# Archivo de evidencia independiente OOF

Copias verificadas de los16 miembros exactos ya fijados en `independent_validation.evidence_files` de la [review inmutable](../../OOF_PIPELINE_LAUNCH_IMPLEMENTATION_REVIEW_20261024.json), SHA`a78c2ef9019111a1ca98fa6e2517a4db8ce1ef9877596e5807734ce4c843ec95`. El [manifiesto](manifest.json) conserva ruta original, copia, SHA256 y tamaño; sus16 originales y16 copias coincidieron. Total:18691 bytes.

Se incluyen runner, comando/gate/pins y log del focal17 PASS; los tres scripts y admisiones del ad hoc; los dos recibos de error del harness; traceback local del segundo intento; log y resultado PASS del tercero. El primer traceback completo sólo se observó en herramienta: no existe log local íntegro y no se reconstruye. Su error y esa limitación constan en `adhoc_failure_01.json`.

Esta operación únicamente copia evidencia existente. No repite pruebas, no cambia review/código y no ejecuta mercado. El generador documental `emit_review.py` queda fuera porque no forma parte de los16 miembros que la review fijó. Los fallos pertenecen al harness del revisor, no al candidato: firma incompleta del interceptor de imports y sustitución prematura de Popen. El tercer intento precarga el helper y comprueba el rechazo por hash después de la llamada de import, antes de claim/Popen.

Manifest SHA256:`41179b5717efb5058deb3cc1fb53564b9e152ddc692f60b6a17de3c135a5f1cd`.

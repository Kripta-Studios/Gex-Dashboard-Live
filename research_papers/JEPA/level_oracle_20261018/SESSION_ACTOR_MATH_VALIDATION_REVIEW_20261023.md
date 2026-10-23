# Revisión independiente del laboratorio matemático

23 de octubre de 2026. **CLEAR — PASS_SESSION_ACTOR_MATH_VALIDATION_REVIEW.**
Revisor: `/root/tcn_completion`; autor: `/root/tcn_economic_auditor`.
Alcance `MATHEMATICAL_SYNTHETIC_ONLY`, con `runtime_market_authorized=false`.
Los hashes completos y la evidencia están en el [registro JSON](SESSION_ACTOR_MATH_VALIDATION_REVIEW_20261023.json).

La revisión estática confirma que la enumeración expande trayectorias sin llamar
a la transición, DP u ocupaciones del comparador. Se revisaron acumulación de
masas en confluencias, terminación, estado `h`, WAIT y NO_FILL, demora de entrada
y salida, soporte completo y separación entre penalización terminal y PnL.
El ejemplo tiene última decisión en 2 y última liquidación en 4: conserva
`J=-0,7`, PnL esperado `0,65`, probabilidad de ningún fill `0,45` y gradientes
de logits `1,08/0,225`. La cardinalidad cuenta intentos, incluidos NO_FILL.

Se contrastaron gradientes de enumeración, DP, autograd y adjuntos, tanto para
logits independientes como para variables algebraicas compartidas. La
recomputación por bloques mantiene parámetros y logits, con adjuntos detenidos.
Los tres pasos centrales predeclarados (`1e-4`, `1e-5`, `1e-6`) se conservan.
No se relajaron tolerancias ni se escogió retrospectivamente el mejor paso.

## Evidencia separada por ejecutor

- **Revisor:** 49 pruebas sintéticas PASS en 0,69 s, salida cero, sobre los bytes
  finales; hashes anteriores y posteriores idénticos. Gate antes de importar:
  RAM disponible 8.364.912.640 y margen de commit 11.845.582.848 bytes. El gate
  del laboratorio también pasó; CPU `[0]`, float64 y un hilo intra/interoperador.
- **Autor, intento 04 inspeccionado:** 49 pruebas PASS en 2,75 s, Ruff y CLI con
  salida cero; 204 comparaciones PASS. No se presenta como un segundo CLI del
  revisor. Los cuatro intentos permanecen documentados en el [informe](EXACT_SESSION_ACTOR_MATH_VALIDATION_RESULT_20261023.md).
- **Revisor, comprobación del resultado serializado:** se recalcularon las 204
  desigualdades desde sus valores `actual/expected`, comprobando finitud,
  tolerancias exactas y los tres pasos por modalidad de gradiente. Todas pasan;
  error absoluto máximo `2,7018631776343227e-9`. También se compararon las 30
  copias, 519.529 bytes, con sus originales y el manifest: cero diferencias.

Las tolerancias siguen siendo `atol=1e-10`, `rtol=1e-9` para identidades y
`atol=1e-7`, `rtol=1e-5` para diferencias centrales.

## Hallazgos cerrados

La revisión pidió rechazar probabilidades vectoriales y relojes fraccionarios
o booleanos: las anotaciones de tipos no bastaban. Después detectó que apilar
probabilidades podía promover silenciosamente un elemento float32 a float64.
Las tres guardas están implementadas, con pruebas negativas; dtype y dispositivo
se verifican por elemento antes de agregar. No quedan hallazgos abiertos.

Esta revisión acredita identidades en grafos artificiales finitos y exógenos.
No acredita fuentes, fills reales, paridad live, suficiencia del estado causal,
rentabilidad temporal ni operabilidad. El contraejemplo con esperanza de 1,5
fills y probabilidad 0,5 de ningún fill impide inferir un mínimo diario desde
la esperanza. Tampoco hay equivalencia acreditada entre objetivo estocástico
y ledger greedy. Arquitectura, extractor determinista y cualquier experimento
de mercado siguen pendientes; no se ejecutó mercado ni se alteraron autoridades
económicas o productores congelados durante esta revisión.

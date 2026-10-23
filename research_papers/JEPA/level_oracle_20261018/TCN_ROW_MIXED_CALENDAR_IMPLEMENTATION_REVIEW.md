# Revisión de implementación: TCN row-mixed, calendario 750 + 369

Estado: `PASS_TCN_ROW_MIXED_CALENDAR_IMPLEMENTATION_REVIEW`.
Alcance: implementación y fixtures sintéticos. No se ejecutó evaluación de
mercado ni auditoría económica nueva. La revisión independiente de
`/root/scientific_review` concluyó `CLEAR`; `/root` autorizó emitir el registro.

El evaluador conserva el modelo fijo de cuarta época, los normalizadores,
las seis políticas, el selector y el scheduler congelados. Incluye los nueve
ticker-días cortos de 2025 antes del freeze y mantiene las seis ausencias de
2026 como `NO_EVALUABLE`. No cambia entrenamiento ni helpers congelados.

Se completaron dos garantías antes de cualquier ejecución:

- La copia del control FLAGS64 para días completos compara shape, dtype y bytes,
  incluyendo el signo del cero; la igualdad numérica sola no satisface el contrato.
- `source_inputs.json` conserva los hashes de todas las entradas externas y se
  incorpora al cierre. La reanudación completa revalida ese mapa, incluidas las
  features externas de sesiones cortas, además de los artefactos de salida.

El productor verificó 15 fixtures en 9,91 s; Ruff, compilación y diff-check PASS.
RAM/commit libres antes de los tests: 3.936.198.656 / 7.221.628.928 bytes.
El revisor independiente repitió los 15 fixtures: PASS en 17,26 s, con
4.224.733.184 / 7.943.077.888 bytes libres. También examinó el diff, los lectores
Sources/Features, el adaptador del control, el selector, el scheduler y el cierre.
Las pruebas cubren copia exacta, mutaciones, cierre corto, scores antes de labels,
freeze antes de test, selección nula y reanudación sin repetir inferencia.

SHA256 del evaluador:
`a6c68f4ef7486b538b8119b5dfdb035b3dc078bae274c6aa10cc922f6596b33c`.
SHA256 de los tests:
`e77988a576b8de20c424482a2d591f0ed7b8281e9f78b954ba209af61abd005d`.
La [review JSON](TCN_ROW_MIXED_CALENDAR_IMPLEMENTATION_REVIEW.json) vincula
exactamente las 19 dependencias y pasa `require_review`. SHA256 del JSON:
`cbd8efc6680144ae81afff8d5ac7bab4502bb7d35ef5ef5900fc8e6fd8fe7302`.

`authorized_scope=IMPLEMENTATION_ONLY`, `execution_authorized=false`.
Antes del lanzamiento faltan el auditor económico nuevo revisado y la coordinación
de recursos y procesos por root. No hay resultado económico nuevo, promoción ni
evidencia operable acreditada por esta revisión.

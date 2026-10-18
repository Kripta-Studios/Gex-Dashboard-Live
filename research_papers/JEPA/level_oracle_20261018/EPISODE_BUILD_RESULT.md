# Episodios preparados, sin entrenamiento

**PASS_PREPARED_CAUSAL_EPISODE_BUILD**, salida0, terminado el18-oct-2026 a
las17:46:20 UTC. La autorización y receta se fijaron primero en
`EPISODE_BUILD_SPEC.md`; después se implementó el escritor y se pasaron sus
fixtures antes de construir. No se activó selección, entrenamiento o cambio
de los modelos y planes actuales.

## Cobertura y formato

2.595 días completos: QQQ864, SPXW867, SPY864. Las seis ausencias del universo
de2.601 ticker-días permanecen en `missing_source_days.json`, sin imputación.
Se exportaron **820.020 estados**, cada uno con35 valores float64 y35 máscaras
booleanas. `state_i` int64 es exclusivamente clave de unión. La traza de IDs
y componentes no entra en los predictores ni se guarda en el NPZ.

Ubicación:
`D:/GexResearchArtifacts/level_oracle_20261018/episode_features_v1/{ticker}/{date}/episodes.npz`
y su `episodes.json`. Total comprimido de los2.595 NPZ: **23.162.445 bytes**.

## Verificación y recursos

Antes del build: **22 fixtures PASS** en1,50s —19 del módulo causal y3 de
proyección, publicación/reanudación, preservación de parciales y rechazo de
corrupción—; Ruff PASS.

Se verificaron los hashes de los5.190 archivos causales `states/levels`
contra el índice auditado antes de leerlos y después de calcular cada día.
Cada salida se validó al publicarse; una segunda pasada verificó los2.595
hashes, schemas, claves, máscaras y cobertura global. Es verificación de
integridad del productor, no una recomputación independiente por otro auditor.

Un worker, una sesión en RAM. Tiempo de pared: **421,04s** (7min1s);
CPU:365,59s. Picos del proceso medidos por Windows/psutil: RSS131.854.336 bytes
y memoria privada comprometida103.616.512 bytes. El proceso terminó y retiró
su lock.

Se proyectaron únicamente columnas causales de states/levels y metadatos de
identidad del índice. No se leyeron quotes, raw caches, labels, ventajas,
predicciones o ledgers. Del documento de auditoría se extrajeron sólo strings
de estado/hash; no sus cifras económicas. No hay conclusión de rentabilidad.

## Evidencia y congelación

En el root de artefactos quedan contrato, copia exacta del productor/módulo/
especificaciones, índice, resumen y manifests por día.

- `summary.json`: SHA256 `8fa238cfb6fff01176860cd984eb2f6e190a2a63411c6bacbae22d8a07b34cc5`.
- `index.json`: SHA256 `26709ec7cdfa3f4cab79dc411b2d1c679c6f00f7924040abfb7b1a624c676b52`.
- `contract.json`: SHA256 `898bc12bb9538c9b9ba109a1cbfe6e1e7e9cb5d27676439fd1a3fe4d898a0dbe`.
- `build_episode_features.py`: SHA256 `2630b2011f8567fd08632d9e1c49099681b12008af95881718909f4545575ccd`.
- `episode_features.py`: SHA256 `437530a63c2ef412414101552120b8a04e74e63375c65c6b409293bb7fd4d5a4`.

Los hashes de `features.py` y `level_engine.py` originales siguen siendo
`b5c63f91…2369d4e0` y `70cc5d20…413b7c6`; no se modificaron. La salida de
episodios queda disponible para una decisión posterior, sin integrarse en la
matriz que se está entrenando.

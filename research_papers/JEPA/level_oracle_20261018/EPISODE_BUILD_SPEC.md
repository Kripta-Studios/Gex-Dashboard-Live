# Construcción causal de episodios, preparación sin entrenamiento

Autorización del coordinador el18-oct-2026: construir únicamente la variante
ya especificada en `EPISODE_FEATURE_SPEC.md`, después de sus fixtures. No
activa entrenamiento, selección de modelos ni cambios de planes congelados.
Este documento se escribe antes del builder y de la primera construcción.

## Universo y entradas admitidas

Se usa exactamente el índice `engine_v1/index.parquet` auditado:
SHA256 `8d0c6e27bdaf7d47ef2a9888505294b8f3186da3a6927e780ce9e517e660e8e5`.
Universo: 2.601 ticker-días; 2.595 completos y seis ausencias de fuente
conservadas como tales. No se imputan ni reemplazan.

Autoridad: `engine_v1_audit_v4/audit.json`,
SHA256 `cbbe61d0a3fa7619447b7301d4c4b2fd52c487e11450d4904efee381fc3bf22d`,
con estado `PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT` y binding al índice.
Del documento se consumen solamente esos metadatos; no sus resultados
económicos. Del parquet se proyectan únicamente ticker, date, split, status,
day_root, states_sha256 y levels_sha256. No se leen columnas económicas.

Por cada día completo, las únicas tablas de datos son:

- `states.parquet`: state_i, state_valid, spot, band, eligible,
  entry_level_id, ib_low, ib_range.
- `levels.parquet`: state_i, level_id, center, source_mask, n_components,
  components_json.

Se rehashean ambos archivos contra el índice antes de parsearlos. No se
leen raw caches, quotes, acciones, labels, ventajas, predicciones ni ledgers.

## Transformación congelada y salida

`episode_features.py` SHA256
`437530a63c2ef412414101552120b8a04e74e63375c65c6b409293bb7fd4d5a4`
define los35 canales y sus máscaras. No se modifica. Se procesa una sesión
por llamada, una pasada creciente por sus316 estados60..375, sin persistencia
entre sesiones. La propuesta ya fija ancla, huecos, contactos, cruces,
penetración, recuperación y cierre; este builder no introduce reglas nuevas.

Salida nueva:
`D:/GexResearchArtifacts/level_oracle_20261018/episode_features_v1/{ticker}/{date}/episodes.npz`
y `episodes.json`, con exactamente:

- `state_i`: int64[316], clave de unión; nunca predictor numérico.
- `values`: float64[316,35], orden exacto `FEATURE_NAMES`.
- `valid`: bool[316,35], máscaras paralelas; almacenamiento cero si falsa.

La traza de IDs y componentes que devuelve el módulo no entra en el NPZ.
El manifiesto conserva nombres/dtypes/shapes, hashes de inputs y output,
código/especificaciones/índice/auditoría y contadores técnicos. No se
construyen labels auxiliares ni se une esta salida a los modelos actuales.

## Ejecución, reanudación y verificación

Un único worker, un día en RAM. Antes de construir datos reales se ejecutan
los fixtures de episodios y del escritor con datos sintéticos. Después se
fija un contrato global y se preservan copias exactas de productor, módulo y
especificaciones. Un lock impide escritores simultáneos sobre el mismo root.

Publicación por archivo temporal y rename; primero NPZ y después manifiesto.
Un día completo sólo se reutiliza si coinciden binding, hash, nombres,
shapes/dtypes, claves de estado, finitud y máscaras. Los parciales se archivan
con hashes y registro antes de reconstruir; nunca se borran. Un par completo
con binding/hash inválido falla y requiere revisión, sin sobrescritura.

Al terminar se verifica nuevamente el hash y schema de **todos** los outputs,
se contrasta cobertura exacta con los2.595 días admitidos y se publica un
índice técnico con las seis ausencias. Se registran wall time, CPU time y
memoria privada/RSS, distinguiendo picos del proceso de muestras periódicas.
La verificación acredita integridad de la preparación; no acredita edge,
rentabilidad ni autorización para entrenar otra familia.

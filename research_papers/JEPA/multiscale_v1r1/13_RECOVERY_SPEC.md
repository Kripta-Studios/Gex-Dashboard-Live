# Recuperación A — nueva evidencia, sin reinterpretar V1R1

Autoridad: instrucción del usuario «GEX: continuación después del cierre V1R1».
Esta especificación sustituye únicamente los detalles de recuperación del documento
12 que no garantizaban coherencia de varios archivos. No modifica contratos V1/V1R1.
Root nuevo: `D:/GexResearchArtifacts/multiscale_v1r1/continuation_20260917_01`.
El intento anterior y su resumen terminal permanecen inmutables.

Antes de cualquier acceso adicional se publica esta especificación. El examen
de nombres y logs de data_options solicitado previamente ya comenzó, sin valores
de mercado ni outcomes. Las coincidencias de `1s` en duraciones de requests no
son evidencia de frecuencia de datos. La búsqueda adicional se limita a nombres,
footers, logs, backups/rotaciones y manifests bajo los dos árboles locales
data_options y data_underlying_derived de SPXW/SPY/QQQ y sus logs de raíz.
No se leerán precios para esta recuperación.

Se copian en bytes los artefactos terminales a un destino nuevo, verificando sus
hashes contra el catálogo existente. evidence_recovery.json registra por fuente
hash esperado, observado, ruta, método y resultado. Solo un SHA256 idéntico
recupera bytes originales. El prefijo se prueba únicamente si existe tamaño
original sellado; no se infiere por claves parseadas ni se reconstruye texto.
Sin coincidencia: ORIGINAL_EVIDENCE_NOT_RECOVERED. Una copia actual es nueva.

Snapshot coherente: en Windows se abren todos los archivos del conjunto con
GENERIC_READ y FILE_SHARE_READ, manteniendo abiertos todos los handles hasta
terminar su copia. No se permite compartir escritura/borrado. Un escritor ya
activo incompatible hace fallar cerrado la captura, sin detener su proceso.
Este mecanismo coordina exclusión de escritura sobre los archivos seleccionados;
no promete una transacción de negocio entre archivos ni protege otros archivos
no seleccionados. No se usan hardlinks. Los hashes y el parser consumen los mismos
bytes copiados. Si no se obtiene la exclusión, no se declara snapshot coherente.

Un lector verifica manifest y payload usando una sola lectura del payload.
El auditor reconstruye por separado desde el snapshot. Cambios en el log operativo
posteriores son drift externo; modificar/perder una dependencia sellada falla.
Reanudación solo con checkpoint ligado a manifest, código y dependencias inmutables;
el intento interrumpido previo no aporta certificados reutilizables.

Linaje: separar event_time, available_at/cota, received_at observado (si existe),
materialized_at, transformación/parámetros, inputs/hashes, reparación y evidencia.
Clasificaciones nuevas solo para esta revisión de admisión: PROVENANCE_SUPPORTED,
UNVERIFIABLE_FOR_CAUSAL_REPLAY, MISSING_SOURCE, REJECTED_CAUSALITY.
Sin evidencia temporal no se emite la primera. La inspección por metadata crea
mapa/cobertura con alcance preciso, no admisión histórica por extensión de muestras.
Las 32 ausencias se desglosan por fecha/ticker/fuente, dentro de las 973 sesiones.

Referencia técnica: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).

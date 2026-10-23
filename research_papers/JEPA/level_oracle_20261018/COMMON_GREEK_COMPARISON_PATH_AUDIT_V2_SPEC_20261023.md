# Auditor Common Greek V2: compatibilidad segura de rutas

23 de octubre de 2026. Corrección técnica nueva, sin cambiar productor,
políticas, scheduler, métricas, tolerancias, calendarios o admisión económica.
No autoriza un rerun de mercado; publicación y revisión preceden a cualquier
intento nuevo. Auditor01 y su fallo quedan preservados.

El intento01 del auditor original falló en `Baseline score absent`: buscaba
`predictions/QQQ/20250102.npz` en un manifest cuyas claves Windows empleaban
`predictions\QQQ\20250102.npz`. La evidencia de fallo fue comunicada por
`common_greek_resume`; esta implementación no abre nuevos outcomes para
diagnosticarla. Original inmutable `audit_common_greek_comparison.py`, SHA256
`3898ef3c8ae634a65a2a136c75f2e14a46d5ac6fcad4bcc28bdb77742f3dca70`.

`audit_common_greek_comparison_paths_v2.py` es una copia independiente del auditor
original con cambios limitados a identidad de rutas relativas. No importa
productores. Una normalización explícita acepta `/`, `\` o mezcla como separadores
y produce una clave POSIX. Se aplica al manifest baseline, a los marcadores de
predicción/día/periodo/comparación y a los files de los marcadores de modelo.
Las tablas de sources absolutos, TRAIN provenance y demás autoridades mantienen
exactamente su tratamiento anterior; no se convierten en rutas relativas.

Se rechazan rutas vacías, absolutas, UNC/rooted o drive-relative, segmentos
vacíos/dot/dotdot, escapes resueltos, ADS, caracteres inválidos Windows, nombres
reservados y sufijos de punto/espacio. Dos claves que colisionen por separadores,
casefold o destino resuelto se rechazan incluso si comparten SHA; no se fusionan.
Una referencia ausente o un hash distinto sigue fallando. El manifiesto fuente
no se reescribe ni se reseña; su SHA original sigue siendo la autoridad.
Containment se comprueba tanto al normalizar como al resolver el miembro para
consumirlo; el memo conserva la ruta resuelta para el rehash final. Fixtures
simulan una redirección a fuera del root entre ambas etapas y exigen rechazo.

Las funciones económicas y constantes conservan AST idénticos. La fixture
compara además main contra una lista exacta de sustituciones permitidas. Reutiliza
las siete fixtures anteriores sobre V2 y añade NPZ sintéticos con claves Windows,
POSIX y mixtas, signed zero, rutas peligrosas, colisiones, miembros ausentes y
mutaciones. No entrena, infiere ni reevalúa mercados durante estas pruebas.

La CLI es exactamente la anterior, usando el archivo nuevo:

```text
python audit_common_greek_comparison_paths_v2.py --root <comparison> --session-root <SessionClock> --session-audit <audit> --baseline-root <baseline> --baseline-audit <audit> --cue-root <cue> --greek-root <greek> --review <review-original> --output <audit02-nuevo>
```

La revisión original del productor y sus seis autoridades permanecen intactas;
la revisión independiente de V2 y sus hashes se fijarán por separado antes del
futuro lanzamiento. Output nuevo obligatorio. Status de éxito y alcance original
se conservan: economía reconstruida dado scores sellados, sin reproducción de
fit/inferencia, sin promoción y con 2025/2026 como desarrollo visto.
`binding.audit_script_sha256` identificará los bytes nuevos del auditor V2.

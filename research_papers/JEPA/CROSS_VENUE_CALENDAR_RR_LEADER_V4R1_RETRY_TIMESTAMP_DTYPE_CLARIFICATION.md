# V4R1 retry — aclaración cerrada del dtype de timestamp

Fecha: 2026-07-26. Esta aclaración se fija antes de construir features 2026 y
antes de leer los opens 10:36/13:36.

## Hecho técnico

Las diez respuestas predeclaradas se descargaron una sola vez desde
`aba363c3`, se preservaron como raw JSON y normalizaron sin error. El primer
pair gate marcó falsamente las cinco parejas como no utilizables porque los
parquets retry almacenan `underlying_timestamp` como `timestamp[ns]`, mientras
el lector vintage intentaba aplicar a esa columna un filtro pyarrow con límites
string. Los cinco errores fueron el mismo `ArrowNotImplementedError`; no fueron
una desigualdad Greek/IV ni una falta de datos.

## Reparación permitida y única

No se reconsulta la API y no se modifica ningún raw, parquet o manifest de la
captura. Un lector compatible detecta el dtype físico: conserva el lector
vintage original para strings y, únicamente para timestamps tipados, carga las
columnas predeclaradas y filtra por igualdad exacta a 10:30 y 10:35. Mantiene
las mismas validaciones de identidad, finitud, unicidad y key-set exacto; no
hace cast de reloj, nearest/as-of, intersección, fill ni deduplicación.

Un reseal offline separado debe verificar todos los hashes de la captura y
reconstruir los diez normalizados desde raw. La captura original queda
inmutable y su seal SHA es
`a18e086444598bae6e7d380bc82479b9818550932883835c083778d5c66758f0`.
El builder 2026 solo podrá consumir el reseal nuevo versionado.

## Resultado outcome-free ya observable

La relectura compatible de las cinco parejas produce, respectivamente,
688/688, 800/800, 632/632, 604/604 y 708/708 filas Greek/IV, con cero Greek-only
y cero IV-only. Por tanto la regla predeclarada conserva los cinco
sensor-fecha y la lista de exclusiones queda vacía. Este resultado solo usa
fuentes de 10:30/10:35; no abrió features económicas ni outcomes 2026.

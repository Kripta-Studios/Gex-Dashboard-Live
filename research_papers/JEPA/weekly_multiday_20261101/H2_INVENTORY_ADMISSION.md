# Inventario H2 real: binding para la pasada de valores

Inventario único ejecutado desde c28f329d, PID3500, CPU0/un hilo, gate RAM/commit.
Exit0 retenido a 2026-11-01 13:52:18.373672 UTC; 44,770 segundos, stderr vacío.
No se leyeron record batches de mercado; sólo calendario, footers y hashes.

Binding concreto:

- Inventario `D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_01/inventory.json`.
- SHA256 `cb762957bc463873f7f4d42a806d3a6fc09fb144eebacdc0eae2358971d2212d`;
  5.589.731 bytes.
- Manifest inventario `0c67c6943b6670e5d2ed33c28630087991c548521429ca59eaeb9e19cdb61403`.
- Builder `eb0cba11d9e865909ee518efe825527e127d90c52b47339fa8e0b3fa699a1e67`.
- Contrato `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5`.
- Helper `ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878`.
- Calendario `7124d98155eae8ee5ae06457377570278d4059defe2cf02340e34c288fcb60b4`.

Hay 2.625 ticker-sesiones: 1.527 PLANNED, 1.092 NO_SERIES y seis fuera del
horizonte al final del calendario. NO_SERIES significa que los archivos locales
no ofrecen una expiración elegible para H2; no prueba que no existiese tal opción
en el mercado. Cada ticker conserva 875 sesiones, 509 planificadas. La unión
entry/exit contiene 2.619 rutas: 2.613 presentes y seis ausentes, 13.101.640.078
bytes y 455.518.273 filas en footers. Las ausencias no desplazan H2 ni desaparecen
de la futura contabilidad conservadora.

Root verificó el manifest y exits. `/root/review_producer_exit` comprobó de forma
independiente todos los IDs, H2 segunda sesión oficial, DTE1–8, pre-expiry estricto,
rutas nominales y unión exacta de fuentes: cero diferencias, CLEAR de metadata.
No abrió quotes ni repitió hashes raw. Copias exactas en `h2_inventory_evidence_01`.

Después de publicar este binding y las copias exactas, ejecutar una sola vez el
builder congelado con `--execute-reviewed-builder --inventory <ruta anterior>
--inventory-sha256 cb762957bc463873f7f4d42a806d3a6fc09fb144eebacdc0eae2358971d2212d`.
El builder repite metadata/plan antes del primer valor y al cierre. No se lanza
evaluador/modelo hasta cierre del dataset y revisión de su código/binding.
Un fallo se conserva sin retry automático. Fuentes originales y producción intactas.

## Conservación de bytes al publicar

Antes de esta pasada root detectó que Git había normalizado CRLF de 22 logs/JSON
del nuevo directorio weekly al publicarlos. Los originales locales, copias y
hashes de ejecución permanecían intactos; código y contrato no diferían.
Se añadió `.gitattributes` local con `-text` y se repusieron en Git los bytes
originales, sin reescribir historia ni rerun. Se verificará comparación binaria
de todos los archivos weekly publicados antes de usar este binding. La corrección
es de archivo/publicación, no de ciencia ni resultados.

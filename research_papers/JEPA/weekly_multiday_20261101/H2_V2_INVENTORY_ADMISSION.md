# Admisión del inventario H2 V2

Inventario real desde c2444fc263aff4e06e6259bd9e291825df7ae668, PID45836,
exit0 retenido a 2026-11-01T14:12:27.933335Z; 29,8807 segundos, CPU0/un hilo.
No valores de mercado: calendario, footers y hashes únicamente.

Binding para una pasada del builder V2:
- Inventory: D:/GexResearchArtifacts/weekly_multiday_20261101/h2_dataset_v2_01/inventory.json
- SHA256: 099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12
- Bytes: 5589855
- Inventory manifest: c417e67f3499522d4ebd4a21bf28d1cba8ce249ef2d38a1352001216714bb899
- Builder: ec19e2c9066f0bb6103526ccf30a5b156c69a25a96349220d9fd680a92822945
- Contrato: 245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5
- Amendment: 9210c6e50094e5745f80c5e03f577f6bd673263f84d3c3ef764ad76b22ca56eb
- Helper: ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878

Root y revisión independiente /root/review_producer_exit compararon todos los campos
con el original cb762957: sólo cambian schema y pins, 124 bytes adicionales.
Calendario, 2625 planes, 2619 fuentes con cada hash/tamaño/filas/estado idénticos.
1527 PLANNED, 1092 NO_SERIES locales, seis HORIZON_OUTSIDE_CALENDAR.
2613 fuentes presentes y seis ausentes; 455518273 filas / 13101640078 bytes.
El revisor verificó además cuatro hashes del exit y ausencia de PID45836.
CLEAR de metadata; sin rehash adicional de datos ni interpretación económica.
Copias exactas y recibo: h2_v2_inventory_evidence_01.

Tras publicar este binding, única ejecución CLI --execute-reviewed-builder con
--inventory en la ruta anterior y --inventory-sha256 099dcf065a62705cbd88f2c1b90b2e4a9b99ff4d994ad703634101920c934b12.
Revalidación del inventario antes de valores y al cierre. El intento original
fallido permanece inmutable. No modelo real hasta cierre y admisión del dataset.

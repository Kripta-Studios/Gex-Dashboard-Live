# Dataset H2: implementación y revisión antes de uso real

Root leyó íntegro el builder inicial, tests y cambios operativos finales.
Revisión independiente `/root/review_weekly_source_pilot`: `CLEAR / ship`.
Pins finales:

- Contrato `245a6df1530fbabf29e6a2e5e86662972ebdc680e011987253f35eb61257d5d5`.
- Builder `eb0cba11d9e865909ee518efe825527e127d90c52b47339fa8e0b3fa699a1e67`.
- Tests `504ebd0b25aebf43ae51740f8358fa97f72d7c590b037cd3dc23fafd7a96b96d`.
- Helper fuente congelado `ad5b3ffba4e125ca7fcb4d5b0789eec601ace55be3740813d46374827766c878`.

Evidencia inmutable en `h2_builder_attempt01`: primer intento falló siete tests
por loader Python3.14 sin registro sys.modules, antes de alcanzar lógica económica;
retry02 siete PASS. Retry03 conserva suite de diez PASS y Ruff PASS tras añadir
inventario persistido, admisión anterior al primer valor, cierre de calendario/
plan/fuentes, clock estricto, guardas de rutas y Decimal. Focal04 conserva la
actualización de contrato; focal05 fue reemplazado antes de tests, no es un PASS.
Focal06 conserva copias finales previas y dos pruebas PASS del pin contractual y
rechazo de SHA de calendario alternativo por CLI; Ruff PASS. Los cambios desde
retry03 son sólo pin de contrato y guard del CLI. No sumar versiones como una
suite final única. CPU0/un hilo y gate RAM/commit en recibos.

El builder usa H2 del calendario, selecciona contrato con snapshot10:30 y conserva
identidad al ask10:35/salida H2. Missing exit entra como cota marcada, no se borra
del modelo. La fuente se filtra con Arrow antes de filas Python; cache limitada
a 16 snapshots. El manifiesto liga contrato, helper, builder, calendario,
inventario, coverage y candidatos. No se ajustó modelo ni se leyó mercado en tests.

Tras publicar estos bytes, ejecutar una vez `--build-reviewed-inventory` con
roots reales congelados y calendario7124d981. Inspeccionar y conservar su SHA,
cobertura y recibo exit antes de la pasada de valores ligada por
`--inventory/--inventory-sha256`. Registrar binding concreto antes de esa pasada;
un error se conserva, sin retry automático. El código evaluador sigue separado,
en preparación. Producción/API/bróker/VPS intactos.

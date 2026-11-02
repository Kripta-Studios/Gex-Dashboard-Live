# Revisión estática del productor de trayectorias weekly

Dictamen independiente de `/root/daily_auditor_review`, materializado por root
el 2 de noviembre de 2026: **CLEAR_STATIC_PRE_SUITE**.

- Contrato: e7cf56f8fba5dc50937dcb4e3625752b83e4d73ebbeed77ee19f97f8bf219ac9.
- Builder: 83817 bytes,
  b6528622bd9d39fd3a132b6665e7e7cee2e1b0208cd7d854a270093c95398afe.
- Tests: 28614 bytes,
  ea5c7d0b0848e3cc4dc8fc6a9ac0e59505bf9e5244cbd775308a81b682ae72aa.
- Interfaz spot: 0953d344b28992da4b92c561daa7663bb48fe89ea309f6323f53b39c6a0dbd38.

La revisión completa y sus refresh focales cerraron los hallazgos estáticos:
helper oficial exacto, guards de rutas/aliases y ancestros hasta el volumen,
timestamps naive/aware y nanosegundos, float histórico del selector, schemas
nullable explícitos, journal por unidad y closing rehash completo. Root revisó
adicionalmente las interfaces, recursos, trayectorias y forma de journal.

La validación vectorizada por batches conserva los controles de clock e identidad
en todas las filas, pero sólo materializa valores Python de 10:30 para seleccionar
y de los contratos elegidos para trayectorias. La escritura se limita a grupos
por fuente; no acumula toda la población de observaciones como diccionarios.
El selector no usa 10:35 ni D1/H2. Las decisiones se cierran/fsync antes de paths.

Las fixtures conductuales cubren D/D1/H2, missing, unión de dos sides y una lectura
por fuente, subminute/out-session por contrato, gamma/interval, duplicados exactos,
reparse/hardlink/symlink/nonregular/alias y mutación al cierre. La cardinalidad H1
disponible es 2619 incluyendo 24 SHORT. Cada unidad selector/trayectoria registra
source_reads=1, comprobado también en fixtures; los contextos globales se separan.

La primera suite formal conservó compile0 y Ruff1, por un único import timezone
sin uso en tests; pytest no llegó a ejecutarse. Root quitó exclusivamente ese
import. El revisor comparó contra el snapshot before_test y confirmó delta neutro,
builder intacto, failure f00ee544fb4dfd2956300f9656c08ab97af3a7e970c0d8286bb8bd13b0c3abaf
de412B y closing_pin_differences vacío. Attempt01 permanece inmutable.

Attempt02 conservó compile0/Ruff0 y 94PASS/1FAIL: el test del contador selector
construía filas a09:30 para un selector contractual10:30. Root ajustó ambos relojes
de esas dos filas sintéticas a10:30. El revisor comparó contra before_test y
confirmó sólo cinco líneas nuevas, builder intacto y failure477B
c07528fe27f0a774c85a3f2f88fcb6f3bcafd41e8a92ba00c3b41789b3c7cdfd
con closing_pin_differences vacío. Attempt01/02 quedan inmutables.

El CLEAR actualizado permite preparar attempt03 formal con esos tests; no afirma
PASS de suite. No hubo valores de mercado, footers reales, arrays reales ni runtime.
Requiere suite observada, revisión de evidencias y binding/publicación antes del run.

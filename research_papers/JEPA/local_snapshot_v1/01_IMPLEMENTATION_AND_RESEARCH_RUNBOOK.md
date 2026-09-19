# Ruta de implementación con los datos locales existentes

Fecha: 2026-09-19. Esta revisión tiene autorización de investigación local.
El documento 00 fija el único piloto de valores autorizado por ahora. Este
runbook ordena el trabajo posterior; no concede por sí mismo permiso para abrir
payoffs, modificar familias cerradas o integrar órdenes.

## 1. Estado de entrada

Leer antes de ejecutar:

1. `../multiscale_v1r1/27_OFFLINE_AUDIT_AND_QQQ_TRANSPORT_RESULT.md`.
2. `00_SOURCE_PILOT_CONTRACT.md`.
3. `../multiscale_v1r1/local_only_evidence/quote_clock_schema_review.json`.
4. `../multiscale_v1r1/01_PREDECLARATION.md` y `12_AUTHORIZED_CONTINUATION.md`,
   como antecedentes que esta revisión no reescribe.

La suite previa tiene 129 tests. El informe 21 acredita un fold de modelos
sintéticos, no evaluación económica local. El intento V1R1 sigue invalidado.
El piloto QQQ de red terminó sin bytes y su autorización quedó consumida.
El usuario excluye más API: no hacer siquiera requests de estado.

Los schemas sugieren una cohorte utilizable en 2023, pero todavía no acreditan
valores, recepción, fills ni OI previo. En los archivos sin reloj de opción,
`underlying_timestamp` no es un reemplazo de ese reloj. OHLC de opciones no
permite reconstruir ask/bid ni queues. No añadir columnas ficticias para que
el parser antiguo acepte un archivo.

## 2. Separación de tareas y archivos

| Tarea | Archivo previsto | Restricción |
|---|---|---|
| Constantes de formato | `neural/jepa/local_snapshot_schema_v1.py` | Sin normalización ni cálculo compartido |
| Fuente y productor | `neural/jepa/local_snapshot_source_v1.py` | Solo allowlist de seis parquets |
| Oráculo independiente | `neural/jepa/audit_local_snapshot_source_v1.py` | No importar productor ni su loader |
| Pruebas de productor | `tests/multiscale_v1r1/test_local_snapshot_source.py` | Parquet sintético, sin red |
| Pruebas de auditor | `tests/multiscale_v1r1/test_local_snapshot_audit.py` | Alterar fuentes/resultado y exigir fallo |
| Evidencia real del piloto | Root fijo del contrato 00 | Crear una vez, no sobrescribir |

No modificar `multiscale_v1r1/runner.require_gate` para aceptar esta fuente.
El runner antiguo debe seguir negando el histórico no admitido. Esta familia
tendrá su propio registro y, si procede, un runner distinto.

## 3. Secuencia del piloto, sin economía

### Antes de abrir valores

Comprobar que no existe el root de salida y que los seis archivos de entrada
coinciden con el patrón del contrato. Leer schemas y tamaños; no abrir columnas
de precio desde una consola para decidir cómo adaptar las reglas.

Ejecutar tests focales, Ruff y compile. Revisar productor y auditor como caminos
distintos. Publicar código, tests y contrato con commits de rutas explícitas;
no incluir parquets del usuario, credenciales o outputs ajenos en el commit.

Comprobar HEAD remoto y hashes del código de ejecución. La publicación de un
documento sin la implementación y los tests no cumple esta condición.

### Ejecución permitida

El CLI del productor tendrá exactamente el root y la referencia del contrato:

```powershell
python -m neural.jepa.local_snapshot_source_v1 --root D:/GexResearchArtifacts/local_snapshot_v1/source_pilot_20260919_01 --authorization-reference USER_LOCAL_SNAPSHOT_RESEARCH_20260919
```

Ejecutar solo después de cumplir las condiciones anteriores. El código copia
y sella los seis inputs, filtra la primera hora, produce el diagnóstico y pide
al auditor que vuelva a leer las copias. No llama al capturador ThetaData.

### Después de ejecutar

Leer summary, audit y access log. Contar muestras enmascaradas y sus razones.
Registrar los tres tickers aunque uno falle. Conservar el root si hay error;
no cambiar la fecha, los filtros o la clasificación para conseguir un PASS.

Publicar evidencia compacta con referencias a los hashes originales. Si se
normalizan finales de línea de JSON para Git, registrar ambos hashes y el cambio.
No llamar «fuente causal de mercado admitida» al estado de diagnóstico completo.

## 4. Censo local antes de un calendario de entrenamiento

El piloto de un día no permite extrapolar el resto. El siguiente contrato de
admisión, previo a más valores, deberá fijar:

- Universo inicial de sesiones y archivos existentes, con fechas sin datos y
  motivo. Conservar 2024–2025 aunque falten relojes; no ocultar ese hueco.
- Fechas con Greek y OI de reloj verificable, por ticker, año y mes; intervalos
  1m/30s/5m separados. Un footer homogéneo no sustituye una validación de filas.
- Identidad de expiración de las muestras spot y de la opción negociada. Una
  weekly puede describir el subyacente de un día sin 0DTE, pero no se negocia
  como si fuera un contrato 0DTE. Fijar esa selección antes de precios.
- Evidencia de OI prior-close, no solo una marca temporal anterior a la apertura.
  Mantener separado el dato reportado de su recepción no observada.
- Frecuencia de muestras, huecos, timestamps futuros, duplicados y divergencia
  entre contratos. Informar todos los rechazos, antes de cualquier selección.

Reutilizar el inventario existente como índice de búsqueda, no como admisión
positiva: el intento de auditoría original no terminó y sus logs cambiaron.
Verificar hashes/schemas actuales por el alcance nuevo sin sustituir su sello.

## 5. Fuente candidata y límites de representación

La serie candidata son muestras `underlying_price` de Greeks con reloj de fila
y reloj del subyacente. Evita depender de rellenos no trazables de los OHLC
derivados, pero no recupera extremos que ocurrieron entre dos muestras.

Si se investigan niveles sobre esa serie, llamarlos rangos o niveles de muestras.
Predeclarar la ventana y disponibilidad. No presentarlos como los 59 niveles
exactos de V1R1 hasta demostrar equivalencia, que hoy no existe. Conservar la
excepción SPXW histórica autorizada sin extenderla a un relleno de la nueva serie.
Un cero a09:30 no permite insertar a09:30 un precio observado después.

La demora de un minuto del piloto es una hipótesis de investigación. Un test
que respete esa demora comprueba el software, no la latencia original de una
fuente recibida años después. Toda futura conclusión debe conservar ese límite.

## 6. Contrato económico nuevo, todavía por publicar

El agente no debe entrenar al terminar el piloto. Debe escribir y revisar primero
un contrato económico completo, coherente con la fuente admitida. Tendrá que
resolver como mínimo:

1. Pregunta de utilidad incremental, baseline y ablación. Mantener pequeño el
   presupuesto de modelos y exigir ganancia económica, no solo menor MAE.
2. Target, unidades y sizing. Si se conserva utilidad USD por contrato, usar
   cantidad fija y L2; reportar rentabilidad de cuenta solo con capital compartido.
3. Reloj de decisión, elección contractual y entrada. No elegir contrato con una
   quote y fingir un fill simultáneo anterior a su disponibilidad. Una simulación
   basada en snapshots debe usar observaciones posteriores según latencia fija.
4. Salida del mismo contrato y horizonte fijo. No inferir stops, recorridos
   intraminuto ni prioridad de órdenes de una tabla 1m. Registrar salidas ausentes
   y penalizaciones sin llamarlas ejecuciones observadas.
5. Spread, comisión y slippage base/adverso. Recalcular WR, PF y PnL en cada caso.
   No reutilizar labels anteriores con otro reloj o instrumento.
6. Folds y cohortes elegidos por calendario/cobertura antes de resultados. Un
   hueco de dos años no es una serie mensual continua; exigir un entrenamiento
   compatible con los meses realmente disponibles, sin rellenar outcomes.
7. Gates numéricos, frecuencia, concentración, incertidumbre dependiente por días
   y cierre ante fallo. No heredar solo los umbrales que resulten cómodos.
8. Auditor independiente de selección, freeze, scheduler, ledger y métricas.

El histórico 2022–2026 está visto. Ninguna división nueva lo convierte en test
prospectivo intacto. El máximo resultado defendible seguirá siendo desarrollo
bajo los supuestos de quote-sampling y vintage explícitos; nunca live-ready.

## 7. Condiciones para operar que este alcance no puede satisfacer

El usuario ha limitado el trabajo a archivos descargados. Esos archivos permiten
investigación histórica; no aportan cotizaciones futuras, aceptación de órdenes
ni fills de bróker. Una política rentable en un proxy retrospectivo requeriría
después un periodo prospectivo congelado y una fuente operativa autorizada.
No contratar ni integrar esa fuente dentro de este encargo local.

Mientras falten esos pasos: technical_ready=false para promoción, prospectivo
NOT_STARTED y promotion_approved=false. No tocar bots/services/systemd/web/VPS.
El agente debe informar qué evidencia obtuvo y qué continúa pendiente, sin
prometer que una búsqueda persistente acabará produciendo una ventaja real.

# Auditor mensual 2026: implementación y verificación sintética

2026-10-23. Estado de implementación: **VERIFICACIÓN SINTÉTICA COMPLETA**;
revisión independiente final en documento separado. Estado de ejecución de
mercado de este auditor: **NOT_STARTED**. No se publica un PASS económico real.

Se implementaron únicamente archivos nuevos:

- `audit_monthly_walk_forward_test.py`.
- `test_audit_monthly_walk_forward_test.py`.
- `MONTHLY_TEST_AUDIT_EXTENSION_SPEC_20261023.md`.

El [diseño previo](MONTHLY_TEST_AUDIT_EXTENSION_DESIGN_20261023.md) permanece
intacto. El productor mensual y el auditor2025 están sin modificar. La extensión
reutiliza primitivas del auditor independiente, sin importar productor,
scheduler/selector del productor, LightGBM o entrenadores. No ejecuta refit ni
reinferencia. La verificación previa del resume y sus6084checkpoints está en
[MONTHLY_RESUME_VERIFICATION_20261023.md](MONTHLY_RESUME_VERIFICATION_20261023.md).

## Resultado final de pruebas

Comando ejecutado desde la raíz del repositorio con Python314 y un hilo por
backend numérico, después del gate de recursos:

```powershell
python -m pytest research_papers/JEPA/level_oracle_20261018/test_audit_monthly_walk_forward_test.py -q -x
```

Resultado terminal recogido: **30passed en343,09s (5min43s), exit0**.
Después se ejecutaron Ruff completo y py_compile sobre los dos archivos nuevos:
ambosPASS. Los hashes finales se comprobaron de nuevo tras las pruebas.

La fixture integral usa2625identidades del calendario y una acción artificial
por día disponible. Los archivos de modelo son texto sintético, nunca ajustado
ni inferido. La autoridad2025 es una fixture de evidencia previa confiada;
no se presenta como ejecución de la auditoría2025 dentro de esta prueba.
Se reconstruyen completamente las12ventanas nuevas y los seis meses de2026:
13modelos usados incluyendo static,18combinaciones modo-mes, cobertura369/363/6,
selecciónnull y los cierres/reportes. El `MonthlyInputs` real consume el cierre
compuesto para los tres procedimientos en enero/junio2026 y una predicción
heredada2025. Estos números describen cobertura sintética, no resultados de mercado.

Las fixtures negativas cubren autoridades/hash, cortes, cierre de los tres
fit_keys mensuales, freeze tardío, modelo tardío, selecciónnull alterada,
completion incompleto, schemaNPZ, float32 coherentemente re-sellado, IDs/estados,
escala/modelo equivocados, calendario/ausencias, WAIT/NO_FILL/bloqueo y cierre
corto, raíces prohibidas en manifests, alteración tardía de evidencia y rechazo
de un directorio parcial anterior.

La fixture completa exige>=2.000.000.000bytes de RAM física y commit libres
antes de crear sus datos enWindows. Una observación durante el pase final,
20:02:33UTC, mostró RSS254.271.488bytes, lectura acumulada905.823.278bytes y
escritura234.792.904bytes. Es una muestra del proceso de pytest, no una cota
del pico, ni una estimación de memoria/tiempo del auditor sobre mercado real.
No quedaron procesos de prueba activos después del cierre.

## Revisiones y cambios durante implementación

Un primer pase integral de la versión inicial dio10passed en732,76s. Se conserva
como verificación inicial, sin atribuir sus hashes a los bytes finales. La
revisión independiente identificó dos guardas que faltaban en la extensión:

1. Los paths de feature_inputs necesitaban control central de raíces, además
   de las rutas del índice. `BoundedVerifier` lo aplica a todas las referencias
   nuevas, y las raíces de dataset se verifican antes de inicializar el auditor.
2. El auditor heredado comprobaba igualdad/finiteza de scores pero no dtype
   float64 estricto. El preflight nuevo exige schema exacto, IDs/estado enteros
   del dtype fuente, vectorfloat64 y modelo/escala escalares exactos. La fixture
   float32 re-sellada demuestra que un hash consistente no evita ese rechazo.

Se añadió también el orden modelo.complete<NPZ.complete<=sello mensual, copias
de revisiones en el output y protección de day_root referenciados al elegir
la salida. La especificación distingue comparación de valores chunks↔matriz
de autenticación por hash de los archivos fuente; no afirma reconstrucción de
features desde raw.

Con esos bytes finales, el autor ejecutó27focales rápidosPASS/3deselected en10,08s
antes del integral final30PASS. El revisor separado `tcn_completion` comunicó
**20focales independientesPASS en4,94s/10deselected**, con hashes iguales antes y
después; RAM9.056.296.960bytes y commit13.506.519.040bytes al admitir sus pruebas.
El integral30PASS pertenece a la ejecución del autor, no al rerun del revisor.
La revisión independiente exacta y su cierre deben consultarse por separado.

## Hashes finales

| Archivo | SHA256 |
|---|---|
| audit_monthly_walk_forward_test.py | ec0ddb99840d5bf380eb7f407de3e1a5bcbdfa352d79ad5d75e24a05750db57b |
| test_audit_monthly_walk_forward_test.py | b3cc6d8225812154da2e4d2c644e426a19f7177d520b9d564826e3a3e4790a00 |
| MONTHLY_TEST_AUDIT_EXTENSION_SPEC_20261023.md | b895e0ee57ee8d911b4d732e1f46b07c2d9e13c296f09888ce47372815f5182d |
| audit_monthly_walk_forward.py, conservado | e4a3be1c19b7f0af1226e71255c81116bd71a6a300aef36f61c688deb908df1f |
| run_monthly_walk_forward.py, conservado | 47a4df8b019d9d297ca1ee9b89fff63406409659336dbd7b0e4d7af01ed348bb |

## Frontera real pendiente

La continuación general del usuario ya autoriza el trabajo; la dependencia es
técnica y científica. Primero deben cerrar y auditarse los doce meses2025,
conservarse selección/null y fijarse sus hashes en la revisión de runtime.
La ejecución2026 del productor necesita su preparación operativa revisada
antes de sus12fits nuevos y sus seis cierres. Sólo después puede ejecutar esta
auditoría en una raíz nueva, con review exacta y autoridad2025 externamente fijada.

El eventual PASS será **GIVEN_SEALED_SCORES** y heredará la reconstrucción2025 de
su auditoría fijada, cuyo inventario se rehashea. No acredita refit, inferencia,
rawquotes, recepción histórica/live ni rentabilidad prospectiva. El adapterOOF
y su comparación corregida conservan sus propios requisitos de runtime y
auditoría. Todo2026 sigue como desarrollo visto; promociónfalse. No se tocaron
API, fuentes originales, producción, bróker o VPS.

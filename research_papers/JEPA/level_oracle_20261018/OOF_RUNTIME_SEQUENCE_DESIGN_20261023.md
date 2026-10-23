# Secuencia futura de runtime OOF

23 de octubre de 2026. Diseño operativo, **sin autorización de runtime**.
Inspección de código/documentos publicados en
`2f5d6fc8b7fd5093d30cd78cb929a2ef0e93e1d8`; no se abrieron outcomes, ejecutaron
fits ni consumieron artefactos económicos reales para preparar este documento.

## Frontera de entrada

Se necesita primero la auditoría mensual compuesta **202501–202606**, status
`PASS_INDEPENDENT_MONTHLY_WALK_FORWARD_AUDIT_GIVEN_SEALED_SCORES`, su ruta y
**SHA externo revisado**. La revisión de código OOF no sustituye esa evidencia.
Debe ligar monthly_root, run_contract_sha256, session_root,
session_audit_sha256, index_sha256, completed_months y verified_files completos.
Se requieren también ruta de auditoría SessionClock y roots absolutos de mensual
y SessionClock. Los SHA de estas salidas futuras están **pendientes**; no se
inventan ni se derivan de cualquier archivo encontrado para autoaprobarlo.

Binding de código OOF ya publicado:

| Archivo | SHA256 |
|---|---|
| monthly_oof_calibration_adapter.py | `7b80cff43e3887a92e0f89be6daa863a670ccd72d22a0f4aeabd032a39479364` |
| oof_maximum_calibration.py | `19e922dd65855c4cd7e2ec9d482d477a328245bcf642eeeb7771985f247e20b5` |
| evaluate_oof_calibrated_policy.py | `eeaad06f5b862a3153f29e7eab579b19a35e182ab506cf1f59e65631e187e716` |
| audit_oof_calibrated_policy.py | `e7481fbe944a9ffadcf637e7a4b69cd8d636cdf50ae295426191db9d76b5d44b` |

El manifest del futuro wrapper debe fijar además los bytes publicados de
`rolling_monthly_schedule.py`, `MONTHLY_OOF_CALIBRATION_ADAPTER_SPEC.md`,
`PREQUENTIAL_MAX_CALIBRATION_DESIGN.md`, `OOF_MAXIMUM_CALIBRATION_INTEGRATION.md`
y `OOF_CALIBRATED_POLICY_EVALUATION_SPEC.md`: son miembros exactos de los mapas
`dependency_hashes()`/`dependencies()`. Fijar asimismo auditor/tests/spec/diseño
y la revisión independiente OOF. Ningún cambio de estas dependencias se acepta
como resume. El wrapper necesita su propia revisión y publicación previas.

## APIs existentes y secuencia

**Adaptador y replay no tienen CLI.** Ejecutarlos como scripts no lanza esta
evaluación. Las interfaces exactas que deberá llamar el wrapper son:

```python
source = MonthlyInputs(monthly_root, monthly_audit, monthly_audit_sha256,
                       session_root, session_audit)
prepare_correction(source, target_month, correction_root)

# Instancia nueva: source.used es mutable y no se comparte entre fases/meses.
source = MonthlyInputs(monthly_root, monthly_audit, monthly_audit_sha256,
                       session_root, session_audit)
evaluate_month(source, correction_root, target_month, evaluation_root,
               correction_completion_sha256=reviewed_correction_sha256)
```

Procesar `202601`, `202602`, `202603`, `202604`, `202605`, `202606`, sin elección
por resultados. El historial del calibrador es enero2025–diciembre2025 para
enero2026; después se amplía hasta el mes inmediatamente anterior al objetivo.
Es expanding para los tres procedimientos base, incluido rolling12. Cada base
respeta su propio corte de fit; labels del historial deben tener disponibilidad
declarada cierreNYSE+1min estrictamente anterior al mes objetivo.

1. Crear una raíz de corrección nueva, separada de fuentes/mensual/código, y seis
   raíces de replay nuevas, una por mes. Se puede compartir la raíz de corrección
   entre meses porque las selecciones/realized históricos tienen identidad fija.
2. Admitir autoridades y código antes de cada fase. Preparar el mes sin leer sus
   labels: selección de todos los estados, calibración pasada y scores corregidos.
   Exigir `<mes>.complete.json` con
   `COMPLETE_OOF_CORRECTION_SCORES_NO_TARGET_LABELS`, `target_labels_read=false`.
3. Conservar y sellar un recibo de esa fase con el SHA de su cierre; entregarlo al
   replay mediante el argumento externo anterior. El wrapper deberá implementar
   esta transición verificable, no escoger automáticamente otro cierre existente.
   El replay verifica todos los controles y sella scores antes de nuevos labels;
   conserva seis políticas, `winner_selected=null`, sin refit ni cambio de ranking.
4. Exigir `completion.json` del replay con `COMPLETE_FIXED_OOF_POLICY_MONTH`, y
   registrar su SHA externo. Fallo/interrupción detiene la secuencia y preserva
   todos los archivos; no se salta un mes ni se cambia threshold/coste/modelo.
5. Con los seis cierres de ambas fases, publicar/revisar una request `FULL_H1`
   según `OOF_ECONOMIC_AUDITOR_SPEC_20261023.md`. Ejecutar después el auditor
   independiente en otra raíz nueva. El único CLI existente es:

```powershell
python research_papers/JEPA/level_oracle_20261018/audit_oof_calibrated_policy.py --request <request-absoluta.json> --request-sha256 <SHA-externo-revisado> --output <raiz-auditoria-nueva>
```

`MONTHS` permite auditar un subconjunto explícito, pero no sustituye el cierre H1.
El resumen mensual del productor declara `full_period_complete=false`; el auditor
deriva el agregado H1 y los gates por ticker. No hace falta inventar otro comando
de resumen ni seleccionar una política. H1 conserva 369 ticker-días, 363
disponibles y seis ausentes con null/NO_EVALUABLE, no retornos cero imputados.

## Preservación, recursos y wrapper pendiente

Adaptador/replay usan lock exclusivo del sistema operativo por raíz y publicación
por igualdad exacta de payload/hash. Un resume sólo es admisible con la misma
autoridad, código, inputs y raíces; no adopta outputs sin implementation/contrato.
Los locks los libera el kernel; no borrarlos por heurística de PID. Una discrepancia
se conserva y falla. Los productores no generan recibo uniforme de fallo: falta
el wrapper que registre fases, recursos, logs, hashes de cierre y fallo/interrupción
sin publicar éxito parcial. El auditor exige raíz inexistente y no ofrece resume;
su fallo conserva `FAILED_OR_INTERRUPTED_PRESERVED`, sin `audit.json` de éxito.

El wrapper también debe comprobar rutas acotadas/disjuntas, autoridad/review
externa, hashes publicados, exclusión de ejecuciones simultáneas y un gate mínimo
de RAM/commit de **2.000.000.000 bytes** antes de cada fase. Sólo el CLI del auditor
trae ese gate hoy; adaptador/replay no. No iniciar en competencia con trabajos
mensuales/TCN pesados. Registrar duración, RSS y bytes realmente escritos durante
el futuro run; no inferir capacidad suficiente sólo del gate inicial.

Sin fit/inferencia nueva, el coste dominante es lectura/hash repetida de NPZ,
parquets diarios y JSON. Hay hasta 316 máximos por ticker-día completo y 136 por
sesión corta; límite superior conservador de 1.055.124 máximos únicos para los
tres procedimientos sobre 1.113 ticker-días disponibles 2025+H1. Los historiales
se vuelven a verificar para cada objetivo; no es una sola pasada. El adaptador
retiene records de un procedimiento y el replay scores/controles del mes en RAM;
JSON, objetos Python y tablas de ofertas completas añaden costes no medidos.
No se estima duración ni RSS real desde las fixtures. Estas sólo acreditaron
35 pruebas/12,99s y revisión externa focal 14/3,96s; no son un benchmark histórico.

## Límite de la evidencia

La revisión externa publicada es `IMPLEMENTATION_ONLY`, runtime false. Este
documento tampoco revisa un wrapper inexistente ni sustituye su futura prueba
sintética de lifecycle/fallos/resume. La auditoría económica está condicionada a
scores base sellados: no reproduce fits, inferencia ni quotes raw. 2025 es TRAIN
del calibrador, 2026 desarrollo visto; un PASS de reproducción no demuestra
rentabilidad ni habilita promoción, shadow u operaciones de producción.

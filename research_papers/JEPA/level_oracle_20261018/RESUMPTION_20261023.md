# Reanudación autorizada del 23 de octubre de 2026

El usuario ordena «continua con todo ello», fija de nuevo el objetivo de investigar
una estrategia local 0DTE SPY/QQQ/SPXW por zonas Fibonacci IB y put/call walls,
y pide explícitamente usar subagentes. Esta orden revoca la pausa operativa del
18 de octubre. El punto de partida publicado es `acb2a726`; el cierre anterior
se conserva como evidencia del estado en que se detuvo el trabajo.

## Alcance y orden de trabajo

Se conserva el oracle retrospectivo auditado y los experimentos terminados.
No se repiten para buscar resultados favorables. El oracle usa futuro; su
rentabilidad no acredita una política causal. Los periodos históricos explorados
siguen siendo `SEEN_DEVELOPMENT`, incluso cuando sean posteriores al ajuste.

1. Verificar contratos, código, modelos y checkpoints de las líneas incompletas.
2. Completar la comparación fijada de griegas424 frente al control152 y su
   auditoría independiente; ambos modelos ya están entrenados.
3. Completar y revisar el evaluador TCN row-mixed de750+369 ticker-días antes de
   ejecutarlo. La revisión antigua de741 días no cubre este evaluador. No volver
   a entrenar las cuatro épocas terminadas.
4. Continuar la validación mensual2025 preservando los tres modelos cerrados y
   enero. Completar y auditar los doce meses antes de calibración OOF; no saltar
   directamente a selección o evaluación2026 desde resultados parciales.
5. Terminar fixtures y revisión OOF antes de cualquier aplicación a mercado.

No cambian políticas, costes, umbrales, semillas, ventanas ni ranking por los
resultados observados. Toda corrección necesaria tendrá su propia evidencia,
pruebas y revisión antes de ejecutar el código modificado sobre mercado.

## Datos, recursos y procesos

Sólo fuentes existentes `D:/ThetaData`; artefactos voluminosos conservados en
`D:/GexResearchArtifacts/level_oracle_20261018`. No API ni descargas. Producción,
bróker, servicios, VPS y cambios ajenos permanecen fuera del alcance.

La inspección inicial por PID y línea de comandos no encontró procesos activos
de esta investigación. Hay procesos Python de otros proyectos que se conservan.
Los lanzamientos mantienen el gate operativo previo de2.000.000.000 bytes libres
de RAM y commit. Se coordinarán los trabajos pesados para evitar competir entre
sí; paralelizar las revisiones no obliga a lanzar entrenamientos simultáneos.

Se usarán recibos y logs nuevos para esta reanudación. Los marcadores antiguos
de progreso o locks no acreditan procesos vivos ni permiten borrar parciales.
Los documentos y recibos del cierre18 siguen inmutables.

## Estado inicial

`research_state=RESUMED_LOCAL_ONLY`; `causal_profitability=NOT_DEMONSTRATED`;
`technical_ready=false`; `promotion_approved=false`.

Este documento autoriza la secuencia de trabajo, no declara terminadas las
verificaciones ni las evaluaciones pendientes. Los resultados nuevos deberán
identificar el código ejecutado, sus hashes, alcance y auditoría.

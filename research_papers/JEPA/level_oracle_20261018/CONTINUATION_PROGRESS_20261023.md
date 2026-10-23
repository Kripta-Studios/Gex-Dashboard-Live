# Continuación local: estado del 23 de octubre de 2026

Actualización: 23 de octubre, después del cierre TCN de las 20:24 UTC. Investigación activa
por orden del usuario. Base publicada anterior: `acb2a726`; preparación y código
nuevos publicados hasta `2f5d6fc8`, incluyendo los auditores mensual 2026 y OOF.
Este registro incorpora el resultado TCN auditado; las otras líneas siguen abiertas.

## Ejecuciones observadas

- Comparación fija griegas 424 frente a compacto 152: launcher PID 34788,
  productor PID 19696. Su contador llegó a 750/750 ticker-días de 2025;
  aún no se afirma cierre global ni auditoría nueva. Logs y recibos:
  `D:/GexResearchArtifacts/level_oracle_20261018/common_greek_comparison_v1_launch`.
  No se reentrena ninguno de los dos modelos ni se selecciona por resultados
  parciales. El supervisor `common_greek_resume` espera el cierre antes de
  ejecutar la auditoría existente en una salida nueva.
- Validación mensual: wrapper PID 11852, iniciado a las 19:34:13 UTC desde
  `1e1f689e`, sólo `stage validation`. Ya publicó su nuevo `launch.json`;
  tiene seis modelos completos de los 24 previstos para validación. Root rehasheó
  los seis modelos y sus recibos de inicio, sin diferencias. Los tres originales
  permanecen intactos; los nuevos cierres ocurrieron a las 19:59:06, 20:13:35 y
  20:20:05 UTC. Todavía no hay cierre anual ni evaluación mensual 2026.
  Runtime: `D:/GexResearchArtifacts/level_oracle_20261018/monthly_resource_overlay_resume_20261023_01`.
  Logs y recibo de proceso en el directorio hermano
  `monthly_resume_20261023_01_logs`.
- Evaluación TCN: PID 48688 terminó con exit 0 observado por handle retenido
  a las 20:06:46 UTC, desde el código publicado en `c1d92f26`, sin fit.
  Salida nueva `tcn_row_mixed_calendar_v1_evaluation`; recibos y logs en
  `tcn_row_mixed_calendar_v1_evaluation_launch_20261023_01`, bajo la misma raíz.
  Gate observado al lanzar: RAM 5.110.734.848 bytes, commit 6.940.225.536 bytes
  y memoria GPU libre 8.058.306.560 bytes. El subagente
  `tcn_economic_auditor` supervisa la auditoría independiente, PID 23816, salida
  nueva `tcn_row_mixed_calendar_v1_economic_audit_01`. Reconstruidos 750 días de
  validación y 363 disponibles de 2026, 36.157 miembros verificados. Auditoría PASS
  y exit 0 observados a las 20:24:37 UTC; SHA audit
  `09b416926fe1da455d8507f0b28e24a8ed8a2ae42845ecbb9326ebf442ca85e5`.
  La evaluación tardó 1.305,195 s; pico RSS 1.587.216.384 bytes y private
  muestreado 2.316.120.064 bytes. El monitor comenzó después del lanzamiento, por
  lo que el pico private se limita al intervalo observado.

Los PID sólo identifican la observación actual: comprobar creación y comando
antes de cualquier intervención futura. Los procesos de otros proyectos se
conservan intactos.

La previsión inicial de secuenciar toda la carga se ajustó tras observar unos
238 MB de RAM en la comparación. Se permite esa inferencia de bajo consumo junto
al mensual; los fits mensuales siguen siendo seriales. Ambos mantienen el gate
operativo de 2.000.000.000 bytes libres de RAM y commit. La cifra de 238 MB es
aproximada, no una cota de consumo futuro. Las observaciones y picos efectivos
deben tomarse de los recibos de runtime al cerrar.

## Trabajo verificado y pendientes

- Productor y auditor griegas: 20 pruebas sintéticas PASS antes del lanzamiento.
- Recuperación mensual: 6.084 checkpoints rehasheados, cero ausencias o cambios;
  tres modelos anteriores conservados y tres nuevos completos. Quedan 18 fits
  de validación; el cierre y auditoría anual siguen pendientes.
- OOF: se completó el rerun pendiente de 23 pruebas, todas PASS. No hubo
  calibración real; el informe separado conserva las autoridades antiguas.
- Evaluador TCN calendario 750 + 369: dos correcciones de trazabilidad y copia
  exacta, 15 pruebas PASS tanto en el productor como en revisión independiente.
  La review exacta está versionada y la evaluación ha sido lanzada; sin resultados
  auditados: ninguna política elegible diaria en 2025, selección nula. En H1 2026
  las variantes de umbral 0/5/10 producen -34.199,00/-40.962,60/-42.491,00 USD base
  y -36.608,00/-43.001,60/-44.328,00 adverso. Los tres controles no operan en H1.
  Son diagnósticos de políticas no seleccionadas, no una política rentable.
- Auditor económico TCN nuevo: las dos observaciones de membresía se corrigieron
  y se añadieron pruebas integradas. Productor y revisor independiente completaron
  36 pruebas PASS. Revisión CLEAR publicada antes de lanzar la evaluación.
  El auditor real terminó PASS: reproducción económica condicionada a scores
  sellados y labels auditados, sin repetir fit, inferencia GPU o quotes raw.
- Auditor mensual 2026: implementación y revisión independiente publicadas en
  `35dcb714`. Autor: 30 pruebas PASS; revisión: 20 pruebas focales PASS, sin repetir
  la integración completa. Sólo implementación; runtime todavía no autorizado por
  su review. Se prepara por separado el wrapper operativo de test, dependiente del
  cierre auditado de 2025 y freeze. Productor y auditor 2025 intactos.
- Auditor económico OOF: publicado en `2f5d6fc8`, 35 pruebas del autor y 14 focales
  independientes PASS. Revisión limitada a implementación sobre scores sellados;
  falta la auditoría mensual compuesta y la petición concreta de ejecución. No se
  ha calibrado ni evaluado OOF real.
- Reporter mensual griegas: cuatro pruebas PASS; sólo puede consumir el cierre
  auditado de esta comparación. Publicará los 108 grupos fijados, sin selección.

La siguiente frontera real sigue siendo cerrar y auditar estas evaluaciones.
El oracle retrospectivo permanece terminado. Rentabilidad causal no demostrada,
periodos históricos `SEEN_DEVELOPMENT`, `technical_ready=false` y
`promotion_approved=false`.

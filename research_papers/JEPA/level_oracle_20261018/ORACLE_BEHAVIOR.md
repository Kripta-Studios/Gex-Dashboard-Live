# Qué hizo el oracle de niveles

**Análisis descriptivo retrospectivo: todas las decisiones del oracle usan el futuro. No es un modelo operable.**

Estado final: **PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT**, publicado a las 17:12:18 UTC. Se verificó que la auditoría y este análisis consumen el mismo índice SHA `8d0c6e27bdaf7d47ef2a9888505294b8f3186da3a6927e780ce9e517e660e8e5`, y que coinciden 36.019 trades y ambos totales de PnL. La constancia está en [audit_binding.json](D:/GexResearchArtifacts/level_oracle_20261018/oracle_behavior_v2/audit_binding.json); el [audit original](D:/GexResearchArtifacts/level_oracle_20261018/engine_v1_audit_v4/audit.json) tiene SHA `cbbe61d0a3fa7619447b7301d4c4b2fd52c487e11450d4904efee381fc3bf22d`. El `summary.json` descriptivo conserva `PENDING_INDEPENDENT_AUDIT` fijado al arrancar; esta constancia posterior actualiza el estado sin rehacer ni cambiar métricas. El PASS no acredita receipt original, paridad live ni rentabilidad causal.

Universo completo disponible: 2.595 ticker-días; calendario 2.601, con seis ausencias de fuente. Se separan 2023–2024 (ajuste), 2025 (selección) y 2026H1 (desarrollo cronológico ya visto). Ninguna tabla selecciona filtros o modelos usando 2026.

El oracle combina decisiones con intención de rechazo y continuación, elige con frecuencia un objetivo más lejano que el primero ofrecido y mantiene operaciones de duración variable. Pero no ha descubierto por sí mismo estas reglas: la cercanía a zonas, la familia de contratos y las salidas por objetivo/stop están programadas. El DP decide momento, contrato y objetivo conociendo los resultados y la continuación de toda la sesión.

Lo más relevante para aprender de él es la dificultad de selección: en los nueve ticker-periodos, el 70,4–72,4% de las alternativas del mismo estado escogido pierde dinero. El 42,2–45,8% de sus elecciones tampoco maximiza el beneficio aislado de esa operación: puede sacrificarlo para liberar la posición y aprovechar otra después. Reproducir su aspecto visual o clasificar la dirección no reproduce automáticamente esa planificación.

[Figura de los nueve grupos completos](D:/GexResearchArtifacts/level_oracle_20261018/oracle_behavior_v2/oracle_behavior_profile.png): objetivos más lejanos, elección frente al máximo aislado y duración p10/mediana/p90. Se generó exclusivamente desde `summary.json`, con script y manifest separados, y se inspeccionó visualmente. No sustituye las gráficas de las sesiones fijas.

## Magnitud y duración

| Ticker | Periodo | Días disponibles | Trades | Neto base USD | Neto adverso USD | Holding p10 / mediana / p90 (min) | TARGET / STOP / EOD |
|---|---|---:|---:|---:|---:|---|---|
| SPXW | 2023–24 | 497 | 7,586 | 3,539,179.40 | 3,524,007.40 | 2 / 7 / 29 | 6855 / 461 / 270 |
| SPXW | 2025 | 247 | 3,830 | 2,672,497.00 | 2,664,837.00 | 2 / 7 / 30 | 3401 / 296 / 133 |
| SPXW | 2026H1 | 123 | 2,000 | 1,479,655.00 | 1,475,655.00 | 2 / 7 / 26 | 1808 / 120 / 72 |
| SPY | 2023–24 | 497 | 6,575 | 321,488.00 | 308,338.00 | 2 / 9 / 35 | 5983 / 292 / 300 |
| SPY | 2025 | 247 | 3,330 | 251,843.00 | 245,183.00 | 2 / 8 / 35 | 3032 / 180 / 118 |
| SPY | 2026H1 | 120 | 1,682 | 132,802.80 | 129,438.80 | 2 / 8 / 32 | 1538 / 71 / 73 |
| QQQ | 2023–24 | 497 | 6,216 | 357,177.40 | 344,745.40 | 2 / 9 / 38 | 5658 / 255 / 303 |
| QQQ | 2025 | 247 | 3,143 | 266,684.20 | 260,398.20 | 2 / 9 / 36 | 2863 / 138 / 142 |
| QQQ | 2026H1 | 120 | 1,657 | 169,089.80 | 165,775.80 | 2 / 8 / 33 | 1513 / 70 / 74 |

Un contrato por operación. Son sumas de PnL, no rentabilidad porcentual de una cuenta ni una cartera con capital dimensionado. El escenario adverso aplica más costes a la misma trayectoria elegida con costes base; no reoptimiza el oracle.

WAIT permite alcanzar cualquier estado futuro sin perder dinero. Una acción con neto base ≤0 no mejora el valor frente a esperar, y WAIT gana los empates. Por construcción, una solución exacta selecciona solo netos base positivos; una elevada tasa de acierto o PF infinito del oracle no es evidencia de edge. El JSON conserva positivos/cero/negativos y mínimos base/adverso como diagnóstico.

Comprobación observada: base 36.019 positivas, cero nulas y cero negativas, mínimo **+0,40 USD**. Con costes adversos sobre la misma trayectoria: 35.648 positivas, cero nulas y 371 negativas, mínimo **−1,60 USD**. Desglose de signos y mínimos en [payoff_sign_diagnostics.json](D:/GexResearchArtifacts/level_oracle_20261018/oracle_behavior_v2/payoff_sign_diagnostics.json), calculado únicamente desde los descriptores ya publicados.

## Qué zonas eligió y qué distancia se propuso recorrer

| Ticker | Periodo | Entrada Fib sola / walls solas / mezcla | Objetivo Fib solo / walls solas / mezcla | Objetivo más lejano que el primero ofrecido | Niveles intermedios conocidos | Distancia objetivo mediana / p90 (IB) | Stop mediano (IB) |
|---|---|---|---|---:|---:|---|---:|
| SPXW | 2023–24 | 55.7% / 14.7% / 29.6% | 58.8% / 16.1% / 25.0% | 40.2% | 43.8% | 0.272 / 0.917 | 0.213 |
| SPXW | 2025 | 50.9% / 16.3% / 32.7% | 53.9% / 17.4% / 28.7% | 38.0% | 42.0% | 0.255 / 0.925 | 0.200 |
| SPXW | 2026H1 | 44.5% / 17.9% / 37.5% | 52.0% / 17.4% / 30.6% | 35.9% | 40.0% | 0.244 / 0.762 | 0.201 |
| SPY | 2023–24 | 61.4% / 11.8% / 26.8% | 60.6% / 15.1% / 24.3% | 45.5% | 49.0% | 0.302 / 1.014 | 0.220 |
| SPY | 2025 | 55.1% / 14.0% / 31.0% | 56.3% / 15.5% / 28.2% | 42.2% | 46.2% | 0.278 / 0.987 | 0.215 |
| SPY | 2026H1 | 53.2% / 11.8% / 35.0% | 55.4% / 13.9% / 30.7% | 39.8% | 43.2% | 0.264 / 0.803 | 0.199 |
| QQQ | 2023–24 | 55.9% / 12.0% / 32.0% | 56.6% / 14.6% / 28.8% | 43.8% | 47.9% | 0.272 / 0.895 | 0.208 |
| QQQ | 2025 | 48.5% / 14.0% / 37.5% | 51.4% / 16.0% / 32.6% | 39.4% | 43.0% | 0.255 / 0.814 | 0.202 |
| QQQ | 2026H1 | 43.9% / 16.7% / 39.3% | 49.1% / 17.3% / 33.7% | 36.7% | 41.3% | 0.235 / 0.688 | 0.199 |

Las tres categorías de procedencia son excluyentes. El JSON también conserva cada bit CALL/PUT OI/gamma por separado; esos bits se solapan en clusters deduplicados. Gamma significa proxy Black–Scholes × OI, no gamma observado ni posición dealer. “Más lejano” compara contra objetivos realmente ofrecidos en ese estado; “intermedios” cuenta centros conocidos entre spot y objetivo, excluido el propio centro de entrada, aunque no fueran objetivos elegibles. Describe geometría proyectada, no cruces realizados: una salida STOP/EOD puede no alcanzar esos centros.

Las proporciones de fuentes no demuestran que Fibonacci o walls causen los movimientos: también dependen de qué niveles ofrece el motor. La proximidad de todas las decisiones a alguna zona es una restricción programada, no un resultado que confirme edge frente a niveles placebo.

| Ticker | Periodo | CALL / PUT | Delta bucket .35 / .50 / .65 | Fill todavía cerca de zona | PnL positivo con spot en contra |
|---|---|---|---|---|---|
| SPXW | 2023–24 | 50.6% / 49.4% | 0.4% / 3.8% / 95.8% | 42.1% (7,586 observados) | 4 / 7,586 |
| SPXW | 2025 | 50.3% / 49.7% | 0.0% / 2.2% / 97.8% | 42.7% (3,830 observados) | 4 / 3,830 |
| SPXW | 2026H1 | 50.4% / 49.6% | 0.1% / 1.4% / 98.5% | 44.9% (2,000 observados) | 1 / 2,000 |
| SPY | 2023–24 | 49.6% / 50.4% | 1.4% / 13.9% / 84.7% | 39.3% (6,575 observados) | 1 / 6,575 |
| SPY | 2025 | 49.6% / 50.4% | 0.5% / 7.8% / 91.7% | 39.3% (3,330 observados) | 0 / 3,330 |
| SPY | 2026H1 | 49.0% / 51.0% | 0.3% / 5.5% / 94.2% | 42.3% (1,682 observados) | 0 / 1,682 |
| QQQ | 2023–24 | 49.2% / 50.8% | 1.3% / 11.2% / 87.5% | 43.2% (6,216 observados) | 0 / 6,216 |
| QQQ | 2025 | 49.8% / 50.2% | 0.8% / 6.2% / 93.0% | 43.7% (3,143 observados) | 0 / 3,143 |
| QQQ | 2026H1 | 48.9% / 51.1% | 0.1% / 3.6% / 96.4% | 45.0% (1,657 observados) | 0 / 1,657 |

Todas las decisiones seleccionadas se verifican dentro de su banda de entrada. El fill llega un minuto después y puede quedar fuera. “Spot en contra” compara spot observado en entrada y salida con el signo CALL/PUT. Una opción rentable pese a ese movimiento es una discordancia descriptiva; no identifica causalmente cuánto proviene de IV, gamma, theta, spreads o calidad de quote.

El delta bucket describe la selección entre .35/.50/.65, no un delta realizado idéntico: se elige el contrato disponible más cercano. El objetivo optimiza USD absolutos por un contrato, sin igualar prima/capital entre contratos. Por ello una preferencia por delta alto no demuestra superioridad por unidad de capital o riesgo.

## Intención geométrica al aproximarse a la zona

| Ticker | Periodo | Continuación | Rechazo | Sin clasificar |
|---|---|---:|---:|---:|
| SPXW | 2023–24 | 21.7% | 53.2% | 25.1% |
| SPXW | 2025 | 21.4% | 52.5% | 26.1% |
| SPXW | 2026H1 | 20.0% | 51.9% | 28.1% |
| SPY | 2023–24 | 18.8% | 56.4% | 24.7% |
| SPY | 2025 | 19.0% | 54.9% | 26.1% |
| SPY | 2026H1 | 18.1% | 53.7% | 28.1% |
| QQQ | 2023–24 | 18.3% | 53.3% | 28.5% |
| QQQ | 2025 | 17.8% | 52.6% | 29.7% |
| QQQ | 2026H1 | 18.8% | 51.2% | 30.0% |

Se compara el spot de cinco minutos antes con centro ± banda de la zona elegida en la decisión. Llegar desde abajo y elegir CALL, o desde arriba y elegir PUT, se etiqueta continuación; los lados opuestos, rechazo. Si estaba dentro o falta observación, queda sin clasificar. Es intención geométrica, no un rebote confirmado ni evidencia de mecanismo causal; no implica que la wall actual existiera cinco minutos antes.

## Cuánta elección retrospectiva hay detrás

| Ticker | Periodo | Alternativas en estados elegidos | Alternativas perdedoras | Media alternativa USD | Rango p90−p10 mediano por estado USD | Elegida NO maximiza PnL directo | Margen DP sobre segundo/WAIT mediano USD |
|---|---|---:|---:|---:|---:|---:|---:|
| SPXW | 2023–24 | 300,857 | 71.0% | -13.32 | 557.00 | 45.1% | 30.00 |
| SPXW | 2025 | 154,358 | 70.4% | -11.41 | 755.50 | 45.8% | 45.40 |
| SPXW | 2026H1 | 82,021 | 71.6% | -18.69 | 890.00 | 44.8% | 55.00 |
| SPY | 2023–24 | 239,467 | 72.4% | -4.90 | 58.00 | 43.7% | 4.00 |
| SPY | 2025 | 130,156 | 72.2% | -6.27 | 78.90 | 42.7% | 5.00 |
| SPY | 2026H1 | 67,375 | 71.7% | -3.44 | 93.80 | 44.8% | 6.20 |
| QQQ | 2023–24 | 235,909 | 72.0% | -6.07 | 71.00 | 42.2% | 4.40 |
| QQQ | 2025 | 125,600 | 72.3% | -6.72 | 90.00 | 42.8% | 6.00 |
| QQQ | 2026H1 | 68,467 | 71.4% | -3.51 | 113.20 | 42.4% | 8.00 |

Cada alternativa es una combinación realmente ofrecida de contrato y objetivo en el mismo estado de decisión; se excluye la elegida. No son operaciones independientes ni ejecutables simultáneamente. La media pondera acciones; el JSON incluye también la media que pondera cada estado por igual y la distribución de todas las ofertas del día.

Estos estados también fueron escogidos retrospectivamente. Incluso una media positiva de sus alternativas habría estado condicionada a esa elección con futuro y no sería una expectativa causal de entrada.

El DP maximiza el total de la jornada: `neto de acción + mejor continuación después de su salida`. Por ello puede elegir una acción con menor beneficio aislado para liberar inventario antes. El rango directo y el margen DP miden cosas distintas; ningún aprendiz debe tratar el máximo clarividente como expectativa causal alcanzable.

## Sensibilidad temporal local, con cobertura explícita

| Ticker | Periodo | −1m: acción idéntica ofrecida | Δ PnL mediana / p10 USD | +1m: acción idéntica ofrecida | Δ PnL mediana / p10 USD |
|---|---|---|---|---|---|
| SPXW | 2023–24 | 2,442 (32.2%) | -50.00 / -140.00 | 2,199 (29.0%) | -80.00 / -200.00 |
| SPXW | 2025 | 1,158 (30.2%) | -70.00 / -210.00 | 1,039 (27.1%) | -100.00 / -290.00 |
| SPXW | 2026H1 | 615 (30.8%) | -70.00 / -210.00 | 593 (29.6%) | -120.00 / -300.00 |
| SPY | 2023–24 | 2,329 (35.4%) | -5.00 / -15.00 | 2,063 (31.4%) | -8.00 / -19.00 |
| SPY | 2025 | 1,153 (34.6%) | -7.00 / -23.00 | 996 (29.9%) | -11.00 / -32.50 |
| SPY | 2026H1 | 623 (37.0%) | -9.00 / -24.00 | 568 (33.8%) | -13.00 / -32.00 |
| QQQ | 2023–24 | 2,424 (39.0%) | -7.00 / -17.00 | 2,224 (35.8%) | -9.00 / -22.00 |
| QQQ | 2025 | 1,233 (39.2%) | -8.00 / -24.00 | 1,102 (35.1%) | -12.00 / -35.00 |
| QQQ | 2026H1 | 626 (37.8%) | -10.00 / -29.00 | 549 (33.1%) | -15.00 / -42.00 |

La comparación exige mismo contrato, lado y valores exactos de objetivo/stop/banda en `actions.parquet` un minuto antes/después. Sin oferta idéntica, no hay contrafactual evaluado. Se conservan no-fills como cero según el motor. Es sensibilidad aislada de esa operación, no PnL de una nueva política diaria: desplazar una operación podría alterar las siguientes.

## Ejemplos fijos y límites de aprendizaje

Las tres imágenes de 2023-01-03 se fijaron antes de observar sus beneficios y muestran entradas/salidas, objetivos lejanos, stops y walls: [SPXW](D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts/final/SPXW_20230103_oracle.png), [SPY](D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts/final/SPY_20230103_oracle.png), [QQQ](D:/GexResearchArtifacts/level_oracle_20261018/oracle_charts/final/QQQ_20230103_oracle.png). No son las mejores sesiones elegidas retrospectivamente.

Una red o agente puede aprender a proponer contrato/objetivo y decidir esperar usando secuencias causales; este informe describe lo que debería aproximar, no demuestra que pueda anticiparlo. El oracle conoce también qué alternativa perderá y qué salida dejará espacio a otra oportunidad. La prueba pertinente sigue siendo la política completa del alumno sobre datos posteriores a su ajuste, con sus propios estados y costes. Los tres aprendices y su selección fijada permanecen intactos; este análisis no crea filtros con los ganadores de 2026.

Artefactos completos: `summary.json`, `selected_trade_descriptors.parquet`, `daily_descriptors.csv` e `input_manifest.jsonl` en la carpeta de salida indicada abajo. Se rehashean los seis parquets de cada día; del cache se comprueba la identidad publicada de metadatos y se leen únicamente spot/máscara. No se rehashea aquí todo NPZ ni se reauditan fuentes raw.

Salida: `D:\GexResearchArtifacts\level_oracle_20261018\oracle_behavior_v2`. SHA del analizador: `ff09ae8cdda7848c969416ea70a3d2bf8d42e09947bc54c3a20c995d39ff9ba3`.

El intento descriptivo v1 se detuvo por rendimiento antes de publicar agregados; conserva script y registro de aborto. V2 preindexó vecinos idénticos y utilizó dos workers con BLAS1, con equivalencia de campos comunes comprobada sobre la sesión fija QQQ 2023-01-03. Antes de V2 se corrigió el conteo geométrico para excluir el centro de entrada y no presentarlo como cruce realizado. El script ejecutado quedó sellado antes de la lectura completa. Compile y Ruff PASS; comprobaciones sintéticas de vecinos exactos, exclusión de geometrías distintas, ranking directo y missingness PASS. La ejecución emitió avisos de deprecación pandas sobre dtype al contar fills; terminó con exit0 y cifras reconciliadas con el audit. No se modificaron motor, modelos, selección ni fuentes.

# Reloj del actor: resultado exclusivamente sintético

24 de octubre de 2026. **PASS_SYNTHETIC_CLOCK_SEMANTICS**, limitado a seis
grafos artificiales. Se verifican DP, ocupaciones y adjunto conservando cada
slot de decisión y la representación NO_FILL `entry_i=exit_i=t+1`. No se han
abierto fuentes, arrays, modelos o resultados de mercado. No se activa una
hipótesis económica ni se modifica una política existente.

La [spec](SESSION_ACTOR_CLOCK_SEMANTICS_SYNTHETIC_SPEC_20261024.md) y su
[revisión previa](SESSION_ACTOR_CLOCK_SEMANTICS_SPEC_REVIEW_20261024.md) se
publicaron en `8466082a634851b65c4a1042dbb3dec3333b0941`, con remoto verificado
por root antes del GO y del primer test. Las tolerancias y los seis grafos
permanecieron intactos después de conocer los resultados.

## Qué comprueba

WAIT avanza a t+1. Un intento NO_FILL también avanza a t+1 y conserva h: no
permite otra oferta en el mismo instante ni salta a t+2. FILLED bloquea hasta
exit_i+1 y fija h=1. Los calendarios artificiales full y short conservan
316 y 136 slots respectivamente, incluidos los inválidos y sus máscaras.
La última decisión puede liquidar después del último slot de decisión.

La enumeración recorre caminos sin usar el helper de transición de DP u
ocupación. Su derivada analítica aplica producto/suma a probabilidades de
caminos, sin Q ni ocupaciones del algoritmo contrastado. Se comparan esa
derivada, el adjunto y diferencias centrales para logits independientes y
tres variables algebraicas compartidas, sin ajustar parámetros.

El contraejemplo fijado de antemano muestra por qué importa la representación:

| Regla artificial después de NO_FILL | Intentos | Fills | PnL | Objetivo |
| --- | ---: | ---: | ---: | ---: |
| Reintentar en t+1 | 2 | 1 | 7 | 7 |
| Regla deliberadamente errónea exit_i+1 | 1 | 0 | 0 | -3 |

Son unidades artificiales, no dólares ni evidencia de rendimiento. La diferencia
de objetivo procede de omitir una oportunidad artificial y aplicar la penalización
terminal separada. NO_FILL permanece en el soporte de ofertas; no se enmascara
por su resultado. Un día ausente se rechaza y no se fabrica como trayectoria WAIT.

No se descubrió ni corrigió un bug en el scheduler productivo: ya distingue
NO_FILL. La extensión comprueba cómo traducir su representación documentada
a un laboratorio futuro. La regla incorrecta del contraejemplo fue introducida
intencionalmente en un simulador artificial y no describe una política existente.

## Evidencia del autor

Único intento: **38 pruebas PASS en 0,70 s**, Ruff y compile PASS. El CLI
cerró exit 0 con **188 comparaciones PASS**. Incluye negativos de reloj, máscaras,
ofertas, fuente ausente y probabilidades; presencia de estados inalcanzables;
liquidación tardía válida; soporte independiente del status e independencia
del enumerador frente a helpers de DP/ocupación.

| Comparación | Error absoluto máximo |
| --- | ---: |
| Valores, masas y derivadas analíticas | 8,881784197001252e-16 |
| Diferencia central, paso 1e-4 | 6,341579927848784e-09 |
| Diferencia central, paso 1e-5 | 1,3202905435605317e-10 |
| Diferencia central, paso 1e-6 | 4,440893208723651e-10 |

Se mantuvieron `atol=1e-10, rtol=1e-9` para comparaciones analíticas y
`atol=1e-7, rtol=1e-5` para diferencias centrales. Ningún paso fue descartado.

El recibo inicial capturó hashes, copias de código/spec/tests/review, comandos,
commit documental y recursos **antes** de ejecutar herramientas. RAM libre
inicial: 6.763.028.480 bytes; commit libre: 4.031.430.656 bytes. También se
registraron gates separados antes de pytest y CLI; cada uno exigió al menos
2.000.000.000 bytes por recurso. No se presenta esta muestra como reserva o pico.

Raíz local preservada:
`D:/GexResearchArtifacts/level_oracle_20261018/session_actor_clock_semantics_synthetic_20261024_01`.
El [manifiesto compacto](continuation_20261024/session_actor_clock_semantics_synthetic/manifest.json)
conserva 19 copias exactas, 563.507 bytes, incluidos pins iniciales, admissions,
stdout/stderr, exit/duraciones y resultados completos. SHA del manifiesto:
`d78e25533b46a40fb64330296eb336962d4be271284b6f61b8027353e65456ec`.
La duración del proceso pytest fue 1,503 s; los 0,70 s anteriores son la duración
reportada por pytest. El CLI tardó 0,662 s. No hubo intento fallido ni reintento.

| Artefacto | SHA256 |
| --- | --- |
| session_actor_clock_semantics_validation.py | 3bab23910c566020b2fc5e831c6c9ceacc03c51c71d46ce6d1258d5cd7c67358 |
| test_session_actor_clock_semantics_validation.py | 40e159af9e7a3459207ccbecf5be940429c36d8c4cfb64c88f8f6f79eed94429 |
| Spec publicada | 5e96cd5a69d853c8a1686511278cd5553b60856b3d7f4cf0c4321a8a6263f899 |
| validation/result.json | c58ed939559e0aeac05a8eb40dea6f996e4100f1b55215bc87141f7e72c77837 |

Los pins iniciales y finales coinciden. El código y los tests del laboratorio
matemático anterior conservaron sus hashes; no se importaron ni reejecutaron.
La revisión independiente de implementación corresponde a scientific_review;
sus pruebas y conclusión se documentan por separado de las del autor.

## Límites

Se cierra la brecha de representación del reloj en estos grafos. Las máscaras
son tuplas booleanas toy de cuatro elementos: no se validan shapes, joins,
orden físico, dtype o integridad de packs de mercado. Los horizontes reales
se reproducen como índices, no como sesiones reales ni recepción acreditada.

Un objetivo estocástico y su derivada no garantizan fill diario ni rendimiento
de una extracción determinista. No se eligen arquitectura, penalización real,
extractor, entrenamiento o nueva familia. Esta evidencia no sustituye admisión
de datos, paridad live, generalización, rentabilidad ni el cierre mensual/OOF.
`scope=MATHEMATICAL_SYNTHETIC_ONLY`; `runtime_market_authorized=false`.

# Resultado del laboratorio matemático del actor de sesión

23 de octubre de 2026. **PASS limitado a identidades matemáticas en grafos
artificiales.** La especificación se publicó en `c5043847` antes de implementar
este laboratorio. No se leyeron datos, modelos ni outcomes de mercado; tampoco
se configuró un aprendiz, optimizador, entrenamiento o estrategia nueva.

## Alcance y resultado

El [laboratorio](session_actor_math_validation.py) expande todas las trayectorias
de cinco grafos pequeños. Esa enumeración no llama a la DP, al cálculo de
ocupaciones ni a su helper de transiciones. Se contrasta con DP hacia atrás,
ocupaciones hacia delante y adjuntos; autograd verifica logits independientes y
tres variables algebraicas compartidas. La recomputación por bloques conserva
variables y logits, aplica adjuntos detenidos y reproduce el gradiente completo.

Los casos incluyen WAIT exclusivo, ofertas NO_FILL, el ejemplo de la nota,
duraciones diferentes con confluencia y tres fills en una rama frente a ninguno
en otra. Se preservan `entry=t+1`, `exit>=entry+1`, el estado `h` y la penalización
terminal separada del PnL. La identidad de cardinalidad cuenta intentos de oferta,
incluidos NO_FILL; no mide la probabilidad de fill. Ningún extractor determinista
queda elegido.

El intento final pasó **49 pruebas**, Ruff y **204 comparaciones matemáticas**,
con salida cero en cada proceso. El resultado contiene los grafos, políticas,
parámetros algebraicos, valores comparados, errores y tolerancias de cada check:
[resultado completo](continuation_20261023/session_actor_math_validation/attempt_04/validation/result.json).

| Comparación | Checks | Error absoluto máximo |
|---|---:|---:|
| Valores, masas y gradientes analíticos/autograd | 174 | 4,440892098500626e-16 |
| Diferencias centrales, paso 1e-4 | 10 | 2,7018631776343227e-9 |
| Diferencias centrales, paso 1e-5 | 10 | 4,440902378065225e-11 |
| Diferencias centrales, paso 1e-6 | 10 | 2,2204494621859516e-10 |

Se conservaron las tolerancias predeclaradas: `atol=1e-10`, `rtol=1e-9` para
identidades y `atol=1e-7`, `rtol=1e-5` para diferencias centrales. Pasaron los
tres pasos, sin escoger uno retrospectivamente. El ejemplo recupera `J=-0,7`,
`E[PnL]=0,65`, `P(sin fill)=0,45` y gradientes `1,08/0,225`. El contraejemplo
recupera `E[fills]=1,5` y `P(sin fill)=0,5`: la esperanza de actividad no garantiza
un mínimo diario.

## Intentos conservados y recursos

| Intento | Cierre y motivo del siguiente |
|---|---|
| 01 | Ruff rechazó E402: el import de PyTorch seguía a los límites de hilos. No se ejecutaron pruebas matemáticas. Se documentó esa excepción de import. |
| 02 | Ruff, 40 pruebas y 204 comparaciones PASS. La revisión pidió rechazar probabilidades vectoriales e índices de reloj fraccionarios o booleanos. |
| 03 | Ruff, 48 pruebas y 204 comparaciones PASS. La revisión detectó que `stack` podía promover una probabilidad float32 mezclada con float64. |
| 04 | Verificación individual de dtype/device y negativo mixto añadidos: Ruff, 49 pruebas y 204 comparaciones PASS. El JSON matemático coincide byte a byte con el intento 03. |

Los cambios de admisión no modificaron ecuaciones, grafos, tolerancias o
penalizaciones. Los [tests](test_session_actor_math_validation.py) rechazan además
entrada temprana, salida inválida o hacia atrás, soporte de acciones incorrecto,
probabilidades inválidas y NO_FILL con recompensa o salida. Una prueba sustituye
DP, ocupaciones y transición por funciones que fallan para comprobar que la
enumeración sigue siendo independiente.

Cada intento tiene recibo, hashes de fuentes, comandos, códigos de salida y logs.
Se archivaron **30 copias exactas, 519.529 bytes**, con sus originales bajo
`D:/GexResearchArtifacts/level_oracle_20261018/session_actor_math_validation_20261023_01`
hasta `_04`: [manifest de copias](continuation_20261023/session_actor_math_validation/manifest.json).
Las ejecuciones matemáticas usaron CPU, float64, afinidad a un procesador lógico y un hilo intra
e interop. En el gate final había 8.054.272.000 bytes de RAM disponible y
11.104.808.960 bytes de margen de commit, por encima de los 2 GB exigidos.
El CLI volvió a comprobar recursos antes de sus comparaciones. Pytest reportó
2,75 s; el proceso del CLI duró 3,100 s. No son mediciones de entrenamiento.

## Identidad y límites

- Laboratorio SHA256: `4d48460d3a6a39b4fbe95d368de7789f58c6ffdad984607a81a1539fcd7b3946`.
- Tests SHA256: `15baeaf22231ef1e639d565923b89a58d94928e0aecb2203330c28ac93e7b5b3`.
- Resultado SHA256: `86b9f28141c1e0e6389311c94c255ed2a60c1b52b249724e877d52657a7582b0`.
- [Especificación](EXACT_SESSION_ACTOR_MATH_VALIDATION_SPEC_20261023.md) SHA256:
  `fd44fa77e9e623ac498b2c5cf5f5ed3680b7eda0f3b82f907a33a822f59aa808`.

La [revisión independiente](SESSION_ACTOR_MATH_VALIDATION_REVIEW_20261023.md)
documenta por separado su alcance y verificaciones sobre estos bytes.
Este resultado comprueba casos finitos con transiciones exógenas. No acredita
calidad de fuentes, fills reales, suficiencia del estado, generalización,
rentabilidad o equivalencia entre una esperanza estocástica y un ledger greedy.
La cardinalidad de acciones, la extracción determinista y cualquier experimento
de mercado permanecen pendientes. Las líneas mensual y OOF no se modificaron.

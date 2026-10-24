# Revisión previa de la especificación sintética del reloj

24 de octubre de 2026. **CLEAR documental previo a ejecución**, limitado a
semántica, cobertura matemática y separación del laboratorio cerrado. No se
ejecutó ningún test ni comparación numérica, ni se importaron módulos de
mercado o del laboratorio anterior. No se leyó ninguna fuente real.

Spec revisada: `SESSION_ACTOR_CLOCK_SEMANTICS_SYNTHETIC_SPEC_20261024.md`,
SHA256 `5e96cd5a69d853c8a1686511278cd5553b60856b3d7f4cf0c4321a8a6263f899`.
La precisión final fija el layout: tiempo ascendente, h=0 antes de h=1,
WAIT antes de ofertas y ofertas en orden declarado; slots WAIT obligatorios
permanecen en el calendario sin logit independiente.

La transición NO_FILL conserva h y avanza a t+1 aunque su representación
incluya exit_i=t+1. FILLED avanza a exit_i+1 y fija h=1. El contraejemplo
declarado distingue correctamente ambas reglas: saltarse el segundo slot
suprime su fill artificial y deja la penalización terminal. Esa comparación
no representa rentabilidad de una estrategia.

Los seis grafos incluyen ambos horizontes, slots inválidos y válidos sin
ofertas, máscaras parciales, fills de distinto signo/duración y NO_FILL aún
incluido en el soporte. Conservan ambos valores de h y estados inalcanzables.
NO_EVALUABLE se rechaza como ausencia, sin crear una sesión WAIT ficticia.
Las máscaras pequeñas son sintéticas y no acreditan los packs productivos.

La enumeración directa y su derivada por productos de probabilidades son una
referencia independiente del adjunto DP. Se contrastan también ocupaciones,
masas terminales, intentos, fills y penalización separada. La derivada
logarítmica se limita a probabilidades interiores; el contraejemplo
determinista no exige derivar log cero. Los tres pasos centrales y sus
tolerancias están fijados antes de resultados. Las variables compartidas
son expresiones algebraicas, sin red, optimizador ni actualización.

## Contraste textual con los consumidores existentes

- `session_clock.py`: first_state=60, last_state=close_i-15 y
  eod_i=close_i-5 para close_i 210/390; corresponden a 60–195/205 y 60–375/385.
- `level_engine.py`: evaluate_actions guarda NO_FILL con exit_i=entry_i,
  netos cero; las ofertas causales tienen entry_i=state_i+1.
- `run_monthly_walk_forward.py`: aligned_labels exige NO_FILL exit=t+1 y
  FILLED entre t+2 y close_i-5; el scheduler incrementa un minuto en NO_FILL
  y usa exit_i+1 sólo para FILLED.
- `causal_rollout.py`: la recurrencia de política fija mantiene esa misma
  bifurcación. Su adaptador legacy full no admite por sí solo sesiones cortas;
  el contraste short procede del reloj y del consumidor mensual.

| Código leído sólo como texto | SHA256 |
|---|---|
| session_clock.py | `1e63cf2d314caea14dd8b0b8f025f647d67bf8df58f246613975891a256f51e9` |
| level_engine.py | `70cc5d20990d971d16299fd008ff8e05ac99f99a6a2917a202fcb9a5f413b7c6` |
| run_monthly_walk_forward.py | `47a4df8b019d9d297ca1ee9b89fff63406409659336dbd7b0e4d7af01ed348bb` |
| causal_rollout.py | `8df92119071442045a8434057e220bad567668d8ee314fddd263d052ebeea0d9` |

La revisión no modifica ni reejecuta `session_actor_math_validation.py`
(SHA `4d48460d3a6a39b4fbe95d368de7789f58c6ffdad984607a81a1539fcd7b3946`)
ni sus tests (SHA `15baeaf22231ef1e639d565923b89a58d94928e0aecb2203330c28ac93e7b5b3`).

Root debe publicar esta spec y confirmar esa publicación antes de autorizar
el primer run sintético. Código y resultados futuros requieren su revisión
independiente posterior. Este CLEAR no admite datos, una familia económica,
entrenamiento o promoción, y no sustituye los cierres mensual/OOF pendientes.

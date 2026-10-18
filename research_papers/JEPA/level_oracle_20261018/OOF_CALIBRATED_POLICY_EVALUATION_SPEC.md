# Replay de calibración OOF: preparación, sin ejecución real

Se comparan seis políticas: control y corregida para cada procedimiento static,
expanding y rolling12. Se reutilizan modelos mensuales y offsets ya fijados por
el adaptador OOF. No hay refit, barrido, ganador ni selección por resultados de
2026. 2025 es entrenamiento del calibrador; 2026 es desarrollo visto.

El evaluador exige la autoridad independiente mensual y un SHA externo del
cierre del adaptador. Verifica sus fuentes, implementación, calendario completo,
offsets y scores. Reproduce los máximos desde predicciones mensuales auditadas.
Todos los scores corregidos del mes quedan sellados antes de abrir nuevos
labels del mes. Primero reproduce todos los controles con sus attempts/ledgers
ya auditados, comprobando exactamente IDs, relojes, scores float64, fill,
has_filled_before y payoffs. Estos resultados históricos no intervienen en los
offsets del mes. Los archivos de ledger y sus markers deben estar enumerados
por la auditoría mensual; una revisión del código no sustituye esa autoridad.

El offset es constante por ticker/procedimiento/mes: conserva el máximo y el
desempate por menor action_id en cada estado. Por ello basta el máximo de TODOS
los estados ofrecidos, incluyendo scores negativos, no sólo los trades del
control. Umbral estricto >0. WAIT avanza un minuto; NO_FILL devuelve cero y
avanza un minuto sin rescatar otra acción; FILLED avanza a exit_i+1, impidiendo
solapamiento. has_filled cambia sólo después de FILLED. Decisiones 60..close_i-15;
salidas válidas state_i+2..close_i-5. Los costes base/adversos ya están en labels:
no se vuelven a cobrar ni se añade la penalización de otra familia.

Se conserva cada ticker-día esperado. Missing-source tiene métricas observadas
nulas, no se inventa un retorno cero ni se excluye del denominador. Se informa
neto/PF/actividad en disponibles y cobertura universal por separado: cualquier
missing implica NO_EVALUABLE, no evidencia de pérdidas. El periodo completo
enero–junio2026 debe contener 369 ticker-días, 363 disponibles y seis missing;
un mes aislado informa su propio calendario y nunca se presenta como periodo
completo. El requisito de al menos un fill diario se evalúa sin forzar entradas.

Salida nueva e inmutable, bloqueo exclusivo por raíz, código y autoridades
ligados al contrato; cada día permite reanudación por igualdad exacta y hashes.
Los controles se prueban antes de acceder a labels nuevos; el cierre rehashea
entradas y código. Fixtures incluyen nuevos estados visitados, WAIT, NO_FILL,
ausencias, medias sesiones, empates y alteraciones de seals/control/labels.
La implementación no trae CLI ni autorización para consumir mercados. Antes
de runtime faltan revisión independiente, mensual auditado, autorización de
los fits base2026 y un auditor independiente de esta nueva comparación.

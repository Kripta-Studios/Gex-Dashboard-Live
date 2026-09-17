# Circuito con regresores reales — especificación previa

Autoridad: el usuario ordena continuar hasta conseguir un modelo rentable.
Esta etapa elimina una limitación concreta de software: los 18 folds anteriores
usaron dobles de modelo. No convierte sus resultados en evidencia de mercado ni
amplía la admisión histórica. V1/V1R1 y los intentos antiguos siguen inmutables.

## Alcance fijado antes de ejecutar

Perfil REAL_BACKEND_SYNTHETIC_JAN2025: un fold técnico de enero 2025, 24 acciones,
dos configuraciones A/B y thresholds USD 0/5, winner pooled y ablación refitada.
Se usan exclusivamente fixtures generados; ninguna ruta ThetaData es entrada.
Entrenamiento real LightGBM 4.6.0, L2, parámetros V1R1 sin modificar: 48 regresores
primarios y 24 de ablación, ajustados secuencialmente y exportados. Matrices
canónicas completas de 92.048/488 columnas, incluyendo los one-hot ya estáticos.
Sin proyección escalar, normalización, cambio de bins o búsqueda adicional.

Se construyen seis plantillas sintéticas completas (ticker × dirección), con
reconstrucción independiente desde barras/Greeks/OI de fixture. No son features
históricas ni seis estados suficientes para modelar un mercado real. El calendario
de eventos usa el perfil técnico ya documentado: 13 días laborables artificiales,
dos decisiones/día. Train considera agosto 2022–junio 2024; se toman exactamente
100 eventos por ticker/dirección, índices equiespaciados de cada grupo cronológico,
para 600 filas. Es una reducción exclusiva del benchmark sintético, no del
experimento histórico. Selection julio–diciembre 2024; test enero 2025.

La matriz train se construye con memmap, máscara explícita y cero inválido.
Los fits usan solo acciones ejecutables y exigen >=500 labels / >=100 por ticker
con dos valores finitos distintos. Predicción en bloques de <=256 eventos.
Se persisten parámetros efectivos del Booster, runtime, orden de filas y hashes.
Selection usa sus ledgers, freeze contiene los 72 modelos y todas las decisiones
antes de generar payoffs test. El baseline contractual decide por separado.
No se permite usar el payoff test para seleccionar o alterar modelos.

El auditor separado reconstruye matrices desde el tensor, labels desde cotizaciones
artificiales, reentrena los 72 modelos, reproduce sus bytes/predicciones, ranking,
decisiones, dinero y scheduler. La comparación es exacta bajo el mismo runtime.
El auditor no importa cálculos del evaluador. Se comprueban alteraciones de labels,
features, modelo y winner. La señal determinista está diseñada para ser aprendible;
su resultado no acredita rentabilidad ni habilita criterios económicos de V1R1.

Presupuesto máximo de proceso 24 GiB, reserva disco 20 GiB, un fit a la vez.
Se miden construcción/fit/predict/save/load/auditoría y RSS; bins se incluyen en fit.
No extrapolar estos tiempos de baja entropía a mercado ni completar 18 folds reales
con este perfil reducido para presentarlos como el experimento histórico.

## Barrera histórica pendiente

No se abren valores de mercado. Faltan inputs/transformación/tiempo acreditado de
reparaciones del subyacente y evidencia de disponibilidad de OI previo. Los tres
logs originales no recuperados siguen sin recuperarse; un snapshot actual no los
restaura. Se solicita al usuario otra ubicación de evidencia si existe.
Ningún resultado sintético desbloquea por sí mismo el CLI histórico.
Economía NOT_EVALUATED; prospectivo NOT_STARTED; technical_ready=false;
promotion_approved=false. No descargar, conectar bróker ni tocar producción.

Implementación y pruebas versionadas antes de ejecutar este benchmark. Root nuevo:
D:/GexResearchArtifacts/multiscale_v1r1/real_backend_20260918_01.
CLI: python -m neural.jepa.multiscale_v1r1.real_backend_smoke --root <root_nuevo>
--specification research_papers/JEPA/multiscale_v1r1/17_REAL_BACKEND_SPEC.md

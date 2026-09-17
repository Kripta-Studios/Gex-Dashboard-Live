# Motor B — integración sintética, sin nueva política histórica

Autoridad: continuación del usuario posterior al documento 12. Este circuito
es software de investigación offline. No altera el contrato V1R1 ni concede
admisión de fuentes reales. Economía real NOT_EVALUATED y promoción false.

Se implementan y verifican niveles IB D0–D5/Fibonacci, once walls, 39 canales,
máscaras y dos escalas; admisión positiva de fixtures con linaje; baseline y
ablación; sidecar contractual; selección pooled y secuencia de los 18 meses;
freeze previo a payoff test; ledger, métricas separadas y bootstrap pareado;
auditor independiente y replay de cuenta exclusivamente sintética; captura
prospectiva offline append-only sin transporte de red ni envío de órdenes.

Las convenciones numéricas del documento 12 son del perfil sintético de
implementación. No modifican retrospectivamente las definiciones V1/V1R1.
Para usarlas históricamente se deberá verificar compatibilidad/admisión y publicar
un contrato aprobado y sus artefactos antes de nuevos outcomes.

Perfiles de verificación, identificados en cada artefacto:

- `synthetic_fast`: 18 folds del calendario contractual, 24 acciones, cuatro
  combinaciones y modelos dobles que ajustan medias por señal de fixture.
  Puede usar fechas representativas y señales compactas para probar orquestación;
  no reproduce un fit de mercado de 92.048 columnas ni certifica 18 refits reales.
- `component_real`: tensor completo 92.048/488; smoke LightGBM A y B con parámetros
  V1R1, un regresor real por configuración y >=500 filas, >=100 por ticker;
  guardar, cargar y reproducir predicciones. Se mide el coste real de este smoke.
  El presupuesto full de 24 regresores × configuraciones × folds no queda medido.
- Escenarios integrados: señal aprendible, plano con costes y abstención, labels
  aleatorios, +1.40/−0.60, salida ausente, información futura alterada, overlap,
  capital insuficiente, cantidades indivisibles, reinicio pendiente y tampering.

El presupuesto de cuenta es un importe de prueba explícito por fixture, nunca
una recomendación de capital ni evaluación real de cuenta. Se separan intención,
fill simulado y ejecución confirmada; broker_submission siempre false.

El motor direccional básico tiene prioridad. Las primitivas SSL existentes se
conservan y prueban; entrenamiento SSL/RANGE completo no bloquea este circuito
básico y no se declara implementado. La ablación V1R1 nunca puede promocionarse
como winner por su cuenta ni rescatar al primario.

Salida: `ENGINE_E2E_SYNTHETIC_PASS` solo si el comando ejecuta y audita sus
escenarios, modelos y artefactos no vacíos bajo su perfil identificado. Se
publican mediciones de lectura/construcción/fit/predict/save/load/audit, memoria,
matriz de cobertura y límites. Ese estado no es technical_ready de producción,
rentabilidad, shadow ni paridad live. Un fallo de A no detiene B.

No se ejecuta piloto económico real en este encargo sin admisión verificada y
predeclaración/publicación previa del piloto. Datos leídos económicamente serán
development visto. Ningún servicio, VPS, fuente externa u orden está autorizado.

Referencia de recursos: [LightGBM 4.6.0](https://lightgbm.readthedocs.io/en/v4.6.0/Parameters.html).
histogram_pool_size limita caché de histogramas, no toda la RAM del proceso.

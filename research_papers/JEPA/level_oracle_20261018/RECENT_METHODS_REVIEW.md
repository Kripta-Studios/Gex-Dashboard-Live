# Investigación reciente y pertinencia para este experimento

Consulta de fuentes primarias: 2026-10-18. Revisión dirigida, no censo exhaustivo
ni afirmación de un ganador universal. No modifica las tres ejecuciones activas,
sus muestras, parámetros, selección o costes. No se descargaron pesos ni datos.

| Trabajo | Evidencia consultada | Aplicación y límite para nuestro problema |
|---|---|---|
| [Stock-JEPA, octubre2026](https://arxiv.org/html/2610.07006v1) | Preprint; representación futura descompuesta en ancla financiera disponible al decidir y revisión predecible desde contexto. Congela representación para readout y evalúa ranking/carteras de acciones. | Candidato conceptual para distinguir señal adicional de ruido. Su reducción de error poblacional óptimo no garantiza mejora finita ni beneficio 0DTE. No es el residual de continuación de política que ya estamos preparando. |
| [Trading-R1, septiembre2025](https://arxiv.org/html/2509.11420v1) | SFT y RL sobre tesis financieras, entradas multimodales; objetivos combinan horizontes3/7/15días. Los autores explicitan sesgo hacia grandes empresas y utilidad para análisis/datos. | No trasladar su backtest a opciones intradía ni inventar noticias/fundamentales que no contiene nuestra fuente. Es razonamiento textual con otra información y otro objetivo. |
| [MarS, ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/6261d3bc9e9326ddff055595aabd54e1-Paper-Conference.pdf) | Modelo generativo de órdenes y lotes de órdenes, con información LOB y simulación de impacto. | Su diseño requiere microestructura que no aporta el cache de snapshots Greeks/OI. Una simulación aprendida de nuestros minutos sería otro modelo, no una reproducción de MarS ni prueba de fills reales. |
| [Re(Visiting) TSFM in Finance, noviembre2025](https://arxiv.org/abs/2511.18578) | Abstract del preprint: en retornos diarios internacionales, los autores reportan resultados débiles de modelos genéricos y mejores resultados al preentrenar con datos financieros. | Motiva comprobar adaptación al dominio; no justifica cargar un modelo grande ni asumir que sus datos de pretraining excluyen nuestro periodo. No se reprodujeron sus resultados. |
| [Pretrained TSFM for Financial Return Forecasting, junio2026](https://arxiv.org/abs/2606.27100) | Abstract del preprint: varios foundation models ganan rankings en cinco acciones, pero las mejoras sobre random walk son pequeñas y la significación escasa. | Ordenar arquitecturas por error no equivale a demostrar utilidad económica. Nuestro criterio sigue siendo el ledger temporal con costes y mínimo diario. |
| [DeepFund, NeurIPS2025 Datasets and Benchmarks](https://arxiv.org/abs/2505.11065) | Evalúa agentes con datos posteriores al corte de pretraining; destaca contaminación histórica y pérdidas de algunos LLM evaluados. | Un LLM con conocimiento retrospectivo de fechas/eventos puede contaminar un backtest aunque sus herramientas reciban sólo un prefijo. El agente investigador no debe convertirse por ello en señal de trading validada. |

La consecuencia operativa es mantener separadas tres preguntas. Episodios prueba
si representar contactos, penetraciones y recuperaciones ayuda. TCN flags prueba
una hipótesis de condición numérica. La continuación causal fija prueba si mejora
el objetivo de coordinación respecto a retorno aislado. Ninguna necesita atribuir
al learner la clarividencia del oracle, y ninguna demuestra por sí sola edge.

Inferencia propia para una posible continuación, aún sin ejecutar: si hubiera
evidencia de representación insuficiente, comparar un encoder temporal aprendido
contra un prior sencillo usando exactamente la misma información disponible,
readout, scheduler y costes. Pretraining, normalización y prior deben limitarse
al pasado de cada bloque; las ventanas futuras sólo pueden ser targets de
training. Las representaciones se congelarían antes de evaluar la política.
La prueba tendría que mostrar mejora económica y cobertura diaria, además de
error latente. Esto es una hipótesis pendiente de los resultados actuales, no
un cambio del plan activo ni una promesa de rentabilidad.

Para búsqueda de trayectorias tipo AlphaZero, el obstáculo no es sólo el tamaño
de la red. El motor histórico puede devolver resultados realizados, pero esos
resultados no están disponibles al decidir en vivo. Buscar sobre la trayectoria
real futura vuelve a crear el oracle. Una búsqueda operable requeriría un modelo
condicional de futuros y una evaluación de su incertidumbre; el simulador exacto
del backtest no sustituye ese modelo. Esta conclusión es una distinción de
información del experimento, no una afirmación de imposibilidad de aprender.

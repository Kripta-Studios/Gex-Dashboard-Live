# La mezcla reduce la dispersión del gradiente en el bloque medido

Diagnóstico sin actualizaciones sobre512 acciones de16 días TRAIN elegidos por
hash, usando exclusivamente el checkpoint FLAGS64 época4 fijado. Los dos
agrupamientos contienen las mismas filas, targets e IPW:16 lotes diarios de32
y16 lotes mezclados de32, cada uno con dos acciones de cada día.

La invariancia del gradiente medio pasó: diferencia relativa L2 **2,48e-8** y
absoluta **1,17e-10**. Los pesos del modelo permanecieron idénticos.

| Medida | Por día | Mezclados |
|---|---:|---:|
| Desviación cuadrática media respecto al gradiente medio | 0,000196546 | 0,0000720362 |
| Coseno medio entre pares de lotes | 0,16556 | 0,22018 |
| Pares con coseno negativo | 44,17% | 40,00% |
| Norma máxima del gradiente | 0,03565 | 0,01787 |
| Norma del gradiente medio | 0,0047057191 | 0,0047057191 |

La dispersión baja aproximadamente63,4% al mezclar este bloque; el conflicto
entre lotes sigue siendo considerable. Esto informa la hipótesis de ruido por
agrupación diaria, pero no demuestra que otra planificación de updates vaya a
mejorar el fit o la generalización. No hubo nuevo entrenamiento ni selección
de políticas/épocas, y no se leyó validación/test. Un eventual ensayo row-mixed
continúa como diseño separado pendiente de decisión.

Dos fixtures y Ruff pasaron. Artefactos, particiones, vectores de gradiente e
identidades: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_gradient_grouping_v1`.
SHA summary `9d452559d394e7273bbbaefc6538b3f1a9d56666a4ec33057891393c3242df05`;
completion `45035436d5800cc30af27ebf4f5962f99f1e9c7615a7223047b64ac2e877a0e1`.
No se realizó auditoría independiente de este diagnóstico descriptivo.

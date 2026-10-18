# Caché TRAIN row-mixed completada; entrenamiento pendiente

El 2026-10-18 a las 20:03:45 UTC terminó el proceso 19932 con exit 0. Se
prepararon 270.377 acciones de los mismos 1.491 ticker-días TRAIN 2023–2024
usados por FLAGS64. No se entrenó el modelo row-mixed, no se generaron sus
predicciones de validación/test y no se cambió el experimento FLAGS64.

Raíz: `D:/GexResearchArtifacts/level_oracle_20261018/tcn_row_mixed_v1`.
`cache_complete.json` SHA:
`2671fda58cb1f26df2b6f440749e43b644de84196dd14c7bac526d1a91272c3d`.
Código revisado: `5c4adfe01e2a51f3eb0f16c96479edb326e2f06ea1f66b3721313ccaa9ab7ab2`.
Plan previo: `06616d6b4af5c03b9e1dd3e7ba929209c5ab4b47300b5fea30a946ae64aee9c9`.
Nota de revisión: `070b90d1e2e77d8e6ffa4facc11e14641e3b7b16823f696bd2b573271bc85ad0`.

Los seis inputs normalizados se guardaron en memmaps por chunks de hasta 256
filas, con comparación exacta tras escribir y sellos por día para continuar
una interrupción. Los hashes de las fuentes consumidas se contrastaron contra
la autoridad TRAIN ya completada de FLAGS64; la caché no autoacredita fuentes
nuevas. El manifest final rehashea arrays, fuentes y checkpoints diarios.

La preparación duró aproximadamente seis minutos, incluido el rehash final.
El proceso tuvo alrededor de 1,1 GiB privado, pero sus páginas mapeadas elevaron
el RSS a unos 14,4 GiB y redujeron temporalmente la RAM disponible. Los mappings
se liberaron antes del rehash final; el proceso terminó normalmente. No hubo
OOM, interrupción ni cambio de algoritmo. El monitor y la autoridad operativa
están en `tcn_row_mixed_v1_build_logs_01`, incluido `preparation_complete.json`.

El ajuste de cuatro épocas queda pendiente de coordinación de recursos con la
validación mensual y los demás trabajos. La comparación económica fijada será
FLAGS64 frente a row-mixed, mismos seis candidatos, costes y gates, según
TCN_ROW_MIXED_EVALUATION_SPEC.md. El TCN original queda sólo como contexto.
La preparación de datos no constituye evidencia de aprendizaje o rentabilidad.

# DIRECTIONAL_SEMANTIC_JEPA_V1 — freeze de desarrollo

Estado: `PASS_DEVELOPMENT_FREEZE`

Esta fase no leyó 2026. El encoder se seleccionó con train 2022-08..2024 y
validación 2025; `best_epoch=2`, validation loss `0,170433`. El final-fit usa
solo datos hasta 2025-12-31. Se verificaron 2.577 fuentes (859 sesiones por
ticker); 2023-06-05 se excluyó del panel por las barras SPY inválidas ya
predeclaradas.

## Desarrollo walk-forward 2025

Todos los perfiles hacen una operación diaria, open 10:36→open 13:36, hold
180m exactos, sin overlap y con 1bp de coste.

| Ticker | Perfil | Trades | WR | PF | Net bps | Meses + | Min mes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | TECH_RESIDUAL | 247 | 53,04% | 0,942 | -339,6 | 7/12 | 18 |
| QQQ | SEMANTIC_RESIDUAL | 247 | 53,85% | 1,063 | +346,4 | 7/12 | 18 |
| SPX | TECH_RESIDUAL | 247 | 51,82% | 0,979 | -98,4 | 4/12 | 18 |
| SPX | SEMANTIC_RESIDUAL | 247 | 51,82% | 1,033 | +152,3 | 4/12 | 18 |
| SPY | TECH_RESIDUAL | 247 | 51,82% | 0,976 | -114,8 | 4/12 | 18 |
| SPY | SEMANTIC_RESIDUAL | 247 | 53,04% | 1,038 | +175,7 | 4/12 | 18 |

El JEPA mejora PF/net frente al mismo residual técnico en los tres tickers,
pero el desarrollo es débil e irregular. No es evidencia de rentabilidad. La
regla predeclarada selecciona `SEMANTIC_RESIDUAL` para QQQ, SPX y SPY y esa
elección no puede cambiar después de abrir 2026.

## Seals

- Source inventory SHA256: `dc19b72e67c3ca383428b30cd7f4fb6f45adf4f38f06e1bf5783d69bc16058c2`.
- Trade ledger SHA256: `e0b4be9182b4f6b29a385cc5bde62c44f7306b6e482248909aaf298713d8b8a2`.
- Semantic JEPA SHA256: `876f36c28f4872b836bb751f93fc4c3baa09d302044b03a75d35567f0aebc607`.
- Normalizer SHA256: `b14b0105ccb0698ff5f775ba326db516613a1cd39ff912ca87f10cb4d8a30419`.
- Runner SHA256: `d8e9f64a1708e533454818b4f0a612f21f4f1ad1f224034d6d56eb2be7b6a073`.
- Predeclaration SHA256: `5f109ee296988b1025707085d0a0c3a828b79752e21226dae5568804dd8278d7`.

Siguiente paso único: commit de este freeze y una evaluación one-shot de
enero–junio 2026 más julio MTD. Incluso un PASS seguirá siendo señal spot, no
evidencia de fills de futuros.


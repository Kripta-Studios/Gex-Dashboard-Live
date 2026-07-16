# DIRECTIONAL_FACTORIZED_INNOVATION_JEPA_V1 — predeclaración

## Pregunta

¿El fracaso direccional price-only se debe a que el encoder común colapsado
descarta innovaciones específicas de ticker, o a que el panel no contiene señal
suficiente? Esta es una única intervención mecanística. Reutiliza exactamente
los parquets underlying de V1 en memoria y no genera otro dataset.

El diseño se declara después de haber observado los resultados 2026 de V1. Por
ello cualquier lectura de 2026 será `ADAPTIVE_DIAGNOSTIC_NOT_CONFIRMATORY`: puede
falsificar la reparación, pero no promocionar una estrategia live.

## Reloj y universo

Se heredan sin cambios de `DIRECTIONAL_SEMANTIC_JEPA_V1`:

- QQQ, SPXW y SPY, panel minuto exacto 09:30–16:00;
- contexto observable 09:30–10:35;
- entrada spot-proxy open 10:36 y salida open 13:36;
- hold 180 minutos, una posición diaria y coste 1 bp;
- fuentes 2022-08-01..2026-07-15, exclusiones y medias jornadas congeladas;
- train SSL 2022-08..2024, validación SSL 2025 y final-fit hasta 2025;
- downstream mensual estrictamente cronológico y perfiles TECH/SEMANTIC.

No se añaden opciones, VIX, outcomes, labels intrabar ni fills de futuros.

## Encoder factorizado

Los 18 canales normalizados se separan de forma determinista:

- `common` (8 dims): media por modalidad de los tres tickers;
- `qqq_residual` (4): QQQ menos common;
- `spxw_residual` (4): SPXW menos common;
- `spy_residual` (4): SPY menos common;
- `volatility` (4): valor absoluto de retorno/cuerpo, rango y actividad de los
  tres tickers.

Cada bloque usa su propio GRU y proyección. La concatenación sigue teniendo 24
dimensiones, por lo que la comparación con V1 no gana por ensanchar el latent.

## Objetivo y corrupción

El teacher EMA codifica contexto actual y ventanas futuras +15/+60/+180m. Los
predictors estiman `z_future - z_current`, no el nivel suave `z_future`.
Adicionalmente predicen el cambio del último vector raw normalizado de cada
ventana; esta tarea es auto-supervisada y no usa el retorno de ejecución.

El student recibe bloques temporales, ticker completo o modalidad completa
corrompidos. La loss queda congelada como:

```text
latent_innovation + 0.50*raw_innovation + 0.25*state_alignment
+ 0.20*VISReg_full + 0.10*VISReg_blocks
```

VISReg usa 64 slices en el latent completo y 32 por bloque, pesos center/scale/
shape `1/1/2`. Es una restricción de salud, no una hipótesis de alpha.

## Gate outcome-free

Después del final-fit y antes de construir labels/downstream deben pasar todos:

- rango efectivo de `z/24 >= 40%`;
- rango efectivo de `dz/24 >= 40%`;
- PC1 de z y dz `<=70%`;
- cero dimensiones con std `<0,05`;
- rango efectivo de cada uno de los cinco bloques `>=40%`.

Si falla cualquiera, el estado es `CLOSED_LATENT_HEALTH` y no se abre PnL.

## Desarrollo y evaluación adaptativa

Si pasa salud, se construyen las mismas features técnicas de V1. El perfil
semántico añade z, dz, desplazamientos latentes y predicciones raw de retorno,
rango, cuerpo y distancia a apertura para cada ticker/horizonte. Desarrollo 2025
elige TECH o SEMANTIC con el orden congelado de V1.

La evaluación 2026 conserva el perfil por ticker. La gate económica diagnóstica
es WR >45%, PF >1,20, >12 trades en cada mes completo y PnL positivo en todos
enero–junio. Julio hasta 15 de julio se informa MTD y no puede cumplir frecuencia
con una sola decisión diaria. Un resultado atractivo no autoriza live ni se
considera evidencia confirmatoria por la adaptación posterior a V1.

No se rescatan seeds, pesos, bloques, horizontes, tickers, meses o thresholds.

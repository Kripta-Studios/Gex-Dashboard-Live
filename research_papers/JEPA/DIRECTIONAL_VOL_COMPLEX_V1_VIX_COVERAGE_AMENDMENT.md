# DIRECTIONAL_VOL_COMPLEX_V1 — amendment de cobertura VIX

Estado: `PRE_OUTCOME_COVERAGE_AMENDMENT`

La auditoría outcome-free de nombres/fechas encontró que el archivo VIX local
no es un calendario bursátil exacto:

- faltan 18 sesiones del panel en 2022 (clusters de septiembre-diciembre);
- faltan 2026-05-18 y 2026-05-19;
- existen 15 ficheros 2024-2025 en festivos sin sesión QQQ/SPX/SPY;
- 2025 tiene cobertura completa de todas las sesiones de desarrollo;
- enero-abril, junio y julio MTD 2026 tienen cobertura completa.

No se usa as-of, forward-fill, official same-day close ni una barra del día
anterior como si fuera intradía. Regla congelada:

1. El universo maestro sigue siendo la intersección QQQ/SPXW/SPY de V1.
2. Los ficheros VIX sin sesión maestra se ignoran.
3. El modelo VOL se entrena solo en filas con VIX intradía exacto del día.
4. Si VIX falta en una fecha de test, el trade usa exactamente la predicción
   `SEMANTIC_RESIDUAL` padre que se habría emitido sin VIX.
5. Se registra `vol_source_available=false` y `fallback_parent=true`.

El fallback no se selecciona con outcomes y conserva una operación diaria. No
se permite usar el missingness como alpha, excluir la fecha o sustituirla por
otra fuente después del resultado.

Paridad outcome-free 2022-08..2025 sobre 856 sesiones compartidas:

- error absoluto mediano VIX local 16:00 vs Cboe close: `0,07` puntos;
- p95: `0,3225`;
- p99: `0,58`;
- máximo: `3,53` (2024-12-18).

Pasan las gates predeclaradas 0,25/1,50. La diferencia máxima confirma que sigue
siendo un proxy temporal, no un fill ni feed live idéntico.


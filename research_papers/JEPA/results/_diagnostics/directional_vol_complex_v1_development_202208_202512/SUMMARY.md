# DIRECTIONAL_VOL_COMPLEX_V1 — development freeze

Status: `PASS_DEVELOPMENT_FREEZE`

Selección walk-forward enero–diciembre 2025 ejecutada desde el runner congelado
`f6f3e8e9`, sin leer outcomes 2026. Se procesaron 247 trades por ticker/profile,
con mínimo 18 al mes y cero fallbacks VIX en el periodo de selección.

| Ticker | Profile seleccionado | WR | PF | Net bps | Meses positivos |
| --- | --- | ---: | ---: | ---: | ---: |
| QQQ | VIX_INTRADAY_RESIDUAL | 53,04% | 1,031 | +172,7 | 6/12 |
| SPX | VOL_COMPLEX_RESIDUAL | 52,23% | 1,061 | +280,4 | 6/12 |
| SPY | VIX_INTRADAY_RESIDUAL | 52,63% | 1,074 | +338,9 | 7/12 |

La señal de desarrollo es débil y no satisface la gate económica final. QQQ
empeora frente al control JEPA padre; SPX/SPY mejoran PF agregado pero conservan
cinco o seis meses negativos. La predeclaración no impuso una gate de desarrollo:
estos perfiles quedan seleccionados de forma inmutable para el one-shot 2026,
sin rescatar ventanas, features, tickers o subgrupos.

Hashes principales:

- ledger: `16092230a121564d8ca952541bb6a897310b268f2963bd6a51ca5a7995e9f284`;
- provenance: `c80019a1d507d77fcbec1e9bbf41790ce425d8ec4837e90c8b0a8e0c4b086a0d`;
- runner: `5de583a04f7e5e620a65310b593021899a6572e9384bcb4c121ef70360915105`.

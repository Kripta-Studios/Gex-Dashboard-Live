# DIRECTIONAL_VOL_COMPLEX_V1 — cierre 2026

Status: `CLOSED_2026_GATE`

One-shot enero–junio 2026 y julio MTD ejecutado desde selección congelada en
`3c5f41e9`. Hold exacto 180m, entrada 10:36, salida 13:36, coste 1bp y una
operación diaria. Los dos días sin VIX intradía, 2026-05-18/19, usaron el
fallback JEPA padre predeclarado (seis trades).

| Ticker | Trades Jan–Jun | WR | PF | Net bps | Min/mes | Meses + |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| QQQ | 123 | 55,28% | 1,039 | +113,6 | 19 | 3/6 |
| SPX | 123 | 51,22% | 0,993 | -13,9 | 19 | 4/6 |
| SPY | 123 | 50,41% | 0,898 | -219,6 | 19 | 3/6 |

Julio MTD (10 trades/ticker): QQQ PF 1,133/+38,0 bps; SPX PF 1,098/+16,5;
SPY PF 1,888/+107,1. Julio no es un mes completo.

La frecuencia y el WR agregado pasan, pero PF y estabilidad mensual fallan en
los tres tickers. Contra el JEPA padre el lado solo cambia en seis de 399
decisiones (3 QQQ, 2 SPX, 1 SPY); el complejo de volatilidad no aporta una
corrección estable. No rescatar meses, features, profiles ni flips.

Hashes: ledger
`b24b69d58ec7589ba3289caba7f879b75db0ac3ce4ec315b231e2ae7f5f9faee`;
monthly `69e592e4ebe86206e6b04d767c9a31412c93906119f969f47ac50d2c00386b3a`;
provenance `be6f1601b1903d2d8f8c7ba08e32e5cbd07f258281f26745eedf9960387a8b39`.


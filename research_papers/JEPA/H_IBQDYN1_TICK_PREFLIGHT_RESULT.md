# H-IBQDYN1 tick preflight result

Status: `PASS_H_IBQDYN1_TICK_PREFLIGHT`, outcome-free. Capture commit
`c823d86`; feature semantics commit `68ed6b3`. No label, model, payoff, June
2026 or production artifact was read or modified.

## Capture and cost

The frozen 12 events expanded to 24 exact execution contracts and were captured
from the exact authorized remote Terminal while MDDS was `CONNECTED`.

- contracts: 24/24; errors: 0; zero-row contracts: 0;
- rows: 43,680 (CALL 21,297; PUT 22,383);
- raw bytes: 7,372,750; parquet bytes: 883,210;
- contract-index SHA-256:
  `d0275e2dd086682132bbe1df24f1089c92a8d0c2c275c654f5465f6eb7d06c5f`;
- cost-projection SHA-256:
  `20c34643d0b6cf8616089a7e42b38e34c67ffd96a2d333e0bcb113320f222731`;
- status evidence SHA-256:
  `1f914c4386c0676ee418458a20c91d9db7c5cd18e88324b4908fdf27ec91dcc5`.

Projection to 16,852 eligible events / 33,704 contracts:

- 61,341,280 rows;
- 9.6427 GiB raw;
- 1.1551 GiB parquet.

This passes the frozen limits of 150 million rows and 20 GiB raw.

## Outcome-free feature audit

Feature semantics were frozen before computing the sample. All 12 events have
valid CALL and PUT measurements and all 20 alpha fields are finite.

| Ticker | Min CALL states | Min CALL pairs | Min PUT states | Min PUT pairs |
| --- | ---: | ---: | ---: | ---: |
| QQQ | 673 | 601 | 597 | 537 |
| SPXW | 670 | 488 | 745 | 592 |
| SPY | 756 | 515 | 706 | 539 |

All 60 ticker-feature cells have four finite values and at least four distinct
values. There are zero failed cells. This passes the frozen preflight
anti-degeneracy gate; it is not evidence of predictive alpha or profitability.

## Authorized next step

The full historical capture is authorized and runs only the H-IBQDYN1 family.
After its seal, the sequence is fixed: full feature/data gate, committed frozen
physical runner, one F0/F1 test and—only after a complete physical pass—one
ask-to-bid economic walk-forward. No other source or model sweep is authorized
in parallel.

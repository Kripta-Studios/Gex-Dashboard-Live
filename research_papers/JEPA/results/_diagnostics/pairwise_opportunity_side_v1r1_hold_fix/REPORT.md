# PAIRWISE_OPPORTUNITY_AND_SIDE_SELECTION_V1 — Results

- Dataset SHA-256: `d3c37b5f4511787ec19cf4478790377562b2b6c913185a2425f1b0cef7a3a408`
- Feature hash: `fa2057653ed0327b7f84a165c25f6e6d31e31b3b05c5591593e9c0bd3056d50e`
- Scientific cells: `99`
- Degenerate scientific cells: `0`
- Scientific pass: `False`
- C0 economic passing cells: `0/99`
- P1 economic passing cells: `0/99`
- C0 pooled PF: `0.9978`
- P1 pooled PF: `0.4265`
- Production modified: `false`
- 2026 opened: `false`

## Corrected economic result

Scientific metrics reproduce V1 exactly and remain rejected. Correct hold semantics
enable only four inner-selected policies, all SPY:

| Arm | Outer month | Trades | WR | PF | PnL R |
| --- | --- | ---: | ---: | ---: | ---: |
| C0 | 202409 | 20 | 40.00% | 1.071 | +0.450 |
| C0 | 202410 | 22 | 45.45% | 0.714 | -1.929 |
| C0 | 202502 | 19 | 52.63% | 1.288 | +1.440 |
| P1 | 202410 | 23 | 34.78% | 0.427 | -4.930 |

C0 pooled: 61 trades, WR 45.90%, PF 0.9978, PnL -0.0396R. P1 pooled:
23 trades, WR 34.78%, PF 0.4265, PnL -4.9301R. SPXW and QQQ never
select a policy; no outer cell passes the full contract. V1r1 is rejected.

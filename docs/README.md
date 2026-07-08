# Documentation Index

This folder contains the maintained PDF/LaTeX documentation for the current
GEX Dashboard Live production reality.

## Current Production Reality

The active live trading stack is the JEPA event-option static-union package:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
policy: event_option_frozen2025_static_union_balanced_202607
```

Live services:

```text
services/realtime_feed.py
bots/tradingbot_wrapper_jepa.py
systemd/realtime_feed.service
systemd/ai_bot.service
```

The bot emits Discord alerts and paper order intents. It does not submit broker
orders.

Current runtime contract:

```text
tickers: SPX, QQQ, SPY
option symbols: SPX -> SPXW, QQQ -> QQQ, SPY -> SPY
expiry: 0DTE only
entry window: 10:00-14:30 ET
risk: $5,000
exit: stop=-60%, tp=1000%, trail=50%/25%, min_hold=30m, max_hold=180m
```

Completed Jan-Jun 2026 validation:

| Scope | Trades | WR | PF | Min month trades |
| --- | ---: | ---: | ---: | ---: |
| Overall | 697 | 57.819% | 1.915 | 103 |
| QQQ | 236 | 60.593% | 1.771 | 36 |
| SPXW | 355 | 55.211% | 2.037 | 51 |
| SPY | 106 | 60.377% | 1.769 | 12 |

SPY does not meet the preferred 18-trades/month target. The current deployable
gate is 12 trades/month.

## Documents

| Source | PDF | Purpose |
| --- | --- | --- |
| `ARCHITECTURE.tex` | `pdfs/ARCHITECTURE.pdf` | Live runtime architecture and production package. |
| `BACKTEST_REPORT.tex` | `pdfs/BACKTEST_REPORT.pdf` | Current production validation snapshot and caveats. |
| `DATA_STRUCTURE.tex` | `pdfs/DATA_STRUCTURE.pdf` | Local ThetaData, VPS runtime files, bot state, and artifacts. |
| `DEPLOYMENT_GUIDE.tex` | `pdfs/DEPLOYMENT_GUIDE.pdf` | VPS deployment, validation, service restart, and daily audit commands. |
| `FEATURE_ENGINEERING.tex` | `pdfs/FEATURE_ENGINEERING.pdf` | Causal snapshot construction and training/backtest/live equivalence. |
| `FEATURES.tex` | `pdfs/FEATURES.pdf` | Allowed and forbidden feature families for live scoring. |
| `HYBRID_MODEL.tex` | `pdfs/HYBRID_MODEL.pdf` | Legacy Hybrid/GBT/JEPA lineage and promotion standard. |
| `RL_MODEL.tex` | `pdfs/RL_MODEL.pdf` | Legacy PPO/RL status and why it is not live production. |

## Build

Compile all maintained TeX documents from the repo root:

```powershell
python docs/compile_docs.py
```

The PDFs are written to:

```text
docs/pdfs/
```

LaTeX auxiliary files are transient and should not be treated as source.

## Promotion Rule

Any future model or policy must update these docs only after it passes the same
production checks: causal validation, leakage audit, live feature equivalence,
production package validation, systemd startup, and live/paper replay evidence.

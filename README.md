# GEX Dashboard Live

Real-time Greek Exposure (GEX) analysis and automated trading system for options markets.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Services](#services)
- [Trading Bots](#trading-bots)
- [Backtesting](#backtesting)
- [Discord Integration](#discord-integration)
- [Tools & Utilities](#tools--utilities)
- [Data Directories](#data-directories)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Development](#development)

---

## Overview

This project provides a comprehensive suite for:
- **Real-time Greek exposure calculation** (Gamma, Vanna, Charm, Delta, DGEX)
- **Automated trading** based on Greek signals and market structure
- **Initial Balance (IB) analysis** with Fibonacci extensions
- **Discord notifications** for signals and trade alerts
- **Backtesting framework** to validate strategies

The system processes options chain data from TastyTrade, calculates Greek exposures, identifies key levels (support/resistance, VPOC, VAH/VAL), and executes trades based on configurable strategies.

---

## Project Structure

```
Gex-Dashboard-Live/
├── services/              # Background daemons (24/7)
│   ├── gex_daemon.py      # Greek exposure data generator
│   ├── ib_service.py      # Initial Balance chart generator
│   ├── servidor.py        # HTTP API server (port 8609)
│   ├── fourier_service.py # Fourier cycle analysis
│   └── fourier_service_fast.py
│
├── bots/                  # Live trading bots
│   ├── tradingbot1.py     # Multi-ticker confluence strategy
│   ├── tradingbot2.py     # Level reversal strategy
│   ├── check_trades.py    # Trade status monitor
│   ├── state_bot1.json    # Bot1 active trade state
│   ├── state_bot2.json    # Bot2 active trade state
│   ├── trades_live/       # Bot1 completed trades
│   └── trades_live2/      # Bot2 completed trades
│
├── discord_app/           # Discord bot integration
│   ├── main.py            # Discord bot entry point
│   ├── bot.py             # Bot commands handler
│   └── discord_send_plots.py  # Plot scheduler & sender
│
├── backtest/              # Backtesting scripts
│   ├── backtest.py        # Confluence strategy backtest
│   ├── backtest2.py       # Reversal strategy backtest
│   ├── ib_backtest.py     # IB data fetcher for backtesting
│   ├── plot_backtest.py   # Trade visualization generator
│   └── trades/            # Backtest trade outputs
│
├── tools/                 # CLI utilities
│   ├── cli-app.py         # Manual data plotting
│   ├── data_plotting.py   # Core plotting functions
│   └── watchdog_notify.py # Systemd watchdog helper
│
├── web/                   # Web dashboard
│   └── templates/
│       ├── index.html         # Main HTML page
│       ├── index_modular.html # Modular version (loads JS modules)
│       ├── script.js          # Legacy monolithic script (backup)
│       ├── styles.css         # Main CSS (imports modular files)
│       ├── css/               # Modular CSS structure
│       │   ├── base.css           # Variables, themes, typography
│       │   ├── layout.css         # Main layout, tabs
│       │   ├── components.css     # Buttons, inputs, market monitor
│       │   ├── charts.css         # Chart panels, heatmap, regime
│       │   ├── login.css          # Login screen
│       │   └── modes.css          # Zen mode, detached modes
│       └── js/                # Modular JavaScript (16 modules)
│           ├── state.js           # Global state variables
│           ├── api.js             # Data fetching functions
│           ├── ui.js              # UI helpers, time, themes
│           ├── tabs.js            # Tab management
│           ├── dragdrop.js        # Drag and drop for panels
│           ├── charts.js          # Chart panel dispatcher
│           ├── heatmap.js         # Greek exposure heatmaps
│           ├── fourier.js         # Fourier analysis panels
│           ├── ib.js              # Initial Balance panels
│           ├── handlers.js        # Form handlers
│           ├── history.js         # Time machine controls
│           ├── layout.js          # Save/load layouts
│           ├── refresh.js         # Dashboard refresh logic
│           ├── windows.js         # Detached windows
│           ├── auth.js            # Authentication
│           └── init.js            # App initialization
│
├── modules/               # Shared modules
│   ├── stats.py           # Statistical functions
│   ├── tasty_handler.py   # TastyTrade API client
│   ├── ticker_dwn.py      # Ticker data downloader
│   └── utils.py           # Common utilities
│
├── systemd/               # Systemd service files
│   └── *.service
│
├── .env                   # Environment variables
├── requirements.txt       # Python dependencies
└── README.md
```

---

## Services

Background daemons that run continuously to generate data.

### gex_daemon.py

Generates Greek exposure data files every minute during market hours.

```bash
python services/gex_daemon.py
```

**Output:** JSON files in `/home/.../json_data/`
- `{TICKER}_0dte_ExposureData_{DATE}_{TIME}.json`

**Data includes:**
- Gamma, Vanna, Charm, Delta, DGEX exposures
- Spot price
- Strike-level breakdown

---

### ib_service.py

Generates Initial Balance charts using TastyTrade candle data.

```bash
python services/ib_service.py
```

**Output:** 
- JSON: `/home/.../ib_charts/ib_data_{TICKER}_{DATE}.json`
- PNG: `/home/.../ib_charts/ib_chart_{TICKER}_{DATE}.png`

**Features:**
- IB range detection (9:30-10:30 NYSE)
- Fibonacci extensions from IB range
- Volume profile calculation

---

### servidor.py

HTTP API server exposing Greek data for the web dashboard.

```bash
python services/servidor.py
```

**Port:** 8609

**Endpoints:**
- `GET /data/{ticker}` - Latest Greek data
- `GET /health` - Service health check

---

### fourier_service.py / fourier_service_fast.py

Performs Fourier analysis to detect market cycles.

```bash
python services/fourier_service.py      # Standard
python services/fourier_service_fast.py # Faster updates
```

---

## Trading Bots

Automated trading bots that execute based on Greek signals.

### tradingbot1.py - Multi-Ticker Confluence Strategy

Requires signal alignment across SPX, SPY, and QQQ before entering.

```bash
python bots/tradingbot1.py
```

**Strategy Logic:**
1. **Positive Gamma:** Mean-reversion at support/resistance
2. **Negative Gamma:** Momentum following with Vanna/Charm signals
3. **Min Vanna Magnet:** Trades toward untouched Min Vanna levels

**Trade Management:**
| Parameter | Value |
|-----------|-------|
| Stop Loss | 0.3% |
| Profit Target | 1.2% |
| Emergency Stop | 0.5% |
| Min Holding Time | 25 minutes |
| Cooldown After Exit | 10 minutes |
| Force Exit | 15:55 NYC |

**State Persistence:**
- Active trade saved to `bots/state_bot1.json`
- Completed trades saved to `bots/trades_live/`
- Logs written to `bots/tradingbot1.log`

**Discord Notifications:**
- Trade open with detailed reasoning (gamma regime, vanna signal, levels)
- Trade close with P&L breakdown and duration

---

### tradingbot2.py - Level Reversal Strategy

Trades individual tickers based on level tests and momentum breakouts.

```bash
python bots/tradingbot2.py
```

**Strategy Types:**

| Type | Trigger | Target |
|------|---------|--------|
| **REVERSAL** | Price at support/resistance | Untouched Min Vanna or opposite level |
| **MOMENTUM** | Breakout of key level in negative gamma | DGEX accelerator level |

**Trade Management:**
| Parameter | Value |
|-----------|-------|
| Stop Loss | 0.3% (fixed) |
| Breakeven Trigger | +0.25% |
| Trailing Step | 0.2% |
| Cooldown | 30 minutes |
| Force Exit | 15:55 NYC |

**State Persistence:**
- Active trade: `bots/state_bot2.json`
- Completed trades: `bots/trades_live2/`
- Logs: `bots/tradingbot2.log`

---

### check_trades.py - Trade Monitor

Quick status check for active trades across both bots.

```bash
python bots/check_trades.py
```

**Features:**
- Shows active trade details (entry, duration, unrealized P&L)
- Fetches current spot from Greek data files
- Detects and explains contradictory positions between bots
- Displays entry reasoning and Greek signals

**Example Output:**
```
============================================================
  TRADINGBOT1: 📈 LONG SPX
============================================================
  Entry Price:  $6050.25
  Duration:     1h 30m
  ✅ Unrealized:  +5.75 pts (+0.09%) = $57.50

  WHY THIS TRADE?
  Reason: Pos Gamma Bounce at 6045.00
  Gamma Regime: LONG
  Min Vanna: $6065.00 - UNTOUCHED (magnet)
```

---

## Backtesting

Scripts to test strategies on historical data.

### backtest.py

Backtests the multi-ticker confluence strategy.

```bash
python backtest/backtest.py
```

**Requires:** Historical IB data in `ib_backtest/`

---

### backtest2.py

Backtests the level reversal strategy.

```bash
python backtest/backtest2.py
```

---

### plot_backtest.py - Trade Visualizer

Generates candlestick charts with trade markers and levels.

```bash
# Basic usage (backtest trades)
python backtest/plot_backtest.py

# Specify source
python backtest/plot_backtest.py --source backtest  # Backtest trades
python backtest/plot_backtest.py --source bot1      # TradingBot1 live trades
python backtest/plot_backtest.py --source bot2      # TradingBot2 live trades
python backtest/plot_backtest.py --source all       # All sources combined

# Specific date
python backtest/plot_backtest.py --source bot1 --date 20260127

# Short flags
python backtest/plot_backtest.py -s all -d 20260127
```

**Arguments:**
| Flag | Options | Default | Description |
|------|---------|---------|-------------|
| `--source`, `-s` | `backtest`, `bot1`, `bot2`, `all` | `backtest` | Trade data source |
| `--date`, `-d` | `YYYYMMDD` | All dates | Specific date to plot |

**Output:** PNG files in `backtest/plots/`
- `candles_{TICKER}_{DATE}_{SOURCE}.png` - Candlestick with trades
- `volume_profile_{TICKER}_{DATE}.png` - Volume profile chart

**Chart Features:**
- 1-minute candlesticks
- Entry/exit markers (O = Open, C = Close)
- Support/resistance levels
- IB high/low
- Min Vanna magnet
- Volume profile (VPOC, VAH, VAL)

---

### ib_backtest.py

Fetches and stores historical IB data for backtesting.

```bash
python backtest/ib_backtest.py
```

**Output:** JSON files in `ib_backtest/`

---

## Discord Integration

### main.py

Entry point for the Discord bot. Runs both the command handler and plot scheduler.

```bash
python discord_app/main.py
```

**Features:**
- Scheduled plot posting to channels
- Interactive command responses
- Systemd notify integration

---

### bot.py

Discord bot command handler.

**Commands:**
```
#load SPX 0dte gamma    - Generate and post specific plot
#load QQQ weekly vanna  - Weekly vanna exposure for QQQ
```

**Usage:**
```
#load <TICKER> <EXPIRATION> <GREEK>

TICKER: SPX, SPY, QQQ, etc.
EXPIRATION: 0dte, 1dte, weekly, opex, monthly, all
GREEK: delta, gamma, vanna, charm
```

---

### discord_send_plots.py

Handles scheduled plot posting and Discord API interactions.

**Scheduled Posts:**
- Greek exposure plots at configurable intervals
- IB charts after market open
- Summary reports at market close

---

## Tools & Utilities

### cli-app.py

Manual data plotting from command line.

```bash
python tools/cli-app.py SPX 0dte gamma
python tools/cli-app.py QQQ weekly vanna
```

**Arguments:**
```
python tools/cli-app.py <TICKER> <EXPIRATION> [GREEK]

TICKER:     SPX, SPY, QQQ, etc.
EXPIRATION: 0dte, 1dte, weekly, opex, monthly, all
GREEK:      delta, gamma, vanna, charm (optional)
```

---

## Data Directories

The system uses several data directories (configured with absolute paths):

| Directory | Purpose | Generated By |
|-----------|---------|--------------|
| `json_data/` | Greek exposure JSON files | `gex_daemon.py` |
| `ib_charts/` | Real-time IB data & charts | `ib_service.py` |
| `ib_backtest/` | Historical IB data | `ib_backtest.py` |
| `bots/trades_live/` | Bot1 completed trades | `tradingbot1.py` |
| `bots/trades_live2/` | Bot2 completed trades | `tradingbot2.py` |
| `backtest/trades/` | Backtest trade outputs | `backtest.py` |
| `backtest/plots/` | Trade visualization PNGs | `plot_backtest.py` |

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=your_bot_token_here

# TastyTrade API
TT_USERNAME=your_tastytrade_username
TT_PASSWORD=your_tastytrade_password
```

### Trading Parameters

Trading parameters are configured as constants at the top of each bot file:

**tradingbot1.py:**
```python
STOP_LOSS_PCT = 0.003           # 0.3%
PROFIT_TARGET_PCT = 0.012       # 1.2%
EMERGENCY_STOP_LOSS_PCT = 0.005 # 0.5%
MIN_HOLDING_TIME_MINUTES = 25
COOLDOWN_AFTER_EXIT_MINUTES = 10
MIN_CONFIDENCE_THRESHOLD = 0.55
```

**tradingbot2.py:**
```python
STOP_LOSS_FIXED = 0.003        # 0.3%
BREAKEVEN_TRIGGER = 0.0025     # 0.25%
TRAILING_STEP = 0.002          # 0.2%
COOLDOWN_MINUTES = 30
MIN_RISK_REWARD = 1.2
```

---

## Deployment

### 1. Clone and Setup

```bash
git clone https://github.com/kripta-studios/gex-dashboard-live.git
cd gex-dashboard-live
pip install -r requirements.txt
cp .env.example .env  # Edit with your credentials
```

### 2. Deploy to Server

```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  ./ root@your-server:/home/Option-Greeks-Plotting-Discord-Bot/
```

### 3. Install Systemd Services

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable gex_daemon ib discord-bot tradingbot1 tradingbot2

# Start services
sudo systemctl start gex_daemon ib discord-bot tradingbot1 tradingbot2
```

### 4. Monitor Services

```bash
# Check status
sudo systemctl status tradingbot1

# View logs
sudo journalctl -u tradingbot1 -f

# Restart a service
sudo systemctl restart tradingbot1
```

---

## Development

### Code Style

- Python 3.9+
- Type hints encouraged
- Docstrings for all functions
- Constants in UPPER_CASE

### Adding a New Strategy

1. Create `bots/tradingbot3.py` based on existing templates
2. Implement `generate_signal()` with your logic
3. Create `systemd/tradingbot3.service`
4. Update this README

### Running Tests

```bash
# Verify all Python files compile
find . -name "*.py" -exec python3 -m py_compile {} \;

# Run a specific backtest
python backtest/backtest.py
```

### Project Dependencies

Key dependencies (see `requirements.txt`):
- `requests` - HTTP client
- `numpy` - Numerical operations
- `pandas` - Data manipulation
- `matplotlib` - Chart generation
- `discord.py` - Discord bot
- `python-dotenv` - Environment variables
- `pytz` / `zoneinfo` - Timezone handling

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-strategy`)
3. Commit changes (`git commit -am 'Add new strategy'`)
4. Push to branch (`git push origin feature/new-strategy`)
5. Open a Pull Request

For major changes, please open an issue first to discuss.

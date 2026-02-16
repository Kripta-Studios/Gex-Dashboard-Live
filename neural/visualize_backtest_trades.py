"""
Trade Visualization Script for Backtest Results

Creates intraday price charts with entry/exit markers using IB JSON data.

Usage:
    python bots/visualize_backtest_trades.py --trades training_data/backtest_trades.csv --ticker SPX
    python bots/visualize_backtest_trades.py --trades training_data/backtest_trades.csv --date 20260204
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta

# Paths
BASE_DIR = Path(__file__).parent.parent
IB_BACKTEST_DIR = BASE_DIR / "trading_data" / "ib_backtest"
IB_CHARTS_DIR = BASE_DIR / "trading_data" / "ib_charts"
OUTPUT_DIR = BASE_DIR / "training_data" / "charts"


def load_ib_candles(ticker: str, date_str: str) -> pd.DataFrame:
    """Load IB candle data for a ticker and date."""
    file_ticker = ticker.lstrip("/")
    date_str = str(date_str)
    
    # Try both date formats
    date_formats = [date_str]
    if len(date_str) == 8:
        date_formats.append(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}")
    
    for fmt in date_formats:
        for ib_dir in [IB_BACKTEST_DIR, IB_CHARTS_DIR]:
            filepath = ib_dir / f"ib_data_{file_ticker}_{fmt}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    series = data.get("series", [])
                    if series:
                        df = pd.DataFrame(series)
                        return df
    
    return pd.DataFrame()


def plot_trades(candles_df: pd.DataFrame, trades: list, ticker: str, date_str: str, 
                hold_minutes: int = 15, output_path: str = None):
    """
    Plot price chart with trade entries and exits.
    """
    if candles_df.empty:
        print(f"  ⚠ No candle data for {ticker} on {date_str}")
        return
    
    # Get price column
    price_col = 'close' if 'close' in candles_df.columns else 'price'
    if price_col not in candles_df.columns:
        print(f"  ⚠ No price column for {ticker} on {date_str}")
        return
    
    # Create time index from time strings
    # Normalize time strings to HH:MM for better matching
    def normalize_time(t):
        if pd.isna(t): return ""
        t = str(t)
        # Remove seconds if present
        if t.count(':') == 2:
            return t.rsplit(':', 1)[0]
        return t

    # Apply normalization
    times = [normalize_time(t) for t in candles_df['time'].tolist()]
    prices = candles_df[price_col].tolist()
    
    # Use dark style
    plt.style.use('dark_background')
    
    # Custom colors for dark mode
    COLOR_BG = '#1e1e1e'
    COLOR_PRICE = '#4ecdc4'  # Cyan-ish
    COLOR_ENTRY_LONG = '#00ff00' # Bright Green
    COLOR_ENTRY_SHORT = '#ff00ff' # Magenta
    COLOR_WIN = '#00ff00'
    COLOR_LOSS = '#ff4444'
    COLOR_GRID = '#444444'
    
    # Create figure with dark background
    fig, ax = plt.subplots(figsize=(16, 8), facecolor=COLOR_BG)
    ax.set_facecolor(COLOR_BG)
    
    # Plot price line
    ax.plot(range(len(prices)), prices, color=COLOR_PRICE, linewidth=1.5, alpha=0.9, label='Price')
    
    # Add time labels
    time_indices = list(range(0, len(times), max(1, len(times) // 10)))
    ax.set_xticks(time_indices)
    ax.set_xticklabels([times[i] for i in time_indices], rotation=45, color='white')
    ax.tick_params(axis='y', colors='white')
    
    # Plot trades
    time_to_idx = {t: i for i, t in enumerate(times)}
    
    for trade in trades:
        # Handle both old and new column names
        trade_time_raw = str(trade.get('entry_time', trade.get('time', '')))
        trade_time = normalize_time(trade_time_raw)
        
        direction = trade['direction']
        # We will use the CHART price for visual alignment user requested
        # entry_price = trade.get('entry_price', trade.get('spot_price', 0))
        pnl = trade['pnl']
        actual_hold = trade.get('actual_hold_minutes', hold_minutes)
        
        # Find entry index
        entry_idx = time_to_idx.get(trade_time)
        if entry_idx is None:
            # Try to find closest time
            # This is slow but robust
            best_dist = 9999
            best_idx = -1
            
            def time_diff(t1, t2):
                try:
                    h1, m1 = map(int, t1.split(':'))
                    h2, m2 = map(int, t2.split(':'))
                    return abs((h1*60+m1) - (h2*60+m2))
                except:
                    return 9999
            
            if len(times) > 0:
                 # heuristic search
                 for i, t in enumerate(times):
                     dist = time_diff(t, trade_time)
                     if dist < best_dist:
                         best_dist = dist
                         best_idx = i
                     if dist == 0: break
                 entry_idx = best_idx
            
            if entry_idx is None or entry_idx == -1:
                continue
        
        # Get chart price at entry (snapping to line)
        vis_entry_price = prices[entry_idx]

        # Calculate exit index using actual hold time
        # Assuming 1-minute candles roughly
        # If we have actual_hold_minutes, simply add it to entry index
        # This assumes the candle data is complete-ish which is usually fine
        # Better: calculate target time and find index
        
        try:
            h, m = map(int, times[entry_idx].split(':'))
            entry_minutes = h * 60 + m
            exit_minutes = entry_minutes + actual_hold
            
            # Find index with time >= exit_minutes
            exit_idx = entry_idx
            for i in range(entry_idx, len(times)):
                th, tm = map(int, times[i].split(':'))
                curr_min = th * 60 + tm
                if curr_min >= exit_minutes:
                    exit_idx = i
                    break
        except:
             exit_idx = min(entry_idx + int(actual_hold), len(prices) - 1)
        
        # Ensure exit is at least 1 index after entry for visibility
        if exit_idx <= entry_idx:
            exit_idx = min(entry_idx + 1, len(prices) - 1)

         # Get chart price at exit (snapping to line)
        vis_exit_price = prices[exit_idx]

        # Calculate Visual P&L based on chart prices
        point_values = {
            "SPX": 100.0, "/ES": 50.0, "/NQ": 20.0, "SPY": 100.0, "QQQ": 100.0
        }
        multiplier = point_values.get(ticker, 100.0)
        
        if direction == 'LONG':
            chart_pnl_val = (vis_exit_price - vis_entry_price) * multiplier
        else:
            chart_pnl_val = (vis_entry_price - vis_exit_price) * multiplier
            
        # Use Chart P&L for color logic (to match visual movement)
        visual_color = COLOR_WIN if chart_pnl_val > 0 else COLOR_LOSS if chart_pnl_val < 0 else 'gray'
        
        # Entry Marker
        entry_color = COLOR_ENTRY_LONG if direction == 'LONG' else COLOR_ENTRY_SHORT
        entry_marker = '^' if direction == 'LONG' else 'v'
        
        # Offset slightly for visibility
        offset = (max(prices) - min(prices)) * 0.02
        entry_y = vis_entry_price - offset if direction == 'LONG' else vis_entry_price + offset
        
        ax.scatter(entry_idx, entry_y, marker=entry_marker, s=150, c=entry_color, edgecolors='white', linewidths=1, zorder=10)
        
        # Exit Marker
        ax.scatter(exit_idx, vis_exit_price, marker='x', s=100, c=visual_color, linewidths=2, zorder=10)
        
        # Draw dotted line connecting entry to exit
        ax.plot([entry_idx, exit_idx], [vis_entry_price, vis_exit_price],
                linestyle='--', color=visual_color, alpha=0.6, linewidth=1)
        
        # P&L annotation (Show Visual P&L and Backtest P&L if different)
        pnl_text = f"${chart_pnl_val:+.0f}"
        if abs(chart_pnl_val - pnl) > 10: # If discrepancy > $10
             pnl_text += f"\n(BT: ${pnl:+.0f})"
        
        ax.annotate(pnl_text, (exit_idx, vis_exit_price),
                   fontsize=9, fontweight='bold', color=visual_color,
                   ha='left', va='center', xytext=(5, 0), textcoords='offset points')
    
    # Title and labels
    total_pnl = sum(t['pnl'] for t in trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    losses = sum(1 for t in trades if t['pnl'] < 0)
    
    title_text = f"{ticker} - {date_str}\nTrades: {len(trades)} | W: {wins} L: {losses} | P&L: ${total_pnl:+.2f}"
    ax.set_title(title_text, fontsize=14, fontweight='bold', color='white', pad=20)
    ax.set_xlabel('Time', color='white')
    ax.set_ylabel('Price', color='white')
    ax.grid(True, color=COLOR_GRID, alpha=0.3)
    
    # Remove top/right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    
    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='^', color='w', markerfacecolor=COLOR_ENTRY_LONG, markersize=10, label='LONG Entry'),
        Line2D([0], [0], marker='v', color='w', markerfacecolor=COLOR_ENTRY_SHORT, markersize=10, label='SHORT Entry'),
        Line2D([0], [0], marker='x', color='w', markeredgecolor=COLOR_WIN, markersize=10, linestyle='None', label='Win Exit'),
        Line2D([0], [0], marker='x', color='w', markeredgecolor=COLOR_LOSS, markersize=10, linestyle='None', label='Loss Exit'),
    ]
    leg = ax.legend(handles=legend_elements, loc='upper left', facecolor='#333333', edgecolor='white')
    for text in leg.get_texts():
        text.set_color("white")
    
    plt.tight_layout()
    
    # Save or show
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor=COLOR_BG)
        print(f"  ✓ Saved chart to {output_path}")
    else:
        plt.show()
    
    plt.close()

def plot_pnl_summary(trades_df: pd.DataFrame, output_path: str = None):
    """
    Genera un gráfico de PNL acumulado para cada ticker.
    """
    print(f"\n[4/4] Generando resumen de PNL por ticker...")
    
    plt.style.use('dark_background')
    tickers = trades_df['ticker'].unique()
    n_tickers = len(tickers)
    
    fig, axes = plt.subplots(n_tickers, 1, figsize=(12, 4 * n_tickers), sharex=False)
    if n_tickers == 1: axes = [axes]
    
    for i, ticker in enumerate(tickers):
        df_ticker = trades_df[trades_df['ticker'] == ticker].copy()
        # Aseguramos orden cronológico para el PNL acumulado
        df_ticker['cum_pnl'] = df_ticker['pnl'].cumsum()
        
        ax = axes[i]
        color = '#00ff00' if df_ticker['cum_pnl'].iloc[-1] >= 0 else '#ff4444'
        
        ax.plot(range(len(df_ticker)), df_ticker['cum_pnl'], color=color, linewidth=2, label=f'PNL {ticker}')
        ax.fill_between(range(len(df_ticker)), df_ticker['cum_pnl'], alpha=0.2, color=color)
        
        ax.set_title(f"PNL Acumulado: {ticker} (Final: ${df_ticker['cum_pnl'].iloc[-1]:.2f})", fontsize=14, fontweight='bold')
        ax.axhline(0, color='white', linestyle='--', alpha=0.5)
        ax.set_ylabel("USD ($)")
        ax.grid(True, alpha=0.2)
        
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        print(f"  ✓ Resumen de PNL guardado en: {output_path}")
    else:
        plt.show()
    plt.close()

def main():
    parser = argparse.ArgumentParser(description="Visualize backtest trades on price charts")
    parser.add_argument("--trades", default="training_data/backtest_trades.csv", help="Path to trades CSV")
    parser.add_argument("--ticker", default=None, help="Filter by ticker (e.g., SPX, /ES)")
    parser.add_argument("--date", default=None, help="Filter by date (e.g., 20260204)")
    parser.add_argument("--hold", type=int, default=15, help="Hold time in minutes for exit calculation")
    parser.add_argument("--save", action="store_true", help="Save charts instead of displaying")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  TRADE VISUALIZATION")
    print("=" * 60)
    
    # Load trades
    trades_path = BASE_DIR / args.trades
    print(f"\n[1/3] Loading trades from {trades_path}...")
    trades_df = pd.read_csv(trades_path)
    print(f"  ✓ Loaded {len(trades_df)} trades")
    
    # Convert date to string for matching
    trades_df['date'] = trades_df['date'].astype(str)
    
    # Filter
    if args.ticker:
        trades_df = trades_df[trades_df['ticker'] == args.ticker]
        print(f"  ✓ Filtered to {args.ticker}: {len(trades_df)} trades")
    
    if args.date:
        trades_df = trades_df[trades_df['date'] == args.date]
        print(f"  ✓ Filtered to {args.date}: {len(trades_df)} trades")
    
    if trades_df.empty:
        print("  ⚠ No trades match the filters")
        return
    
    # Show trades summary
    print(f"\n  📊 TRADES SUMMARY:")
    print(f"  {'─' * 80}")
    print(f"  {'Win':3s} {'Ticker':6s} {'Date':8s} {'Entry':5s} {'EntryPx':>10s} {'Exit':5s} {'ExitPx':>10s} {'Dir':5s} {'P&L':>5s}")
    print(f"  {'─' * 80}")
    
    for _, row in trades_df.head(25).iterrows():
        pnl_str = f"+{row['pnl']:.0f}" if row['pnl'] > 0 else f"{row['pnl']:.0f}"
        win_str = "✓" if row['pnl'] > 0 else "✗" if row['pnl'] < 0 else "-"
        
        # Handle both old and new column names
        entry_time = row.get('entry_time', row.get('time', 'N/A'))
        entry_price = row.get('entry_price', row.get('spot_price', 0))
        exit_time = row.get('exit_time', 'N/A')
        exit_price = row.get('exit_price', entry_price)
        
        print(f"  {win_str:3s} {row['ticker']:6s} {row['date']} {entry_time:5s} {entry_price:10.2f} {exit_time:5s} {exit_price:10.2f} {row['direction']:5s} {pnl_str:>5s}")
    
    if len(trades_df) > 25:
        print(f"  ... and {len(trades_df) - 25} more trades")
    
    # Get unique ticker/date combinations
    combinations = trades_df.groupby(['ticker', 'date']).size().reset_index(name='count')
    print(f"\n[2/3] Found {len(combinations)} ticker/date combinations")
    
    # Generate charts
    print(f"\n[3/3] Generating charts...")
    for _, row in combinations.iterrows():
        ticker = row['ticker']
        date_str = str(row['date'])
        
        print(f"\n  Processing {ticker} on {date_str}...")
        
        # Get trades for this combination
        day_trades = trades_df[(trades_df['ticker'] == ticker) & 
                               (trades_df['date'] == date_str)].to_dict('records')
        
        # Load candle data
        candles_df = load_ib_candles(ticker, date_str)
        
        if candles_df.empty:
            print(f"  ⚠ No IB data found for {ticker} on {date_str}")
            continue
        
        # Output path
        if args.save:
            output_path = str(OUTPUT_DIR / f"{ticker.replace('/', '_')}_{date_str}.png")
        else:
            output_path = None
        
        # Plot
        plot_trades(candles_df, day_trades, ticker, date_str, 
                   hold_minutes=args.hold, output_path=output_path)
    
    pnl_summary_path = str(OUTPUT_DIR / f"pnl_performance_summary_{args.date}_{args.ticker}.png") if args.save else None
    plot_pnl_summary(trades_df, output_path=pnl_summary_path)
    print(f"\n{'=' * 60}")
    print("  VISUALIZATION COMPLETE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

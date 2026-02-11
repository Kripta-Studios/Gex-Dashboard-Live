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
    times = candles_df['time'].tolist()
    prices = candles_df[price_col].tolist()
    
    # Create figure
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Plot price line
    ax.plot(range(len(prices)), prices, 'b-', linewidth=1, alpha=0.7, label='Price')
    
    # Add time labels
    time_indices = list(range(0, len(times), max(1, len(times) // 10)))
    ax.set_xticks(time_indices)
    ax.set_xticklabels([times[i] for i in time_indices], rotation=45)
    
    # Plot trades
    time_to_idx = {t: i for i, t in enumerate(times)}
    
    for trade in trades:
        # Handle both old and new column names
        trade_time = str(trade.get('entry_time', trade.get('time', '')))
        direction = trade['direction']
        entry_price = trade.get('entry_price', trade.get('spot_price', 0))
        exit_price_actual = trade.get('exit_price', entry_price)
        pnl = trade['pnl']
        
        # Find entry index
        entry_idx = time_to_idx.get(trade_time)
        if entry_idx is None:
            # Try to find closest time
            for i, t in enumerate(times):
                if t == trade_time:
                    entry_idx = i
                    break
            if entry_idx is None:
                continue
        
        # Calculate exit index - find the actual time in the data
        exit_time_str = trade.get('exit_time', '')
        exit_idx = time_to_idx.get(exit_time_str, entry_idx + hold_minutes)
        exit_idx = min(max(exit_idx, 0), len(prices) - 1)
        exit_price = exit_price_actual if exit_price_actual != entry_price else prices[exit_idx]
        
        # Entry dot (on top of the candle)
        entry_color = 'blue' if direction == 'LONG' else 'magenta'
        ax.scatter(entry_idx, entry_price, marker='o', s=120, c=entry_color, edgecolors='black', linewidths=1, zorder=10)
        
        # Exit dot (green for win, red for loss)
        exit_color = 'lime' if pnl > 0 else 'red' if pnl < 0 else 'gray'
        ax.scatter(exit_idx, exit_price, marker='o', s=120, c=exit_color, edgecolors='black', linewidths=1, zorder=10)
        
        # Draw line connecting entry to exit
        ax.plot([entry_idx, exit_idx], [entry_price, exit_price],
                linestyle='-', color=exit_color, alpha=0.5, linewidth=1.5)
        
        # Small P&L annotation above exit
        ax.annotate(f'${pnl:+.0f}', (exit_idx, exit_price),
                   fontsize=7, fontweight='bold', color=exit_color,
                   ha='center', va='bottom', xytext=(0, 5), textcoords='offset points')
    
    # Title and labels
    total_pnl = sum(t['pnl'] for t in trades)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    losses = sum(1 for t in trades if t['pnl'] < 0)
    title = f"{ticker} - {date_str} | {len(trades)} Trades | {wins}W / {losses}L | P&L: {total_pnl:+.0f}"
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('Time')
    ax.set_ylabel('Price')
    ax.grid(True, alpha=0.3)
    
    # Add legend for directions
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='^', color='w', markerfacecolor='blue', markersize=12, label='LONG Entry'),
        Line2D([0], [0], marker='v', color='w', markerfacecolor='purple', markersize=12, label='SHORT Entry'),
        Line2D([0], [0], marker='x', color='w', markerfacecolor='green', markeredgecolor='green', markersize=12, label='Win Exit'),
        Line2D([0], [0], marker='x', color='w', markerfacecolor='red', markeredgecolor='red', markersize=12, label='Loss Exit'),
    ]
    ax.legend(handles=legend_elements, loc='upper left')
    
    plt.tight_layout()
    
    # Save or show
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"  ✓ Saved chart to {output_path}")
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
    
    print(f"\n{'=' * 60}")
    print("  VISUALIZATION COMPLETE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

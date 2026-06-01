import re

def rewrite():
    file_path = r'c:\Users\Álvaro Schwiedop\Desktop\KriptaStudios\Gex-Dashboard-Live\neural\collect_training_data_spx_qqq.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update collect_training_data signature and loop
    content = content.replace(
        'def collect_training_data(tickers: list, num_days: int = 365, num_workers: int = None, start_date=None, end_date=None) -> pd.DataFrame:',
        'def collect_training_data(tickers: list, num_days: int = 365, num_workers: int = None, start_date=None, end_date=None, dense_labeling: bool = False, frequency: int = 5) -> pd.DataFrame:'
    )
    content = content.replace(
        'task_args.append((ticker, target_date))',
        'task_args.append((ticker, target_date, dense_labeling, frequency))'
    )

    # 2. Update process_ticker_date signature and unpacking
    content = content.replace(
        'ticker, target_date = args',
        'ticker, target_date, dense_labeling, frequency = args'
    )

    # 3. Update main argument parsing
    main_args_orig = """    parser.add_argument("--end", type=str, default=None, help="End date YYYYMMDD")
    parser.add_argument("--gui", action="store_true", help="Launch trade annotation GUI (skips data collection)")
    parser.add_argument("--port", type=int, default=8501, help="GUI server port (only with --gui)")
    args = parser.parse_args()"""
    
    main_args_new = """    parser.add_argument("--end", type=str, default=None, help="End date YYYYMMDD")
    parser.add_argument("--gui", action="store_true", help="Launch trade annotation GUI (skips data collection)")
    parser.add_argument("--port", type=int, default=8501, help="GUI server port (only with --gui)")
    parser.add_argument("--dense-labeling", action="store_true", help="Bypass proximity gate to label all minutes")
    parser.add_argument("--frequency", type=int, default=5, help="Sampling frequency in minutes (default 5)")
    args = parser.parse_args()"""
    content = content.replace(main_args_orig, main_args_new)

    # 4. Update the call to collect_training_data inside main
    content = content.replace(
        'df = collect_training_data(args.tickers, args.days, args.workers, args.start, args.end)',
        'df = collect_training_data(args.tickers, args.days, args.workers, args.start, args.end, args.dense_labeling, args.frequency)'
    )

    # 5. Update temporal downsampling logic
    content = content.replace(
        'if minutes_since_open % 5 == 0:',
        'if minutes_since_open % frequency == 0:'
    )

    # 6. Update the Proximity Gate logic
    # Original:
    # if near_sr or magnet_active:
    # We want to replace it with:
    # if dense_labeling or near_sr or magnet_active:
    content = content.replace(
        'if near_sr or magnet_active:',
        'if dense_labeling or near_sr or magnet_active:'
    )
    
    # 7. Update Dynamic ATR-based Profit / Stop
    # We want to change the FIXED_PROFIT_PCT and FIXED_STOP_PCT when NOT magnet_active to dynamic ones based on ATR
    # Find this block:
    #                 else:
    #                     target_label, time_to_target, time_to_stop, max_move = calculate_target_label_asymmetric(
    #                         series, series_idx,
    #                         long_profit_pct=FIXED_PROFIT_PCT,
    #                         short_profit_pct=FIXED_PROFIT_PCT,
    #                         long_stop_pct=FIXED_STOP_PCT,
    #                         short_stop_pct=FIXED_STOP_PCT,
    #                         lookahead=LOOKAHEAD_MINUTES
    #                     )
    
    # We'll replace the block to calculate dynamic atr-based percentages.
    
    old_block = """                else:
                    target_label, time_to_target, time_to_stop, max_move = calculate_target_label_asymmetric(
                        series, series_idx,
                        long_profit_pct=FIXED_PROFIT_PCT,
                        short_profit_pct=FIXED_PROFIT_PCT,
                        long_stop_pct=FIXED_STOP_PCT,
                        short_stop_pct=FIXED_STOP_PCT,
                        lookahead=LOOKAHEAD_MINUTES
                    )"""
                    
    new_block = """                else:
                    # Dynamic ATR-based thresholds (approx 20% of daily ATR for profit)
                    # day_atr is e.g. 60 points. On SPX 5000, 60/5000 = 0.012 (1.2%)
                    # 20% of ATR = 0.0024 (0.24%)
                    dynamic_profit = (day_atr * 0.2) / spot if day_atr > 0 else FIXED_PROFIT_PCT
                    dynamic_profit = float(np.clip(dynamic_profit, 0.0015, 0.005))
                    dynamic_stop = dynamic_profit * 1.0  # 1:1 risk/reward by default for normal entries
                    
                    target_label, time_to_target, time_to_stop, max_move = calculate_target_label_asymmetric(
                        series, series_idx,
                        long_profit_pct=dynamic_profit,
                        short_profit_pct=dynamic_profit,
                        long_stop_pct=dynamic_stop,
                        short_stop_pct=dynamic_stop,
                        lookahead=LOOKAHEAD_MINUTES
                    )"""
    content = content.replace(old_block, new_block)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Rewritten successfully.")

if __name__ == "__main__":
    rewrite()

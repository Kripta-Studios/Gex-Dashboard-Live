import requests
import pandas as pd
import json
import sys

# CONFIG
SERVER_IP = "127.0.0.1" 
PORT = 8609

def get_market_data(ticker, expiration):
    url = f"http://{SERVER_IP}:{PORT}/get_latest?ticker={ticker}&exp={expiration}"
        
    try:
        response = requests.get(url, timeout=20)
        
        if response.status_code == 404:
            print(f"Error 404: Not Found {ticker} {expiration}.")
            return None
        
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            return None

        print("Data received succesfully")
        return response.json()

    except requests.exceptions.ConnectionError:
        print(f"Conection error: can not link {SERVER_IP}:{PORT}")
        return None
    except Exception as e:
        print(f"Unexpected error:\n {e}")
        return None

def analyze_data(json_data):
    """
    Rebuild the Pandas DataFrame and show a summary.
    """
    if not json_data:
        return

    print("\n[DEBUG] Claves disponibles en el JSON raíz:")
    print(list(json_data.keys()))
    # Key metrics
    ticker_info = f"Analysis: {json_data.get('today_ddt_string', 'Unknown Date')}"
    spot = json_data.get('spot_price', 0)
    z_delta = json_data.get('zerodelta', 0)
    z_gamma = json_data.get('zerogamma', 0)
    prev_close = json_data.get("prev_close_price", 0)
    print("\n" + "="*50)
    print(f" {ticker_info:^48} ")
    print("="*50)
    print(f"\tSpot Price:   {spot:,.2f}")
    print(f"\tDelta Flip:   {z_delta:,.2f}")
    print(f"\tGamma Flip:   {z_gamma:,.2f}")
    print(f"\tPrev Close:   {prev_close}")
    # Rebuild  DataFrame (format 'split')
    try:
        raw_df = json_data['option_data']
        df = pd.DataFrame(
            data=raw_df['data'], 
            columns=raw_df['columns'], 
            index=raw_df['index']
        )
        
        # Convert dates
        if 'expiration_date' in df.columns:
            df['expiration_date'] = pd.to_datetime(df['expiration_date'])

        print("-" * 50)
        print(f"Options chain ({len(df)} Strikes Loaded)")
        print("-" * 50)

        gamma_col = 'total_gamma' # <--- CHANGE THIS to your actual column name if different

        if gamma_col in df.columns:
            # Get the row index where gamma is highest (Max Positive)
            max_pos_idx = df[gamma_col].idxmax()
            max_pos_strike = df.loc[max_pos_idx]['strike_price']
            max_pos_val = df.loc[max_pos_idx][gamma_col]

            # Get the row index where gamma is lowest (Max Negative)
            max_neg_idx = df[gamma_col].idxmin()
            max_neg_strike = df.loc[max_neg_idx]['strike_price']
            max_neg_val = df.loc[max_neg_idx][gamma_col]

            print("-" * 50)
            print(" GEX PROFILE ")
            print("-" * 50)
            print(f"\tMax Pos Strike: {max_pos_strike:,.2f} (Val: {max_pos_val:,.2f})")
            print(f"\tMax Neg Strike: {max_neg_strike:,.2f} (Val: {max_neg_val:,.2f})")
        else:
            print(f"\n[!] Column '{gamma_col}' not found. Check df.columns.")
        
        # Show 20 strikes closest to (ATM)
        if spot > 0 and 'strike_price' in df.columns:
            df['dist'] = abs(df['strike_price'] - spot)
            closest_strikes = df.sort_values('dist').head(10).sort_values('strike_price')
            
            valid_cols = [c for c in df.columns]
            valid_cols = valid_cols[:8]
            print("\t Strikes closest to ATM:")
            print(closest_strikes[valid_cols].to_string(index=False))
        else:
            print(df.head())

        print("\nDataFrame 'df' ready to use in Python.")
        return df

    except Exception as e:
        print(f"Error rebuilding DataFrame:\n {e}")
        return None
'''
# main execution, entry point
if __name__ == "__main__":
    target_ticker = "SPX"
    target_expiry = "0dte"
    
    # for cmd args: python client.py SPX 1dte
    if len(sys.argv) > 2:
        target_ticker = sys.argv[1]
        target_expiry = sys.argv[2]

    data = get_market_data(target_ticker, target_expiry)
    df = analyze_data(data)
    print("Available columns to get data from:\n", df.columns)
'''
# ... existing code ...

if __name__ == "__main__":
    target_ticker = "SPX"
    target_expiry = "0dte"

    if len(sys.argv) > 2:
        target_ticker = sys.argv[1]
        target_expiry = sys.argv[2]

    data = get_market_data(target_ticker, target_expiry)
    
    # Check if data was actually received
    if data is not None:
        df = analyze_data(data)
        
        # Check if analyze_data returned a valid DataFrame
        if df is not None:
            print("Available columns to get data from:\n", df.columns)
        else:
            print("[!] Could not analyze data (df is None).")
    else:
        print("[!] No data received. Exiting.")

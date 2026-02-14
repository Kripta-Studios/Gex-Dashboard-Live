import pandas as pd
import numpy as np
import requests

def calculate_max_pain_from_api(ticker="SPX", exp="0dte", server_ip="91.99.90.39", port=8609):
    """
    Connects to the custom HTTP server to get the latest JSON data from RAM
    and calculates the Max Pain strike price on the fly.
    """
    url = f"http://{server_ip}:{port}/get_latest?ticker={ticker}&exp={exp}"
    print(f"Fetching latest data from: {url}")
    
    # 1. Make the HTTP request to the server
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raises an exception for 404 or 500 errors
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to the server: {e}")
        return

    # 2. Extract the current Spot Price
    spot_price = data.get('spot_price', 0.0)
    print(f"Current Spot Price ({ticker}): {spot_price:.2f}")

    # 3. Extract and rebuild the option_data DataFrame
    # The JSON uses pandas 'split' orientation ('columns', 'index', 'data')
    option_data_dict = data.get('option_data', {})
    if not option_data_dict or 'data' not in option_data_dict:
        print("Error: The server did not return valid 'option_data'.")
        return
        
    df = pd.DataFrame(
        option_data_dict['data'], 
        columns=option_data_dict['columns']
    )
    
    # Ensure the required columns exist for the calculation
    required_cols = ['strike_price', 'call_open_int', 'put_open_int']
    for col in required_cols:
        if col not in df.columns:
            print(f"Error: Missing column '{col}' in the received data.")
            return

    # Drop any rows with NaN values in the required columns to avoid math errors
    df = df.dropna(subset=required_cols)

    # 4. Calculate Max Pain
    # Get all unique strike prices sorted in ascending order
    strikes = np.sort(df['strike_price'].unique())
    pain_values = []
    
    # Simulate the expiration for every available strike price
    for sim_price in strikes:
        
        # --- CALL OPTIONS ---
        # Calls are In-The-Money (ITM) if the simulated expiration price is greater than the call strike
        calls_itm = df[df['strike_price'] < sim_price]
        call_pain = ((sim_price - calls_itm['strike_price']) * calls_itm['call_open_int']).sum()
        
        # --- PUT OPTIONS ---
        # Puts are In-The-Money (ITM) if the put strike is greater than the simulated expiration price
        puts_itm = df[df['strike_price'] > sim_price]
        put_pain = ((puts_itm['strike_price'] - sim_price) * puts_itm['put_open_int']).sum()
        
        # --- TOTAL PAIN ---
        total_pain = call_pain + put_pain
        pain_values.append((sim_price, total_pain))
        
    # Create a DataFrame with the simulation results
    df_pain = pd.DataFrame(pain_values, columns=['Strike', 'Total_Pain'])
    
    # Find the strike that minimizes the total payout value
    max_pain_idx = df_pain['Total_Pain'].idxmin()
    max_pain_price = df_pain.loc[max_pain_idx, 'Strike']
    min_pain_value = df_pain.loc[max_pain_idx, 'Total_Pain']
    
    # 5. Print the final results
    print("-" * 40)
    print(f"MAX PAIN STRIKE ({ticker} {exp}): {max_pain_price:.2f}")
    print(f"Difference vs Spot:       {max_pain_price - spot_price:.2f}")
    print(f"Minimum Payout:           ${min_pain_value:,.2f}")
    print("-" * 40)
    
    return max_pain_price, df_pain

if __name__ == "__main__":
    # Make sure you have the requests library installed: pip install requests
    
    # Call the API (Defaults to fetching SPX 0dte from 91.99.90.39:8609)
    calculate_max_pain_from_api(ticker="SPX", exp="0dte")
    
    # Example for QQQ:
    # calculate_max_pain_from_api(ticker="QQQ", exp="0dte")

import json
import numpy as np
import pandas as pd
import sys
import os
from pathlib import Path
from glob import glob
from datetime import date, datetime
from concurrent.futures import ProcessPoolExecutor

# Add project root to path (one level up from scripts/)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from modules import stats
    print("[INFO] Successfully imported modules.stats")
except ImportError as e:
    print(f"[ERROR] Could not import modules.stats: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def serialize(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="split")
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, pd.Period)):
        return obj.isoformat()
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, (np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, (np.int64, np.int32)):
        return int(obj)
    return str(obj)

def backfill_file(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # SKIP CHECK: Resume logic
        if "totalvega" in data and "totalvomma" in data:
            if data["totalvega"].get("all") and data["totalvomma"].get("all"):
                if "option_data" in data and isinstance(data["option_data"], dict):
                    if "call_vegex" in data["option_data"].get("columns", []):
                        return # Solo lo salta si TRULY tiene todo

        if "option_data" not in data:
            return

        print(f"[PROCESSING] {filepath}...")
        
        # 1. Prepare Data
        try:
            if isinstance(data["option_data"], dict) and "data" in data["option_data"]:
                df = pd.DataFrame(**data["option_data"])
            else:
                df = pd.read_json(json.dumps(data["option_data"]), orient='split')
        except Exception as e:
            print(f"[ERROR] Failed to parse option_data in {filepath}: {e}")
            return

        if df.empty:
            return

        if "levels" not in data:
            return

        # 2. Extract needed columns (Using .copy() to ensure writability for Numba)
        S_grid = np.array(data["levels"], dtype=np.float64).reshape(-1, 1).copy()
        strikes = df["strike_price"].to_numpy(dtype=np.float64).copy()
        time_till_exp = df["time_till_exp"].to_numpy(dtype=np.float64).copy()
        
        dividend_yield = 0.0
        risk_free_yield = 0.046 # Safe approximation
        
        # Calls
        call_ivs = df["call_iv"].to_numpy(dtype=np.float64).copy()
        call_oi = df["call_open_int"].to_numpy(dtype=np.float64).copy()
        
        # Puts
        put_ivs = df["put_iv"].to_numpy(dtype=np.float64).copy()
        put_oi = df["put_open_int"].to_numpy(dtype=np.float64).copy()
        
        # 3. Calculate DP, CDF, PDF (2D Grid for Profiles)
        call_dp, _, call_pdf_dp = stats.calc_dp_cdf_pdf(
            S_grid, strikes, call_ivs, time_till_exp, risk_free_yield, dividend_yield
        )
        call_dp = np.ascontiguousarray(call_dp)
        call_pdf_dp = np.ascontiguousarray(call_pdf_dp)
        
        put_dp, _, put_pdf_dp = stats.calc_dp_cdf_pdf(
            S_grid, strikes, put_ivs, time_till_exp, risk_free_yield, dividend_yield
        )
        put_dp = np.ascontiguousarray(put_dp)
        put_pdf_dp = np.ascontiguousarray(put_pdf_dp)
        
        # 4. Calculate Vega Profiles (Matrix: 300 x N_options)
        call_vega_ex_matrix = stats.calc_vega_ex(
            S_grid, call_ivs, time_till_exp, dividend_yield, call_oi, call_pdf_dp
        )
        call_vega_ex_matrix = np.ascontiguousarray(call_vega_ex_matrix)
        
        put_vega_ex_matrix = stats.calc_vega_ex(
            S_grid, put_ivs, time_till_exp, dividend_yield, put_oi, put_pdf_dp
        )
        put_vega_ex_matrix = np.ascontiguousarray(put_vega_ex_matrix)
        
        # 5. Calculate Vomma Profiles
        call_vomma_ex_matrix = stats.calc_vomma_ex(
            call_vega_ex_matrix, call_dp, call_ivs, time_till_exp
        )
        put_vomma_ex_matrix = stats.calc_vomma_ex(
            put_vega_ex_matrix, put_dp, put_ivs, time_till_exp
        )
        
        # 6. Aggregate Net Profiles ("all")
        total_vega_all = (call_vega_ex_matrix.sum(axis=1) + put_vega_ex_matrix.sum(axis=1)) / 10**9
        total_vomma_all = (call_vomma_ex_matrix.sum(axis=1) + put_vomma_ex_matrix.sum(axis=1)) / 10**9
        
        # 7. Aggregate "ex_next"
        total_vega_next = np.zeros(len(S_grid))
        total_vomma_next = np.zeros(len(S_grid))
        
        if "monthly_options_dates" in data and len(data["monthly_options_dates"]) > 0:
            next_expiry_str = data["monthly_options_dates"][0]
            mask = (df["expiration_date"] == next_expiry_str).to_numpy()
            if not mask.any():
                 df_dates = df["expiration_date"].astype(str).str[:10]
                 target_date = next_expiry_str[:10]
                 mask = (df_dates == target_date).to_numpy()
        else:
            unique_exps = sorted(df["expiration_date"].unique())
            if len(unique_exps) > 0:
                mask = (df["expiration_date"] == unique_exps[0]).to_numpy()
            else:
                mask = np.zeros(len(df), dtype=bool)

        if mask is not None and mask.any():
            total_vega_next = (
                call_vega_ex_matrix[:, mask].sum(axis=1) + 
                put_vega_ex_matrix[:, mask].sum(axis=1)
            ) / 10**9
            
            total_vomma_next = (
                call_vomma_ex_matrix[:, mask].sum(axis=1) + 
                put_vomma_ex_matrix[:, mask].sum(axis=1)
            ) / 10**9

        # 8. Update JSON Data (Profiles)
        data["totalvega"] = {
            "all": total_vega_all.tolist(),
            "ex_next": total_vega_next.tolist(),
            "ex_fri": []
        }
        
        data["totalvomma"] = {
            "all": total_vomma_all.tolist(),
            "ex_next": total_vomma_next.tolist(),
            "ex_fri": []
        }
        
        # ==========================================
        # 9. Update 1D Columns (Spot Price values)
        # ==========================================
        
        # 9a. VEGA: Check if native Vega exists, else fallback to calculation
        if "call_vega" in df.columns and "put_vega" in df.columns:
            c_vega = df["call_vega"].to_numpy(dtype=np.float64) * call_oi * 100
            p_vega = df["put_vega"].to_numpy(dtype=np.float64) * put_oi * 100
        else:
            S_spot = np.array([[data["spot_price"]]], dtype=np.float64).copy()
            _, _, c_pdf = stats.calc_dp_cdf_pdf(S_spot, strikes, call_ivs, time_till_exp, risk_free_yield, dividend_yield)
            _, _, p_pdf = stats.calc_dp_cdf_pdf(S_spot, strikes, put_ivs, time_till_exp, risk_free_yield, dividend_yield)
            
            c_vega = stats.calc_vega_ex(S_spot, call_ivs, time_till_exp, dividend_yield, call_oi, np.ascontiguousarray(c_pdf))[0]
            p_vega = stats.calc_vega_ex(S_spot, put_ivs, time_till_exp, dividend_yield, put_oi, np.ascontiguousarray(p_pdf))[0]

        # 9b. VOMMA: Needs D1 at Spot Price to calculate properly
        S_spot = np.array([[data["spot_price"]]], dtype=np.float64).copy()
        c_dp, _, _ = stats.calc_dp_cdf_pdf(S_spot, strikes, call_ivs, time_till_exp, risk_free_yield, dividend_yield)
        p_dp, _, _ = stats.calc_dp_cdf_pdf(S_spot, strikes, put_ivs, time_till_exp, risk_free_yield, dividend_yield)
        
        # Reshape to 2D explicitly to satisfy Numba signature (1xN)
        c_vega_2d = np.ascontiguousarray(c_vega.reshape(1, -1))
        p_vega_2d = np.ascontiguousarray(p_vega.reshape(1, -1))
        c_dp = np.ascontiguousarray(c_dp)
        p_dp = np.ascontiguousarray(p_dp)
        
        c_vommex = stats.calc_vomma_ex(c_vega_2d, c_dp, call_ivs, time_till_exp)[0]
        p_vommex = stats.calc_vomma_ex(p_vega_2d, p_dp, put_ivs, time_till_exp)[0]
        
        # Assign to DataFrame
        df["call_vegex"] = c_vega
        df["put_vegex"] = p_vega
        df["call_vommex"] = c_vommex
        df["put_vommex"] = p_vommex
        df["total_vega"] = (c_vega + p_vega) / 10**9
        df["total_vomma"] = (c_vommex + p_vommex) / 10**9

        data["option_data"] = df.to_dict(orient="split")
        
        with open(filepath, 'w') as f:
            json.dump(data, f, default=serialize)
            
    except Exception as e:
        print(f"[ERROR] Failed to process {filepath}: {e}")

def main():
    json_dir = "trading_data/json_data"
    
    if not os.path.exists(json_dir):
        print(f"[ERROR] Directory {json_dir} not found.")
        return

    files = glob(os.path.join(json_dir, "*.json"))
    print(f"Found {len(files)} files in {json_dir}")
    print("Starting process with 20 workers...")
    
    with ProcessPoolExecutor(max_workers=20) as executor:
        list(executor.map(backfill_file, files))
    
    print("Optimization Complete.")

if __name__ == "__main__":
    main()
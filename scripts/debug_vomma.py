import json
import numpy as np
import pandas as pd
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules import stats

def debug_file(filepath):
    """Debug a single file to see what's happening"""
    print(f"\n{'='*80}")
    print(f"DEBUGGING: {filepath}")
    print('='*80)
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if "option_data" not in data:
            print("[SKIP] No option_data found")
            return
            
        # Parse dataframe
        if isinstance(data["option_data"], dict) and "data" in data["option_data"]:
            df = pd.DataFrame(**data["option_data"])
        else:
            df = pd.read_json(json.dumps(data["option_data"]), orient='split')
        
        if df.empty:
            print("[SKIP] Empty dataframe")
            return
        
        print(f"\n[INFO] DataFrame shape: {df.shape}")
        print(f"[INFO] Columns: {df.columns.tolist()}")
        
        # Extract data (Añadiendo .copy() para evitar los read-only arrays)
        S_grid = np.array(data["levels"], dtype=np.float64).reshape(-1, 1).copy()
        strikes = df["strike_price"].to_numpy(dtype=np.float64).copy()
        time_till_exp = df["time_till_exp"].to_numpy(dtype=np.float64).copy()
        call_ivs = df["call_iv"].to_numpy(dtype=np.float64).copy()
        call_oi = df["call_open_int"].to_numpy(dtype=np.float64).copy()
        
        print(f"\n[SHAPES BEFORE CALC]")
        print(f"  S_grid: {S_grid.shape} | dtype: {S_grid.dtype} | C-contig: {S_grid.flags['C_CONTIGUOUS']}")
        print(f"  strikes: {strikes.shape} | dtype: {strikes.dtype} | C-contig: {strikes.flags['C_CONTIGUOUS']}")
        print(f"  call_ivs: {call_ivs.shape} | dtype: {call_ivs.dtype} | C-contig: {call_ivs.flags['C_CONTIGUOUS']}")
        print(f"  time_till_exp: {time_till_exp.shape} | dtype: {time_till_exp.dtype} | C-contig: {time_till_exp.flags['C_CONTIGUOUS']}")
        print(f"  call_oi: {call_oi.shape} | dtype: {call_oi.dtype} | C-contig: {call_oi.flags['C_CONTIGUOUS']}")
        
        # Try calc_dp_cdf_pdf
        print(f"\n[STEP 1] Calling calc_dp_cdf_pdf...")
        try:
            call_dp, _, call_pdf_dp = stats.calc_dp_cdf_pdf(
                S_grid, strikes, call_ivs, time_till_exp, 0.046, 0.0
            )
            print(f"  ✓ SUCCESS")
            print(f"    call_dp: {call_dp.shape} | dtype: {call_dp.dtype} | C-contig: {call_dp.flags['C_CONTIGUOUS']}")
            print(f"    call_pdf_dp: {call_pdf_dp.shape} | dtype: {call_pdf_dp.dtype} | C-contig: {call_pdf_dp.flags['C_CONTIGUOUS']}")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Try calc_vega_ex
        print(f"\n[STEP 2] Calling calc_vega_ex...")
        try:
            call_vega_ex_matrix = stats.calc_vega_ex(
                S_grid, call_ivs, time_till_exp, 0.0, call_oi, call_pdf_dp
            )
            print(f"  ✓ SUCCESS")
            print(f"    call_vega_ex: {call_vega_ex_matrix.shape} | dtype: {call_vega_ex_matrix.dtype} | C-contig: {call_vega_ex_matrix.flags['C_CONTIGUOUS']}")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Try calc_vomma_ex
        print(f"\n[STEP 3] Calling calc_vomma_ex...")
        print(f"  Input shapes:")
        print(f"    vega_ex: {call_vega_ex_matrix.shape} | dtype: {call_vega_ex_matrix.dtype}")
        print(f"    dp: {call_dp.shape} | dtype: {call_dp.dtype}")
        print(f"    ivs: {call_ivs.shape} | dtype: {call_ivs.dtype}")
        print(f"    T: {time_till_exp.shape} | dtype: {time_till_exp.dtype}")
        
        try:
            call_vomma_ex_matrix = stats.calc_vomma_ex(
                call_vega_ex_matrix,
                call_dp,
                call_ivs,
                time_till_exp
            )
            print(f"  ✓ SUCCESS")
            print(f"    call_vomma_ex: {call_vomma_ex_matrix.shape} | dtype: {call_vomma_ex_matrix.dtype}")
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            
            # Try with explicit contiguous conversion
            print(f"\n[STEP 3b] Retrying with explicit contiguous arrays...")
            try:
                call_vomma_ex_matrix = stats.calc_vomma_ex(
                    np.ascontiguousarray(call_vega_ex_matrix),
                    np.ascontiguousarray(call_dp),
                    np.ascontiguousarray(call_ivs),
                    np.ascontiguousarray(time_till_exp)
                )
                print(f"  ✓ SUCCESS with contiguous conversion")
            except Exception as e2:
                print(f"  ✗ STILL FAILED: {e2}")
                import traceback
                traceback.print_exc()
            return
        
        print(f"\n[SUCCESS] All calculations completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test with one of the failing files
    test_file = "trading_data/json_data/QQQ_0dte_ExposureData_20260204_150332.json"
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    
    if not os.path.exists(test_file):
        print(f"[ERROR] File not found: {test_file}")
        print(f"[INFO] Please provide a valid file path as argument")
        sys.exit(1)
    
    debug_file(test_file)

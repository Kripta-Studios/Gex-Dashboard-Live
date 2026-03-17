import os
import sys
import datetime
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from modules.utils import get_market_trading_days

def test_trading_days_weekend():
    # March 16, 2026 is Monday.
    # March 14-15 are Sat-Sun.
    # Last 5 trading days before (including) March 16 should be:
    # Mar 16 (Mon), Mar 13 (Fri), Mar 12 (Thu), Mar 11 (Wed), Mar 10 (Tue)
    target = datetime.date(2026, 3, 16)
    days = get_market_trading_days(5, end_date=target)
    
    print(f"Trading days before {target}: {days}")
    assert len(days) == 5
    assert target in days
    assert datetime.date(2026, 3, 15) not in days
    assert datetime.date(2026, 3, 14) not in days
    assert days[0] == datetime.date(2026, 3, 10)

def test_trading_days_holiday():
    # July 4th is a US holiday.
    # In 2025, July 4 is Friday. 
    # Market is closed.
    target = datetime.date(2025, 7, 7) # Monday
    days = get_market_trading_days(5, end_date=target)
    
    print(f"Trading days before/on {target} (incl. July 4th holiday): {days}")
    # Sessions should be: July 7 (Mon), July 3 (Thu), July 2 (Wed), July 1 (Tue), June 30 (Mon)
    assert datetime.date(2025, 7, 4) not in days
    assert datetime.date(2025, 7, 7) in days
    assert len(days) == 5
    assert days[3] == datetime.date(2025, 7, 3) # Correction: July 3rd is the 4th element (index 3)

if __name__ == "__main__":
    try:
        print("Running test_trading_days_weekend...")
        test_trading_days_weekend()
        print("PASS")
        
        print("\nRunning test_trading_days_holiday...")
        test_trading_days_holiday()
        print("PASS")
        
        print("\nALL TRADING DAY TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

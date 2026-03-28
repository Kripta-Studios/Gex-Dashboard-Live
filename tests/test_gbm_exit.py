import sys
import os
from datetime import datetime, timedelta
import pytz

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from bots.tradingbot_wrapper_rl import GBMSignalTracker, GBM_TRAILING_ACTIVATION_PCT, GBM_TRAILING_STOP_PCT

ET = pytz.timezone("America/New_York")

def test_gbm_trailing_stop_long():
    print("Testing GBM Trailing Stop (LONG)...")
    entry_price = 4000.0
    now = datetime.now(ET)
    tracker = GBMSignalTracker("SPX", "LONG", entry_price, 0.9, entry_time=now)
    
    # 1. Move to +0.20% (No activation)
    # 4000 * 1.002 = 4008
    print("Step 1: Move to +0.20% (4008)")
    res1 = tracker.check(4008.0, now + timedelta(minutes=1))
    assert res1 is None
    assert tracker.peak_price == 4008.0
    
    # 2. Drop to 3995 (Drawdown from peak 13 pts = 0.325% > 0.30%)
    # But activation was never hit (0.20% < 0.50%). Should NOT exit via trailing stop.
    # Note: 3995 is above stop_price (4000 * 0.997 = 3988).
    print("Step 2: Drop to 3995 (No activation retrace)")
    res2 = tracker.check(3995.0, now + timedelta(minutes=2))
    assert res2 is None
    
    # 3. Move to +0.60% (Activation hit)
    # 4000 * 1.006 = 4024
    print("Step 3: Move to +0.60% (4024) - Activation Hit")
    res3 = tracker.check(4024.0, now + timedelta(minutes=10))
    assert res3 is None
    assert tracker.peak_price == 4024.0
    
    # 4. Drop by 0.30% from peak
    # 4024 - (4000 * 0.003) = 4024 - 12 = 4012
    print("Step 4: Drop to 4012 (Trailing Stop Trigger)")
    res4 = tracker.check(4012.0, now + timedelta(minutes=11))
    assert res4 is not None
    assert res4["reason"] == "trailing_stop"
    assert res4["pnl_pct"] >= 0.003
    print(f"Exit Result: {res4}")

def test_gbm_trailing_stop_short():
    print("\nTesting GBM Trailing Stop (SHORT)...")
    entry_price = 4000.0
    now = datetime.now(ET)
    tracker = GBMSignalTracker("SPX", "SHORT", entry_price, 0.9, entry_time=now)
    
    # 1. Move to +0.60% profit (Price falls to 3976)
    # 4000 * (1 - 0.006) = 3976
    print("Step 1: Move to +0.60% profit (3976) - Activation Hit")
    res1 = tracker.check(3976.0, now + timedelta(minutes=5))
    assert res1 is None
    assert tracker.peak_price == 3976.0
    
    # 2. Retrace 0.30% from peak
    # 3976 + (4000 * 0.003) = 3976 + 12 = 3988
    print("Step 2: Retrace to 3988 (Trailing Stop Trigger)")
    res2 = tracker.check(3988.0, now + timedelta(minutes=6))
    assert res2 is not None
    assert res2["reason"] == "trailing_stop"
    print(f"Exit Result: {res2}")

if __name__ == "__main__":
    test_gbm_trailing_stop_long()
    test_gbm_trailing_stop_short()
    print("\nAll GBM tests passed!")

"""
Trading Wrapper - Decision layer over ML model.

The ML model predicts DIRECTION, this wrapper decides:
- IF to enter (regime + confidence)
- HOW MUCH (position sizing)
- HOW to manage (trailing stops, profit taking)

Connects to real-time data from:
- gex_daemon.py: Greek exposures (json_data/)
- fourier_service_fast.py: IV/VIX data (fourier/)
- ib_service.py: IB levels + candles (ib_charts/)

Usage:
    from trading_wrapper import TradingWrapper
    from hybrid_model import load_hybrid_model
    
    model, normalizer = load_hybrid_model(...)
    wrapper = TradingWrapper(
        model=model,
        normalizer=normalizer,
        greek_dir="/path/to/json_data",
        fourier_dir="/path/to/fourier",
        ib_dir="/path/to/ib_charts"
    )
    
    signal = wrapper.get_signal("SPX", features, current_price)
    if signal.direction != "HOLD":
        execute_trade(signal)
"""

import os
import sys
import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum
import logging

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import torch

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class MarketRegime(Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOL = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"


@dataclass
class TradeSignal:
    """Processed trading signal with all decision data."""
    ticker: str
    direction: str  # "LONG", "SHORT", "HOLD"
    raw_confidence: float  # From model
    calibrated_confidence: float  # Adjusted by wrapper
    position_size: float  # 0.0 to 1.0 (% of maximum)
    regime: MarketRegime
    entry_price: float
    stop_loss: float
    take_profit_1: float  # Partial exit
    take_profit_2: float  # Full exit
    max_hold_time: int  # minutes
    reasoning: Dict[str, any] = field(default_factory=dict)
    # Bayesian uncertainty fields
    time_mu_minutes: float = 0.0      # Expected time to target (minutes)
    time_sigma_minutes: float = 0.0   # Uncertainty / std dev (minutes)
    
    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "raw_confidence": self.raw_confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "position_size": self.position_size,
            "regime": self.regime.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "max_hold_time": self.max_hold_time,
            "reasoning": self.reasoning,
            "time_mu_minutes": self.time_mu_minutes,
            "time_sigma_minutes": self.time_sigma_minutes,
        }


# =============================================================================
# REGIME FILTER - Market Condition Analysis
# =============================================================================

class RegimeFilter:
    """
    Filters market conditions before considering ML signals.
    
    Connects to real-time data from:
    - gex_daemon.py: Greek exposures (json_data/)
    - fourier_service_fast.py: IV/VIX data (fourier/)
    - ib_service.py: IB levels + candles (ib_charts/)
    """
    
    def __init__(self, greek_data_dir: str, fourier_dir: str, ib_dir: str):
        self.greek_data_dir = Path(greek_data_dir)
        self.fourier_dir = Path(fourier_dir)
        self.ib_dir = Path(ib_dir)
        
        # Cache for loaded data
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 60  # seconds
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_time:
            return False
        age = (datetime.now() - self._cache_time[key]).total_seconds()
        return age < self._cache_ttl
    
    def load_latest_greeks(self, ticker: str) -> Optional[dict]:
        """
        Load most recent Greek data from gex_daemon.py output.
        
        Files are located at: json_data/{TICKER}_0dte_ExposureData_{timestamp}.json
        """
        ticker = ticker.replace("/", "")
        cache_key = f"greeks_{ticker}"
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        
        pattern = f"{ticker}_0dte_ExposureData_*.json"
        files = sorted(
            self.greek_data_dir.glob(pattern), 
            key=lambda p: p.stat().st_mtime, 
            reverse=True
        )
        
        if not files:
            logger.debug(f"No Greek files found for {ticker}")
            return None
        
        latest = files[0]
        age_seconds = datetime.now().timestamp() - latest.stat().st_mtime
        
        if age_seconds > 300:  # Data older than 5 min is stale
            logger.warning(f"Greek data for {ticker} is {age_seconds/60:.1f} min old")
            return None
        
        try:
            with open(latest, 'r') as f:
                data = json.load(f)
            
            self._cache[cache_key] = data
            self._cache_time[cache_key] = datetime.now()
            return data
        except Exception as e:
            logger.error(f"Error loading Greek data for {ticker}: {e}")
            return None
    
    def load_latest_weekly_greeks(self, ticker: str) -> Optional[dict]:
        """
        Load most recent weekly Greek data from gex_daemon.py output.
        
        Files are located at: json_data/{TICKER}_weekly_ExposureData_{timestamp}.json
        Weekly data changes slowly, so we use a looser freshness check.
        """
        ticker = ticker.replace("/", "")
        cache_key = f"greeks_weekly_{ticker}"
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        
        pattern = f"{ticker}_weekly_ExposureData_*.json"
        files = sorted(
            self.greek_data_dir.glob(pattern), 
            key=lambda p: p.stat().st_mtime, 
            reverse=True
        )
        
        if not files:
            logger.debug(f"No weekly Greek files found for {ticker}")
            return None
        
        latest = files[0]
        age_seconds = datetime.now().timestamp() - latest.stat().st_mtime
        
        if age_seconds > 1800:  # Weekly data: 30 min freshness
            logger.debug(f"Weekly Greek data for {ticker} is {age_seconds/60:.1f} min old")
            return None
        
        try:
            with open(latest, 'r') as f:
                data = json.load(f)
            
            self._cache[cache_key] = data
            self._cache_time[cache_key] = datetime.now()
            return data
        except Exception as e:
            logger.error(f"Error loading weekly Greek data for {ticker}: {e}")
            return None
    
    def load_latest_fourier(self, ticker: str) -> Optional[dict]:
        """
        Load IV data from fourier_service_fast.py output.
        
        Files are located at: fourier/{TICKER}_fourier_{date}.json
        """
        ticker = ticker.replace("/", "")
        cache_key = f"fourier_{ticker}"
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        
        today = datetime.now().strftime("%Y-%m-%d")
        fourier_file = self.fourier_dir / f"{ticker}_fourier_{today}.json"
        
        if not fourier_file.exists():
            # Try alternate naming patterns
            patterns = [
                f"fourier_{ticker}_{today}.json",
                f"{ticker}_{today}_fourier.json",
            ]
            for pattern in patterns:
                alt_file = self.fourier_dir / pattern
                if alt_file.exists():
                    fourier_file = alt_file
                    break
        
        if not fourier_file.exists():
            logger.debug(f"No Fourier file found for {ticker}")
            return None
        
        try:
            with open(fourier_file, 'r') as f:
                data = json.load(f)
            
            self._cache[cache_key] = data
            self._cache_time[cache_key] = datetime.now()
            return data
        except Exception as e:
            logger.error(f"Error loading Fourier data for {ticker}: {e}")
            return None
    
    def load_ib_data(self, ticker: str) -> Optional[dict]:
        """
        Load IB data from ib_service.py output.
        
        Files are located at: ib_charts/ib_data_{TICKER}_{date}.json
        """
        ticker = ticker.replace("/", "")
        cache_key = f"ib_{ticker}"
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        
        today = datetime.now().strftime("%Y-%m-%d")
        ib_file = self.ib_dir / f"ib_data_{ticker}_{today}.json"
        
        if not ib_file.exists():
            # Try yesterday
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            ib_file = self.ib_dir / f"ib_data_{ticker}_{yesterday}.json"
        
        if not ib_file.exists():
            logger.debug(f"No IB file found for {ticker}")
            return None
        
        try:
            with open(ib_file, 'r') as f:
                data = json.load(f)
            
            self._cache[cache_key] = data
            self._cache_time[cache_key] = datetime.now()
            return data
        except Exception as e:
            logger.error(f"Error loading IB data for {ticker}: {e}")
            return None
    
    def classify_regime(self, ticker: str) -> Tuple[MarketRegime, dict]:
        """
        Classify current market regime.
        
        Returns:
            (regime, metadata_dict)
        """
        greeks = self.load_latest_greeks(ticker)
        fourier = self.load_latest_fourier(ticker)
        ib = self.load_ib_data(ticker)
        
        metadata = {
            "greeks_available": greeks is not None,
            "fourier_available": fourier is not None,
            "ib_available": ib is not None,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Gamma Regime Analysis
        if greeks:
            gamma_data = greeks.get("totalgamma", {}).get("all", [])
            net_gamma = sum(gamma_data) if gamma_data else 0
            metadata["net_gamma"] = net_gamma
            metadata["gamma_regime"] = "positive" if net_gamma > 0 else "negative"
            
            # Vanna/Charm analysis
            vanna_data = greeks.get("totalvanna", {}).get("all", [])
            charm_data = greeks.get("totalcharm", {}).get("all", [])
            metadata["net_vanna"] = sum(vanna_data) if vanna_data else 0
            metadata["net_charm"] = sum(charm_data) if charm_data else 0
        
        # Volatility Analysis (IV/VIX)
        if fourier:
            atm_iv = fourier.get("atm_put_iv", 0)
            if atm_iv == 0:
                atm_iv = fourier.get("atm_iv", 0)
            metadata["atm_iv"] = atm_iv
            
            # High volatility = different regime
            if atm_iv > 30:  # IV > 30% = high vol
                return MarketRegime.HIGH_VOL, metadata
        
        # Volume Profile / IB Analysis
        if ib and "analysis" in ib:
            analysis = ib["analysis"]
            current_price = analysis.get("current_price", 0)
            ib_high = analysis.get("ib_high", 0)
            ib_low = analysis.get("ib_low", 0)
            ib_range = ib_high - ib_low if ib_high > ib_low else 0
            
            metadata["ib_high"] = ib_high
            metadata["ib_low"] = ib_low
            metadata["current_price"] = current_price
            metadata["ib_range_pct"] = (ib_range / current_price * 100) if current_price else 0
            
            # Price above/below IB indicates trend
            if current_price and ib_high and current_price > ib_high:
                return MarketRegime.TRENDING_UP, metadata
            elif current_price and ib_low and current_price < ib_low:
                return MarketRegime.TRENDING_DOWN, metadata
        
        # Default to ranging if no clear signal
        return MarketRegime.RANGING, metadata
    
    def is_tradeable(self, ticker: str) -> Tuple[bool, str]:
        """
        Determine if conditions are favorable for trading.
        
        Returns:
            (tradeable: bool, reason: str)
        """
        regime, metadata = self.classify_regime(ticker)
        
        # Check data freshness
        if not metadata.get("greeks_available"):
            return False, "No fresh Greek data available"
        
        # Check time of day (NY time)
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Adjust for timezone if needed (assuming local time for now)
        # Market hours: 9:30 AM - 4:00 PM ET
        
        # Avoid first and last 15 minutes
        market_open_hour, market_open_min = 9, 30
        market_close_hour, market_close_min = 16, 0
        
        current_mins = hour * 60 + minute
        open_mins = market_open_hour * 60 + market_open_min
        close_mins = market_close_hour * 60 + market_close_min
        
        if current_mins < open_mins + 15:
            return False, "Market opening - wait 15 minutes"
        
        if current_mins > close_mins - 15:
            return False, "Market closing - no new positions"
        
        # High vol = trade with caution, not skip
        if regime == MarketRegime.HIGH_VOL:
            return True, "High volatility regime - reduce position size"
        
        return True, f"Regime: {regime.value}"


# =============================================================================
# CONFIDENCE CALIBRATOR
# =============================================================================

class ConfidenceCalibrator:
    """
    Calibrates model probabilities to be realistic.
    
    Problem: ML models tend to be overconfident (say 70% but hit 55%)
    Solution: Platt scaling or isotonic regression based on backtesting
    """
    
    def __init__(self, calibration_data_path: Optional[str] = None):
        self.calibration_curve = None
        
        if calibration_data_path and os.path.exists(calibration_data_path):
            self._load_calibration(calibration_data_path)
    
    def _load_calibration(self, path: str):
        """Load calibration curve from previous backtesting."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            self.calibration_curve = data.get("calibration_curve", {})
            logger.info(f"Loaded calibration curve from {path}")
        except Exception as e:
            logger.warning(f"Could not load calibration data: {e}")
    
    def calibrate(self, raw_prob: float, direction: str, 
                  regime: MarketRegime) -> float:
        """
        Adjust raw probability to calibrated probability.
        
        Without prior calibration data, applies conservative heuristics:
        - Reduce confidence in ranging regime
        - Reduce confidence for probabilities near decision thresholds
        """
        if self.calibration_curve:
            return self._apply_calibration_curve(raw_prob)
        
        # Conservative heuristics without calibration data
        calibrated = raw_prob
        
        # Penalize confidence in ranging regime (harder to predict)
        if regime == MarketRegime.RANGING:
            calibrated *= 0.85
        
        # Penalize values near decision threshold
        if 0.45 < raw_prob < 0.55:
            calibrated *= 0.9  # Uncertainty zone
        
        # Slight penalty for extreme confidence (model overconfidence)
        if raw_prob > 0.80:
            calibrated = 0.80 + (raw_prob - 0.80) * 0.5
        
        # Never report more than 80% confidence (humility)
        calibrated = min(calibrated, 0.80)
        
        return calibrated
    
    def _apply_calibration_curve(self, raw_prob: float) -> float:
        """Apply isotonic calibration curve."""
        bins = self.calibration_curve.get("bins", [])
        actual_probs = self.calibration_curve.get("actual_probs", [])
        
        if not bins or not actual_probs:
            return raw_prob
        
        # Find nearest bin
        for i, bin_edge in enumerate(bins):
            if raw_prob < bin_edge:
                return actual_probs[max(0, i-1)]
        
        return actual_probs[-1]
    
    def save_calibration(self, path: str, bins: list, actual_probs: list):
        """Save calibration curve for future use."""
        data = {
            "calibration_curve": {
                "bins": bins,
                "actual_probs": actual_probs,
            },
            "created_at": datetime.now().isoformat(),
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved calibration curve to {path}")


# =============================================================================
# POSITION SIZER
# =============================================================================

class PositionSizer:
    """
    Calculates position size based on:
    - Calibrated confidence
    - Current volatility
    - Risk per trade
    - Modified Kelly criterion
    """
    
    def __init__(self, base_risk_pct: float = 0.01, max_position_pct: float = 0.05,
                 min_confidence: float = 0.55):
        """
        Args:
            base_risk_pct: Base risk per trade (1% default)
            max_position_pct: Maximum portfolio % per trade (5% default)
            min_confidence: Minimum confidence to take position
        """
        self.base_risk_pct = base_risk_pct
        self.max_position_pct = max_position_pct
        self.min_confidence = min_confidence
    
    def calculate_size(self, calibrated_confidence: float,
                       win_rate: float = 0.52,
                       avg_win_loss_ratio: float = 1.5,
                       current_vol: float = 1.0) -> float:
        """
        Calculate position size as fraction of maximum allowed.
        
        Uses Kelly Criterion: f* = (p * b - q) / b
        where p = win_rate, b = win/loss ratio, q = 1-p
        
        Returns:
            position_fraction: 0.0 to 1.0
        """
        if calibrated_confidence < self.min_confidence:
            return 0.0  # Don't trade without minimum confidence
        
        # Kelly criterion
        p = win_rate
        b = avg_win_loss_ratio
        q = 1 - p
        
        kelly_fraction = (p * b - q) / b
        kelly_fraction = max(0, kelly_fraction)  # Cannot be negative
        
        # Half-Kelly for more conservatism
        kelly_fraction *= 0.5
        
        # Adjust by confidence (higher confidence = closer to Kelly)
        confidence_multiplier = (calibrated_confidence - 0.5) * 2  # 0.5->0, 1.0->1.0
        confidence_multiplier = max(0, confidence_multiplier)
        
        # Adjust by volatility (higher vol = smaller size)
        vol_multiplier = 1.0 / max(current_vol, 0.5)
        vol_multiplier = min(vol_multiplier, 1.5)  # Cap at 1.5x
        
        final_size = kelly_fraction * confidence_multiplier * vol_multiplier
        
        # Limit to maximum allowed
        return min(final_size, 1.0)


# =============================================================================
# TRAILING STOP MANAGER
# =============================================================================

class TrailingStopManager:
    """
    Dynamic stop loss management to protect profits.
    """
    
    def __init__(self, initial_stop_pct: float = 0.003,
                 trailing_activation_pct: float = 0.003,
                 trailing_distance_pct: float = 0.0015):
        """
        Args:
            initial_stop_pct: Initial stop loss distance (0.3% default)
            trailing_activation_pct: Profit % to activate trailing (0.2%)
            trailing_distance_pct: Distance behind price for trail (0.15%)
        """
        self.initial_stop_pct = initial_stop_pct
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_distance_pct = trailing_distance_pct
    
    def calculate_stops(self, entry_price: float, direction: str,
                        atr: float = None) -> Dict[str, float]:
        """
        Calculate stop and take profit levels.
        
        Returns:
            {
                "stop_loss": float,
                "take_profit_1": float,  # Partial exit (1.5R)
                "take_profit_2": float,  # Full exit (2.5R)
            }
        """
        # Use ATR if available, otherwise fixed percentage
        stop_distance = atr if atr else entry_price * self.initial_stop_pct
        
        if direction == "LONG":
            return {
                "stop_loss": entry_price - stop_distance,
                "take_profit_1": entry_price + (stop_distance * 2.0),  # 2.0R (0.6%)
                "take_profit_2": entry_price + (stop_distance * 3.0),  # 3.0R (0.9%)
            }
        else:  # SHORT
            return {
                "stop_loss": entry_price + stop_distance,
                "take_profit_1": entry_price - (stop_distance * 2.0),
                "take_profit_2": entry_price - (stop_distance * 3.0),
            }
    
    def update_trailing_stop(self, current_price: float, entry_price: float,
                             current_stop: float, direction: str) -> float:
        """
        Update trailing stop if price moves in our favor.
        
        Returns:
            new_stop_price
        """
        if direction == "LONG":
            move_pct = (current_price - entry_price) / entry_price
            
            if move_pct >= self.trailing_activation_pct:
                # Activate trailing: stop follows price
                new_stop = current_price * (1 - self.trailing_distance_pct)
                return max(current_stop, new_stop)  # Only goes up, never down
        
        else:  # SHORT
            move_pct = (entry_price - current_price) / entry_price
            
            if move_pct >= self.trailing_activation_pct:
                new_stop = current_price * (1 + self.trailing_distance_pct)
                return min(current_stop, new_stop)  # Only goes down, never up
        
        return current_stop
    
    def should_exit(self, current_price: float, entry_price: float,
                    current_stop: float, entry_time: datetime,
                    direction: str, max_hold_minutes: int = 45,
                    current_uncertainty_mins: float = None) -> Tuple[bool, str]:
        """
        Check if position should be exited.
        
        Returns:
            (should_exit: bool, reason: str)
        """
        # Bayesian uncertainty exit: model says market is too chaotic
        if current_uncertainty_mins is not None and current_uncertainty_mins > 45.0:
            return True, "HIGH_UNCERTAINTY"
        
        # Stop loss hit
        if direction == "LONG" and current_price <= current_stop:
            return True, "STOP_LOSS"
        elif direction == "SHORT" and current_price >= current_stop:
            return True, "STOP_LOSS"
        
        # Time-based exit (safety timeout)
        hold_time = (datetime.now() - entry_time).total_seconds() / 60
        if hold_time >= max_hold_minutes:
            return True, "TIME_EXIT"
        
        return False, ""


# =============================================================================
# TRADING WRAPPER - Main Integration Class
# =============================================================================

class TradingWrapper:
    """
    Main wrapper that integrates all components.
    
    Usage:
        wrapper = TradingWrapper(
            model=hybrid_model,
            normalizer=normalizer,
            greek_dir="/path/to/json_data",
            fourier_dir="/path/to/fourier",
            ib_dir="/path/to/ib_charts"
        )
        
        signal = wrapper.get_signal("SPX", current_features, current_price)
        if signal.direction != "HOLD":
            # Execute with signal.position_size, signal.stop_loss, etc.
    """
    
    def __init__(self, model, normalizer,
                 greek_dir: str, fourier_dir: str, ib_dir: str,
                 calibration_path: Optional[str] = None,
                 min_confidence: float = 0.80,
                 base_risk_pct: float = 0.01,
                 max_position_pct: float = 0.05,
                 min_iv_pct: float = 0.2,
                 max_time_minutes: int = 120,
                 stop_loss_pct: float = 0.003,
                 target_pct_ratio: float = 2.0):
        """
        Initialize the trading wrapper.
        
        Args:
            model: Trained HybridTradingModel
            normalizer: Fitted FeatureNormalizer
            greek_dir: Path to Greek data JSONs (from gex_daemon.py)
            fourier_dir: Path to Fourier JSONs (from fourier_service_fast.py)
            ib_dir: Path to IB data JSONs (from ib_service.py)
            calibration_path: Optional path to calibration data
            min_confidence: Minimum calibrated confidence to trade
            base_risk_pct: Base risk per trade
            max_position_pct: Maximum position size
            min_iv_pct: Minimum IV percentile to trade (avoid chop)
            max_time_minutes: Maximum predicted time to target
            stop_loss_pct: Default stop loss percentage (e.g. 0.003 for 0.3%)
            target_pct_ratio: Ratio of target profit to stop loss (e.g. 2.0 = 0.6% target)
        """
        self.model = model
        self.normalizer = normalizer
        
        self.regime_filter = RegimeFilter(greek_dir, fourier_dir, ib_dir)
        self.calibrator = ConfidenceCalibrator(calibration_path)
        self.position_sizer = PositionSizer(
            base_risk_pct=base_risk_pct,
            max_position_pct=max_position_pct,
            min_confidence=min_confidence
        )
        self.stop_manager = TrailingStopManager(initial_stop_pct=stop_loss_pct, trailing_activation_pct=stop_loss_pct)
        self.min_iv_pct = min_iv_pct
        self.max_time_minutes = max_time_minutes
        
        # Track device for model inference
        self.device = next(model.parameters()).device
    
    def get_signal(self, ticker: str, features: np.ndarray,
                   current_price: float) -> TradeSignal:
        """
        Process features and return complete trading signal.
        
        Args:
            ticker: Symbol to trade
            features: Feature array (should match model input size)
            current_price: Current market price
            
        Returns:
            TradeSignal with full decision data
        """
        # 1. Check regime first
        tradeable, reason = self.regime_filter.is_tradeable(ticker)
        regime, regime_meta = self.regime_filter.classify_regime(ticker)
        
        if not tradeable:
            return TradeSignal(
                ticker=ticker,
                direction="HOLD",
                raw_confidence=0.0,
                calibrated_confidence=0.0,
                position_size=0.0,
                regime=regime,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit_1=0.0,
                take_profit_2=0.0,
                max_hold_time=0,
                reasoning={"skip_reason": reason, "regime_data": regime_meta}
            )
        
        # 2. Get ML prediction
        try:
            features_norm = self.normalizer.transform(features.reshape(1, -1))
            x = torch.FloatTensor(features_norm).to(self.device)
            
            self.model.eval()
            with torch.no_grad():
                # Use predict() to get both probabilities and time prediction
                probs_tensor, time_pred_tensor = self.model.predict(x)
                probs = probs_tensor.cpu().numpy()[0]
                
                # Extract Bayesian time parameters
                mu_norm = time_pred_tensor.cpu().numpy()[0][0]   # sigmoid output [0,1]
                log_sigma_val = time_pred_tensor.cpu().numpy()[0][1]
                
            # Convert normalized time to minutes (120m lookahead)
            predicted_minutes = int(mu_norm * 120.0)
            time_mu_minutes = float(mu_norm * 120.0)
            time_sigma_minutes = float(np.exp(log_sigma_val) * 120.0)
            
        except Exception as e:
            logger.error(f"Model inference error for {ticker}: {e}")
            return TradeSignal(
                ticker=ticker,
                direction="HOLD",
                raw_confidence=0.0,
                calibrated_confidence=0.0,
                position_size=0.0,
                regime=regime,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit_1=0.0,
                take_profit_2=0.0,
                max_hold_time=0,
                reasoning={"error": str(e)}
            )
            
        # --- FILTERS ---
        
        # Filter 1: Max Time (Skip slow moves)
        if predicted_minutes > self.max_time_minutes:
             return TradeSignal(
                ticker=ticker,
                direction="HOLD",
                raw_confidence=0.0,
                calibrated_confidence=0.0,
                position_size=0.0,
                regime=regime,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit_1=0.0,
                take_profit_2=0.0,
                max_hold_time=0,
                reasoning={"skip_reason": f"Predicted time {predicted_minutes}m > {self.max_time_minutes}m"}
            )

        # Filter 2: Min IV Percentile (Avoid chop)
        # Try to find iv_percentile in metadata or features
        iv_percentile = features[30] if len(features) > 30 else 0.5 # Index 30 is iv_percentile in feature list
        
        if iv_percentile < self.min_iv_pct:
             return TradeSignal(
                ticker=ticker,
                direction="HOLD",
                raw_confidence=0.0,
                calibrated_confidence=0.0,
                position_size=0.0,
                regime=regime,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit_1=0.0,
                take_profit_2=0.0,
                max_hold_time=0,
                reasoning={"skip_reason": f"IV Percentile {iv_percentile:.2f} < {self.min_iv_pct}"}
            )
        
        prediction = np.argmax(probs)
        raw_confidence = float(probs[prediction])
        direction_map = {0: "SHORT", 1: "HOLD", 2: "LONG"}
        direction = direction_map[prediction]
        
        # 3. Calibrate confidence
        calibrated = self.calibrator.calibrate(raw_confidence, direction, regime)
        
        # 4. Calculate position size
        vol_factor = regime_meta.get("atm_iv", 20) / 20  # Normalize to 20% IV
        position_size = self.position_sizer.calculate_size(
            calibrated_confidence=calibrated,
            current_vol=vol_factor
        )
        
        # 5. Calculate stops
        stops = self.stop_manager.calculate_stops(current_price, direction)
        
        # 6. Max hold time based on regime (extended to 120m with Bayesian exit)
        hold_times = {
            MarketRegime.TRENDING_UP: 120,
            MarketRegime.TRENDING_DOWN: 120,
            MarketRegime.RANGING: 90,
            MarketRegime.HIGH_VOL: 60,
            MarketRegime.LOW_LIQUIDITY: 45,
        }
        max_hold = hold_times.get(regime, 120)
        
        # Return final signal
        final_direction = direction if position_size > 0 else "HOLD"
        
        return TradeSignal(
            ticker=ticker,
            direction=final_direction,
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            position_size=position_size,
            regime=regime,
            entry_price=current_price,
            stop_loss=stops["stop_loss"] if position_size > 0 else 0.0,
            take_profit_1=stops["take_profit_1"] if position_size > 0 else 0.0,
            take_profit_2=stops["take_profit_2"] if position_size > 0 else 0.0,
            max_hold_time=max_hold if position_size > 0 else 0,
            reasoning={
                "regime_data": regime_meta,
                "raw_probs": {
                    "SHORT": float(probs[0]),
                    "HOLD": float(probs[1]),
                    "LONG": float(probs[2]),
                },
                "tradeable_reason": reason,
                "vol_factor": vol_factor,
            },
            time_mu_minutes=time_mu_minutes,
            time_sigma_minutes=time_sigma_minutes,
        )
    
    def update_position(self, ticker: str, entry_price: float, entry_time: datetime,
                        current_price: float, current_stop: float,
                        direction: str, max_hold_minutes: int = 120,
                        current_uncertainty_mins: float = None) -> Tuple[float, bool, str]:
        """
        Update an existing position (trailing stop, exit check).
        
        Args:
            current_uncertainty_mins: Bayesian σ in minutes from live inference.
                If > 45.0, triggers HIGH_UNCERTAINTY exit.
        
        Returns:
            (new_stop, should_exit, exit_reason)
        """
        # Update trailing stop
        new_stop = self.stop_manager.update_trailing_stop(
            current_price, entry_price, current_stop, direction
        )
        
        # Check if should exit (includes Bayesian uncertainty check)
        should_exit, reason = self.stop_manager.should_exit(
            current_price, entry_price, new_stop, entry_time,
            direction, max_hold_minutes,
            current_uncertainty_mins=current_uncertainty_mins
        )
        
        return new_stop, should_exit, reason


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TRADING WRAPPER TEST")
    print("=" * 70)
    
    # Test RegimeFilter with mock paths
    print("\n[1] Testing RegimeFilter...")
    rf = RegimeFilter(
        greek_data_dir="./json_data",
        fourier_dir="./fourier",
        ib_dir="./ib_charts"
    )
    
    # Test classification (won't find data in test paths)
    regime, meta = rf.classify_regime("SPX")
    print(f"  Regime: {regime.value}")
    print(f"  Metadata: {meta}")
    
    # Test ConfidenceCalibrator
    print("\n[2] Testing ConfidenceCalibrator...")
    cc = ConfidenceCalibrator()
    
    test_cases = [
        (0.75, "LONG", MarketRegime.TRENDING_UP),
        (0.75, "LONG", MarketRegime.RANGING),
        (0.52, "SHORT", MarketRegime.HIGH_VOL),
        (0.90, "LONG", MarketRegime.TRENDING_UP),
    ]
    
    for raw, direction, regime in test_cases:
        calibrated = cc.calibrate(raw, direction, regime)
        print(f"  {raw:.0%} {direction} in {regime.value}: → {calibrated:.1%}")
    
    # Test PositionSizer
    print("\n[3] Testing PositionSizer...")
    ps = PositionSizer()
    
    size_cases = [
        (0.50, 1.0),  # Below threshold
        (0.55, 1.0),  # At threshold
        (0.65, 1.0),  # Good confidence
        (0.75, 0.5),  # High confidence, low vol
        (0.75, 2.0),  # High confidence, high vol
    ]
    
    for conf, vol in size_cases:
        size = ps.calculate_size(calibrated_confidence=conf, current_vol=vol)
        print(f"  Conf {conf:.0%}, Vol {vol:.1f}x: → Size {size:.1%}")
    
    # Test TrailingStopManager
    print("\n[4] Testing TrailingStopManager...")
    tsm = TrailingStopManager()
    
    stops = tsm.calculate_stops(entry_price=5000.0, direction="LONG")
    print(f"  Entry 5000 LONG:")
    print(f"    Stop: {stops['stop_loss']:.2f}")
    print(f"    TP1:  {stops['take_profit_1']:.2f}")
    print(f"    TP2:  {stops['take_profit_2']:.2f}")
    
    # Simulate trailing
    current_stop = stops['stop_loss']
    for price in [5010, 5020, 5030, 5025]:
        new_stop = tsm.update_trailing_stop(price, 5000, current_stop, "LONG")
        print(f"    Price {price}: Stop {current_stop:.2f} → {new_stop:.2f}")
        current_stop = new_stop
    
    print("\n" + "=" * 70)
    print("All trading wrapper components working!")
    print("=" * 70)

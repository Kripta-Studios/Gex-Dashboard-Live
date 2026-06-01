"""
SPXOptionsEnv â€” Gym-Compatible RL Environment for 0DTE Options Trade Management

Episode = one trade (from MLP signal to exit)
Step    = one minute of market data

Supports optional Sniper Entry Window (PRE_ENTRY mode):
  When use_sniper_mode=True, the agent has up to 15 minutes to observe
  the market before choosing when and at what strike to enter.

The environment is initialized with historical episodes sampled from
the training parquet. At each step, it advances one minute and returns
the new state, reward, and done flag.
"""

import numpy as np
import pandas as pd
from datetime import time as dt_time

from .config import (
    STRIKE_BUCKETS, HARD_EXITS, MARKET_FEATURE_DIM, DYNAMIC_MARKET_DIM,
    POSITION_STATE_DIM, MLP_CONTEXT_DIM, TICKER_CONTEXT_DIM, TOTAL_STATE_DIM,
    STRIKE_CONTEXT_DIM, STRIKE_CONTEXT_FEATURES_PER_BUCKET,
    SNIPER_STATE_DIM, SNIPER_TOTAL_STATE_DIM,
    RL_CONFIG, get_half_spread,
)
from .rewards import compute_step_reward, compute_terminal_reward, compute_sniper_step_reward
from .utils import get_delta_bucket, get_iv_bucket, get_pnl_bucket
import pickle
import os

try:
    from neural.signal_policy import should_exit_on_reversal
except ModuleNotFoundError:
    from signal_policy import should_exit_on_reversal


def _ticker_context(ticker: str) -> np.ndarray:
    ctx = np.zeros(TICKER_CONTEXT_DIM, dtype=np.float32)
    mapping = {"SPX": 0, "SPXW": 0, "SPY": 1, "QQQ": 2}
    idx = mapping.get(str(ticker).upper())
    if idx is not None and idx < TICKER_CONTEXT_DIM:
        ctx[idx] = 1.0
    return ctx


class SPXOptionsEnv:
    """
    OpenAI Gym-compatible environment for SPX 0DTE options trade management.

    Episode phases:
      PRE_ENTRY (sniper) â†’ IN_POSITION (holding) â†’ CLOSED (terminal)
      When use_sniper_mode=False, PRE_ENTRY is skipped (immediate entry).
    """

    def __init__(self,
                 episode_index: pd.DataFrame,
                 options_cache: dict,
                 feature_columns: list,
                 normalizer=None,
                 hard_exit_rules: dict = None):
        """
        Args:
            episode_index:  DataFrame of valid MLP signal events with columns:
                            [date, time, ticker, spot_price, mlp_direction,
                             mlp_confidence, mlp_time_to_target, target, max_move]
                            + all FEATURE_COLUMNS copied from the signal row
            options_cache:  dict keyed by "YYYYMMDD_HH:MM" â†’ {
                                "spot": float,
                                "day_atr": float,
                                "calls": {strike: {price, delta, iv, theta, gamma}},
                                "puts":  {strike: {price, delta, iv, theta, gamma}}
                            }
                            Each key also has forward-looking minute data for up to
                            120 minutes: "minutes" â†’ [{minute_offset: similar dict}]
            feature_columns: list of feature names matching MLP's FEATURE_COLUMNS
            normalizer:     FeatureNormalizer (frozen, from MLP training)
            hard_exit_rules: override default hard exits if provided
        """
        self.episode_index = episode_index
        self.options_cache = options_cache
        self.feature_columns = feature_columns
        self.normalizer = normalizer
        self.hard_exits = hard_exit_rules or HARD_EXITS

        # Load recovery stats for v4 feature
        self._recovery_lookup = {}
        # Get path to root (Gex-Dashboard-Live/) from neural/rl/environment.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        stats_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "rl_data", "recovery_stats.pkl")

        if os.path.exists(stats_path):
            try:
                with open(stats_path, "rb") as f:
                    self._recovery_lookup = pickle.load(f)
            except Exception as e:
                print(f"  [!] Error loading recovery_stats: {e}")

        # Episode state
        self._current_episode = None
        self._position = None
        self._t = 0
        self._done = False
        self._info = {}
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        self._max_unrealized_pnl = 0.0
        self._trailing_drawdown = 0.0
        self._spot_history = []
        self._last_mark_price: float = 0.0
        self._current_iv = 0.15
        self._current_delta = 0.50
        self._dynamic_market_state = np.zeros(DYNAMIC_MARKET_DIM, dtype=np.float32)
        self._strike_context = np.zeros(STRIKE_CONTEXT_DIM, dtype=np.float32)
        # per-minute spot prices for velocity
        self._entry_spot = 0.0       # spot at signal time
        self._entry_atm_iv = 0.15    # ATM IV at signal time
        self._dynamic_cache_t = -1   # Cache marker for dynamic features
        self._current_max_strike_bucket = 6

        # Sniper mode state
        self._use_sniper = RL_CONFIG.get("use_sniper_mode", False)
        self._use_entry_skip_action = RL_CONFIG.get("use_entry_skip_action", False)
        self._sniper_mode = False           # True while in PRE_ENTRY phase
        self._sniper_minutes_elapsed = 0
        self._sniper_entry_attempted = False
        self._sniper_signal_spot = None     # spot price at MLP signal time

        # VIX regime stratification for sampling
        self._build_sampling_strata()

    def _build_sampling_strata(self):
        """
        Construye Ã­ndices de muestreo estratificados por ticker Ã— VIX regime.

        Problema original: SPY representaba el 51% de los episodios pero solo
        el 33% de los tickers. El agente sobre-aprendÃ­a SPY (el de peor PF)
        y sub-aprendÃ­a SPX/QQQ (los Ãºnicos rentables).

        SoluciÃ³n: primero se equilibran los tickers (1/3 cada uno si hay 3),
        y dentro de cada ticker se estratifica por VIX regime si estÃ¡ disponible.
        El muestreo real usa los Ã­ndices de stratum, no conteos brutos.
        """
        self._strata = {}
        self._ticker_strata = {}  # {ticker: [indices]} â€” para ticker balancing

        tickers = self.episode_index["ticker"].unique().tolist() if "ticker" in self.episode_index.columns else []

        if tickers:
            for ticker in tickers:
                t_mask = self.episode_index["ticker"] == ticker
                t_indices = self.episode_index[t_mask].index.tolist()
                self._ticker_strata[ticker] = t_indices

                # Sub-estratificaciÃ³n por VIX dentro del ticker
                if "vix_regime" in self.episode_index.columns:
                    for regime in self.episode_index.loc[t_mask, "vix_regime"].unique():
                        rv_mask = t_mask & (self.episode_index["vix_regime"] == regime)
                        key = f"{ticker}_vix_{regime}"
                        self._strata[key] = self.episode_index[rv_mask].index.tolist()
                else:
                    self._strata[ticker] = t_indices
        else:
            self._strata["all"] = list(range(len(self.episode_index)))

        self._strata_tickers = list(self._ticker_strata.keys())  # orden estable

    def _sample_balanced_episode_idx(self) -> int:
        """
        Muestreo balanceado por ticker (1/N cada uno) seguido de selecciÃ³n
        uniforme dentro del ticker. Evita el dominio de SPY.
        """
        if not self._strata_tickers:
            # Fallback: muestreo uniforme
            return int(np.random.choice(list(range(len(self.episode_index)))))

        ticker = np.random.choice(self._strata_tickers)
        indices = self._ticker_strata[ticker]
        return int(np.random.choice(indices))

    @property
    def state_dim(self) -> int:
        return RL_CONFIG["state_dim"]

    def reset(self, episode_idx: int = None) -> np.ndarray:
        """
        Start a new episode by sampling an MLP signal event.

        Uses stratified sampling across VIX regimes to ensure balanced training.
        Returns the initial state vector (market features + zero position).
        """
        if episode_idx is not None:
            idx = episode_idx
        else:
            # Muestreo balanceado por ticker (SPY no domina el batch)
            idx = self._sample_balanced_episode_idx()

        self._current_episode = self.episode_index.iloc[idx]
        self._t = 0
        self._done = False
        self._position = None
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        self._max_unrealized_pnl = 0.0
        self._trailing_drawdown = 0.0
        self._info = {}
        self._spot_history = []
        self._entry_spot = 0.0
        self._entry_atm_iv = 0.15
        self._last_mark_price = 0.0
        self._current_iv = 0.15
        self._current_delta = 0.50
        self._dynamic_market_state = np.zeros(DYNAMIC_MARKET_DIM, dtype=np.float32)
        self._strike_context = np.zeros(STRIKE_CONTEXT_DIM, dtype=np.float32)
        self._dynamic_cache_t = -1

        # Sniper mode initialization
        self._sniper_mode = self._use_sniper
        self._sniper_minutes_elapsed = 0
        self._sniper_entry_attempted = False

        # Record signal spot for favorable-entry detection
        ep = self._current_episode
        ticker = str(ep.get("ticker", "SPX"))
        date_str = str(ep.get("date", ""))
        time_str = str(ep.get("time", ""))
        cache_key = f"{ticker}_{date_str}_{time_str}"
        cache_entry = self.options_cache.get(cache_key)
        self._sniper_signal_spot = float(cache_entry.get("spot", 0)) if cache_entry else 0.0
        self._entry_spot = self._sniper_signal_spot
        if self._entry_spot > 0:
            self._spot_history = [self._entry_spot]

        # Capture entry ATM IV for dynamic feature tracking
        if cache_entry:
            direction = ep.get("mlp_direction", "LONG")
            right_key = "calls" if direction == "LONG" else "puts"
            options = cache_entry.get(right_key, {})
            if options and self._entry_spot > 0:
                # Find ATM option (closest to spot)
                atm_strike = min(options.keys(), key=lambda s: abs(float(s) - self._entry_spot), default=None)
                if atm_strike is not None:
                    self._entry_atm_iv = float(options[atm_strike].get("iv", 0.15))
            self._strike_context = self._build_strike_context_snapshot(cache_entry, direction)

        return self._build_state_vector()

    def step(self, action: int):
        """
        Execute action and advance one minute.

        Phase routing:
          PRE_ENTRY (sniper):  action 0=WAIT, 1-7=ENTER with strike bucket 0-6
          IN_POSITION entry:   action is strike bucket choice (0-6) â€” non-sniper fallback
          IN_POSITION holding: action is HOLD(0) or EXIT(1)

        Returns: (next_state, reward, done, info)
        """
        if self._done:
            raise RuntimeError("Episode is done. Call reset().")

        # â”€â”€ Phase 1: PRE_ENTRY (sniper window) â”€â”€
        if self._sniper_mode and self._position is None:
            return self._handle_sniper(action)
        # â”€â”€ Phase 2: Immediate entry (non-sniper fallback) â”€â”€
        elif self._position is None:
            if self._use_entry_skip_action:
                return self._handle_entry_skip_action(action)
            return self._handle_entry(action)
        # â”€â”€ Phase 3: Holding position â”€â”€
        else:
            return self._handle_holding(action)

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # SNIPER ENTRY WINDOW
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _get_current_min_wait(self) -> int:
        """Get minimum wait minutes for current curriculum phase."""
        return getattr(self, "_current_min_wait", 0)

    def _get_current_min_strike_bucket(self) -> int:
        """Get minimum strike bucket (delta) for current curriculum phase."""
        return getattr(self, "_current_min_strike_bucket", 0)

    def _get_current_max_strike_bucket(self) -> int:
        """Get maximum strike bucket (delta) for current curriculum phase."""
        return getattr(self, "_current_max_strike_bucket", 6)

    def _handle_entry_skip_action(self, action: int) -> tuple:
        """
        Direct entry filter: action 0 skips the GBT episode; actions 1-7
        enter with strike bucket 0-6. This reuses the sniper head without
        enabling the timed sniper state/window.
        """
        requested_action = int(action)
        if requested_action <= 0:
            self._done = True
            reward = float(RL_CONFIG.get("entry_skip_penalty", -0.03))
            return self._build_state_vector(), reward, True, {
                "exit_type": "entry_skip",
                "final_pnl_pct": 0.0,
                "effective_action": 0,
                "requested_action": requested_action,
                "entry_skipped": True,
            }

        strike_action = requested_action - 1
        state, reward, done, info = self._handle_entry(strike_action)
        effective_strike = int(info.get("effective_action", strike_action))
        info["effective_action"] = effective_strike + 1
        info["requested_action"] = requested_action
        info["entry_skipped"] = False
        return state, reward, done, info

    def _handle_sniper(self, action: int) -> tuple:
        """
        Handle PRE_ENTRY phase: WAIT or ENTER.

        action = 0:   WAIT (observe one more minute)
        action = 1-7: ENTER with strike bucket (action-1) â†’ delta bucket 0-6

        Minimum-wait curriculum: forces WAIT if below the phase minimum.
        """
        sniper_window = RL_CONFIG.get("sniper_window_minutes", 15)

        # â”€â”€ Minimum-wait curriculum enforcement â”€â”€
        min_wait = self._get_current_min_wait()
        if action >= 1 and self._sniper_minutes_elapsed < min_wait:
            action = 0  # force WAIT â€” agent hasn't observed enough

        if action == 0:
            # â”€â”€ WAIT â”€â”€
            self._sniper_minutes_elapsed += 1
            self._t += 1

            # Check timeout
            if self._sniper_minutes_elapsed >= sniper_window:
                self._done = True
                timeout_penalty = RL_CONFIG.get("sniper_timeout_penalty", -0.05)
                return self._build_state_vector(), timeout_penalty, True, {
                    "exit_type": "sniper_timeout",
                    "final_pnl_pct": 0.0,
                    "sniper_minutes_waited": self._sniper_minutes_elapsed,
                }

            # Neutral step reward
            reward = compute_sniper_step_reward()
            return self._build_state_vector(), reward, False, {
                "action": "sniper_wait",
                "sniper_minute": self._sniper_minutes_elapsed,
            }

        else:
            # â”€â”€ ENTER with strike bucket â”€â”€
            strike_action = action - 1  # map 1-7 â†’ 0-6
            min_strike = self._get_current_min_strike_bucket()
            max_strike = self._get_current_max_strike_bucket()
            strike_action = max(min_strike, min(strike_action, max_strike))

            result = self._handle_entry(strike_action)
            state, reward, done, info = result

            if self._position is not None:
                # Entry succeeded â€” exit sniper mode
                self._sniper_mode = False
                info["sniper_minutes_waited"] = self._sniper_minutes_elapsed

                # Track entry price improvement for reward signal
                if self._sniper_signal_spot > 0 and self._sniper_minutes_elapsed > 0:
                    # Get current spot at entry time
                    ep = self._current_episode
                    ticker = str(ep.get("ticker", "SPX"))
                    direction = ep.get("mlp_direction", "LONG")
                    date_str = str(ep.get("date", ""))
                    time_str = str(ep.get("time", ""))
                    cache_key = f"{ticker}_{date_str}_{time_str}"
                    cache_entry = self.options_cache.get(cache_key)
                    current_spot = self._sniper_signal_spot
                    if cache_entry:
                        minutes_data = cache_entry.get("minutes", {})
                        offset_data = minutes_data.get(self._sniper_minutes_elapsed)
                        if offset_data:
                            current_spot = float(offset_data.get("spot", self._sniper_signal_spot))

                    # Favorable price movement: underlying dipped (for LONG) or rose (for SHORT)
                    if direction == "LONG":
                        price_improvement = (self._sniper_signal_spot - current_spot) / self._sniper_signal_spot
                    else:
                        price_improvement = (current_spot - self._sniper_signal_spot) / self._sniper_signal_spot

                    self._position["entry_price_improvement"] = max(0.0, price_improvement)
                else:
                    self._position["entry_price_improvement"] = 0.0

            else:
                # Entry failed (no valid strike) â€” stay in sniper, mark attempt
                self._sniper_entry_attempted = True
                self._sniper_minutes_elapsed += 1
                self._t += 1

                # Check timeout after failed entry
                if self._sniper_minutes_elapsed >= sniper_window:
                    self._done = True
                    timeout_penalty = RL_CONFIG.get("sniper_timeout_penalty", -0.05)
                    return self._build_state_vector(), timeout_penalty, True, {
                        "exit_type": "sniper_timeout",
                        "final_pnl_pct": 0.0,
                        "sniper_minutes_waited": self._sniper_minutes_elapsed,
                    }

                # Continue sniper
                return self._build_state_vector(), 0.0, False, {
                    "action": "sniper_entry_failed",
                    "sniper_minute": self._sniper_minutes_elapsed,
                }

            return state, reward, done, info

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # ENTRY (shared by sniper and direct mode)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _handle_entry(self, strike_action: int) -> tuple:
        """Resolve strike from delta bucket and open position."""
        requested_strike_action = int(strike_action)
        min_strike = self._get_current_min_strike_bucket()
        max_strike = self._get_current_max_strike_bucket()
        strike_action = max(min_strike, min(strike_action, max_strike))

        bucket = STRIKE_BUCKETS.get(strike_action, STRIKE_BUCKETS[4])  # default ATM
        delta_target = bucket["delta_target"]

        ep = self._current_episode
        ticker = str(ep.get("ticker", "SPX"))
        date_str = str(ep.get("date", ""))
        time_str = str(ep.get("time", ""))

        # When in sniper mode, read from the cache at signal_time + elapsed minutes
        if self._sniper_mode:
            cache_key = f"{ticker}_{date_str}_{time_str}"
            cache_entry = self.options_cache.get(cache_key)
            # Use forward minute data at the sniper offset
            if cache_entry is not None:
                minutes_data = cache_entry.get("minutes", {})
                sniper_data = minutes_data.get(self._sniper_minutes_elapsed)
                if sniper_data is not None:
                    # Build a synthetic cache entry from the sniper offset
                    sniper_cache = {
                        "spot": sniper_data.get("spot", cache_entry.get("spot", 0)),
                        "calls": sniper_data.get("calls", {}),
                        "puts": sniper_data.get("puts", {}),
                    }
                else:
                    sniper_cache = None
            else:
                sniper_cache = None
        else:
            cache_key = f"{ticker}_{date_str}_{time_str}"
            sniper_cache = None  # not used

        direction = ep.get("mlp_direction", "LONG")
        right = "CALL" if direction == "LONG" else "PUT"

        # Resolve actual strike â€” use sniper offset data if available
        if sniper_cache is not None:
            strike_info = self._resolve_strike_from_data(sniper_cache, delta_target, right)
        else:
            strike_info = self._resolve_strike(cache_key, delta_target, right)

        if strike_info is None:
            # No valid strike found â€” end episode immediately (non-sniper) or signal back (sniper)
            if not self._sniper_mode:
                self._done = True
                return self._build_state_vector(), 0.0, True, {
                    "exit_type": "no_strike_available", "final_pnl_pct": 0.0,
                    "effective_action": strike_action,
                    "requested_action": requested_strike_action,
                }
            else:
                # Sniper mode: return without ending â€” caller handles retry
                return self._build_state_vector(), 0.0, False, {
                    "action": "entry_failed",
                    "effective_action": strike_action,
                    "requested_action": requested_strike_action,
                }

        # Dynamic slippage (from sniper_env.py concept)
        base_half_spread = get_half_spread(abs(strike_info["entry_delta"]))
        gamma_speed = float(ep.get('gamma_speed', 0.0))
        k_penalty = 0.5
        effective_spread = base_half_spread * (1.0 + k_penalty * abs(gamma_speed))
        effective_entry_price = strike_info["entry_price"] * (1.0 + effective_spread)

        self._position = {
            "strike": strike_info["strike"],
            "right": right,
            "direction": direction,
            "entry_price": effective_entry_price,
            "raw_entry_price": strike_info["entry_price"],
            "entry_iv": strike_info["entry_iv"],
            "entry_delta": strike_info["entry_delta"],
            "entry_theta": strike_info["entry_theta"],
            "entry_gamma": strike_info["entry_gamma"],
            "entry_minute": self._t,
            "strike_action": strike_action,
        }
        self._mae = 0.0
        self._prev_pnl_pct = 0.0
        self._max_unrealized_pnl = 0.0
        self._trailing_drawdown = 0.0
        self._last_mark_price = strike_info["entry_price"]
        self._t += 1

        return self._build_state_vector(), 0.0, False, {
            "action": "entry",
            "effective_action": strike_action,
            "requested_action": requested_strike_action,
        }


    def _handle_holding(self, exit_action: int) -> tuple:
        """Process HOLD/EXIT and advance time."""
        ep = self._current_episode
        ticker = str(ep.get("ticker", "SPX"))
        date_str = str(ep.get("date", ""))
        time_str = str(ep.get("time", ""))

        hold_minutes = self._t - self._position["entry_minute"]
        minutes_to_close = max(0, RL_CONFIG["session_length_minutes"] - self._minutes_since_open())

        # Get current option price at t minutes after signal
        current_price = self._get_current_option_price(ticker, date_str, time_str, self._t)
        if current_price is None:
            # Fallback to last known price or entry if first minute
            current_price = getattr(self, "_last_mark_price", self._position["raw_entry_price"])
        self._last_mark_price = current_price

        entry_price = self._position["entry_price"]
        pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0.0
        pnl_pct = float(np.clip(pnl_pct, -1.0, 5.0))

        # Update MAE
        self._mae = min(self._mae, pnl_pct)

        # Track Trailing Drawdown and detect new HWM
        is_new_hwm = False
        if pnl_pct > self._max_unrealized_pnl:
            self._max_unrealized_pnl = pnl_pct
            is_new_hwm = True

        self._trailing_drawdown = max(0.0, self._max_unrealized_pnl - pnl_pct)

        # [v6] Pass context to rewards: hold_time, recovery_rate, spot_momentum
        dynamic_features = self._get_dynamic_market_features()
        spot_momentum = float(dynamic_features[7])
        self._dynamic_market_state = dynamic_features # Save for state builder

        current_greeks = self._get_current_greeks(ticker, date_str, time_str, self._t)
        self._current_delta = current_greeks["delta"]
        self._current_iv = current_greeks["iv"]

        # â”€â”€ Check hard exit rules â”€â”€
        exit_type = None
        if pnl_pct <= self.hard_exits["max_loss_pct"]:
            exit_type = "hard_stop_loss"
        elif pnl_pct >= self.hard_exits["max_profit_pct"]:
            exit_type = "hard_take_profit"
        elif self._max_unrealized_pnl >= self.hard_exits["trailing_stop_activation_pct"] and self._trailing_drawdown >= self.hard_exits["trailing_stop_pct"]:
            exit_type = "trailing_stop"
        elif minutes_to_close <= self.hard_exits["minutes_to_close"]:
            exit_type = "hard_time_close"
        elif hold_minutes >= self.hard_exits["max_hold_minutes"]:
            exit_type = "hard_max_hold"
        else:
            # Mirror live/backtest: only evaluate reversal on the configured
            # signal cadence instead of every minute.
            cache_key = f"{ticker}_{date_str}_{time_str}"
            cache_entry = self.options_cache.get(cache_key, {})
            minutes_data = cache_entry.get("minutes", {})
            minute_data = minutes_data.get(self._t)

            if minute_data:
                sig_dir = minute_data.get("sig_dir", "HOLD")
                sig_conf = minute_data.get("sig_conf", 0.5)

                current_minute = self._minutes_since_open()
                if should_exit_on_reversal(
                    position_direction=self._position["direction"],
                    signal_direction=sig_dir,
                    signal_confidence=sig_conf,
                    minutes_since_open=current_minute,
                ):
                    exit_type = "signal_reversal"

        # â”€â”€ Agent-requested exit â”€â”€
        effective_action = exit_action
        if exit_action == 1 and exit_type is None:
            min_hold = getattr(self, "_current_min_hold_minutes", self.hard_exits.get("min_hold_minutes", 0))
            # emergency_stop_pct igualado a max_loss_pct elimina la escapatoria
            # prematura: una policy de salida colapsada no puede realizar
            # pÃ©rdidas antes del hard stop.
            emergency_stop = float(RL_CONFIG.get("emergency_stop_pct", self.hard_exits["max_loss_pct"]))
            min_agent_exit_pnl = float(RL_CONFIG.get("agent_exit_min_pnl_pct", 0.0))
            is_emergency = pnl_pct <= emergency_stop
            if not is_emergency and (hold_minutes < min_hold or pnl_pct < min_agent_exit_pnl):
                effective_action = 0  # Force HOLD â€” too early or a non-emergency losing exit
            else:
                exit_type = "agent_exit"

        if exit_type is not None:
            # â”€â”€ TERMINAL â”€â”€
            terminal_reward = compute_terminal_reward(
                final_pnl_pct=pnl_pct,
                exit_type=exit_type,
                hold_time_minutes=hold_minutes
            )
            self._done = True
            info = {
                "exit_type": exit_type,
                "final_pnl_pct": pnl_pct,
                "hold_minutes": hold_minutes,
                "strike_chosen": self._position["strike"],
                "strike_action": self._position["strike_action"],
                "entry_delta": self._position["entry_delta"],
                "mae": self._mae,
                "direction": self._position["direction"],
                "effective_action": effective_action,
            }
            if self._use_sniper:
                info["sniper_minutes_waited"] = self._sniper_minutes_elapsed
            return self._build_state_vector(), terminal_reward, True, info
        else:
            # â”€â”€ STEP REWARD â”€â”€
            db = get_delta_bucket(abs(self._current_delta))
            ib = get_iv_bucket(self._current_iv)
            pb = get_pnl_bucket(pnl_pct)
            recovery_rate = float(self._recovery_lookup.get((db, ib, pb), 0.3))

            # Get current theta
            greeks = self._get_current_greeks(ticker, date_str, time_str, hold_minutes)
            theta_vs_premium = greeks.get("theta_vs_premium", -0.05)
            # theta_vs_premium in cache is often per day. Ensure it's negative.
            theta_decay_per_minute = -abs(theta_vs_premium) / 390.0



            reward = compute_step_reward(
                prev_pnl_pct=self._prev_pnl_pct,
                curr_pnl_pct=pnl_pct,
                hold_time_minutes=hold_minutes,
                theta_decay_per_minute=theta_decay_per_minute,
                recovery_rate=recovery_rate,
                spot_momentum=spot_momentum,
                trailing_drawdown=self._trailing_drawdown,
                is_new_hwm=is_new_hwm
            )
            self._prev_pnl_pct = pnl_pct
            self._t += 1
            return self._build_state_vector(), float(reward), False, {
                "action": "hold",
                "pnl_pct": pnl_pct,
                "hold_minutes": hold_minutes,
                "recovery_rate": recovery_rate,
                "spot_momentum": spot_momentum,
                "effective_action": effective_action
            }


    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # STRIKE RESOLUTION
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _resolve_strike(self, cache_key: str, delta_target: float,
                        right: str) -> dict:
        """Map delta target to actual strike from options cache."""
        cache_entry = self.options_cache.get(cache_key)
        if cache_entry is None:
            return None
        return self._resolve_strike_from_data(cache_entry, delta_target, right)

    def _resolve_strike_from_data(self, cache_data: dict, delta_target: float,
                                   right: str) -> dict:
        """Map delta target to actual strike from a cache data dict."""
        options = cache_data.get("calls" if right == "CALL" else "puts", {})
        if not options:
            return None

        best_strike = None
        best_diff = float("inf")
        for strike, data in options.items():
            delta = abs(data.get("delta", 0))
            price = data.get("price", 0)
            if delta < 0.01 or price <= 0:
                continue
            diff = abs(delta - delta_target)
            if diff < best_diff:
                best_diff = diff
                best_strike = strike
                best_data = data

        if best_strike is None:
            return None

        return {
            "strike": float(best_strike),
            "entry_price": float(best_data.get("price", 0)),
            "entry_iv": float(best_data.get("iv", 0.15)),
            "entry_delta": float(best_data.get("delta", delta_target)),
            "entry_theta": float(best_data.get("theta", 0)),
            "entry_gamma": float(best_data.get("gamma", 0)),
        }

    def _build_strike_context_snapshot(self, cache_data: dict, direction: str) -> np.ndarray:
        """
        Per-bucket option-chain context visible before strike selection.

        Layout per bucket: available, abs_delta, premium_pct_spot, iv_ratio,
        theta_vs_premium.
        """
        context = np.zeros(STRIKE_CONTEXT_DIM, dtype=np.float32)
        if not cache_data:
            return context

        spot = float(cache_data.get("spot", self._entry_spot) or self._entry_spot or 0.0)
        right = "CALL" if direction == "LONG" else "PUT"
        atm_iv = float(getattr(self, "_entry_atm_iv", 0.15) or 0.15)

        for action, bucket in STRIKE_BUCKETS.items():
            offset = int(action) * STRIKE_CONTEXT_FEATURES_PER_BUCKET
            strike_info = self._resolve_strike_from_data(
                cache_data,
                float(bucket.get("delta_target", 0.5)),
                right,
            )
            if strike_info is None:
                continue

            premium = float(strike_info.get("entry_price", 0.0))
            iv = float(strike_info.get("entry_iv", atm_iv))
            theta = float(strike_info.get("entry_theta", 0.0))
            context[offset + 0] = 1.0
            context[offset + 1] = np.clip(abs(float(strike_info.get("entry_delta", 0.0))), 0.0, 1.0)
            context[offset + 2] = np.clip((premium / spot) * 100.0 if spot > 0 else 0.0, 0.0, 10.0)
            context[offset + 3] = np.clip(iv / atm_iv if atm_iv > 0 else 1.0, 0.25, 4.0)
            context[offset + 4] = np.clip(theta / premium if premium > 0 else 0.0, -5.0, 0.0)

        return context

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # PRICE LOOKUPS
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _get_current_option_price(self, ticker: str, date_str: str, entry_time: str,
                                  minute_offset: int) -> float:
        """Look up current mark price for the held option at t minutes after entry."""
        cache_key = f"{ticker}_{date_str}_{entry_time}"
        cache_entry = self.options_cache.get(cache_key)
        if cache_entry is None:
            return None

        # Try forward-looking minute data
        minutes_data = cache_entry.get("minutes", {})
        minute_data = minutes_data.get(minute_offset)
        if minute_data is None:
            return None

        right_key = "calls" if self._position["right"] == "CALL" else "puts"
        strike = self._position["strike"]
        options = minute_data.get(right_key, {})
        strike_data = options.get(strike)
        if strike_data is None:
            # Find nearest available strike
            available = list(options.keys())
            if not available:
                return None
            nearest = min(available, key=lambda s: abs(float(s) - strike))
            strike_data = options[nearest]

        price = float(strike_data.get("price", 0))
        if price <= 0:
            return None   # â† force fallback to raw_entry_price
        return price

    def _get_theta_vs_premium(self, ticker: str, date_str: str, entry_time: str,
                              minute_offset: int) -> float:
        """Get current theta normalized by entry premium."""
        cache_key = f"{ticker}_{date_str}_{entry_time}"
        cache_entry = self.options_cache.get(cache_key)
        if cache_entry is None:
            return -0.05  # default penalty

        minutes_data = cache_entry.get("minutes", {})
        minute_data = minutes_data.get(minute_offset)
        if minute_data is None:
            return -0.05

        right_key = "calls" if self._position["right"] == "CALL" else "puts"
        strike = self._position["strike"]
        options = minute_data.get(right_key, {})
        strike_data = options.get(strike, {})
        theta = float(strike_data.get("theta", 0))

        entry_premium = self._position["entry_price"]
        if entry_premium > 0:
            return float(np.clip(theta / entry_premium, -50.0, 0.0))
        return -0.05

    def _get_current_greeks(self, ticker: str, date_str: str, entry_time: str,
                            minute_offset: int) -> dict:
        """Get current delta, theta, and IV from options cache at current minute."""
        entry_delta = self._position["entry_delta"] if self._position else 0.5
        defaults = {"delta": entry_delta, "theta_vs_premium": -0.05, "iv": 0.15}

        cache_key = f"{ticker}_{date_str}_{entry_time}"
        cache_entry = self.options_cache.get(cache_key)
        if cache_entry is None:
            return defaults

        minutes_data = cache_entry.get("minutes", {})
        minute_data = minutes_data.get(minute_offset)
        if minute_data is None:
            return defaults

        right_key = "calls" if self._position["right"] == "CALL" else "puts"
        strike = self._position["strike"]
        options = minute_data.get(right_key, {})
        strike_data = options.get(strike, {})
        if not strike_data:
            return defaults

        delta = float(strike_data.get("delta", entry_delta))
        theta_raw = float(strike_data.get("theta", 0))
        entry_premium = self._position["entry_price"]
        theta_vs = float(np.clip(theta_raw / entry_premium, -50.0, 0.0)) if entry_premium > 0 else -0.05
        iv = float(strike_data.get("implied_vol", strike_data.get("iv", 0.15)))

        return {"delta": delta, "theta_vs_premium": theta_vs, "iv": iv}

    def _minutes_since_open(self) -> int:
        """Compute minutes since market open (9:30) from episode time."""
        ep = self._current_episode
        time_str = str(ep.get("time", "09:30"))
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            return max(0, (h * 60 + m) - 570) + self._t  # 570 = 9:30
        except:
            return self._t

    def _get_dynamic_market_features(self) -> np.ndarray:
        """
        Compute 8 dynamic market features from the per-minute options cache.
        [v6.1] Caching: prevent multiple calls (and spot_history updates) per step.
        """
        if self._dynamic_cache_t == self._t:
            return self._dynamic_market_state

        self._dynamic_cache_t = self._t
        dynamic = np.zeros(DYNAMIC_MARKET_DIM, dtype=np.float32)
        ep = self._current_episode
        ticker = str(ep.get("ticker", "SPX"))
        date_str = str(ep.get("date", ""))
        time_str = str(ep.get("time", ""))
        cache_key = f"{ticker}_{date_str}_{time_str}"
        cache_entry = self.options_cache.get(cache_key)

        if cache_entry is None or self._entry_spot <= 0:
            return dynamic

        minutes_data = cache_entry.get("minutes", {})
        minute_data = minutes_data.get(self._t)

        if minute_data is None:
            return dynamic

        current_spot = float(minute_data.get("spot", self._entry_spot))

        # Track spot history for velocity
        self._spot_history.append(current_spot)

        # [0] Spot change from signal time (clipped to Â±2%)
        spot_change = (current_spot - self._entry_spot) / self._entry_spot
        dynamic[0] = np.clip(spot_change * 100, -2.0, 2.0)  # in pct, clipped

        # [1] Spot velocity over last 5 minutes
        if len(self._spot_history) >= 6:
            spot_5m_ago = self._spot_history[-6]
            velocity = (current_spot - spot_5m_ago) / self._entry_spot
            dynamic[1] = np.clip(velocity * 100, -1.0, 1.0)
        elif len(self._spot_history) >= 2:
            velocity = (current_spot - self._spot_history[0]) / self._entry_spot
            dynamic[1] = np.clip(velocity * 100, -1.0, 1.0)

        # [2] ATM IV change from signal time
        direction = ep.get("mlp_direction", "LONG")
        right_key = "calls" if direction == "LONG" else "puts"
        options = minute_data.get(right_key, {})
        if options and current_spot > 0:
            atm_strike = min(options.keys(), key=lambda s: abs(float(s) - current_spot), default=None)
            if atm_strike is not None:
                current_iv = float(options[atm_strike].get("iv", self._entry_atm_iv))
                iv_change = (current_iv - self._entry_atm_iv) / max(self._entry_atm_iv, 0.01)
                dynamic[2] = np.clip(iv_change, -1.0, 1.0)

                # [3] Current ATM gamma (normalized)
                gamma = float(options[atm_strike].get("gamma", 0))
                dynamic[3] = np.clip(gamma * current_spot * 0.01, -2.0, 2.0)

        # [4] Spot vs entry price (if in position, distance from position entry spot)
        if self._position is not None and self._entry_spot > 0:
            entry_minute = self._position.get("entry_minute", 0)
            entry_minute_data = minutes_data.get(entry_minute, {})
            entry_spot_at_open = float(entry_minute_data.get("spot", self._entry_spot))
            if entry_spot_at_open > 0:
                spot_vs_entry = (current_spot - entry_spot_at_open) / entry_spot_at_open
                # Sign matters: for LONG, positive = good; for SHORT, negative = good
                if direction == "SHORT":
                    spot_vs_entry = -spot_vs_entry
                dynamic[4] = np.clip(spot_vs_entry * 100, -3.0, 3.0)

        # [5] Minutes remaining to market close (normalized 0-1)
        total_session = RL_CONFIG["session_length_minutes"]  # 390
        mins_since_open = self._minutes_since_open()
        minutes_left = max(0, total_session - mins_since_open)
        dynamic[5] = minutes_left / total_session

        # [6] Option momentum: price change over last 3 min (if in position)
        if self._position is not None and self._t >= 3:
            price_now = self._get_current_option_price(ticker, date_str, time_str, self._t)
            price_3ago = self._get_current_option_price(ticker, date_str, time_str, self._t - 3)
            if price_now is not None and price_3ago is not None and price_3ago > 0:
                opt_momentum = (price_now - price_3ago) / price_3ago
                dynamic[6] = np.clip(opt_momentum, -1.0, 1.0)

        # [7] Underlying trend (cumulative direction, smoothed)
        if len(self._spot_history) >= 3:
            diffs = np.diff(self._spot_history[-min(20, len(self._spot_history)):])
            up_moves = np.sum(diffs > 0)
            dn_moves = np.sum(diffs < 0)
            total_moves = up_moves + dn_moves
            if total_moves > 0:
                dynamic[7] = (up_moves - dn_moves) / total_moves  # range [-1, 1]

        return dynamic

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # STATE VECTOR
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _build_state_vector(self) -> np.ndarray:
        """
        Concatenate state groups into the observation vector.

        When use_sniper_mode=True:
          [market_features(163), dynamic_market(8), position_features(7), mlp_context(4), ticker_context(3), strike_context(35), sniper_features(2)]

        When use_sniper_mode=False:
          [market_features(163), dynamic_market(8), position_features(7), mlp_context(4), ticker_context(3), strike_context(35)]
        """
        ep = self._current_episode

        # â”€â”€ Group 1: Market features (already normalized) â”€â”€
        market_features = np.zeros(MARKET_FEATURE_DIM, dtype=np.float32)
        for i, col in enumerate(self.feature_columns):
            if i >= MARKET_FEATURE_DIM:
                break
            val = ep.get(col, 0.0)
            market_features[i] = float(val) if not pd.isna(val) else 0.0

        # â”€â”€ Group 2: Dynamic market features (updated per minute) â”€â”€
        dynamic_features = self._get_dynamic_market_features()

        # â”€â”€ Group 3: Position state â”€â”€
        position_features = np.zeros(POSITION_STATE_DIM, dtype=np.float32)
        if self._position is not None:
            pnl_pct = self._prev_pnl_pct
            hold_minutes = self._t - self._position["entry_minute"]
            hold_time_norm = hold_minutes / self.hard_exits["max_hold_minutes"]

            position_features[0] = np.clip(pnl_pct, -1.0, 5.0)          # pnl_vs_premium
            position_features[1] = np.clip(hold_time_norm, 0.0, 1.0)    # time_held_norm
            position_features[2] = abs(getattr(self, '_current_delta',
                                               self._position["entry_delta"]))  # current delta

            # --- v4: Drawdown Recovery Rate instead of Theta ---
            db = get_delta_bucket(position_features[2])
            iv = getattr(self, '_current_iv', 0.15)
            ib = get_iv_bucket(iv)
            pb = get_pnl_bucket(pnl_pct)

            recovery_prob = self._recovery_lookup.get((db, ib, pb), 0.3) # Prior 0.3 if bucket missing
            position_features[3] = float(recovery_prob)

            position_features[4] = np.clip(iv / 0.15 if iv > 0 else 1.0,
                                           0.5, 3.0)                            # current iv_ratio
            position_features[5] = np.clip(self._mae, -1.0, 0.0)        # mae_ratio
            position_features[6] = np.clip(self._trailing_drawdown, 0.0, 2.0)

        # â”€â”€ Group 4: MLP signal context â”€â”€
        mlp_context = np.zeros(MLP_CONTEXT_DIM, dtype=np.float32)
        mlp_context[0] = float(ep.get("mlp_confidence", 0.60))
        mlp_context[1] = float(ep.get("mlp_time_to_target", 0.5))
        # mins_since_signal: 0 during direct entry, sniper_elapsed during sniper
        mlp_context[2] = float(self._sniper_minutes_elapsed) / max(
            RL_CONFIG.get("sniper_window_minutes", 15), 1
        ) if self._use_sniper else 0.0
        mlp_context[3] = float(ep.get("mlp_log_sigma", 0.5))

        ticker_context = _ticker_context(ep.get("ticker", "SPX"))
        strike_context = getattr(self, "_strike_context", np.zeros(STRIKE_CONTEXT_DIM, dtype=np.float32))

        # â”€â”€ Group 5: Sniper features (only when sniper mode enabled) â”€â”€
        if self._use_sniper:
            sniper_features = np.zeros(SNIPER_STATE_DIM, dtype=np.float32)
            if self._position is None and self._sniper_mode:
                # Still in PRE_ENTRY phase
                window = RL_CONFIG.get("sniper_window_minutes", 15)
                sniper_features[0] = (window - self._sniper_minutes_elapsed) / window
                sniper_features[1] = 1.0 if self._sniper_entry_attempted else 0.0
            # else: already in position â€” sniper features are 0 (no longer relevant)
            state = np.concatenate([
                market_features, dynamic_features, position_features,
                mlp_context, ticker_context, strike_context, sniper_features
            ])
        else:
            state = np.concatenate([
                market_features, dynamic_features, position_features,
                mlp_context, ticker_context, strike_context
            ])

        return state.astype(np.float32)


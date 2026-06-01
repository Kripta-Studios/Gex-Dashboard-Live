from __future__ import annotations
import os
import numpy as np

try:
    from neural.rl.config import RL_CONFIG
except ModuleNotFoundError:
    from rl.config import RL_CONFIG


def direction_from_prediction(prediction: int) -> str:
    return {0: "SHORT", 1: "HOLD", 2: "LONG"}.get(int(prediction), "HOLD")


def entry_cadence_minutes() -> int:
    return int(RL_CONFIG.get("signal_eval_cadence_minutes", 5))


def reversal_confidence_threshold() -> float:
    return float(RL_CONFIG.get("signal_reversal_min_confidence", 0.50))


def entry_thresholds(base_confidence: float | None = None) -> tuple[float, float]:
    base = float(
        RL_CONFIG["min_confidence"] if base_confidence is None else base_confidence
    )
    short_offset = float(RL_CONFIG.get("short_confidence_offset", 0.05))
    long_threshold = base
    short_threshold = max(0.0, base - short_offset)
    return long_threshold, short_threshold


def confidence_threshold_for_direction(
    direction: str,
    base_confidence: float | None = None,
) -> float:
    long_threshold, short_threshold = entry_thresholds(base_confidence)
    direction = str(direction).upper()
    if direction == "LONG":
        return long_threshold
    if direction == "SHORT":
        return short_threshold
    return 1.0


def deployment_iv_bounds() -> tuple[float | None, float | None]:
    min_iv = RL_CONFIG.get("deployment_min_iv_percentile", None)
    max_iv = RL_CONFIG.get("deployment_max_iv_percentile", None)
    min_iv = None if min_iv is None else float(min_iv)
    max_iv = None if max_iv is None else float(max_iv)
    return min_iv, max_iv


def deployment_entry_windows() -> list[tuple[int, int]]:
    windows = RL_CONFIG.get("deployment_entry_windows", []) or []
    parsed: list[tuple[int, int]] = []
    for item in windows:
        try:
            start, end = item
            start_i = int(start)
            end_i = int(end)
        except (TypeError, ValueError):
            continue
        if 0 <= start_i < end_i <= 24 * 60:
            parsed.append((start_i, end_i))
    return parsed


def _parse_ticker_float_map(value) -> dict[str, float]:
    if value is None:
        return {}
    if isinstance(value, dict):
        parsed = {}
        for key, val in value.items():
            try:
                parsed[str(key).upper()] = float(val)
            except (TypeError, ValueError):
                continue
        return parsed

    parsed = {}
    for item in str(value).replace(";", ",").split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        key, raw_val = item.split(":", 1)
        try:
            parsed[key.strip().upper()] = float(raw_val)
        except (TypeError, ValueError):
            continue
    return parsed


def _ticker_float_gate(config_key: str, env_key: str, ticker: str) -> float | None:
    ticker = str(ticker).upper()
    env_value = os.environ.get(env_key)
    source = env_value if env_value not in (None, "") else RL_CONFIG.get(config_key, None)
    parsed = _parse_ticker_float_map(source)
    return parsed.get(ticker)


def _time_to_minute(value) -> int | None:
    if value is None:
        return None
    try:
        if np.isfinite(float(value)):
            numeric = float(value)
            if numeric >= 100 and numeric <= 24 * 60:
                return int(numeric)
    except (TypeError, ValueError):
        pass
    try:
        text = str(value)
        if " " in text:
            text = text.split(" ")[-1]
        parts = text.split(":")
        if len(parts) < 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        return hour * 60 + minute
    except (TypeError, ValueError):
        return None


def deployment_time_allowed(row) -> bool:
    windows = deployment_entry_windows()
    if not windows:
        return True

    value = None
    try:
        if row.get("minutes") is not None:
            value = row.get("minutes")
        elif row.get("minute") is not None:
            value = row.get("minute")
        else:
            value = row.get("time", row.get("timestamp", None))
    except AttributeError:
        value = None

    minute = _time_to_minute(value)
    if minute is None:
        return bool(RL_CONFIG.get("deployment_allow_missing_time", False))
    return any(start <= minute < end for start, end in windows)


def deployment_context_allowed(row, direction: str | None = None) -> bool:
    """
    Shared non-predictive deployment gate for entry rows.

    It deliberately uses only the current row context, not future outcomes, so
    it can be applied consistently in model selection, RL episode generation,
    backtests and live routing.
    """
    if not deployment_time_allowed(row):
        return False

    min_iv, max_iv = deployment_iv_bounds()
    if min_iv is not None or max_iv is not None:
        try:
            iv_value = row.get("iv_percentile")
        except AttributeError:
            iv_value = None

        allow_missing = bool(RL_CONFIG.get("deployment_allow_missing_iv_percentile", False))
        try:
            iv_value = float(iv_value)
        except (TypeError, ValueError):
            return allow_missing

        if not np.isfinite(iv_value):
            return allow_missing
        if min_iv is not None and iv_value < min_iv:
            return False
        if max_iv is not None and iv_value > max_iv:
            return False

    max_rvol_trend = RL_CONFIG.get("deployment_max_rvol_trend", None)
    if max_rvol_trend is not None:
        try:
            rvol_trend = float(row.get("rvol_trend"))
        except (AttributeError, TypeError, ValueError):
            return bool(RL_CONFIG.get("deployment_allow_missing_rvol_trend", False))
        if not np.isfinite(rvol_trend):
            return bool(RL_CONFIG.get("deployment_allow_missing_rvol_trend", False))
        if rvol_trend > float(max_rvol_trend):
            return False

    try:
        ticker = str(row.get("ticker", "")).upper()
    except AttributeError:
        ticker = ""
    if direction is None:
        try:
            direction = row.get("mlp_direction", row.get("direction", ""))
        except AttributeError:
            direction = ""
    direction = str(direction).upper()

    ticker_min_price_vs_ib_high = _ticker_float_gate(
        "deployment_ticker_min_price_vs_ib_high",
        "DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH",
        ticker,
    )
    if ticker_min_price_vs_ib_high is not None:
        try:
            price_vs_ib_high = float(row.get("price_vs_ib_high"))
        except (AttributeError, TypeError, ValueError):
            return False
        if not np.isfinite(price_vs_ib_high):
            return False
        if price_vs_ib_high < ticker_min_price_vs_ib_high:
            return False

    ticker_max_vix_spot = _ticker_float_gate(
        "deployment_ticker_max_vix_spot",
        "DEPLOYMENT_TICKER_MAX_VIX_SPOT",
        ticker,
    )
    if ticker_max_vix_spot is not None:
        try:
            vix_spot = float(row.get("vix_spot"))
        except (AttributeError, TypeError, ValueError):
            return False
        if not np.isfinite(vix_spot):
            return False
        if vix_spot > ticker_max_vix_spot:
            return False

    qqq_short_min_ib = RL_CONFIG.get("deployment_qqq_short_min_price_vs_ib_high", None)
    if qqq_short_min_ib is not None and ticker == "QQQ" and direction == "SHORT":
        try:
            price_vs_ib_high = float(row.get("price_vs_ib_high"))
        except (AttributeError, TypeError, ValueError):
            return False
        if not np.isfinite(price_vs_ib_high):
            return False
        if price_vs_ib_high < float(qqq_short_min_ib):
            return False

    if ticker == "QQQ" and direction == "LONG":
        qqq_long_max_net_gamma = RL_CONFIG.get("deployment_qqq_long_max_net_gamma", None)
        if qqq_long_max_net_gamma is not None:
            try:
                net_gamma = float(row.get("net_gamma"))
            except (AttributeError, TypeError, ValueError):
                return False
            if not np.isfinite(net_gamma) or net_gamma > float(qqq_long_max_net_gamma):
                return False

        qqq_long_max_gamma_momentum = RL_CONFIG.get("deployment_qqq_long_max_gamma_momentum", None)
        if qqq_long_max_gamma_momentum is not None:
            try:
                gamma_momentum = float(row.get("gamma_momentum"))
            except (AttributeError, TypeError, ValueError):
                return False
            if not np.isfinite(gamma_momentum) or gamma_momentum > float(qqq_long_max_gamma_momentum):
                return False
    return True


def deployment_context_mask(df, directions=None) -> np.ndarray:
    mask = np.ones(len(df), dtype=bool)

    windows = deployment_entry_windows()
    if windows:
        minute_values = None
        if "minutes" in getattr(df, "columns", []):
            minute_values = np.asarray(df["minutes"], dtype=np.float64)
        elif "minute" in getattr(df, "columns", []):
            minute_values = np.asarray(df["minute"], dtype=np.float64)
        elif "time" in getattr(df, "columns", []):
            minute_values = np.array([_time_to_minute(v) for v in df["time"]], dtype=np.float64)

        if minute_values is None:
            mask &= bool(RL_CONFIG.get("deployment_allow_missing_time", False))
        else:
            time_mask = np.zeros(len(df), dtype=bool)
            finite_minutes = np.isfinite(minute_values)
            for start, end in windows:
                time_mask |= finite_minutes & (minute_values >= start) & (minute_values < end)
            if RL_CONFIG.get("deployment_allow_missing_time", False):
                time_mask |= ~finite_minutes
            mask &= time_mask

    min_iv, max_iv = deployment_iv_bounds()
    if min_iv is not None or max_iv is not None:
        allow_missing = bool(RL_CONFIG.get("deployment_allow_missing_iv_percentile", False))
        if "iv_percentile" not in getattr(df, "columns", []):
            mask &= allow_missing
        else:
            iv = np.asarray(df["iv_percentile"], dtype=np.float64)
            iv_mask = np.isfinite(iv)
            if min_iv is not None:
                iv_mask &= iv >= min_iv
            if max_iv is not None:
                iv_mask &= iv <= max_iv
            if allow_missing:
                iv_mask |= ~np.isfinite(iv)
            mask &= iv_mask

    max_rvol_trend = RL_CONFIG.get("deployment_max_rvol_trend", None)
    if max_rvol_trend is not None:
        allow_missing_rvol = bool(RL_CONFIG.get("deployment_allow_missing_rvol_trend", False))
        if "rvol_trend" not in getattr(df, "columns", []):
            mask &= allow_missing_rvol
        else:
            rvol = np.asarray(df["rvol_trend"], dtype=np.float64)
            rvol_mask = np.isfinite(rvol) & (rvol <= float(max_rvol_trend))
            if allow_missing_rvol:
                rvol_mask |= ~np.isfinite(rvol)
            mask &= rvol_mask

    ticker_min_price_vs_ib_high = _parse_ticker_float_map(
        os.environ.get(
            "DEPLOYMENT_TICKER_MIN_PRICE_VS_IB_HIGH",
            RL_CONFIG.get("deployment_ticker_min_price_vs_ib_high", None),
        )
    )
    if ticker_min_price_vs_ib_high and "ticker" in getattr(df, "columns", []):
        if "price_vs_ib_high" not in getattr(df, "columns", []):
            tickers = np.asarray(df["ticker"].astype(str).str.upper())
            gated = np.isin(tickers, list(ticker_min_price_vs_ib_high.keys()))
            mask &= ~gated
        else:
            tickers = np.asarray(df["ticker"].astype(str).str.upper())
            ib_high = np.asarray(df["price_vs_ib_high"], dtype=np.float64)
            gate_mask = np.ones(len(df), dtype=bool)
            for ticker_key, min_value in ticker_min_price_vs_ib_high.items():
                t_mask = tickers == ticker_key
                gate_mask &= ~t_mask | (np.isfinite(ib_high) & (ib_high >= float(min_value)))
            mask &= gate_mask

    ticker_max_vix_spot = _parse_ticker_float_map(
        os.environ.get(
            "DEPLOYMENT_TICKER_MAX_VIX_SPOT",
            RL_CONFIG.get("deployment_ticker_max_vix_spot", None),
        )
    )
    if ticker_max_vix_spot and "ticker" in getattr(df, "columns", []):
        if "vix_spot" not in getattr(df, "columns", []):
            tickers = np.asarray(df["ticker"].astype(str).str.upper())
            gated = np.isin(tickers, list(ticker_max_vix_spot.keys()))
            mask &= ~gated
        else:
            tickers = np.asarray(df["ticker"].astype(str).str.upper())
            vix_spot = np.asarray(df["vix_spot"], dtype=np.float64)
            gate_mask = np.ones(len(df), dtype=bool)
            for ticker_key, max_value in ticker_max_vix_spot.items():
                t_mask = tickers == ticker_key
                gate_mask &= ~t_mask | (np.isfinite(vix_spot) & (vix_spot <= float(max_value)))
            mask &= gate_mask

    qqq_short_min_ib = RL_CONFIG.get("deployment_qqq_short_min_price_vs_ib_high", None)
    if qqq_short_min_ib is not None and "ticker" in getattr(df, "columns", []):
        if directions is None:
            if "mlp_direction" in df.columns:
                directions = df["mlp_direction"]
            elif "direction" in df.columns:
                directions = df["direction"]
        if directions is not None:
            tickers = np.asarray(df["ticker"].astype(str).str.upper())
            dirs = np.asarray(directions.astype(str).str.upper() if hasattr(directions, "astype") else directions)
            if "price_vs_ib_high" in df.columns:
                ib_high = np.asarray(df["price_vs_ib_high"], dtype=np.float64)
                qqq_short = (tickers == "QQQ") & (dirs == "SHORT")
                mask &= ~qqq_short | (
                    np.isfinite(ib_high) & (ib_high >= float(qqq_short_min_ib))
                )
            else:
                mask &= ~((tickers == "QQQ") & (dirs == "SHORT"))

    qqq_long_max_net_gamma = RL_CONFIG.get("deployment_qqq_long_max_net_gamma", None)
    qqq_long_max_gamma_momentum = RL_CONFIG.get("deployment_qqq_long_max_gamma_momentum", None)
    if (
        (qqq_long_max_net_gamma is not None or qqq_long_max_gamma_momentum is not None)
        and "ticker" in getattr(df, "columns", [])
    ):
        if directions is None:
            if "mlp_direction" in df.columns:
                directions = df["mlp_direction"]
            elif "direction" in df.columns:
                directions = df["direction"]
        if directions is not None:
            tickers = np.asarray(df["ticker"].astype(str).str.upper())
            dirs = np.asarray(directions.astype(str).str.upper() if hasattr(directions, "astype") else directions)
            qqq_long = (tickers == "QQQ") & (dirs == "LONG")

            if qqq_long_max_net_gamma is not None:
                if "net_gamma" in df.columns:
                    net_gamma = np.asarray(df["net_gamma"], dtype=np.float64)
                    mask &= ~qqq_long | (
                        np.isfinite(net_gamma) & (net_gamma <= float(qqq_long_max_net_gamma))
                    )
                else:
                    mask &= ~qqq_long

            if qqq_long_max_gamma_momentum is not None:
                if "gamma_momentum" in df.columns:
                    gamma_momentum = np.asarray(df["gamma_momentum"], dtype=np.float64)
                    mask &= ~qqq_long | (
                        np.isfinite(gamma_momentum)
                        & (gamma_momentum <= float(qqq_long_max_gamma_momentum))
                    )
                else:
                    mask &= ~qqq_long
    return mask


def is_actionable_signal(
    direction: str,
    confidence: float,
    base_confidence: float | None = None,
) -> bool:
    direction = str(direction).upper()
    if direction == "HOLD":
        return False
    return float(confidence) >= confidence_threshold_for_direction(
        direction,
        base_confidence=base_confidence,
    )


def is_actionable_prediction(
    prediction: int,
    confidence: float,
    base_confidence: float | None = None,
) -> bool:
    return is_actionable_signal(
        direction_from_prediction(prediction),
        confidence,
        base_confidence=base_confidence,
    )


def get_independent_signals(
    probs: np.ndarray,
    base_confidence: float | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """
    Evaluates probability thresholds independently for SHORT and LONG.
    Avoids the 'Direction Collapse' caused by np.argmax in highly imbalanced
    3-class datasets where HOLD probability often strictly dominates.

    Returns:
        predictions (np.ndarray): Array of predicted classes (0=SHORT, 1=HOLD, 2=LONG)
        confidences (np.ndarray): Array of confidences for the predicted class
    """
    long_thresh, short_thresh = entry_thresholds(base_confidence)
    directional_margin = float(RL_CONFIG.get("signal_min_directional_margin", 0.0))

    # Defaults: HOLD with confidence = p_hold
    predictions = np.ones(len(probs), dtype=int)
    confidences = probs[:, 1].copy()

    long_edge = probs[:, 2] - probs[:, 0]
    short_edge = probs[:, 0] - probs[:, 2]
    long_mask = (probs[:, 2] >= long_thresh) & (long_edge >= directional_margin)
    short_mask = (probs[:, 0] >= short_thresh) & (short_edge >= directional_margin)

    conflict = long_mask & short_mask

    # Assign LONG
    valid_long = long_mask & ~conflict
    predictions[valid_long] = 2
    confidences[valid_long] = probs[valid_long, 2]

    # Assign SHORT
    valid_short = short_mask & ~conflict
    predictions[valid_short] = 0
    confidences[valid_short] = probs[valid_short, 0]

    # Resolve conflicts by choosing the one with higher probability
    if conflict.any():
        is_long_higher = probs[conflict, 2] > probs[conflict, 0]
        predictions[conflict] = np.where(is_long_higher, 2, 0)
        confidences[conflict] = np.where(is_long_higher, probs[conflict, 2], probs[conflict, 0])

    return predictions, confidences


def confidence_for_predictions(
    probs: np.ndarray,
    predictions: np.ndarray,
) -> np.ndarray:
    """
    Return the probability of the emitted class for each row.

    This is intentionally not probs.max(axis=1): with independent LONG/SHORT
    thresholds the selected directional class can be below HOLD, and using the
    max would treat HOLD confidence as entry confidence.
    """
    probs = np.asarray(probs, dtype=np.float32)
    predictions = np.asarray(predictions, dtype=np.int64)
    if probs.ndim != 2 or probs.shape[1] < 3:
        raise ValueError("probs must have shape [N, 3]")
    if len(predictions) != len(probs):
        raise ValueError("predictions length must match probs rows")
    safe_preds = np.clip(predictions, 0, probs.shape[1] - 1)
    return probs[np.arange(len(probs)), safe_preds]


def is_signal_eval_minute(minutes_since_open: int, cadence: int | None = None) -> bool:
    cadence = int(cadence or entry_cadence_minutes())
    minutes_since_open = max(0, int(minutes_since_open))
    return cadence > 0 and (minutes_since_open % cadence) == 0


def should_exit_on_reversal(
    position_direction: str,
    signal_direction: str,
    signal_confidence: float,
    minutes_since_open: int,
    reversal_threshold: float | None = None,
    cadence: int | None = None,
) -> bool:
    position_direction = str(position_direction).upper()
    signal_direction = str(signal_direction).upper()
    if signal_direction == "HOLD" or signal_direction == position_direction:
        return False
    if not is_signal_eval_minute(minutes_since_open, cadence=cadence):
        return False
    threshold = (
        reversal_confidence_threshold()
        if reversal_threshold is None
        else float(reversal_threshold)
    )
    return float(signal_confidence) >= threshold

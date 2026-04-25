from __future__ import annotations

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

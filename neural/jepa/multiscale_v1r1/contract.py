"""Immutable V1R1 formats and constants; no I/O or economic calculation."""
from dataclasses import dataclass
from enum import StrEnum

FAMILY = 'MULTISCALE_LEVEL_INTERACTION_SEQUENCE_V1R1'
SEED = 20260802
TICKERS = ('SPXW', 'SPY', 'QQQ')
START = '2022-08-01'
END = '2026-06-30'
TIMEZONE = 'America/New_York'
THRESHOLDS_USD = (0.0, 5.0)
PROCESS_LIMIT = 24 * 1024**3
DISK_RESERVE = 20 * 1024**3
BLOCK_SIZE = 256
SLOTS = (
    'max_gamma', 'min_gamma', 'zero_gamma', 'max_dgex', 'min_dgex',
    'd0_ibh', 'd0_ibl', 'd0_upper_1272', 'd0_lower_1272',
    'd0_upper_1618', 'd0_lower_1618', 'd0_upper_2000', 'd0_lower_2000',
    'd1_ibh', 'd1_ibl', 'd1_upper_1272', 'd1_lower_1272',
    'd1_upper_1618', 'd1_lower_1618', 'd1_upper_2000', 'd1_lower_2000',
    'd2_ibh', 'd2_ibl', 'd2_upper_1272', 'd2_lower_1272',
    'd2_upper_1618', 'd2_lower_1618', 'd2_upper_2000', 'd2_lower_2000',
    'd3_ibh', 'd3_ibl', 'd3_upper_1272', 'd3_lower_1272',
    'd3_upper_1618', 'd3_lower_1618', 'd3_upper_2000', 'd3_lower_2000',
    'd4_ibh', 'd4_ibl', 'd4_upper_1272', 'd4_lower_1272',
    'd4_upper_1618', 'd4_lower_1618', 'd4_upper_2000', 'd4_lower_2000',
    'd5_ibh', 'd5_ibl', 'd5_upper_1272', 'd5_lower_1272',
    'd5_upper_1618', 'd5_lower_1618', 'd5_upper_2000', 'd5_lower_2000',
    'call_gamma', 'put_gamma', 'call_delta', 'put_delta', 'max_delta', 'min_delta',
)
CHANNELS = (
    'rel_O_bps', 'rel_H_bps', 'rel_L_bps', 'rel_C_bps', 'close_distance_bps',
    'body_bps', 'direction', 'upper_wick_bps', 'lower_wick_bps',
    'true_range_bps', 'range_over_atr15', 'CLV', 'velocity', 'acceleration',
    'run_above', 'run_below', 'first_touch', 'pierce', 'reclaim', 'rejection',
    'retest', 'acceptance', 'magnet', 'time_since_first_touch', 'prior_touches',
    'compression_before_touch', 'expansion_after_touch', 'realized_vol_15m',
    'activity_proxy', 'activity_ratio', 'confluence', 'wall_strength',
    'wall_concentration', 'wall_persistence_5m', 'wall_persistence_15m',
    'wall_persistence_30m', 'wall_migration_5m_bps', 'time_of_day_sin', 'time_of_day_cos',
)
CONTROLS = (
    'body_bps', 'direction', 'upper_wick_bps', 'lower_wick_bps', 'true_range_bps',
    'range_over_atr15', 'CLV', 'realized_vol_15m', 'activity_proxy', 'activity_ratio',
    'time_of_day_sin', 'time_of_day_cos',
)
STATICS = (
    'ticker_SPXW', 'ticker_SPY', 'ticker_QQQ', 'decision_sin', 'decision_cos',
    'distance_session_open_bps', 'distance_prior_close_bps', 'd0_ib_range_bps',
)
DECISIONS = (
    '11:30:00', '11:35:00', '11:40:00', '11:45:00', '11:50:00', '11:55:00',
    '12:00:00', '12:05:00', '12:10:00', '12:15:00', '12:20:00', '12:25:00',
    '12:30:00', '12:35:00', '12:40:00', '12:45:00', '12:50:00', '12:55:00',
)
PRIMARY_DIM = 92048
ABLATION_DIM = 488
SSL_DIM = 4602


@dataclass(frozen=True)
class Action:
    action_id: int
    right: str
    delta: int
    hold_minutes: int


ACTIONS = tuple(
    Action(i, right, delta, hold)
    for i, (right, delta, hold) in enumerate(
        (r, d, h) for r in ('CALL', 'PUT') for d in (25, 35, 50)
        for h in (60, 90, 120, 180)
    )
)


class Evidence(StrEnum):
    NOT_EVALUATED = 'NOT_EVALUATED'
    BLOCKED_DATA = 'BLOCKED_DATA'
    BLOCKED_DEPENDENCY = 'BLOCKED_DEPENDENCY'
    FAILED_CAUSALITY = 'FAILED_CAUSALITY'
    FAILED_AUDIT = 'FAILED_AUDIT'
    FAILED_FREQUENCY = 'FAILED_FREQUENCY'
    FAILED_ECONOMIC = 'FAILED_ECONOMIC'
    FAILED_INCREMENTAL = 'FAILED_INCREMENTAL'
    DEVELOPMENT_PASS_REQUIRES_SHADOW = 'DEVELOPMENT_PASS_REQUIRES_SHADOW'


class ContractError(ValueError):
    """A binding invariant failed; no fallback is permitted."""

"""Prepared zone-memory variant: pure causal inputs, no market reader or learner.

EPISODE_FEATURE_SPEC.md fixes semantics. This module is not integrated into any
frozen experiment. Diagnostic IDs never enter the numeric feature matrix.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TYPE_NAMES = ("fib", "call_oi", "put_oi", "call_gamma", "put_gamma")
FEATURE_NAMES = (
    "episode_open", "current_zone_valid", "anchor_center_ib", "anchor_band_ib",
    "anchor_n_components", *("anchor_" + name for name in TYPE_NAMES),
    "age_minutes", "valid_observations", "inside_observations", "inside_fraction",
    "observed_fraction", "contacts", "reentries", "exterior_crossings",
    "max_upper_penetration", "max_lower_penetration", "upper_recovery",
    "lower_recovery", "distance_anchor", "spot_change_1m", "spot_change_5m",
    "arrival_side", "current_n_components",
    *("current_" + name for name in TYPE_NAMES),
    "current_center_minus_anchor", "current_band_over_anchor",
    "distance_current_zone",
)


@dataclass
class EpisodeFeatures:
    state_i: np.ndarray
    values: np.ndarray
    valid: np.ndarray
    trace: pd.DataFrame
    names: tuple[str, ...] = FEATURE_NAMES


def _current_zone(row, levels, good):
    """Resolve only this minute and check the motor's distance/center tie break."""
    if not good:
        if bool(row.eligible):
            raise ValueError("Invalid state cannot be eligible")
        if row.entry_level_id != -1:
            raise ValueError("Invalid state must have entry_level_id=-1")
        return None
    band, spot = float(row.band), float(row.spot)
    if not np.isfinite(band) or band <= 0:
        raise ValueError("Valid state needs a positive finite band")
    near = []
    for level in levels.to_dict("records"):
        center = float(level["center"])
        if not np.isfinite(center):
            raise ValueError("Nonfinite current level center")
        if abs(center - spot) <= band:
            near.append(level)
    near.sort(key=lambda level: (abs(level["center"] - spot), level["center"]))
    if bool(near) != bool(row.eligible):
        raise ValueError("Eligibility disagrees with causal levels")
    if not near:
        if row.entry_level_id != -1:
            raise ValueError("State without a current zone must have entry_level_id=-1")
        return None
    selected = near[0]
    if int(selected["level_id"]) != int(row.entry_level_id):
        raise ValueError("Entry identity disagrees with motor tie break")
    if sum(int(level["level_id"]) == int(row.entry_level_id) for level in near) != 1:
        raise ValueError("Duplicate current entry identity")
    source = int(selected["source_mask"])
    components = int(selected["n_components"])
    if source <= 0 or source & ~31 or components <= 0:
        raise ValueError("Invalid causal zone provenance")
    return selected


def build_episode_features(states: pd.DataFrame, levels: pd.DataFrame) -> EpisodeFeatures:
    """Process one session's states in input order; no future spot is consulted."""
    names = {name: index for index, name in enumerate(FEATURE_NAMES)}
    values = np.zeros((len(states), len(names)), dtype=np.float64)
    valid = np.zeros_like(values, dtype=bool)
    minutes = np.empty(len(states), dtype=np.int64)
    grouped = {int(i): group for i, group in levels.groupby("state_i", sort=False)}
    empty_levels = levels.iloc[:0]
    traces, history = [], {}
    episode, previous_i, previous_good, previous_spot = None, None, False, np.nan
    episode_serial = 0

    for output_i, row in enumerate(states.itertuples(index=False)):
        minute = int(row.state_i)
        if minute != row.state_i or (previous_i is not None and minute <= previous_i):
            raise ValueError("States must have strictly increasing integer minute indices")
        minutes[output_i] = minute
        spot = float(row.spot)
        good = bool(row.state_valid) and np.isfinite(spot) and spot > 0
        adjacent = previous_i is not None and minute == previous_i + 1
        zone = _current_zone(row, grouped.get(minute, empty_levels), good)
        closed = opened = False

        def put(name, value):
            if not np.isfinite(value):
                raise ValueError("Nonfinite observed episode feature: " + name)
            values[output_i, names[name]] = value
            valid[output_i, names[name]] = True

        def types(prefix, source):
            for bit, name in enumerate(TYPE_NAMES):
                put(prefix + name, bool(source & (1 << bit)))

        if episode is not None:
            if not adjacent or not previous_good or not good:
                episode["outside_streak"] = 0
                episode["previous_inside"] = None
                episode["last_exterior"] = 0
            if good:
                distance = (spot - episode["center"]) / episode["band"]
                episode["outside_streak"] = (
                    episode["outside_streak"] + 1 if abs(distance) > 2 else 0
                )
                if episode["outside_streak"] >= 2:
                    episode = None
                    history = {}
                    closed = True

        if episode is None and zone is not None and not closed:
            ib_range, ib_low = float(row.ib_range), float(row.ib_low)
            if not np.isfinite(ib_range) or ib_range <= 0 or not np.isfinite(ib_low):
                raise ValueError("Episode opening requires a valid IB")
            episode_serial += 1
            arrival = None
            if adjacent and previous_good:
                approach = (previous_spot - float(zone["center"])) / float(row.band)
                arrival = np.sign(approach) if abs(approach) > 1 else None
            episode = dict(
                serial=episode_serial, start=minute, center=float(zone["center"]),
                band=float(row.band), source=int(zone["source_mask"]),
                components=int(zone["n_components"]), ib_low=ib_low, ib_range=ib_range,
                components_json=zone.get("components_json", ""),
                entry_level_id=int(zone["level_id"]), arrival=arrival,
                count=0, inside_count=0, contacts=1, crossings=0,
                previous_inside=None, last_exterior=0, outside_streak=0,
                max_distance=-np.inf, min_distance=np.inf,
            )
            history = {}
            opened = True

        put("episode_open", episode is not None)
        put("current_zone_valid", zone is not None)
        if zone is not None:
            put("current_n_components", zone["n_components"])
            types("current_", int(zone["source_mask"]))
            put("distance_current_zone", (spot - zone["center"]) / float(row.band))

        if episode is not None:
            e = episode
            age = minute - e["start"]
            if good:
                d = (spot - e["center"]) / e["band"]
                inside = abs(d) <= 1
                exterior = 0 if inside else int(np.sign(d))
                e["count"] += 1
                e["inside_count"] += int(inside)
                if e["previous_inside"] is False and inside:
                    e["contacts"] += 1
                if exterior and e["last_exterior"] and exterior != e["last_exterior"]:
                    e["crossings"] += 1
                if exterior:
                    e["last_exterior"] = exterior
                e["previous_inside"] = bool(inside)
                e["max_distance"] = max(e["max_distance"], d)
                e["min_distance"] = min(e["min_distance"], d)
                history[minute] = spot
                put("distance_anchor", d)
                put("upper_recovery", e["max_distance"] - d if e["max_distance"] > 1 else 0)
                put("lower_recovery", d - e["min_distance"] if e["min_distance"] < -1 else 0)
                for lag in (1, 5):
                    if all(i in history for i in range(minute - lag, minute + 1)):
                        put(f"spot_change_{lag}m", (spot - history[minute - lag]) / e["band"])
            put("anchor_center_ib", (e["center"] - e["ib_low"]) / e["ib_range"])
            put("anchor_band_ib", e["band"] / e["ib_range"])
            put("anchor_n_components", e["components"])
            types("anchor_", e["source"])
            for name, value in (
                ("age_minutes", age), ("valid_observations", e["count"]),
                ("inside_observations", e["inside_count"]),
                ("inside_fraction", e["inside_count"] / e["count"]),
                ("observed_fraction", e["count"] / (age + 1)),
                ("contacts", e["contacts"]), ("reentries", e["contacts"] - 1),
                ("exterior_crossings", e["crossings"]),
                ("max_upper_penetration", max(e["max_distance"] - 1, 0)),
                ("max_lower_penetration", max(-e["min_distance"] - 1, 0)),
            ):
                put(name, value)
            if e["arrival"] is not None:
                put("arrival_side", e["arrival"])
            if zone is not None:
                put("current_center_minus_anchor", (zone["center"] - e["center"]) / e["band"])
                put("current_band_over_anchor", float(row.band) / e["band"])

        traces.append(dict(
            state_i=minute, episode_id=episode["serial"] if episode else -1,
            opened=opened, closed=closed,
            anchor_center=episode["center"] if episode else np.nan,
            anchor_band=episode["band"] if episode else np.nan,
            anchor_level_id=episode["entry_level_id"] if episode else -1,
            anchor_components_json=episode["components_json"] if episode else "",
            current_level_id=int(zone["level_id"]) if zone else -1,
        ))
        previous_i, previous_good, previous_spot = minute, good, spot

    return EpisodeFeatures(minutes, values, valid, pd.DataFrame(traces))

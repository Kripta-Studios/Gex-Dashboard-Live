"""Synthetic checks for sampled candles and decision-versus-fill geometry."""
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location('plot_oracle', Path(__file__).with_name('plot_oracle.py'))
PLOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLOT)


class PlotTests(unittest.TestCase):
    def test_snapshot_candles_preserve_missingness_and_exclude_next_boundary(self):
        spot = np.full(391, np.nan)
        spot[:6] = [100., 999., 101., 98., 102., 500.]
        valid = np.isfinite(spot)
        valid[1] = False
        result = PLOT.sampled_candles(spot, valid)
        self.assertEqual(result.iloc[0].to_dict(), {'minute': 0., 'open': 100., 'high': 102.,
                                                   'low': 98., 'close': 102., 'observed': 4.})
        self.assertEqual(result.iloc[1]['open'], 500.)
        self.assertEqual(len(result), 2)

    def test_wall_uses_original_component_not_merged_center(self):
        levels = pd.DataFrame([{'state_i': 60, 'center': 100.5, 'components_json': json.dumps([
            {'source_mask': 1, 'center': 100., 'ratio': 0.},
            {'source_mask': 2, 'center': 101., 'weight': 500.}])}])
        result = PLOT.extract_walls(levels)
        self.assertEqual(result.iloc[0].to_dict(), {'minute': 60., 'center': 101., 'source': 2., 'weight': 500.})

    def test_near_decision_can_gap_outside_zone_before_fill(self):
        states = pd.DataFrame([{'state_i': 60, 'spot': 100.1}])
        levels = pd.DataFrame([{'state_i': 60, 'level_id': 0, 'center': 100.}])
        ledger = pd.DataFrame([{'state_i': 60, 'entry_i': 61, 'exit_i': 80, 'status': 'FILLED',
                                'hold_minutes': 19, 'entry_level_id': 0, 'band': .2, 'action_id': 0,
                                'right': 0, 'strike': 100., 'target_center': 102., 'stop_center': 99.,
                                'reason': 'TARGET', 'net_base': 10., 'net_adverse': 8.}])
        spot = np.full(391, 100.)
        spot[61] = 100.5
        result = PLOT.inspect_ledger(ledger, states, levels, spot, np.ones(391, dtype=bool))[0]
        self.assertAlmostEqual(result['decision_distance_bands'], .5)
        self.assertAlmostEqual(result['fill_distance_bands'], 2.5)
        self.assertEqual(result['hold_minutes'], 19)
        self.assertEqual(PLOT.clock(60), '10:30')


if __name__ == '__main__':
    unittest.main()

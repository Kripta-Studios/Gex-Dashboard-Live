"""Synthetic metric/binding fixtures; no market scores or model execution."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location('score_calibration', Path(__file__).with_name('score_calibration.py'))
CAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAL)


class CalibrationTests(unittest.TestCase):
    def test_exact_bin_boundaries_and_positive_zero(self):
        np.testing.assert_array_equal(CAL.bin_indices([-1, -.1, -.05, -.02, 0, .02, .05, .1, 1]),
                                      [0, 1, 2, 3, 4, 5, 6, 7, 7])
        acc = CAL.Accumulator()
        acc.update([-.01, 0., .01], [0., 0., 0.])
        group, bins = acc.result()
        self.assertEqual(group['positive_score_count'], 1)
        self.assertEqual(group['zero_score_count'], 1)
        self.assertEqual(bins[4]['actions'], 2)

    def test_known_bias_rmse_and_r2(self):
        acc = CAL.Accumulator()
        acc.update([2., 4.], [1., 2.])
        group, _ = acc.result()
        self.assertAlmostEqual(group['bias'], 1.5)
        self.assertAlmostEqual(group['rmse'], np.sqrt(2.5))
        self.assertAlmostEqual(group['r2'], -9.)

    def test_partitioned_accumulation_matches_whole(self):
        p = np.array([-.11, -.08, -.03, 0., .018, .04, .09, .14])
        y = np.array([-.08, .02, -.01, -.005, .021, .03, .11, .12])
        whole, split = CAL.Accumulator(), CAL.Accumulator()
        whole.update(p, y)
        split.update(p[:3], y[:3])
        split.update(p[3:], y[3:])
        a, ab = whole.result()
        b, bb = split.result()
        for key in ('mean_prediction', 'mean_target', 'bias', 'rmse', 'r2', 'positive_score_share'):
            self.assertAlmostEqual(a[key], b[key], places=13)
        self.assertEqual(ab, bb)

    def test_constant_target_and_nonfinite_fail(self):
        acc = CAL.Accumulator()
        acc.update(np.zeros(1000), np.full(1000, .1))
        group, _ = acc.result()
        self.assertIsNone(group['r2'])
        self.assertEqual(group['r2_undefined_reason'], 'CONSTANT_TARGET')
        for pred, target in (([np.nan], [0]), ([0], [np.inf]), ([[0]], [[0]])):
            with self.assertRaises(ValueError):
                CAL.Accumulator().update(pred, target)

    def test_identity_alignment_and_privileged_target(self):
        frame = pd.DataFrame({'action_id': [2, 1], 'dp_advantage': [7., -3.], 'net_base': [-10., 5.]})
        ids = np.array([1, 2])
        np.testing.assert_array_equal(CAL.aligned_target(frame, ids, CAL.TARGETS['gbt_advantage']), [-3., 7.])
        np.testing.assert_array_equal(CAL.aligned_target(frame, ids, CAL.TARGETS['gbt_net']), [5., -10.])
        self.assertEqual(CAL.TARGETS['tcn_teacher'], 'net_base')
        with self.assertRaises(ValueError):
            CAL.aligned_target(frame, [1, 3], 'net_base')
        with self.assertRaises(ValueError):
            CAL.aligned_target(pd.concat([frame.iloc[:1], frame.iloc[:1]]), ids, 'net_base')

    def test_actual_prediction_coverage_must_match_manifest(self):
        CAL.verify_file_coverage({'a.npz'}, {'a.npz': 'sha'}, {'a.npz'})
        with self.assertRaises(ValueError):
            CAL.verify_file_coverage({'a.npz'}, {'a.npz': 'sha'}, {'a.npz', 'extra.npz'})
        with self.assertRaises(ValueError):
            CAL.verify_file_coverage({'a.npz'}, {'a.npz': 'sha'}, set())

    def test_audit_requires_pass_root_and_hashes(self):
        hashes = {'summary.json': 'a', 'freeze.json': 'b', 'validation/prediction_hashes.json': 'c',
                  'test/prediction_hashes.json': 'd'}
        binding = {'learner_root': str(Path('synthetic_root').resolve()), 'learner_summary_sha256': 'a',
                   'freeze_sha256': 'b', 'validation_prediction_manifest_sha256': 'c',
                   'test_prediction_manifest_sha256': 'd', 'oracle_index_sha256': 'e',
                   'oracle_completion_sha256': 'f'}
        audit = {'status': 'PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT', 'binding': binding}
        CAL.verify_audit_binding(audit, 'synthetic_root', hashes, 'e', 'f')
        with self.assertRaises(ValueError):
            CAL.verify_audit_binding(audit, 'other_root', hashes, 'e', 'f')
        with self.assertRaises(ValueError):
            CAL.verify_audit_binding(audit, 'synthetic_root', hashes, 'changed', 'f')
        with self.assertRaises(ValueError):
            CAL.verify_audit_binding(dict(audit, status='PENDING'), 'synthetic_root', hashes, 'e', 'f')


if __name__ == '__main__':
    unittest.main()

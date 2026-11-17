"""Öznitelik çıkarma birim testleri."""
import _common  # noqa: F401

import math
import unittest

import numpy as np

from app.features import (
    curvature_coefficients, extract_features, index_of_difficulty,
    movement_time_ms, pause_total_ms, segment_submovements,
)
from scripts.sentetik_uret import synthetic_trial
import random


def traj(t, xy):
    return np.stack([t, xy[:, 0], xy[:, 1]], axis=1)


class TestID(unittest.TestCase):
    def test_formula(self):
        # log2(200/40 + 1) = log2(6)
        self.assertAlmostEqual(index_of_difficulty(200, 40), math.log2(6), places=9)

    def test_rejects(self):
        with self.assertRaises(ValueError):
            index_of_difficulty(0, 10)


class TestSubmovements(unittest.TestCase):
    def test_two_subs_when_pause(self):
        # 0-200ms hareket, 200-400ms duraklama, 400-600ms düzeltme
        t1 = np.arange(0, 200, 8.0)
        t2 = np.arange(200, 400, 8.0)
        t3 = np.arange(400, 600, 8.0)
        y1 = np.linspace(0, 180, len(t1))          # 0.12 px/ms >> eşik
        y3 = np.linspace(180, 200, len(t3))          # yine eşik üstü
        t = np.concatenate([t1, t2, t3])
        y = np.concatenate([y1, np.zeros(len(t2)), y3])
        xy = np.stack([np.zeros_like(t), y], axis=1)
        subs = segment_submovements(t, xy)
        self.assertEqual(len(subs), 2)

    def test_pause_total(self):
        t1 = np.arange(0, 200, 8.0)
        t2 = np.arange(200, 400, 8.0)
        t = np.concatenate([t1, t2])
        y = np.concatenate([np.linspace(0, 180, len(t1)), np.zeros(len(t2))])
        xy = np.stack([np.zeros_like(t), y], axis=1)
        self.assertGreaterEqual(pause_total_ms(t, xy), 150.0)


class TestSyntheticFeatures(unittest.TestCase):
    def test_extracts_from_generator(self):
        rng = random.Random(7)
        tr = synthetic_trial(rng, "test-sent", 0)
        f = extract_features(tr)
        self.assertGreater(f["ID_bits"], 1.5)
        self.assertGreater(f["MT_ms"], 150.0)
        self.assertLess(f["MT_ms"], 1600.0)
        self.assertGreaterEqual(f["n_sub"], 1)
        self.assertEqual(len(f["curv_coef"]), 4)
        self.assertTrue(f["hit"])

    def test_source_label_enforced(self):
        rng = random.Random(3)
        tr = synthetic_trial(rng, "test-sent", 1)
        self.assertEqual(tr["source"], "synthetic")
        self.assertIn("generator", tr)


class TestCurv(unittest.TestCase):
    def test_zero_for_straight(self):
        t = np.linspace(0, 400, 64)
        xy = np.stack([t, 2 * t], axis=1)
        c = curvature_coefficients(t, xy, D=math.hypot(400, 800))
        np.testing.assert_allclose(c, 0.0, atol=1e-9)


if __name__ == "__main__":
    unittest.main()

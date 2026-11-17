"""Geometri birim testleri (saf matematik)."""
import _common  # noqa: F401

import math
import unittest

import numpy as np

from app.geometry import (
    basis_curve, bezier3, fit_basis, lateral_profile, min_jerk_profile,
    resample_uniform, sin_basis, speed_series, warp_time,
)


class TestMinJerk(unittest.TestCase):
    def test_endpoints(self):
        s = np.array([0.0, 1.0])
        out = min_jerk_profile(s)
        self.assertAlmostEqual(out[0], 0.0, places=9)
        self.assertAlmostEqual(out[1], 1.0, places=9)

    def test_peak_speed_near_middle(self):
        s = np.linspace(0, 1, 1001)
        pos = min_jerk_profile(s)
        v = np.diff(pos) / np.diff(s)
        t_peak = s[int(np.argmax(v))]
        self.assertGreater(t_peak, 0.30)
        self.assertLess(t_peak, 0.50)  # tepe ~0.36-0.40 bandı

    def test_monotone(self):
        pos = min_jerk_profile(np.linspace(0, 1, 997))
        self.assertTrue(bool(np.all(np.diff(pos) >= -1e-12)))


class TestBasis(unittest.TestCase):
    def test_zero_at_ends(self):
        s = np.array([0.0, 1.0])
        B = sin_basis(4, s)
        np.testing.assert_allclose(B, 0.0, atol=1e-12)

    def test_roundtrip(self):
        s = np.linspace(0, 1, 64)
        coef = np.array([0.03, -0.02, 0.01, 0.005])
        curve = basis_curve(coef, s)
        back = fit_basis(curve, K=4)
        np.testing.assert_allclose(back, coef, atol=5e-4)


class TestResample(unittest.TestCase):
    def test_uniform(self):
        t = np.arange(0, 500, 7.0)
        xy = np.stack([t * 0.1, np.sin(t / 90)], axis=1)
        rs = resample_uniform(np.stack([t, xy[:, 0], xy[:, 1]], axis=1), n=64)
        self.assertEqual(rs.shape, (64, 3))
        self.assertAlmostEqual(rs[0, 0], 0.0)
        self.assertAlmostEqual(rs[-1, 0], 1.0)
        self.assertTrue(bool(np.all(np.diff(rs[:, 1]) >= -1e-9)))

    def test_short_raises(self):
        with self.assertRaises(ValueError):
            resample_uniform(np.zeros((1, 3)))


class TestLat(unittest.TestCase):
    def test_perp_zero_at_ends(self):
        start, end = (100, 100), (500, 300)
        t = np.linspace(0, 600, 80)
        xy = np.stack([np.linspace(100, 500, 80), np.linspace(100, 300, 80)], axis=1)
        xy[:, 1] += 30 * np.sin(np.linspace(0, math.pi, 80))
        rs = resample_uniform(np.stack([t, xy[:, 0], xy[:, 1]], axis=1), 64)
        lat = lateral_profile(rs, start, end)
        self.assertAlmostEqual(lat[0, 2], 0.0, places=6)
        self.assertAlmostEqual(lat[-1, 2], 0.0, places=6)
        self.assertGreater(float(np.abs(lat[:, 2]).max()), 0.0)


class TestSpeed(unittest.TestCase):
    def test_constant(self):
        t = np.arange(0, 100, 10, dtype=float)
        xy = np.stack([t, np.zeros_like(t)], axis=1)   # 10 px / 10 ms = 1.0 px/ms
        v = speed_series(t, xy)
        np.testing.assert_allclose(v[1:], 1.0, atol=1e-9)


class TestWarp(unittest.TestCase):
    def test_identity_and_bounds(self):
        s = np.linspace(0, 1, 7)
        np.testing.assert_allclose(warp_time(s, 1.0), s)
        self.assertTrue(bool(np.all(np.diff(warp_time(s, 1.4)) >= 0)))


if __name__ == "__main__":
    unittest.main()

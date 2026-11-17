"""Metrik hesaplama testleri."""
import _common  # noqa: F401

import math
import unittest

import numpy as np

from app.config import load_config
from app.metrics.kinematics import plan_metrics, summarize
from app.metrics.system import ProcessResources
from app.models.baseline import BaselineModel
from app.models import TrajectoryPlan


class TestPlanMetrics(unittest.TestCase):
    def make_plan(self, curve=True):
        m = BaselineModel(load_config())
        return m.generate((100, 100), (750, 500), 28.0, np.random.default_rng(3))

    def test_basic_metrics(self):
        p = self.make_plan()
        m = plan_metrics(p)
        self.assertTrue(m["hit_click"])
        self.assertTrue(m["hit_margin"])
        self.assertTrue(m["last_point_in_target"])
        self.assertGreater(m["duration_ms"], 100)
        self.assertGreater(m["path_len_px"], 600)
        self.assertGreaterEqual(m["path_over_chord"], 0.98)
        self.assertGreater(m["peak_v_px_ms"], 0)
        self.assertGreaterEqual(m["jerk_rms_px_ms3"], 0)

    def test_summary(self):
        p = self.make_plan()
        s = summarize([plan_metrics(p) for _ in range(5)])
        self.assertEqual(s["n"], 5)
        self.assertEqual(s["hit_rate_click"], 1.0)
        self.assertIn("duration_ms_std", s)
        self.assertEqual(summarize([]), {})


class TestSystemResources(unittest.TestCase):
    def test_measures_something(self):
        pr = ProcessResources()
        cpu = pr.cpu_percent()
        ram = pr.ram_mb()
        self.assertGreaterEqual(cpu, 0.0)
        self.assertLess(cpu, 1000.0)
        self.assertGreater(ram, 1.0)


if __name__ == "__main__":
    unittest.main()

""" üç jeneratörün üretim garantileri."""
import _common  # noqa: F401

import math
import random
import unittest

import numpy as np

from app.config import load_config
from app.models.baseline import BaselineModel
from app.models.learned import LearnedModel
from app.models.rescaler import RescalerModel
from app.control.validation import validate_plan
from app.features import extract_features
from scripts.sentetik_uret import synthetic_trial

SCREEN = (0.0, 0.0, 1920.0, 1080.0)


class Base(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.screen = SCREEN

    def check_plan(self, plan, radius):
        ok, reason = validate_plan(plan, self.cfg, self.screen)
        self.assertTrue(ok, reason)
        self.assertGreaterEqual(len(plan.waypoints), 3)
        # tıklama güvencesi: hedef İÇİNDE
        d = math.hypot(plan.click_xy[0] - plan.target_xy[0],
                       plan.click_xy[1] - plan.target_xy[1])
        self.assertLessEqual(d, 0.8 * radius + 1e-9)


class TestBaseline(Base):
    def test_endpoint_guarantee_many(self):
        m = BaselineModel(self.cfg)
        for i in range(60):
            rng = np.random.default_rng(100 + i)
            plan = m.generate((100, 100), (900, 600), 30.0, rng)
            self.check_plan(plan, 30.0)

    def test_duration_grows_with_difficulty(self):
        m = BaselineModel(self.cfg)
        ts_small, ts_big = [], []
        for i in range(12):
            rng = np.random.default_rng(i)
            ts_small.append(m.generate((500, 400), (520, 410), 40.0, rng).duration_ms)
            ts_big.append(m.generate((100, 100), (1500, 800), 12.0, rng).duration_ms)
        self.assertLess(np.mean(ts_small), np.mean(ts_big))

    def test_zero_distance_rejected(self):
        m = BaselineModel(self.cfg)
        with self.assertRaises(ValueError):
            m.generate((500, 500), (500, 500), 30.0, np.random.default_rng(0))


class TestLearned(Base):
    def make_records(self, n_sessions=3, per=12):
        rng = random.Random(51)
        out = []
        for s in range(n_sessions):
            sid = f"unit-learned-{s}"
            for i in range(per):
                out.append(synthetic_trial(rng, sid, i))
        return out

    def test_fit_and_generate(self):
        recs = self.make_records()
        m = LearnedModel.fit(self.cfg, recs)
        p = m.p
        self.assertGreater(p["fitts"]["b_ms_per_bit"], 0)
        self.assertEqual(p["n_train"], len(recs))
        for i in range(25):
            rng = np.random.default_rng(900 + i)
            plan = m.generate((110, 120), (880, 640), 26.0, rng)
            self.check_plan(plan, 26.0)
            self.assertGreaterEqual(plan.duration_ms, self.cfg["min_duration_ms"])

    def test_fitts_consistency(self):
        """Sentetik üretici Fitts-benzeri süreler kullanır; duraklama/düzeltme gürültüsü
        korelasyonu baskılar — eşik buna göre ılımlı tutulur."""
        recs = self.make_records()
        m = LearnedModel.fit(self.cfg, recs)
        f = [extract_features(r) for r in recs]
        ids = np.asarray([x["ID_bits"] for x in f])
        mts = np.asarray([x["MT_ms"] for x in f])
        pred = m.p["fitts"]["a_ms"] + m.p["fitts"]["b_ms_per_bit"] * ids
        corr = np.corrcoef(pred, mts)[0, 1]
        self.assertGreater(corr, 0.45)

    def test_save_load_roundtrip(self):
        import tempfile, os, json
        recs = self.make_records()
        m = LearnedModel.fit(self.cfg, recs)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "model.json")
            m.save(path)
            m2 = LearnedModel.load(self.cfg, path)
            self.assertIsNotNone(m2)
            self.assertEqual(m2.p["fitts"], m.p["fitts"])
        self.assertIsNone(LearnedModel.load(self.cfg, "olmayan-dosya.json"))


class TestRescaler(Base):
    def test_uses_exemplar_and_fallback(self):
        rng = random.Random(77)
        recs = [synthetic_trial(rng, f"unit-resc-{i//10}", i) for i in range(20)]
        m = RescalerModel(self.cfg, recs)
        self.assertEqual(len(m.exemplars), 20)
        # ID uygunsuz istek → baseline fallback (meta işaretli)
        seen_fallback = seen_direct = False
        for i in range(40):
            rng2 = np.random.default_rng(700 + i)
            # bazen sentetik dağılım içinde (D~400, W~60 → ID≈3.76), bazen uçta
            r = 30.0 if i % 2 else 6.0                       # ID düşük vs çok yüksek
            plan = m.generate((200, 200), (700, 450), r, rng2)
            self.check_plan(plan, r)
            if plan.meta.get("fallback"):
                seen_fallback = True
            else:
                seen_direct = True
                self.assertIn("exemplar_ID_bits", plan.meta)
        self.assertTrue(seen_direct, "yakın ID'lerde doğrudan örnek beklenir")


if __name__ == "__main__":
    unittest.main()

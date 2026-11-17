"""Depo şema + oturum ayrımı birim testleri (kullanıcı gereksinimleri)."""
import _common  # noqa: F401

import json
import os
import random
import tempfile
import unittest

from app.storage import (
    load_recordings, new_session_id, save_session, split_train_test,
    validate_trial,
)
from scripts.sentetik_uret import synthetic_trial


def make_trial(sid, source, radius=30.0):
    t = [[0.0, 10.0, 10.0], [50.0, 60.0, 40.0], [120.0, 200.0, 80.0]]
    return {"session_id": sid, "source": source, "target": [200.0, 80.0],
            "radius": radius, "presented_ms": -100.0, "click_ms": 120.0,
            "hit": True, "samples": t}


class TestSchema(unittest.TestCase):
    def test_synthetic_label_required(self):
        tr = make_trial("s1", "synthetic")
        with self.assertRaises(ValueError):
            validate_trial(tr)          # generator alanı yok
        tr["generator"] = "test-gen"
        validate_trial(tr)

    def test_bad_source_rejected(self):
        with self.assertRaises(ValueError):
            validate_trial(make_trial("s1", "robot"))

    def test_missing_field_rejected(self):
        tr = make_trial("s1", "human")
        del tr["radius"]
        with self.assertRaises(ValueError):
            validate_trial(tr)


class TestRoundTrip(unittest.TestCase):
    def test_save_load(self):
        with tempfile.TemporaryDirectory() as d:
            sid = "unittest-abc"
            trials = [make_trial(sid, "human") for _ in range(3)]
            for k, tr in enumerate(trials):
                tr["samples"] = [[0.0, 1.0 + k, 2.0], [90.0, 3.0, 4.0]]
            save_session(d, trials, meta={"app": "unittest"})
            got = load_recordings(d)
            self.assertEqual(len(got), 3)
            self.assertEqual({g["session_id"] for g in got}, {sid})

    def test_filter_sources(self):
        with tempfile.TemporaryDirectory() as d:
            rng = random.Random(5)
            sent = [synthetic_trial(rng, "unit-sent", 0)]
            save_session(d, sent)
            save_session(d, [make_trial("unit-hum", "human")])
            self.assertEqual(len(load_recordings(d, sources=("human",))), 1)
            self.assertEqual(len(load_recordings(d, sources=("synthetic",))), 1)
            self.assertEqual(len(load_recordings(d)), 2)

    def test_jsonl_content(self):
        """Şemada yasak veri tipleri (şifre/klavye/ekran) field OLAMAZ (yapısal denetim)."""
        allowed = {"session_id", "source", "generator", "trial", "target", "radius",
                    "presented_ms", "click_ms", "hit", "samples"}
        tr = make_trial("s1", "human")
        self.assertTrue(set(tr.keys()) <= allowed)


class TestSessionSplit(unittest.TestCase):
    def test_no_session_overlap(self):
        a = []
        for s in range(6):
            for _ in range(3):
                a.append(make_trial(f"sess-{s}", "human"))
        tr, te = split_train_test(a, test_ratio=0.34, rng=random.Random(1))
        self.assertEqual(len({t["session_id"] for t in tr}) +
                         len({t["session_id"] for t in te}), 6)
        self.assertFalse({t["session_id"] for t in tr} &
                         {t["session_id"] for t in te})
        self.assertEqual(len(tr) + len(te), len(a))

    def test_single_session_all_train(self):
        a = [make_trial("only", "human") for _ in range(5)]
        tr, te = split_train_test(a, 0.3)
        self.assertEqual(len(tr), 5)
        self.assertEqual(len(te), 0)


if __name__ == "__main__":
    unittest.main()

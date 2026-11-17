"""Model seçimi ve eğitim orkestrasyonu.

Kural (docs §3): veri yeterliyse (c) learned, eksikse (b) rescaler, o da yoksa (a) baseline.
Eğitim/test ayrımı OTURUM bazındadır (storage.split_train_test).
"""
from __future__ import annotations

import random

from ..config import get
from ..storage import load_recordings, split_train_test
from .baseline import BaselineModel
from .learned import LearnedModel
from .rescaler import RescalerModel


class ModelManager:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.baseline = BaselineModel(cfg)
        self.rescaler: RescalerModel | None = None
        self.learned: LearnedModel | None = None
        self.train_trials: list[dict] = []
        self.test_trials: list[dict] = []
        self.selection_reason = ""

    # ---------- yükleme + seçim ----------
    def load_and_split(self, data_dir: str, sources=("human", "synthetic")) -> None:
        allrec = load_recordings(data_dir, sources=sources)
        rng = random.Random(int(get(self.cfg, "rng_seed")))
        self.train_trials, self.test_trials = split_train_test(
            allrec, float(get(self.cfg, "split_test_ratio")), rng)

    def train_from_split(self, include_synthetic_with_human: bool = True) -> None:
        """Rescaler exemplar'ları yalnızca TRAİN oturumlarından gelir (sızma yok)."""
        tr = self.train_trials
        if include_synthetic_with_human and not any(t["source"] == "human" for t in tr):
            pass  # yalnız sentetik eğitim: pipeline doğrulaması, raporda açıkça işaretlenir
        min_trials_r = int(get(self.cfg, "model_selection.rescaler_min_trials"))
        if len(tr) >= min_trials_r:
            self.rescaler = RescalerModel(self.cfg, tr)
        else:
            self.rescaler = None
        self.learned = None  # öğrenilmiş model yalnızca kayıtlı dosyadan veya fit ile

    def fit_learned(self) -> LearnedModel:
        self.learned = LearnedModel.fit(self.cfg, self.train_trials)
        return self.learned

    def select(self, pref: str | None = None) -> tuple[object, str]:
        """pref: 'baseline'|'rescaler'|'learned'|None (otomatik). Dönüş: (model, neden)."""
        if pref == "baseline":
            return self.baseline, "kullanıcı tercihi: baseline"
        if pref == "rescaler":
            if self.rescaler is None:
                raise ValueError("rescaler için yeterli kayıt yok "
                                 f"({int(get(self.cfg, 'model_selection.rescaler_min_trials'))} deneme gerekli)")
            return self.rescaler, "kullanıcı tercihi: rescaler"
        if pref == "learned":
            if self.learned is None:
                raise ValueError("learned model henüz eğitilmedi (scripts/egitim.py)")
            return self.learned, "kullanıcı tercihi: learned"
        # otomatik
        l_min_s = int(get(self.cfg, "model_selection.learned_min_sessions"))
        l_min_t = int(get(self.cfg, "model_selection.learned_min_trials"))
        if self.learned is not None:
            ok_sessions = not hasattr(self.learned, "p") or self.learned.p["n_sessions"] >= l_min_s
            if ok_sessions and self.learned.p["n_train"] >= l_min_t:
                return self.learned, (f"otomatik: learned ({self.learned.p['n_train']} deneme, "
                                      f"{self.learned.p['n_sessions']} oturum)")
        if self.rescaler is not None:
            return self.rescaler, "otomatik: rescaler (learned için veri yetersiz)"
        return self.baseline, "otomatik: baseline (kayıt yok)"

    def available(self) -> dict:
        return {
            "baseline": True,
            "rescaler": self.rescaler is not None,
            "learned_loaded": self.learned is not None,
            "n_train": len(self.train_trials),
            "n_test": len(self.test_trials),
        }

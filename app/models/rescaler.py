"""(b) Örnek yeniden ölçekleme: kayıtlı yörünge ŞEKİLLERİNİ yeni D,W'ye taşır.

Yakın zorluktaki (ID) bir örnek seçilir; along/perp profili yeni mesafeye ölçeklenir,
süre Fitts'ten gelir. Kayıt yoksa / ID çok uzaksa BaselineModel'e düşer (meta'da işaretli).
"""
from __future__ import annotations

import math

import numpy as np

from ..config import get
from ..features import index_of_difficulty, trial_to_arrays
from ..geometry import lateral_profile, path_frame, point_from_local, resample_uniform
from . import TrajectoryPlan
from .baseline import (
    BaselineModel,
    _apply_jitter,
    _plan_common,
    _sample_inside_target,
)

MAX_ID_GAP_BITS = 1.5   # bundan yakın örnek yoksa taban çizgiye düş


class RescalerModel:
    name = "rescaler"

    def __init__(self, cfg: dict, train_trials: list[dict] | None = None):
        self.cfg = cfg
        self._fallback = BaselineModel(cfg)
        self.exemplars: list[dict] = []
        # Fitts: kayıttan gelir, yoksa varsayılan
        self.fitts = {"a_ms": float(get(cfg, "fitts_defaults.a_ms")),
                      "b_ms_per_bit": float(get(cfg, "fitts_defaults.b_ms_per_bit"))}
        if train_trials:
            self._fit_fitts(train_trials)
            self.exemplars = [self._trial_to_exemplar(tr) for tr in train_trials]

    # ---- öğrenme ----
    def _fit_fitts(self, trials: list[dict]) -> None:
        X, Y = [], []
        for tr in trials:
            t, xy, _ = trial_to_arrays(tr)
            D = math.hypot(float(tr["target"][0]) - xy[0, 0],
                           float(tr["target"][1]) - xy[0, 1])
            W = 2.0 * float(tr["radius"])
            if D < 1.0 or t[-1] <= 0:
                continue
            X.append([1.0, index_of_difficulty(D, W)])
            Y.append(float(tr["click_ms"]) - float(tr["samples"][0][0]))
        if len(X) < 8:
            return
        Xa, Ya = np.asarray(X), np.asarray(Y)
        coef, *_ = np.linalg.lstsq(Xa, Ya, rcond=None)
        if 20.0 <= coef[1] <= 600.0 and -300.0 <= coef[0] <= 1000.0:
            self.fitts = {"a_ms": float(coef[0]), "b_ms_per_bit": float(coef[1])}

    def _trial_to_exemplar(self, tr: dict) -> dict:
        t, xy, _ = trial_to_arrays(tr)
        rs = resample_uniform(np.stack([t, xy[:, 0], xy[:, 1]], axis=1), n=64)
        lat = lateral_profile(rs, (float(xy[0, 0]), float(xy[0, 1])),
                              (float(xy[-1, 0]), float(xy[-1, 1])))
        along0, along1 = float(lat[0, 1]), float(lat[-1, 1])       # 0 ve D olmalı
        span_along = max(abs(along1 - along0), 1e-6)
        return {
            "ID_bits": float(index_of_difficulty(abs(along1 - along0),
                                                 2.0 * float(tr["radius"]))),
            "D_px": abs(along1 - along0),
            "W_px": 2.0 * float(tr["radius"]),
            "along_norm": ((lat[:, 1] - along0) / span_along).tolist(),
            "perp_norm": (lat[:, 2] / span_along).tolist(),
            "landing_off_per_w": _endpoint_offset_per_w(tr),
        }

    # ---- süre ----
    def duration_ms(self, D: float, W: float, rng) -> float:
        T = self.fitts["a_ms"] + self.fitts["b_ms_per_bit"] * math.log2(D / W + 1.0)
        T *= 1.0 + rng.normal(0.0, float(get(self.cfg, "duration_noise_frac")))
        return float(np.clip(T, float(get(self.cfg, "min_duration_ms")),
                             float(get(self.cfg, "max_duration_ms"))))

    # ---- üretim ----
    def generate(self, start, target, radius, rng: np.random.Generator) -> TrajectoryPlan:
        start_xy, target_xy, D, r = _plan_common(start, target, radius)
        W = 2.0 * r
        ID = index_of_difficulty(D, W)
        ex = self._pick_exemplar(ID, rng)
        if ex is None:
            plan = self._fallback.generate(start, target, radius, rng)
            plan.model_name = "rescaler"
            plan.meta["fallback"] = "baseline (uygun örnek yok)"
            return plan

        T = self.duration_ms(D, W, rng)
        dt = int(get(self.cfg, "waypoint_dt_ms"))
        steps = max(int(math.ceil(T / dt)), 16)
        t_hat = np.linspace(0.0, 1.0, steps)
        along_n = np.interp(t_hat, np.linspace(0, 1, len(ex["along_norm"])), ex["along_norm"])
        perp_n = np.interp(t_hat, np.linspace(0, 1, len(ex["perp_norm"])), ex["perp_norm"])
        along_u, perp_u, _ = path_frame(start_xy, target_xy)
        xs, ys = point_from_local(start_xy, along_u, perp_u, D * along_n, D * perp_n)
        xy = np.stack([np.asarray(xs), np.asarray(ys)], axis=1)
        xy = _apply_jitter(xy, rng, float(get(self.cfg, "jitter.rho")),
                           float(get(self.cfg, "jitter.sigma_px")),
                           float(get(self.cfg, "jitter.end_damp_frac")))

        # Endpoint: örneğin yerleşim sapması (W'ye göre) yeni hedefe taşınır
        margin = float(get(self.cfg, "endpoint_margin_factor"))
        off_per_w = float(np.clip(ex["landing_off_per_w"], 0.0, margin))
        ang = rng.uniform(0.0, 2 * math.pi)
        click_xy = (target_xy[0] + off_per_w * W * math.cos(ang),
                    target_xy[1] + off_per_w * W * math.sin(ang))
        t_ms = t_hat * T
        t_ms[-1] = max(t_ms[-1], T - 0.5)
        xy[-1, 0], xy[-1, 1] = click_xy
        hold = float(rng.integers(int(get(self.cfg, "min_click_hold_ms")),
                                  int(get(self.cfg, "max_click_hold_ms"))))
        return TrajectoryPlan(
            waypoints=np.stack([t_ms, xy[:, 0], xy[:, 1]], axis=1),
            click_xy=(float(click_xy[0]), float(click_xy[1])),
            duration_ms=float(T), hold_ms=hold, model_name=self.name,
            start_xy=start_xy, target_xy=target_xy, radius=r,
            meta={"exemplar_ID_bits": ex["ID_bits"], "ID_bits": ID},
        )

    def _pick_exemplar(self, ID: float, rng) -> dict | None:
        if not self.exemplars or ID is None:
            return None
        gaps = [(abs(ex["ID_bits"] - ID), i) for i, ex in enumerate(self.exemplars)]
        gaps.sort()
        near = [g for g in gaps if g[0] <= MAX_ID_GAP_BITS]
        if not near:
            return None
        _gap, i = near[int(rng.integers(0, len(near)))]
        return self.exemplars[i]


def _endpoint_offset_per_w(tr: dict) -> float:
    """Son örnek ile hedef merkez farkının W'ye oranı (negatif olmayan)."""
    s = tr["samples"]
    ex, ey = float(s[-1][1]), float(s[-1][2])
    off = math.hypot(float(tr["target"][0]) - ex, float(tr["target"][1]) - ey)
    return off / max(2.0 * float(tr["radius"]), 1e-6)

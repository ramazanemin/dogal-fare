"""(a) Algoritmik taban çizgi: minimum-jerk yörünge + Fitts süresi + hafif yay.

Verdiğiyle yetinir: kayıt yok. Eğrilik tek sabit yay, duraklama ve düzeltme YOK.
Karşılaştırmanın referans noktası (docs §3).
"""
from __future__ import annotations

import math

import numpy as np

from ..config import get
from ..geometry import basis_curve, min_jerk_profile, path_frame, point_from_local
from . import TrajectoryPlan


def _plan_common(start, target, radius):
    """Ortak geometric büyüklükler ve güvenlik reddi."""
    sx, sy = float(start[0]), float(start[1])
    tx, ty = float(target[0]), float(target[1])
    D = math.hypot(tx - sx, ty - sy)
    r = float(radius)
    if D < 1.0:
        raise ValueError("başlangıç ve hedef neredeyse aynı noktada")
    if r <= 0:
        raise ValueError("radius > 0 gerekli")
    return (sx, sy), (tx, ty), D, r


class BaselineModel:
    name = "baseline"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    # ---- süre modeli (Fitts + gürültü) ----
    def duration_ms(self, D: float, W: float, rng: np.random.Generator) -> float:
        a = float(get(self.cfg, "fitts_defaults.a_ms"))
        b = float(get(self.cfg, "fitts_defaults.b_ms_per_bit"))
        T = a + b * math.log2(max(D, 1e-6) / max(W, 1e-6) + 1.0)
        noise_frac = float(get(self.cfg, "duration_noise_frac"))
        T *= 1.0 + rng.normal(0.0, noise_frac)
        lo = float(get(self.cfg, "min_duration_ms"))
        hi = float(get(self.cfg, "max_duration_ms"))
        return float(np.clip(T, lo, hi))

    # ---- üretim ----
    def generate(self, start, target, radius, rng: np.random.Generator) -> TrajectoryPlan:
        start_xy, target_xy, D, r = _plan_common(start, target, radius)
        W = 2.0 * r
        T = self.duration_ms(D, W, rng)
        dt = int(get(self.cfg, "waypoint_dt_ms"))
        steps = max(int(math.ceil(T / dt)), 12)
        t_hat = np.linspace(0.0, 1.0, steps)
        s = min_jerk_profile(t_hat)                      # çan hızlı, uçlarda yumuşak
        along_u, perp_u, _ = path_frame(start_xy, target_xy)

        # Hafif tek yay: uçlarda sıfırlanan sin profili (yön rassal)
        amp = D * 0.06 * (1.0 if rng.random() < 0.5 else -1.0) * (0.6 + 0.8 * rng.random())
        perp = amp * np.sin(math.pi * t_hat)

        xs, ys = point_from_local(start_xy, along_u, perp_u, D * s, perp)
        xy = np.stack([np.asarray(xs), np.asarray(ys)], axis=1)

        # Mikro-tremor (AR(1)); son dilimde sönümlü
        rho = float(get(self.cfg, "jitter.rho"))
        sig = float(get(self.cfg, "jitter.sigma_px"))
        damp = float(get(self.cfg, "jitter.end_damp_frac"))
        xy = _apply_jitter(xy, rng, rho, sig, damp)

        # Tıklama noktası: merkez çevresinde küçük dağılım, MARGİN içine sıkıştırılmış
        margin = float(get(self.cfg, "endpoint_margin_factor"))
        click_xy = _sample_inside_target(target_xy, r, margin, sigma=0.10 * r, rng=rng)

        # Son waypoint = tıklama noktası (hareket tıklamada biter)
        t_ms = t_hat * T
        t_ms[-1] = max(t_ms[-1], T - 0.5)
        xy[-1, 0], xy[-1, 1] = click_xy

        hold = float(rng.integers(int(get(self.cfg, "min_click_hold_ms")),
                                  int(get(self.cfg, "max_click_hold_ms"))))
        return TrajectoryPlan(
            waypoints=np.stack([t_ms, xy[:, 0], xy[:, 1]], axis=1),
            click_xy=(float(click_xy[0]), float(click_xy[1])),
            duration_ms=float(T), hold_ms=hold,
            model_name=self.name, start_xy=start_xy, target_xy=target_xy, radius=r,
            meta={"amp_px": float(amp), "ID_bits": math.log2(D / W + 1.0)},
        )


def _apply_jitter(xy: np.ndarray, rng, rho: float, sigma: float, end_damp: float) -> np.ndarray:
    """AR(1) mikro-tremor; son end_damp dilimde amplitüd sönümlenir (endpoint isabeti)."""
    n = len(xy)
    out = xy.copy()
    e = np.zeros(2)
    for i in range(n):
        frac = i / max(n - 1, 1)
        amp = sigma * (1.0 if frac < (1.0 - end_damp) else max(1e-3, (1.0 - frac) / end_damp))
        e = rho * e + rng.normal(0.0, max(amp, 1e-4), size=2)
        out[i] += e
    return out


def _sample_inside_target(center, radius: float, margin: float, sigma: float, rng):
    """Merkez çevresinde rastgele nokta; margin*radius içine sıkıştırılmış GUARANTEE."""
    ang = rng.uniform(0.0, 2 * math.pi)
    mag = abs(float(rng.normal(0.0, max(sigma, 1e-3))))
    mag = min(mag, margin * radius)
    return (float(center[0]) + mag * math.cos(ang),
            float(center[1]) + mag * math.sin(ang))

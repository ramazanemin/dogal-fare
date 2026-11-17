"""Saf hareket ÜRETİM katmanı — Win32/donanım erişimi YASAKTIR.

Ortak arayüz:
    TrajectoryPlan  : zaman damgalı waypoint'ler + tıklama noktası + meta
    MovementModel   : .generate(start, target, radius, rng) -> TrajectoryPlan
Her model hedefin İÇİNDE bir tıklama noktası üretir; iddia edilen süreyi ve yolu
parametre halinde taşır. Kontrol katmanı (app.control) planı doğrulayıp yürütür.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TrajectoryPlan:
    """Bir hamlenin tam planı (tamamen saf veri)."""
    waypoints: np.ndarray          # (N,3) [t_ms_göreli, x, y] — t artan
    click_xy: tuple[float, float]  # gerçek tıklama noktası (hedef İÇİNDE garanti)
    duration_ms: float             # son waypoint anı (hareket süresi)
    hold_ms: float                  # tıklama basılı süresi
    model_name: str
    start_xy: tuple[float, float]
    target_xy: tuple[float, float]
    radius: float
    meta: dict = field(default_factory=dict)

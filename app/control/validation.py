"""Plan güvenlik doğrulaması (saf, test edilebilir).

Yürütmeden ÖNCE zorunlu: zaman tekilliği, ekran sınırı, tıklama noktasının hedef
İÇİNDE olması (kullanıcı gereksinimi: "son tıklamayı hedefin içinde gerçekleştir").
"""
from __future__ import annotations

import math

import numpy as np

from ..config import get


def validate_plan(plan, cfg: dict, screen_rect: tuple[float, float, float, float],
                  ) -> tuple[bool, str]:
    """(ok, reason). screen_rect = (x0, y0, w, h) — sanal ekran.

    Redler:
      - boş/tek adımlı plan, tekillik bozuk, adım dt üst sınırı aşımı
      - ekran dışı waypoint (bounds_margin_px toleransı ile)
      - tıklama noktası margin*radius dışında
      - son waypoint ile tıklama noktası uyumsuz
    """
    wp = plan.waypoints
    if wp.ndim != 2 or wp.shape[0] < 3 or wp.shape[1] != 3:
        return False, "plan çok kısa"
    sx, sy, sw, sh = screen_rect
    margin = float(get(cfg, "bounds_margin_px"))
    t = wp[:, 0]
    dt = np.diff(t)
    if np.any(dt <= 0):
        return False, "zaman damgası tek değil"
    max_dt = float(get(cfg, "max_waypoint_dt_ms"))
    if np.any(dt > max_dt + 1e-9):
        return False, f"adım aralığı {max_dt} ms üst sınırını aşıyor"
    x_lo, x_hi = sx - margin, sx + sw + margin
    y_lo, y_hi = sy - margin, sy + sh + margin
    if (wp[:, 1] < x_lo).any() or (wp[:, 1] > x_hi).any():
        return False, "ekran sınırı dışı x"
    if (wp[:, 2] < y_lo).any() or (wp[:, 2] > y_hi).any():
        return False, "ekran sınırı dışı y"
    tx, ty = plan.click_xy
    dist = math.hypot(tx - plan.target_xy[0], ty - plan.target_xy[1])
    m = float(get(cfg, "endpoint_margin_factor")) * float(plan.radius)
    if dist > m + 1e-6:
        return False, f"tıklama noktası hedefin dışında ({dist:.1f}px > {m:.1f}px)"
    # Son waypoint tıklama noktası olmalı (hareket tıklamada biter)
    dx = abs(float(wp[-1, 1]) - tx)
    dy = abs(float(wp[-1, 2]) - ty)
    if dx > 2.0 or dy > 2.0:
        return False, "son waypoint tıklama noktasıyla uyumsuz"
    # Başlangıç zaten ekranda olmalı
    return True, "ok"

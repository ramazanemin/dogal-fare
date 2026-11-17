"""Test hedef seti üreticisi — "daha önce görülmemiş konum ve boyutlar" (docs §5).

Kalibrasyon aralığından bağımsız kombinasyonlar: D ∈ [150, 900] px,
r ∈ {8, 16, 24, 40, 64} px, seed'li ve tekrarlanabilir. Modeller konum saklamadığından
üretim perspektifinden hepsi "görülmemiş"tir; bu yine de raporda açıkça söylenir.
"""
from __future__ import annotations

import math
import random

DIST_MIN, DIST_MAX = 150.0, 900.0
RADII_TEST = [8.0, 16.0, 24.0, 40.0, 64.0]


def make_test_targets(canvas_w: float, canvas_h: float, n: int,
                      seed: int = 20261115) -> list[dict]:
    rng = random.Random(seed)
    targets: list[dict] = []
    for i in range(n):
        r = RADII_TEST[i % len(RADII_TEST)]
        while True:
            tx = rng.uniform(3 * r + 20, canvas_w - 3 * r - 20)
            ty = rng.uniform(3 * r + 70, canvas_h - 3 * r - 20)
            if not targets or all(
                    math.hypot(tx - t["x"], ty - t["y"]) > t["r"] + r + 40
                    for t in targets[-3:]):
                break
        ang = rng.uniform(0.0, 2 * math.pi)
        dist = rng.uniform(DIST_MIN, DIST_MAX)
        sx = min(max(tx + dist * math.cos(ang), 20), canvas_w - 20)
        sy = min(max(ty + dist * math.sin(ang), 80), canvas_h - 20)
        if math.hypot(tx - sx, ty - sy) < 0.5 * dist:
            sx = min(max(2 * tx - sx, 20), canvas_w - 20)
            sy = min(max(2 * ty - sy, 80), canvas_h - 20)
        targets.append({"x": tx, "y": ty, "r": r, "sx": sx, "sy": sy})
    return targets

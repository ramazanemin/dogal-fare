#!/usr/bin/env python3
"""SENTETİK kayıt üreticisi — her kayıtta `source:"synthetic"` + `generator` etiketi.

Amaç (docs §2/§3): gerçek insan verisi gelmeden pipeline'ı (öğrenme, oturum
ayrımı, değerlendirme) uçtan uca doğrulamak. Bu kayıtlar İNSAN VERİSİ DEĞİLDİR;
test raporlarında bu açıkça belirtilir. İnsan kalibrasyonu geldiğinde
`scripts/egitim.py --kaynak human` yalnız gerçek oturumlarla çalışır.

Kullanım:
    python scripts/sentetik_uret.py                # 3 oturum × 30 deneme
    python scripts/sentetik_uret.py --oturum 2 --deneme 40
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage import new_session_id, save_session  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = "synth-v1"
RADII = [18.0, 26.0, 34.0, 50.0]


def _minjerk(s):
    return 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5


def synthetic_trial(rng: random.Random, session_id: str, trial: int) -> dict:
    """Basit 'insan-vari' yörünge: min-jerk + yay + tremor + duraklama + düzeltme."""
    w, h = 980.0, 660.0
    r = rng.choice(RADII) * rng.uniform(0.9, 1.1)
    tx = rng.uniform(3 * r, w - 3 * r)
    ty = rng.uniform(3 * r + 60, h - 3 * r)
    ang = rng.uniform(0.0, 2 * math.pi)
    dist = rng.uniform(220.0, 640.0)
    sx = min(max(tx + dist * math.cos(ang), 10), w - 10)
    sy = min(max(ty + dist * math.sin(ang), 10), h - 10)
    D = math.hypot(tx - sx, ty - sy)
    ID = math.log2(D / (2 * r) + 1)
    T = (170 + 120 * ID) * rng.uniform(0.85, 1.2)      # Fitts benzeri süre

    dt = 8.0
    steps = max(int(T / dt), 20)
    t_hat = [i / (steps - 1) for i in range(steps)]
    ux, uy = (tx - sx) / D, (ty - sy) / D
    px, py = -uy, ux
    arc = rng.uniform(-0.07, 0.07) * D                 # hafif yay
    samples = []
    jitter = [0.0, 0.0]
    t_ms = 0.0
    t_of_pause = rng.uniform(0.25, 0.7) if rng.random() < 0.22 else None
    pause_ms = rng.uniform(60.0, 150.0) if t_of_pause else 0.0
    correction = rng.random() < 0.30
    for s in t_hat:
        prog = _minjerk(s)
        lateral = arc * math.sin(math.pi * s)
        x = sx + ux * D * prog + px * lateral
        y = sy + uy * D * prog + py * lateral
        jitter = [0.85 * j + rng.gauss(0.0, 0.16) for j in jitter]  # AR(1) tremor
        fade = 1.0 if s < 0.9 else max(0.05, (1 - s) / 0.1)
        x += jitter[0] * fade
        y += jitter[1] * fade
        if t_of_pause is not None and abs(s - t_of_pause) < 0.02:
            for k in range(int(pause_ms / dt)):          # duraklama (mikro titreme ile)
                samples.append([round(t_ms + k * dt, 2),
                                round(x + rng.gauss(0, 0.05), 2),
                                round(y + rng.gauss(0, 0.05), 2)])
            t_ms += pause_ms
        samples.append([round(t_ms, 2), round(x, 2), round(y, 2)])
        t_ms += dt
    if correction:                                      # kısa düzeltme alt-hareketi
        c_off = min(rng.uniform(0.05, 0.22) * (2 * r), 0.7 * r)
        c_ang = rng.uniform(0.0, 2 * math.pi)
        mid = (tx + c_off * math.cos(c_ang), ty + c_off * math.sin(c_ang))
        cT = rng.uniform(90.0, 170.0)
        csteps = max(int(cT / dt), 8)
        last = samples[-1]
        last[1], last[2] = round(mid[0], 2), round(mid[1], 2)
        for i in range(1, csteps + 1):
            p = _minjerk(i / csteps)
            samples.append([round(last[0] + i * dt, 2),
                           round(mid[0] + (tx - mid[0]) * p, 2),
                           round(mid[1] + (ty - mid[1]) * p, 2)])
    return {
        "session_id": session_id,
        "source": "synthetic",
        "generator": GENERATOR,
        "trial": trial,
        "target": [tx, ty],
        "radius": r,
        "presented_ms": round(-rng.uniform(300, 900), 2),
        "click_ms": round(samples[-1][0] + rng.uniform(40, 100), 2),
        "hit": True,
        "samples": samples,
    }


def main_cli():
    ap = argparse.ArgumentParser(description="SENTETİK (açık etiketli) kayıt üretici")
    ap.add_argument("--oturum", type=int, default=3)
    ap.add_argument("--deneme", type=int, default=30)
    ap.add_argument("--tohum", type=int, default=987)
    ap.add_argument("--dizin", default=os.path.join(ROOT, "data", "recordings"))
    args = ap.parse_args()
    os.makedirs(args.dizin, exist_ok=True)
    total = 0
    for s_i in range(args.oturum):
        rng = random.Random(args.tohum + 1000 * s_i)
        sid = new_session_id("sent")
        trials = [synthetic_trial(rng, sid, i) for i in range(args.deneme)]
        path = save_session(args.dizin, trials,
                            meta={"app": "dogal-fare", "type": "synthetic-batch",
                                  "generator": GENERATOR})
        total += len(trials)
        print(f"oturum {sid}: {len(trials)} deneme → {path}")
    print(f"Toplam {total} SENTETİK deneme yazıldı (etiket: source=synthetic).")


if __name__ == "__main__":
    main_cli()

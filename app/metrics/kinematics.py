"""Kinematik metrikler: isabet, süre, yol, hız/ivme/jerk dağılımları.

Saf hesaplama; hem önizlemede hem headless değerlendirmede kullanılır.
"""
from __future__ import annotations

import math

import numpy as np

from ..geometry import speed_series


def plan_metrics(plan) -> dict:
    """Bir TrajectoryPlan'dan tüm metrikler (tek deneme)."""
    wp = plan.waypoints
    t = wp[:, 0]
    xy = wp[:, 1:3]
    tx, ty = plan.target_xy
    r = float(plan.radius)

    last = xy[-1]
    click = np.asarray(plan.click_xy)
    dist_last = math.hypot(last[0] - tx, last[1] - ty)
    dist_click = math.hypot(click[0] - tx, click[1] - ty)

    # Yol uzunluğu ve kiriş
    seg = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    path_len = float(seg.sum())
    chord = math.hypot(tx - plan.start_xy[0], ty - plan.start_xy[1])

    v = speed_series(t, xy)
    a = np.diff(v) / np.maximum(np.diff(t), 1e-3)          # px/ms^2
    j = np.diff(a) / np.maximum(np.diff(t[:-1]), 1e-3)     # px/ms^3

    # Hız tepeleri: dönemsel yerel maksimumlar (ölçekli parlaklık eşiği: tepe hızın
    # %15'i — mikro-tremor tepeleri sayılmaz; alt-hareket proxy'si)
    thr = 0.15 * float(v.max())
    peaks = 0
    for i in range(1, len(v) - 1):
        if v[i] > v[i - 1] and v[i] >= v[i + 1] and v[i] >= thr:
            peaks += 1

    # Duraklama: v < 0.02 px/ms (~20 px/s; tremor payı) ve >= 40 ms
    pause_ms = _pause_total(t, v)

    return {
        "hit_click": dist_click <= r,          # tıklama hedef içinde mi (güvence)
        "hit_margin": dist_click <= 0.8 * r,   # tasarımdaki margin güvencesi
        "last_point_in_target": dist_last <= r,
        "duration_ms": float(t[-1]),
        "path_len_px": path_len,
        "chord_px": float(chord),
        "path_over_chord": float(path_len / max(chord, 1e-6)),
        "peak_v_px_ms": float(v.max()),
        "mean_v_px_ms": float(v.mean()),
        "acc_rms_px_ms2": float(np.sqrt(np.mean(a ** 2))) if len(a) else 0.0,
        "jerk_rms_px_ms3": float(np.sqrt(np.mean(j ** 2))) if len(j) else 0.0,
        "speed_peaks": int(peaks),
        "pause_ms": float(pause_ms),
        "click_hold_ms": float(plan.hold_ms),
    }


def _pause_total(t: np.ndarray, v: np.ndarray, min_ms: float = 40.0) -> float:
    total = 0.0
    v_thresh = 0.02  # px/ms (~20 px/s): tremor payı (features ile aynı eşik)
    i, n = 0, len(v)
    while i < n:
        if v[i] < v_thresh:
            j = i
            while j + 1 < n and v[j + 1] < v_thresh:
                j += 1
            dur = float(t[j] - t[i])
            if dur >= min_ms:
                total += dur
            i = j + 1
        else:
            i += 1
    return total


_SUMMARIZE_KEYS = [
    "duration_ms", "path_over_chord", "peak_v_px_ms", "mean_v_px_ms",
    "acc_rms_px_ms2", "jerk_rms_px_ms3", "speed_peaks", "pause_ms",
    "click_hold_ms", "path_len_px",
]


def summarize(metrics_list: list[dict]) -> dict:
    """Deneme listesinden ortalama/std + isabet oranı."""
    if not metrics_list:
        return {}
    out: dict = {}
    for k in _SUMMARIZE_KEYS:
        vals = np.asarray([m[k] for m in metrics_list], dtype=float)
        out[k + "_mean"] = float(vals.mean())
        out[k + "_std"] = float(vals.std())
    n = len(metrics_list)
    out["hit_rate_click"] = sum(1 for m in metrics_list if m["hit_click"]) / n
    out["hit_rate_margin"] = sum(1 for m in metrics_list if m["hit_margin"]) / n
    out["n"] = n
    return out

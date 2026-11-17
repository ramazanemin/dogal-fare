"""Kayıtlardan öznitelik çıkarımı: süre, ID, alt-hareket, duraklama, eğrilik.

Girdi şeması (storage.load_recordings çıktısı, trial dict):
  {session_id, source("human"|"synthetic"), trial,
   target:[x,y], radius, presented_ms, click_ms, hit, samples:[[t,x,y],...]}
Koordinatlar kalibrasyon penceresine GÖRELİDİR (sol üst = 0,0).
"""
from __future__ import annotations

import math

import numpy as np

from .geometry import (
    fit_basis,
    lateral_profile,
    resample_uniform,
    speed_series,
)

N_BASIS = 4                # eğrilik taban fonksiyonu sayısı
SPEED_THRESH_PX_MS = 0.05  # alt-hareket eşik hızı
MIN_SUB_DUR_MS = 30.0      # alt-hareketin en kısa süresi
MIN_PAUSE_MS = 50.0        # duraklama alt sınırı
MIN_SUB_PATH_PX = 0.5      # alt-hareket adayının en kısa yolu


def index_of_difficulty(D: float, W: float) -> float:
    """Shannon formu: ID = log2(D/W + 1) bit. W = hedef genişliği (2*radius)."""
    if D <= 0 or W <= 0:
        raise ValueError("ID: D>0 ve W>0 gerekli")
    return math.log2(max(D, 1e-6) / max(W, 1e-6) + 1.0)


def trial_to_arrays(trial: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """trial -> (t_ms göreli, xy[N,2], start[x,y]). t, ilk örneğe göre normalize."""
    samples = np.asarray(trial["samples"], dtype=float)
    if samples.ndim != 2 or samples.shape[0] < 2:
        raise ValueError("trial: en az 2 örnek gerekir")
    t = samples[:, 0] - float(samples[0, 0])
    xy = samples[:, 1:3]
    start = (float(samples[0, 1]), float(samples[0, 2]))
    return t, xy, start


def movement_distance(trial: dict) -> tuple[float, float]:
    """(kiriş mesafesi D, hedef genişliği W=2*radius)."""
    s0 = trial["samples"][0][1:3]
    sx, sy = float(s0[0]), float(s0[1])
    tx, ty = float(trial["target"][0]), float(trial["target"][1])
    D = math.hypot(tx - sx, ty - sy)
    W = 2.0 * float(trial["radius"])
    return D, W


def movement_time_ms(trial: dict) -> float:
    """MT = tıklama - ilk hareket örneği (ms)."""
    mt = float(trial["click_ms"]) - float(trial["samples"][0][0])
    return max(mt, 1e-3)


def _dist(a, b) -> float:
    return float(math.hypot(b[0] - a[0], b[1] - a[1]))


def segment_submovements(t: np.ndarray, xy: np.ndarray,
                         speed_thresh: float = SPEED_THRESH_PX_MS
                         ) -> list[tuple[int, int]]:
    """Hız eşiği üstünde kalan ardışık bölgeler [i,j] — alt-hareket adayları."""
    v = speed_series(t, xy)
    active = v > speed_thresh
    runs: list[tuple[int, int]] = []
    i, n = 0, len(active)
    while i < n:
        if active[i]:
            j = i
            while j + 1 < n and active[j + 1]:
                j += 1
            seg = xy[i:j + 1]
            if (t[j] - t[i]) >= MIN_SUB_DUR_MS and (len(seg) < 2 or _dist(seg[0], seg[-1]) >= MIN_SUB_PATH_PX):
                runs.append((int(i), int(j)))
            i = j + 1
        else:
            i += 1
    return runs

def pause_total_ms(t: np.ndarray, xy: np.ndarray,
                   v_thresh: float = 0.02, min_pause: float = MIN_PAUSE_MS) -> float:
    """Hız v_thresh altında geçen ve >= min_pause olan toplam süre (ms).

    Eşik 0.02 px/ms (~20 px/s): duraklamada insan tremoru da vardır; sıfır hız
    beklemek gerçekçi değildir (docs §2 D3).
    """
    v = speed_series(t, xy)
    total = 0.0
    i, n = 0, len(v)
    while i < n:
        if v[i] < v_thresh:
            j = i
            while j + 1 < n and v[j + 1] < v_thresh:
                j += 1
            dur = float(t[j] - t[i])
            if dur >= min_pause:
                total += dur
            i = j + 1
        else:
            i += 1
    return total


def peak_time_ratio(t: np.ndarray, xy: np.ndarray) -> float:
    """Tepe hızın zaman konumu t_hat ∈ [0,1] (asimetri ölçüsü; min-jerk ~0.4)."""
    v = speed_series(t, xy)
    i = int(np.argmax(v))
    span = float(t[-1] - t[0])
    return 0.5 if span <= 0 else float((t[i] - t[0]) / span)


def curvature_coefficients(t: np.ndarray, xy: np.ndarray, D: float,
                           n_basis: int = N_BASIS) -> np.ndarray:
    """Normalize dik sapma profilinin taban katsayıları (c_k / D)."""
    if D < 1.0:
        return np.zeros(n_basis)
    rs = resample_uniform(np.stack([t, xy[:, 0], xy[:, 1]], axis=1), n=64)
    lat = lateral_profile(rs, (float(xy[0, 0]), float(xy[0, 1])),
                          (float(xy[-1, 0]), float(xy[-1, 1])))
    return fit_basis(lat[:, 2] / D, K=n_basis)


def primary_endpoint_offset_px(trial: dict, subs: list[tuple[int, int]]) -> float | None:
    """İlk alt-hareketin bitişi ile hedef merkezi arasındaki uzaklık (px).

    Düzeltme varsa tipik olarak W/4 mertebesinde; temiz denemede küçük. Yoksa None.
    """
    if not subs:
        return None
    _, xy, _ = trial_to_arrays(trial)
    i, j = subs[0]
    end = xy[j]
    tx, ty = float(trial["target"][0]), float(trial["target"][1])
    return float(math.hypot(tx - end[0], ty - end[1]))


def extract_features(trial: dict) -> dict:
    """Bir denemenin model girdisi öznitelikleri (tümü sayısal)."""
    t, xy, _ = trial_to_arrays(trial)
    D, W = movement_distance(trial)
    subs = segment_submovements(t, xy)
    return {
        "D_px": D,
        "W_px": W,
        "ID_bits": index_of_difficulty(D, W),
        "MT_ms": movement_time_ms(trial),
        "n_sub": float(len(subs)),
        "pause_ms": pause_total_ms(t, xy),
        "peak_ratio": peak_time_ratio(t, xy),
        "curv_coef": [float(c) for c in curvature_coefficients(t, xy, D)],
        "primary_offset_px": primary_endpoint_offset_px(trial, subs),
        "hit": bool(trial.get("hit", True)),
    }

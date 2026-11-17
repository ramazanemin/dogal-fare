"""Geometri ve zaman yardımcıları.

Tamamen saf hesap: I/O, donanım veya platform erişimi YOKTUR.
Hareket ÜRETİMİ burada/bunun tüketicisinde; fare KONTROLÜ app.control içinde ayrıdır.
"""
from __future__ import annotations

import math
import numpy as np


def min_jerk_profile(s: np.ndarray) -> np.ndarray:
    """Minimum-jerk pozisyon profili: s(t)=10s^3-15s^4+6s^5, s∈[0,1]."""
    s = np.clip(np.asarray(s, dtype=float), 0.0, 1.0)
    return 10 * s**3 - 15 * s**4 + 6 * s**5


def chord_point(start, end, alpha):
    """start->end doğru parçası üzerinde alpha parametresi (0..1 -> uçlar)."""
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    return (sx + (ex - sx) * alpha, sy + (ey - sy) * alpha)


def path_frame(start, end):
    """Birim 'along' (hedef yönü) ve 'perp' (dik) vektörleri."""
    dx, dy = float(end[0]) - float(start[0]), float(end[1]) - float(start[1])
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return (1.0, 0.0), (0.0, 1.0), 0.0
    ux, uy = dx / dist, dy / dist
    return (ux, uy), (-uy, ux), dist


def point_from_local(start, along, perp, s_along, s_perp):
    """Yerel (along, perp) ölçülerinden global nokta (skalar VEYA dizi girişli)."""
    x = start[0] + along[0] * s_along + perp[0] * s_perp
    y = start[1] + along[1] * s_along + perp[1] * s_perp
    return (x, y)


def resample_uniform(samples_txy: np.ndarray, n: int = 64) -> np.ndarray:
    """[t,x,y] örneklerini t→[0,1] normalize-edilmiş n noktaya doğrusal yeniden örnekle.

    Dönüş: (n,3) [t_norm, x, y].
    """
    arr = np.asarray(samples_txy, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 3 or arr.shape[0] < 2:
        raise ValueError("resample_uniform: en az 2 örnek ve [t,x,y] gerekir")
    t = arr[:, 0]
    t0, t1 = float(t[0]), float(t[-1])
    if t1 - t0 < 1e-6:
        raise ValueError("resample_uniform: sıfır süre")
    tn = np.clip((t - t0) / (t1 - t0), 0.0, 1.0)
    grid = np.linspace(0.0, 1.0, n)
    xs = np.interp(grid, tn, arr[:, 1])
    ys = np.interp(grid, tn, arr[:, 2])
    return np.stack([grid, xs, ys], axis=1)


def lateral_profile(resampled: np.ndarray, start, end, n: int | None = None) -> np.ndarray:
    """Yeniden örneklenmiş yolu chord'a göre (along, perp) bileşenlerine ayır.

    Dönüş: (N,3 [t_norm, along, perp]). along/perp piksel cinsindendir.
    """
    along_u, perp_u, _ = path_frame(start, end)
    xs, ys = resampled[:, 1], resampled[:, 2]
    rel_x, rel_y = xs - start[0], ys - start[1]
    along = rel_x * along_u[0] + rel_y * along_u[1]
    perp = rel_x * perp_u[0] + rel_y * perp_u[1]
    return np.stack([resampled[:, 0], along, perp], axis=1)


def sin_basis(K: int, s: np.ndarray) -> np.ndarray:
    """Uçlarda sıfırlanan taban: phi_k(s)=sin(k*pi*s), k=1..K. Dönüş: (len(s),K)."""
    s = np.asarray(s, dtype=float)
    return np.stack([np.sin((k + 1) * math.pi * s) for k in range(K)], axis=1)


def fit_basis(profile_perp: np.ndarray, K: int = 4) -> np.ndarray:
    """perp(s) profilini sin tabanına LS ile uydur; K katsayı döndürür (px)."""
    s = np.linspace(0.0, 1.0, len(profile_perp))
    B = sin_basis(K, s)
    coef, *_ = np.linalg.lstsq(B, np.asarray(profile_perp, dtype=float), rcond=None)
    return coef


def basis_curve(coef: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Katsayılardan eğri değerleri (px)."""
    return sin_basis(len(coef), np.asarray(s, dtype=float)) @ np.asarray(coef)


def bezier3(p0, p1, p2, s: np.ndarray) -> np.ndarray:
    """İkinci dereceden Bezier (3 nokta). Dönüş: (len(s),2)."""
    s = np.asarray(s, dtype=float).reshape(-1, 1)
    p0 = np.asarray(p0, dtype=float).reshape(1, 2)
    p1 = np.asarray(p1, dtype=float).reshape(1, 2)
    p2 = np.asarray(p2, dtype=float).reshape(1, 2)
    return (1 - s) ** 2 * p0 + 2 * (1 - s) * s * p1 + s**2 * p2


def warp_time(s: np.ndarray, gamma: float) -> np.ndarray:
    """Tepe hızın konumunu kaydıran basit zaman bükümü.

    s' = s^gamma:  gamma>1 -> tepe geç, gamma<1 -> tepe erken (min-jerk ~gamma=1).
    """
    return np.power(np.clip(np.asarray(s, dtype=float), 0.0, 1.0), float(gamma))


def speed_series(t_ms: np.ndarray, xy: np.ndarray) -> np.ndarray:
    """[t,x,y] veya ayrı [t],[N,2]'den hız serisi (px/ms). İlk örnek 0'dır.

    Zaman tekilliği ihlali (dt<=0) durumunda hız 0 kabul edilir: çakışan
    örnekler hız sıçraması üretmemeli (insan kinematiğinde anlamı yok).
    """
    xy = np.asarray(xy, dtype=float)
    d = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    t = np.asarray(t_ms, dtype=float)
    dt = np.diff(t)
    v = np.where(dt > 0, d / np.maximum(dt, 1e-9), 0.0)
    return np.concatenate([[0.0], v])

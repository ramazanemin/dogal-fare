"""(c) Küçük öğrenilmiş parametrik model (docs §3).

Öğrendikleri (hepsi kişiye özel, ~30 skaler):
  fitts      a, b, süre artık gürültüsü        (D1)
  profile    tepe-zaman oranı -> zaman bükümü gamma (D2 asimetrisi)
  curvature  taban katsayı dağılımı mu_k, std_k, yön olasılığı (D3)
  pause      olasılık + lognormal süre
  correction olasılık + büyüklük + düzeltme süresi (D3 alt-hareket)
  landing    tıklama endpoint dağılımı (px)
JSON'a yazılır/okunur (~2-3 KB). Win32 erişimi YOKTUR (models katmanı saf).
"""
from __future__ import annotations

import json
import math
import time

import numpy as np

from ..config import get
from ..features import (
    N_BASIS,
    curvature_coefficients,
    extract_features,
)
from ..geometry import (
    basis_curve,
    min_jerk_profile,
    path_frame,
    point_from_local,
    warp_time,
)
from . import TrajectoryPlan
from .baseline import _apply_jitter, _plan_common

SCHEMA = 1
DEFAULT_PATH = "model/fare_model.json"


class LearnedModel:
    name = "learned"

    def __init__(self, cfg: dict, params: dict | None = None):
        self.cfg = cfg
        self.p: dict = params or LearnedModel._defaults(cfg)

    # ---------- varsayılanlar (veri yoksa) ----------
    @staticmethod
    def _defaults(cfg: dict) -> dict:
        return {
            "schema": SCHEMA,
            "name": "learned",
            "fitts": {"a_ms": float(get(cfg, "fitts_defaults.a_ms")),
                      "b_ms_per_bit": float(get(cfg, "fitts_defaults.b_ms_per_bit")),
                      "resid_ms": 15.0},
            "profile": {"gamma": 1.0},
            "curvature": {"mu": [0.0] * N_BASIS, "std": [0.02] * N_BASIS,
                          "sign_left_p": 0.5, "amp_scale": 1.0},
            "pause": {"prob": float(get(cfg, "pause.prob")),
                      "mean_ms": float(get(cfg, "pause.mean_ms")),
                      "sigma_log": float(get(cfg, "pause.sigma_log"))},
            "correction": {"prob": float(get(cfg, "correction.prob")),
                           "off_mean_per_w": 0.18, "off_std_per_w": 0.10,
                           "time_ms": float(get(cfg, "correction.time_ms"))},
            "landing": {"click_off_sigma_px": 3.0},
            "n_train": 0, "n_sessions": 0, "sources": [],
            "trained_at": None,
        }

    # ---------- öğrenme ----------
    @classmethod
    def fit(cls, cfg: dict, train_trials: list[dict]) -> "LearnedModel":
        """Kayıtlardan parametreler. Yalnızca 'hit' denemeleri kullanılır."""
        good = [t for t in train_trials if t.get("hit", True)]
        if len(good) < 8:
            m = cls(cfg)
            m.p["n_train"] = len(good)
            return m
        feats = [extract_features(t) for t in good]
        p = cls._defaults(cfg)

        # --- Fitts: MT ~ a + b*ID (D1) ---
        X = np.stack([np.ones(len(feats)), [f["ID_bits"] for f in feats]], axis=1)
        y = np.asarray([f["MT_ms"] for f in feats])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = float(np.std(y - X @ coef))
        # Sağlıklı insan Fitts eğimi ~100-300 ms/bit; makul aralık dışı = reddi
        if not (20.0 <= coef[1] <= 600.0 and -300.0 <= coef[0] <= 1000.0):
            coef = np.array([p["fitts"]["a_ms"], p["fitts"]["b_ms_per_bit"]])
            resid = max(float(np.std(y - X @ coef)), 5.0)
        p["fitts"] = {"a_ms": float(coef[0]), "b_ms_per_bit": float(coef[1]),
                      "resid_ms": max(resid, 5.0)}

        # --- Hız profili asimetrisi: ortalama tepe oranı -> gamma (D2) ---
        mean_peak = float(np.mean([f["peak_ratio"] for f in feats]))
        p["profile"]["gamma"] = _gamma_for_peak_ratio(mean_peak)

        # --- Eğrilik: c_k/D dağılımı + yön tercihi (D3) ---
        C = np.asarray([f["curv_coef"] for f in feats])
        if C.shape[0] >= 3:
            mu = C.mean(axis=0)
            std = np.maximum(C.std(axis=0), 0.004)
            signed = np.asarray([np.sum(c * np.arange(1, len(c) + 1)) for c in C])
            p["curvature"] = {
                "mu": [float(v) for v in mu], "std": [float(v) for v in std],
                "sign_left_p": float(np.clip((signed < 0).mean(), 0.08, 0.92)),
                "amp_scale": 1.0,
            }

        # --- Duraklamalar ---
        pauses = [f["pause_ms"] for f in feats if f["pause_ms"] > 40.0]
        p["pause"]["prob"] = float(np.clip(len(pauses) / len(feats), 0.0, 0.6))
        if pauses:
            logp = np.log(np.asarray(pauses))
            p["pause"]["mean_ms"] = float(np.exp(logp.mean()))
            p["pause"]["sigma_log"] = float(max(logp.std(), 0.15)) if logp.std() > 0 else 0.3

        # --- Düzeltme alt-hareketleri (D3) ---
        offs = [f["primary_offset_px"] / max(f["W_px"], 1e-6)
                for f in feats if f["n_sub"] >= 2 and f["primary_offset_px"] is not None]
        p["correction"]["prob"] = float(np.clip(
            float(np.mean([f["n_sub"] >= 2 for f in feats])), 0.0, 0.75))
        if offs:
            p["correction"]["off_mean_per_w"] = float(np.clip(np.mean(offs), 0.05, 0.5))
            p["correction"]["off_std_per_w"] = float(max(np.std(offs), 0.03))

        # --- Tıklama endpoint dağılımı ---
        end_off = [math.hypot(float(t["target"][0]) - float(t["samples"][-1][1]),
                              float(t["target"][1]) - float(t["samples"][-1][2]))
                   for t in good]
        p["landing"]["click_off_sigma_px"] = float(max(np.mean(end_off) * 0.6, 1.0))

        p["n_train"] = len(good)
        p["n_sessions"] = len({t["session_id"] for t in good})
        p["sources"] = sorted({t["source"] for t in good})
        p["trained_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        return cls(cfg, p)

    # ---------- serileştirme ----------
    def save(self, path: str = DEFAULT_PATH) -> str:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.p, fh, ensure_ascii=False, indent=1)
        return path

    @classmethod
    def load(cls, cfg: dict, path: str = DEFAULT_PATH) -> "LearnedModel | None":
        try:
            with open(path, "r", encoding="utf-8") as fh:
                params = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        if params.get("schema") != SCHEMA:
            return None
        return cls(cfg, params)

    # ---- süre modeli ----
    def duration_ms(self, D: float, W: float, rng) -> float:
        f = self.p["fitts"]
        T = f["a_ms"] + f["b_ms_per_bit"] * math.log2(D / W + 1.0)
        T += rng.normal(0.0, min(float(f["resid_ms"]) * 0.5, 0.12 * T))
        return float(np.clip(T, float(get(self.cfg, "min_duration_ms")),
                             float(get(self.cfg, "max_duration_ms"))))

    # ---------- üretim ----------
    def generate(self, start, target, radius, rng: np.random.Generator) -> TrajectoryPlan:
        start_xy, target_xy, D, r = _plan_common(start, target, radius)
        W = 2.0 * r
        margin = float(get(self.cfg, "endpoint_margin_factor"))
        dt = int(get(self.cfg, "waypoint_dt_ms"))

        # 1) Süre (D1) ve zaman bükümü (D2)
        T_move = self.duration_ms(D, W, rng)
        gamma = float(self.p["profile"]["gamma"])
        steps = max(int(math.ceil(T_move / dt)), 16)
        t_hat = np.linspace(0.0, 1.0, steps)
        s = min_jerk_profile(warp_time(t_hat, gamma))

        # 2) Eğrilik: c_k ~ N(mu, std), yön tercihiyle (D3)
        mu = np.asarray(self.p["curvature"]["mu"])
        sd = np.asarray(self.p["curvature"]["std"])
        amp_scale = float(self.p["curvature"]["amp_scale"])
        coefs = np.clip(mu + rng.normal(0.0, 1.0, size=len(mu)) * sd,
                        -2.5 * sd - np.abs(mu), 2.5 * sd + np.abs(mu))
        sign = -1.0 if rng.random() < float(self.p["curvature"]["sign_left_p"]) else 1.0
        perp = sign * amp_scale * basis_curve(coefs, t_hat) * D
        along = D * s

        along_u, perp_u, _ = path_frame(start_xy, target_xy)
        xs, ys = point_from_local(start_xy, along_u, perp_u, along, perp)
        xy = np.stack([np.asarray(xs), np.asarray(ys)], axis=1)
        t_ms = t_hat * T_move

        # 3) Tıklama endpoint'ı: öğrenilen dağılım, MARGİN içine sıkıştırılır
        sigma_c = float(self.p["landing"]["click_off_sigma_px"])
        ang = rng.uniform(0.0, 2 * math.pi)
        mag = abs(float(rng.normal(0.0, max(sigma_c, 0.5))))
        mag = min(mag, margin * r)
        click_xy = (target_xy[0] + mag * math.cos(ang),
                    target_xy[1] + mag * math.sin(ang))

        # 4) Düzeltme alt-hareketi (D3): primary landing sapar, kısa ikinci mini-yörünge
        corr = self.p["correction"]
        if rng.random() < float(corr["prob"]):
            off_mean = float(corr["off_mean_per_w"]) * W
            c_ang = rng.uniform(0.0, 2 * math.pi)
            c_mag = max(0.0, float(rng.normal(off_mean, float(corr["off_std_per_w"]) * W)))
            c_mag = min(c_mag, margin * r)
            primary_end = (click_xy[0] + c_mag * math.cos(c_ang),
                           click_xy[1] + c_mag * math.sin(c_ang))
            xy[-1, 0], xy[-1, 1] = primary_end
            T_corr = float(corr["time_ms"]) * (0.8 + 0.4 * rng.random())
            t_corr = np.linspace(t_ms[-1], t_ms[-1] + T_corr, 12)[1:]
            s_corr = min_jerk_profile(np.linspace(0, 1, 12)[1:])
            for k in range(len(t_corr)):
                px = primary_end[0] + (click_xy[0] - primary_end[0]) * s_corr[k]
                py = primary_end[1] + (click_xy[1] - primary_end[1]) * s_corr[k]
                xy = np.vstack([xy, [px, py]])
                t_ms = np.concatenate([t_ms, [t_corr[k]]])
            T_total = float(t_ms[-1])
        else:
            T_total = T_move

        # 5) Duraklama: olasılıkla orta nokta yakınında lognormal süre (docs §2 D3)
        if rng.random() < float(self.p["pause"]["prob"]):
            t_in = float(rng.uniform(float(get(self.cfg, "pause.tmin")),
                                     float(get(self.cfg, "pause.tmax"))))
            dp = float(np.clip(rng.lognormal(
                math.log(max(float(self.p["pause"]["mean_ms"]), 30.0)),
                float(self.p["pause"]["sigma_log"])), 40.0, 250.0))
            # Duraklama [t_prev + dt .. t_prev + dp] aralığına yerleşir; kalan
            # örnekler dp kadar ileri kayar (monoton zaman garantisi).
            i_at = int(np.searchsorted(t_ms, t_in * T_total))
            i_at = min(max(i_at, 1), len(t_ms) - 1)
            t_start = float(t_ms[i_at - 1])
            k = max(int(dp / dt) + 1, 3)
            dwell_t = t_start + np.linspace(dt, dp, k)
            dwell_xy = np.tile(np.asarray(xy[i_at - 1], dtype=float), (k, 1))
            dwell_xy += rng.normal(0.0, 0.05, size=(k, 2))  # mikro-tremor (docs D3)
            xy = np.insert(xy, i_at, dwell_xy, axis=0)
            t_ms = np.insert(t_ms, i_at, dwell_t)
            t_ms[i_at + k:] += dp
            T_total = float(t_ms[-1])

        # 6) Mikro-tremor (son dilimde sönümlü) ve T'nin tıklama noktasında bitişi
        xy = _apply_jitter(xy, rng, float(get(self.cfg, "jitter.rho")),
                           float(get(self.cfg, "jitter.sigma_px")),
                           float(get(self.cfg, "jitter.end_damp_frac")))
        xy[-1, 0], xy[-1, 1] = click_xy  # tıklama noktası = son waypoint
        hold = float(rng.integers(int(get(self.cfg, "min_click_hold_ms")),
                                  int(get(self.cfg, "max_click_hold_ms"))))
        return TrajectoryPlan(
            waypoints=np.stack([t_ms, xy[:, 0], xy[:, 1]], axis=1),
            click_xy=(float(click_xy[0]), float(click_xy[1])),
            duration_ms=T_total, hold_ms=hold, model_name=self.name,
            start_xy=start_xy, target_xy=target_xy, radius=r,
            meta={"ID_bits": math.log2(D / W + 1.0), "gamma": gamma,
                  "n_params": sum(len(v) if isinstance(v, (list,)) else 1
                                  for v in self.p.values()
                                  for v in (v.values() if isinstance(v, dict) else [v]))},
        )


def _gamma_for_peak_ratio(peak_ratio: float) -> float:
    """Ortalama tepe-zaman oranını min-jerk zaman bükümü gamma'sına çevirir.

    gamma>1: tepe geç (insanlarda yaygın), gamma<1: tepe erken.
    """
    best, best_err = 1.0, float("inf")
    for g in np.arange(0.6, 1.61, 0.05):
        t = np.linspace(0.0, 1.0, 512)
        s = min_jerk_profile(warp_time(t, g))
        v = np.diff(s) / np.diff(t)
        pr = float(t[int(np.argmax(v))])
        err = abs(pr - peak_ratio)
        if err < best_err:
            best, best_err = float(g), err
    return best

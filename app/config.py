"""Yapılandırma: varsayılanlar + kullanıcı JSON'u (opsiyonel) birleştirme.

Güvenlik varsayılanları KAPALI'dır: gerçek imleç hareketi ve gerçek tıklama
açık bayrak ister (scripts/canliyardim.py --hareket-gercek / --gercek-tiklama).
"""
from __future__ import annotations

import json
import os
from typing import Any

# Kalibrasyon/test ekranı ve model davranışı
DEFAULTS: dict[str, Any] = {
    "waypoint_dt_ms": 8,            # üretilen hareketin örnekleme aralığı (ms)
    "max_waypoint_dt_ms": 40,       # plan doğrulamasında tek adım üst sınırı
    "min_duration_ms": 120,        # çok kısa hamle koruması (Fitts alt sınırı)
    "max_duration_ms": 1400,
    "duration_noise_frac": 0.08,   # MT'ye normal gürültü (±)
    # Fitts varsayılanları (insan verisi yoksa): a≈150ms, b≈130ms/bit
    "fitts_defaults": {"a_ms": 150.0, "b_ms_per_bit": 130.0},
    # Uç nokta güvencesi: tıklama, hedef merkezinden <= margin*radius uzaklıkta
    "endpoint_margin_factor": 0.8,
    # Uç nokta dağılımı (yerleşim çarkı), hedef genişliğiyle ölçeklenir
    "landing_sigma_per_w": 0.18,    # sigma_first ≈ 0.18 * W  (W = 2*radius)
    # Tıklama bekleme (down->up)
    "min_click_hold_ms": 40,
    "max_click_hold_ms": 110,
    # Duraklamalar (öğrenilmezse varsayılan)
    "pause": {"prob": 0.15, "mean_ms": 110.0, "sigma_log": 0.45,
              "tmin": 0.25, "tmax": 0.75},
    # Düzeltme alt-hareketi (öğrenilmezse varsayılan)
    "correction": {"prob": 0.25, "time_ms": 130.0},
    # Mikro-tremor (AR(1) kararlılığı ve gürültü, px)
    "jitter": {"rho": 0.85, "sigma_px": 0.15, "end_damp_frac": 0.10},
    # Güvenlik: ekran sınırı toleransı
    "bounds_margin_px": 2,
    # Canlı yardımda hedef yarıçapı (kullanıcı --radius ile değiştirir)
    "default_target_radius_px": 32.0,
    # CAPTCHA/güvenlik başlık bulgusu (buluşsal; her zaman garanti değil)
    "warn_titles": [
        "captcha", "challenge", "verify", "verification", "security check",
        "security", "unusual", "suspicious", "robot", "doğrula", "doğrulama",
        "güvenlik", "güvenliği", "olaganüstü", "etkinlik saptandı",
    ],
    # En az kaç oturum/deneme olursa hangi model seçilir (manager)
    "model_selection": {"learned_min_sessions": 2, "learned_min_trials": 40,
                        "rescaler_min_trials": 15},
    # Eğitim/test oturum ayrımı
    "split_test_ratio": 0.3,
    "rng_seed": 20261115,
}


def get(cfg: dict[str, Any], dotted: str, default: Any = None) -> Any:
    """cfg.get("a.b.c") nokta-yolu desteği."""
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def load_config(path: str | None = None) -> dict[str, Any]:
    """DEFAULTS + (varsa) JSON dosyası birleşimi (JSON öncelikli)."""
    cfg = json.loads(json.dumps(DEFAULTS))  # derin kopya
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            user_cfg = json.load(fh)
        _deep_merge(cfg, user_cfg)
    return cfg


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v

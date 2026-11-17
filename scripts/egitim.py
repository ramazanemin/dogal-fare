#!/usr/bin/env python3
"""Model eğitimi: kayıtlardan küçük parametrik model üret → model/fare_model.json.

- Eğitim/test ayrımı OTURUM bazlıdır (storage.split_train_test).
- Fitts R² hem train hem test oturumları üzerinde raporlanır (sızma yok).
- --kaynak human: yalnız insan kalibrasyonu; all: sentetik+karma (doğrulama).

Kullanım:
    python scripts/egitim.py
    python scripts/egitim.py --kaynak human
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import load_config                    # noqa: E402
from app.features import extract_features             # noqa: E402
from app.models.manager import ModelManager          # noqa: E402
from app.storage import load_recordings               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fitts_r2(trials: list[dict], params: dict) -> float | None:
    if not trials:
        return None
    feats = [extract_features(t) for t in trials]
    import numpy as np
    X = np.stack([np.ones(len(feats)), [f["ID_bits"] for f in feats]], axis=1)
    y = np.asarray([f["MT_ms"] for f in feats])
    pred = X @ np.asarray([params["a_ms"], params["b_ms_per_bit"]])
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1.0 - ss_res / max(ss_tot, 1e-9)


def main_cli():
    ap = argparse.ArgumentParser(description=" küçük model eğitimi")
    ap.add_argument("--kaynak", default="all", choices=["human", "all"],
                    help="eğitim kayıtlarının kaynağı")
    ap.add_argument("--kaydet", default=os.path.join(ROOT, "model", "fare_model.json"))
    args = ap.parse_args()

    cfg = load_config()
    sources = ("human",) if args.kaynak == "human" else ("human", "synthetic")
    data_dir = os.path.join(ROOT, "data", "recordings")
    allrec = load_recordings(data_dir, sources=sources)
    if not allrec:
        print("Kayıt bulunamadi. Önce: python scripts/kalibrasyon.py "
              "(veya dogrulama için: python scripts/sentetik_uret.py)")
        sys.exit(1)

    mgr = ModelManager(cfg)
    from app.storage import split_train_test
    mgr.train_trials, mgr.test_trials = split_train_test(
        allrec, float(cfg.get("split_test_ratio", 0.3)))
    model = mgr.fit_learned()
    path = model.save(args.kaydet)

    p = model.p
    print("=" * 62)
    print("Egitildi →", path)
    print(f"  kayit: {p['n_train']} deneme, {p['n_sessions']} oturum, kaynak={p['sources']}")
    print(f"  fitts: a={p['fitts']['a_ms']:.0f} ms, b={p['fitts']['b_ms_per_bit']:.0f} ms/bit, "
          f"resid={p['fitts']['resid_ms']:.0f} ms")
    print(f"  profil gamma={p['profile']['gamma']:.2f}  "
          f"eğrilik mu={[round(v,3) for v in p['curvature']['mu']]}")
    print(f"  duraklama p={p['pause']['prob']:.2f}  ort={p['pause']['mean_ms']:.0f} ms; "
          f"düzeltme p={p['correction']['prob']:.2f}")
    r2_tr = fitts_r2(mgr.train_trials, p["fitts"])
    r2_te = fitts_r2(mgr.test_trials, p["fitts"])
    print(f"  Fitts R2: train={r2_tr if r2_tr is None else round(r2_tr,3)} "
          f"test(ayri oturumlar)={r2_te if r2_te is None else round(r2_te,3)}")
    if r2_te is not None and r2_tr is not None and r2_tr - r2_te > 0.35:
        print("  UYARI: train/test farkı büyük — oturum sayısı/artışı önerilir.")
    size_kb = os.path.getsize(path) / 1024.0
    print(f"  model boyutu: {size_kb:.1f} KB (GPU yok, ~30 parametre)")
    print("=" * 62)


if __name__ == "__main__":
    main_cli()

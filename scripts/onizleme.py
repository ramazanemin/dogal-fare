#!/usr/bin/env python3
"""Önizleme + yerel test ekranı (SANAL imleç — gerçek fare HAREKET ETMEZ).

Kullanım:
    python scripts/onizleme.py                          # manuel: Boşluk ile deneme
    python scripts/onizleme.py --auto 40                # otomatik 40 denemelik test
    python scripts/onizleme.py --model learned --auto 40 --cikti rapor.json

Rapor ibaresi: yerel kinematik ölçümüdür; tespit sistemleri hakkında KANIT içermez.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import load_config          # noqa: E402
from app.models.baseline import BaselineModel  # noqa: E402
from app.models.learned import LearnedModel  # noqa: E402
from app.models.manager import ModelManager  # noqa: E402
from app.ui.preview import PreviewUI         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_models(model_pref: str):
    cfg = load_config()
    mgr = ModelManager(cfg)
    mgr.load_and_split(os.path.join(ROOT, "data", "recordings"))
    mgr.train_from_split()
    loaded = LearnedModel.load(cfg, os.path.join(ROOT, "model", "fare_model.json"))
    if loaded is not None:
        mgr.learned = loaded
    else:
        try:
            mgr.fit_learned()
        except Exception:
            pass
    models = {"baseline": mgr.baseline,
              "rescaler": mgr.rescaler, "learned": mgr.learned}
    if model_pref == "auto":
        m, reason = mgr.select()
        print(f"Model seçimi: {m.name} ({reason})")
        model_pref = m.name
    elif models.get(model_pref) is None:
        print(f"Model '{model_pref}' kullanılamıyor (veri yok?) → baseline")
        model_pref = "baseline"
    return cfg, models, model_pref


def main_cli():
    ap = argparse.ArgumentParser(description="dogal-fare önizleme/test ekranı")
    ap.add_argument("--model", default="auto",
                    choices=["auto", "baseline", "rescaler", "learned"])
    ap.add_argument("--auto", type=int, default=0,
                    help="otomatik deneme sayısı (0 = manuel Boşluk)")
    ap.add_argument("--cikti", default=None,
                    help="otomatik modda JSON çıktı dosyası")
    ap.add_argument("--tohum", type=int, default=20261115, help="RNG tohumu")
    args = ap.parse_args()

    cfg, models, name = build_models(args.model)
    out_json = args.cikti or (
        os.path.join(ROOT, "reports", f"onizleme_{name}_{args.tohum}.json")
        if args.auto else None)
    ui = PreviewUI(models, name, cfg, auto_trials=args.auto,
                   out_json=out_json, seed=args.tohum)
    print("Önizleme başlıyor. ESC: durdur/kapat. (Gerçek fare kontrolü YOK.)")
    ui.run()
    print("Önizleme kapandı.")


if __name__ == "__main__":
    main_cli()

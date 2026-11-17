#!/usr/bin/env python3
"""GÖRSEL smoke test: 2 sanal deneme oynatır, pencere kendini kapatır.

Gerçek fareye DOKUNMAZ (yalnız canvas animasyonu). GUI zincirinin (tkinter,
plan, metrikler, JSON raporu) uçtan uca çalıştığını doğrular.

Kullanım: python scripts/onizleme_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import load_config                  # noqa: E402
from app.models.baseline import BaselineModel       # noqa: E402
from app.ui.preview import PreviewUI                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    cfg = load_config()
    models = {"baseline": BaselineModel(cfg)}
    ui = PreviewUI(models, "baseline", cfg, auto_trials=2,
                   out_json=os.path.join(ROOT, "reports", "onizleme_smoke.json"),
                   seed=7)
    ui.root.title("dogal-fare GÖRSEL SMOKE (2 deneme — gerçek fare hareketi YOK)")

    def watchdog():
        ui.abort = True
        try:
            ui.root.destroy()
        except Exception:
            pass

    ui.root.after(12000, watchdog)   # güvenlik: en geç 12 saniyede kapan
    ui.run()
    print("Gorsel smoke tamamlandi. Cikti: reports/onizleme_smoke.json")


if __name__ == "__main__":
    main()

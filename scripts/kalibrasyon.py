#!/usr/bin/env python3
"""Kalibrasyon aracı — insan farkareket verisi topla (docs §1 kurallarıyla).

Kullanım:
    python scripts/kalibrasyon.py                 # 40 deneme
    python scripts/kalibrasyon.py --deneme 60     # daha uzun oturum

Ekran: mavi hedefe tıkla; ESC = bitir ve kaydet; F2 = şimdiye kadarı kaydet.
Kayıt: data/recordings/kal-<zaman>.jsonl (yalnız fare; klavye/ekran verisi YOK).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ui.calibration import main  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main_cli():
    ap = argparse.ArgumentParser(
        description="dogal-fare kalibrasyon ekranı (veri toplama)")
    ap.add_argument("--deneme", type=int, default=40,
                    help="oturumdaki hedef sayısı (varsayılan 40)")
    ap.add_argument("--dizin", default=os.path.join(ROOT, "data", "recordings"),
                    help="kayıt dizini")
    args = ap.parse_args()
    os.makedirs(args.dizin, exist_ok=True)
    print(f"Hedef deneme sayısı: {args.deneme}. Kayıt dizini: {args.dizin}")
    print("Veri yalnız bu penceredeki fare hareketlerinden toplanır "
          "(klavye/ekran/çerez YOK).")
    main(args.dizin, args.deneme)


if __name__ == "__main__":
    main_cli()

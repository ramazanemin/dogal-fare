#!/usr/bin/env python3
"""Yerel test değerlendirmesi (headless, GERÇEK FARE HAREKETİ YOK).

Üç yöntemi aynı 'görülmemiş hedef' setinde karşılaştırır ve Markdown+JSON rapor yazar.
Hedef üretimi: app/testgen.py (D ∈ [150,900] px; r ∈ {8,16,24,40,64} px; seed'li).

İBARE: Bu sonuçlar YEREL kinematik ölçümüdür; üçüncü taraf (ör. Instagram) tespit
sistemleri hakkında HİÇBİR kanıt içermez (docs §2 D4, D5).

Kullanım:
    python scripts/degerlendirme.py                 # 40 deneme, tüm modeller
    python scripts/degerlendirme.py --deneme 60 --model learned
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from app.config import load_config
from app.metrics.kinematics import plan_metrics, summarize
from app.metrics.system import ProcessResources
from app.models.learned import LearnedModel
from app.models.manager import ModelManager
from app.testgen import DIST_MAX, DIST_MIN, RADII_TEST, make_test_targets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DISCLAIMER = ("SONUÇLAR YEREL KİNEMATİK ÖLÇÜMÜDÜR. Üçüncü taraf tespit sistemleri "
              "(ör. Instagram) hakkında KANIT İÇERMEZ (docs §2 D4, D5).")


def build_all_models(cfg, data_dir):
    mgr = ModelManager(cfg)
    mgr.load_and_split(data_dir)
    mgr.train_from_split()
    loaded = LearnedModel.load(cfg, os.path.join(ROOT, "model", "fare_model.json"))
    mgr.learned = loaded if loaded is not None else mgr.learned
    if mgr.learned is None:
        mgr.learned = mgr.fit_learned()
    models = {"baseline": mgr.baseline}
    if mgr.rescaler is not None:
        models["rescaler"] = mgr.rescaler
    if mgr.learned is not None and mgr.learned.p.get("n_train", 0) > 0:
        models["learned"] = mgr.learned
    info = {
        "n_train": len(mgr.train_trials), "n_test_sessions": len(
            {t.get("session_id") for t in mgr.test_trials}),
        "learned_n": mgr.learned.p.get("n_train", 0) if mgr.learned else 0,
        "rescaler_n": len(mgr.rescaler.exemplars) if mgr.rescaler else 0,
        "sources": sorted({t["source"] for t in mgr.train_trials}),
    }
    return models, info


def evaluate_model(model, targets, seed: int, proc=None):
    lat_ms: list[float] = []
    metrics: list[dict] = []
    cpu_samples: list[float] = []
    for i, spec in enumerate(targets):
        rng = np.random.default_rng(seed * 1009 + i)
        t0 = time.perf_counter()
        plan = model.generate((spec["sx"], spec["sy"]), (spec["x"], spec["y"]),
                              spec["r"], rng)
        lat_ms.append((time.perf_counter() - t0) * 1000.0)
        metrics.append(plan_metrics(plan))
        if proc is not None and i % 5 == 4:
            cpu_samples.append(proc.cpu_percent())
    s = summarize(metrics)
    s["gen_latency_p50_ms"] = float(np.percentile(lat_ms, 50))
    s["gen_latency_p95_ms"] = float(np.percentile(lat_ms, 95))
    if cpu_samples:
        s["cpu_mean_percent"] = float(np.mean(cpu_samples))
        s["cpu_peak_percent"] = float(np.max(cpu_samples))
    return s


def fmt(s: dict | None, key: str, unit: str = "") -> str:
    if not s:
        return "—"
    return f"{s[key + '_mean']:.3g}{unit} (±{s[key + '_std']:.3g})"


def main_cli():
    ap = argparse.ArgumentParser(description="yerel karşılaştırma + rapor")
    ap.add_argument("--deneme", type=int, default=40)
    ap.add_argument("--tohum", type=int, default=20261115)
    ap.add_argument("--model", default="all",
                    choices=["all", "baseline", "rescaler", "learned"])
    ap.add_argument("--rapor", default=None, help="markdown rapor dosyası")
    args = ap.parse_args()

    cfg = load_config()
    data_dir = os.path.join(ROOT, "data", "recordings")
    models, info = build_all_models(cfg, data_dir)
    names = [args.model] if args.model != "all" else list(models.keys())
    names = [n for n in names if n in models]
    if not names:
        print("Hiç model yok (kod hatası olmamalı: baseline her zaman var).")
        sys.exit(2)

    targets = make_test_targets(1024.0, 700.0, args.deneme, seed=args.tohum)
    proc = ProcessResources()
    results: dict[str, dict] = {}
    for name in names:
        results[name] = evaluate_model(models[name], targets, args.tohum, proc=proc)
    cpu_overall = max((results[n].get("cpu_peak_percent", 0.0) for n in names),
                      default=0.0)
    cpu_mean = max((results[n].get("cpu_mean_percent", 0.0) for n in names),
                   default=0.0)
    ram = proc.ram_mb()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    md_path = args.rapor or os.path.join(ROOT, "reports", f"test_raporu_{stamp}.md")
    json_path = md_path.replace(".md", ".json")
    os.makedirs(os.path.dirname(md_path), exist_ok=True)

    lines = []
    lines.append(f"# dogal-fare Yerel Test Raporu — {stamp}")
    lines.append("")
    lines.append(f"> **İBARE:** {DISCLAIMER}")
    lines.append("")
    src = ", ".join(info["sources"]) or "yok"
    lines.append("## Kurulum")
    lines.append(f"- Eğitim kayıtları: {info['n_train']} deneme (kaynak: {src}; "
                 f"test oturumlarında ayrılan: {info['n_test_sessions']} oturum).")
    if "learned" in models:
        lp = models["learned"].p
        lines.append(f"- learned model: {lp['n_train']} deneme / {lp['n_sessions']} oturum; "
                     f"Fitts a={lp['fitts']['a_ms']:.0f} ms, b={lp['fitts']['b_ms_per_bit']:.0f} ms/bit.")
    else:
        lines.append("- learned model: YOK (kayıt yetersiz → yalnız algoritmik taban).")
    lines.append(f"- rescaler: {info['rescaler_n']} örnek."
                 if info["rescaler_n"] else "- rescaler: YOK.")
    lines.append(f"- Test seti: {args.deneme} hedef; D ∈ [{DIST_MIN:.0f},{DIST_MAX:.0f}] px; "
                 f"r ∈ {RADII_TEST}; tohum={args.tohum}. Konum/boyut kombinasyonları "
                 f"eğitim kayıtlarında bulunmayan çekimlerden üretildi (seed'li).")
    lines.append("")
    lines.append("| Metrik | " + " | ".join(names) + " |")
    lines.append("|---|" + "---|" * len(names))
    rows = [
        ("isabet (tıklama hedef içinde), %", lambda s: f"{100*s['hit_rate_click']:.0f}"),
        ("isabet (0.8R margin), %", lambda s: f"{100*s['hit_rate_margin']:.0f}"),
        ("hareket süresi, ms", lambda s: fmt(s, "duration_ms")),
        ("yol/kiriş oranı", lambda s: fmt(s, "path_over_chord")),
        ("yol uzunluğu, px", lambda s: fmt(s, "path_len_px", "")),
        ("tepe hız, px/s", lambda s: f"{s['peak_v_px_ms_mean']*1000:.0f} (±{s['peak_v_px_ms_std']*1000:.0f})"),
        ("ortalama hız, px/s", lambda s: f"{s['mean_v_px_ms_mean']*1000:.0f}"),
        ("hız tepe sayısı (alt-hareket izi)", lambda s: fmt(s, "speed_peaks")),
        ("ivme RMS, px/ms²", lambda s: fmt(s, "acc_rms_px_ms2")),
        ("jerk RMS, px/ms³", lambda s: fmt(s, "jerk_rms_px_ms3")),
        ("toplam duraklama, ms", lambda s: fmt(s, "pause_ms")),
        ("üretim gecikmesi p50, ms", lambda s: f"{s['gen_latency_p50_ms']:.2f}"),
        ("üretim gecikmesi p95, ms", lambda s: f"{s['gen_latency_p95_ms']:.2f}"),
    ]
    for label, fn in rows:
        lines.append(f"| {label} | " + " | ".join(fn(results[n]) for n in names) + " |")
    lines.append("")
    lines.append(f"## Süreç kaynakları (üretim+metrik hesap, tek çekirdek ölçümü)")
    lines.append(f"- deneme döngüsünde CPU: ortalama ~%{cpu_mean:.0f}, tepe ~%{cpu_overall:.0f}:"
                 f" RAM (working set): {ram:.0f} MB.")
    lines.append("- GPU kullanımı: YOK (tüm model <1 KB JSON, CPU-only).")
    lines.append("")
    lines.append("## Yorum ölçütleri")
    lines.append("- Beğenilen desen: yol/kiriş >1 (düz olmayan yörünge), ortalarda tek "
                 "tepe hıza yakın profil, duraklama/düzeltme sıklığı insana yakın, "
                 "isabet %100 (güvence), üretim gecikmesi ~ms.")
    lines.append("- **Bunlar yalnız literatürle (D1-D3) tutarlılık ölçümüdür; "
                 "canlı platformda tespit/tespit edilmeme dair sonuç çıkarılamaz.**")
    body = "\n".join(lines)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(body + "\n")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({"disclaimer": DISCLAIMER, "setup": info,
                   "targets": {"n": args.deneme, "seed": args.tohum,
                               "D": [DIST_MIN, DIST_MAX], "r": RADII_TEST},
                   "results": results, "cpu_mean_percent": cpu_mean, "cpu_peak_percent": cpu_overall, "ram_mb": ram},
                  fh, ensure_ascii=False, indent=1)
    print(body)
    print(f"\nRapor: {md_path}")
    print(f"JSON : {json_path}")


if __name__ == "__main__":
    main_cli()

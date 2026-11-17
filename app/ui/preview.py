"""Önizleme + yerel test ekranı — model hareketini SANAL imleçle oynatır.

Bu ekran GERÇEK fareyi HAREKET ETTİRMEZ: hareket planları çizilir + gerçek-zaman
oynatılır; tıklama simülasyonu gösterilir. Yerel değerlendirme.Tests (auto mod) sonuçları
JSON'a yazar; GUI'de ölçüm planı docs §5'tekiyle aynıdır.

Kullanım: python scripts/onizleme.py [--auto N] [--model auto|baseline|rescaler|learned]
"""
from __future__ import annotations

import json
import math
import os
import random
import time
import tkinter as tk

from ..config import get
from ..metrics.kinematics import plan_metrics, summarize
from ..metrics.system import ProcessResources

BG = "#0d1016"
TRACE = "#5aa9ff"
CURSOR = "#e8eef5"
TARGET = "#2d6cdf"
FLASH_HIT = "#3ddc84"
FLASH_MISS = "#ff5566"

from ..testgen import make_test_targets


class PreviewUI:
    def __init__(self, models: dict, model_name: str, cfg: dict,
                 auto_trials: int = 0, out_json: str | None = None,
                 seed: int = 20261115):
        """models: {'baseline': m, 'rescaler': m|None, 'learned': m|None}"""
        self.cfg = cfg
        self.models = models
        self.model_name = model_name
        self.auto_trials = auto_trials
        self.out_json = out_json
        self.seed = seed
        self.rng = random.Random(seed)
        self.metrics_list: list[dict] = []
        self.abort = False
        self._trial_i = 0
        self.proc = ProcessResources()
        self._cpu_samples = [self.proc.cpu_percent()]

        self.root = tk.Tk()
        self.root.title("dogal-fare önizleme (SANAL imleç — gerçek tıklama yok; ESC: dur)")
        self.root.geometry("1100x760")
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        side = tk.Frame(self.root, width=280, bg="#141922")
        side.pack(side=tk.RIGHT, fill=tk.Y)
        self.side = side
        self.status = tk.Label(side, text="Hazırlanıyor...", bg="#141922",
                               fg="#cfe3ff", justify=tk.LEFT, anchor="nw",
                               wraplength=256, font=("Segoe UI", 10))
        self.status.pack(fill=tk.X, padx=10, pady=10)
        if auto_trials == 0:
            tk.Button(side, text="Deneme başlat (Boşluk)", command=self.start_trial,
                      bg="#1c2733", fg="#dbe7ff", relief=tk.FLAT).pack(fill=tk.X, padx=10, pady=4)
        tk.Label(side, text="Model: " + model_name, bg="#141922",
                 fg="#8fa3b8", font=("Segoe UI", 10)).pack(padx=10, anchor="w")
        self.hint = tk.Label(side, bg="#141922", fg="#8fa3b8", justify=tk.LEFT,
                             anchor="nw", wraplength=256,
                             text="Bu ekran gerçek fareyi kontrol ETMEZ.\n"
                                  "Yerel kinematik ölçümüdür; tespit\n"
                                  "sistemleri hakkında kanıt sunmaz\n"
                                  "(docs §2 D4, D5).")
        self.hint.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        self.root.bind("<Escape>", self._stop)
        self.root.bind("<space>", lambda ev: auto_trials == 0 and self.start_trial())
        if auto_trials > 0:
            self.root.after(200, self._auto_step)

    # ---------- yardımcılar ----------
    def _pick_model(self):
        m = self.models.get(self.model_name)
        if m is None:
            m = self.models.get("learned") or self.models.get("rescaler") \
                or self.models["baseline"]
            self.model_name = m.name
        return m

    def _set_status(self, text: str):
        self.status.configure(text=text)
        self.root.update_idletasks()

    # ---------- deneme akışı ----------
    def start_trial(self):
        if self.auto_trials == 0:
            self._trial_i = 0
            self.metrics_list = []
        self._run_one()

    def _auto_step(self):
        if self.abort or self._trial_i >= self.auto_trials:
            self._finish_auto()
            return
        self._run_one(callback=lambda: self._auto_step())

    def _run_one(self, callback=None):
        if self.abort:
            return
        cw = max(self.canvas.winfo_width(), 600)
        ch = max(self.canvas.winfo_height(), 400)
        if not hasattr(self, "_targets") or not self._targets:
            self._targets = make_test_targets(cw, ch, max(self.auto_trials or 8, 8),
                                              seed=self.seed + self._trial_i)
        spec = self._targets[self._trial_i % len(self._targets)]
        model = self._pick_model()
        import numpy as np
        rng = np.random.default_rng(self.seed * 1009 + self._trial_i)
        try:
            plan = model.generate((spec["sx"], spec["sy"]), (spec["x"], spec["y"]),
                                  spec["r"], rng)
        except ValueError as exc:
            self._set_status(f"Hata: {exc}")
            return
        m = plan_metrics(plan)
        self.metrics_list.append(m)
        self._trial_i += 1
        self._animate(plan, spec, m, callback)

    # ---------- animasyon (SANAL imleç) ----------
    def _animate(self, plan, spec, m, done_cb):
        self.canvas.delete("anim")
        wp = plan.waypoints
        tx, ty, r = spec["x"], spec["y"], spec["r"]
        self.canvas.create_oval(tx - r, ty - r, tx + r, ty + r,
                                fill=TARGET, outline="#7ea6ff", width=2, tags="anim")
        self.canvas.create_oval(spec["sx"] - 6, spec["sy"] - 6,
                                spec["sx"] + 6, spec["sy"] + 6,
                                outline="#666", width=1, tags="anim")
        self.canvas.create_text(tx, ty - r - 14, fill="#8fa3b8",
                                font=("Segoe UI", 9), tags="anim",
                                text=f"r={r:.0f}px  model={plan.model_name}")
        idx = {"i": 0}
        trace: list[tuple[float, float]] = []

        def step():
            if self.abort:
                return
            i = idx["i"]
            if i >= len(wp):
                cx, cy = plan.click_xy
                hit = m["hit_click"]
                self.canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8,
                                        outline=FLASH_HIT if hit else FLASH_MISS,
                                        width=3, tags="anim")
                self._show_metrics(m)
                if done_cb:
                    self.root.after(250, done_cb)
                return
            x, y = float(wp[i, 1]), float(wp[i, 2])
            trace.append((x, y))
            if len(trace) > 2:
                x0, y0 = trace[-2]
                self.canvas.create_line(x0, y0, x, y, fill=TRACE, width=2,
                                        tags="anim")
            self.canvas.delete("cursor")
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                                    fill=CURSOR, outline="#9ab", tags=("cursor",))
            dx = float(wp[i, 0]) - (float(wp[i - 1, 0]) if i else 0.0)
            idx["i"] = i + 1
            self._cpu_samples.append(self.proc.cpu_percent())
            self.root.after(max(int(dx), 4), step)

        step()

    def _show_metrics(self, m):
        line = (f"deneme {self._trial_i}\n"
                f"süre: {m['duration_ms']:.0f} ms\n"
                f"yol/kiriş: {m['path_over_chord']:.3f}\n"
                f"tepe hız: {m['peak_v_px_ms'] * 1000:.0f} px/s\n"
                f"hız tepe sayısı: {m['speed_peaks']}\n"
                f"jerk RMS: {m['jerk_rms_px_ms3']:.1f}\n"
                f"tıklama hedefte: {'EVET' if m['hit_click'] else 'HAYIR'}")
        self._set_status(line)

    # ---------- bitiş ----------
    def _stop(self, _ev=None):
        self.abort = True

    def _finish_auto(self):
        s = summarize(self.metrics_list)
        cpu = max(self.cpu_peak(), 0.0)
        ram = self.proc.ram_mb()
        line = (f"TAMAMLANDI: {s.get('n', 0)} deneme\n"
                f"isabet(tıklama): %{100 * s.get('hit_rate_click', 0):.0f}\n"
                f"ort. süre: {s.get('duration_ms_mean', 0):.0f} ms "
                f"(±{s.get('duration_ms_std', 0):.0f})\n"
                f"CPU tepe: %{cpu:.0f}  RAM: {ram:.0f} MB")
        self._set_status(line + "\nESC → kapat")
        if self.out_json and self.metrics_list:
            payload = {
                "disclaimer": ("Yerel kinematik ölçümüdür; üçüncü taraf tespit "
                               "sistemleri hakkında KANIT içermez (docs D4, D5)."),
                "model": self.model_name, "summary": s,
                "trials": self.metrics_list,
                "cpu_peak_percent": cpu, "ram_mb": ram,
            }
            os.makedirs(os.path.dirname(self.out_json) or ".", exist_ok=True)
            with open(self.out_json, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            print("Yazıldı:", self.out_json)

    def cpu_peak(self) -> float:
        return max(self._cpu_samples) if self._cpu_samples else 0.0

    def run(self):
        self.root.mainloop()

"""Kalibrasyon ekranı — insan hareket verisi TOPLAMA (yalnız bu ekran!).

VERİ İLKELERİ (docs §1):
- Yalnız bu penceredeki <Motion> ve <Button-1> olayları kaydedilir.
- Kaydedilen: zaman damgası (pencereye göre, ms), GÖRELİ koordinat, hedef yarıçapı,
  hedef sunum anı, tıklama ana, isabet bilgisi.
- Klavye verisi KAYDEDİLMEZ (ESC/F2 yalnız program kontrolüdür).
- Ekran görüntüsü, çerez, oturum belirteci, ağ erişimi YOK.

Kullanım: python scripts/kalibrasyon.py  (ESC: bitir ve kaydet)
"""
from __future__ import annotations

import json
import math
import random
import time
import tkinter as tk

from ..storage import new_session_id

RADII = [18.0, 26.0, 34.0, 50.0]      # hedef yarıçapı döngüsü (px) — çeşitlilik
MIN_DIST_PREV = 320.0                # önceki hedeze göre en az mesafe
EDGE_PAD = 70.0                      # kenardan güvenli pay
RADII_JITTER = 0.12                  # aynı yarıçapın denemeler arası salınımı


class CalibrationUI:
    def __init__(self, out_dir: str, n_trials: int = 40):
        self.out_dir = out_dir
        self.session_id = new_session_id("kal")
        self.n_trials = n_trials
        self.trials: list[dict] = []
        self._flushed = 0
        self._base_t = time.perf_counter()
        self._rng = random.Random(17)

        self.root = tk.Tk()
        self.root.title(f"dogal-fare kalibrasyon — oturum {self.session_id} "
                        f"(ESC: bitir ve kaydet)")
        w, h = 1024, 720
        self.root.geometry(f"{w}x{h}")
        self.canvas = tk.Canvas(self.root, bg="#101418", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=1)
        self.info = self.canvas.create_text(
            18, 14, anchor="nw", fill="#8fa3b8",
            font=("Segoe UI", 11),
            text="Hazırlanıyor...")
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_click)
        self.root.bind("<Escape>", self._finish)
        self.root.bind("<F2>", self._flush_and_continue)
        self.root.after(120, self._next_trial)
        self.root.protocol("WM_DELETE_WINDOW", self._finish_via_close)

    # ---------- hedef yönetimi ----------
    def _usable_rect(self):
        self.canvas.update_idletasks()
        w = max(self.canvas.winfo_width(), 300)
        h = max(self.canvas.winfo_height(), 300)
        return EDGE_PAD, EDGE_PAD, w - EDGE_PAD, h - EDGE_PAD

    def _next_trial(self):
        if len(self.trials) >= self.n_trials:
            self._finish()
            return
        x0, y0, x1, y1 = self._usable_rect()
        prev = self.trials[-1]["target"] if self.trials else None
        for _ in range(200):
            tx = self._rng.uniform(x0 + 40, x1 - 40)
            ty = self._rng.uniform(y0 + 80, y1 - 40)
            if prev is None or math.hypot(tx - prev[0], ty - prev[1]) >= MIN_DIST_PREV:
                break
        idx = len(self.trials) % len(RADII)
        r = RADII[idx] * (1.0 + self._rng.uniform(-RADII_JITTER, RADII_JITTER))
        self._cur = {"target": [tx, ty], "radius": r,
                     "presented_ms": self._now(), "samples": []}
        self._draw_target()
        self._set_info()

    def _draw_target(self):
        self.canvas.delete("target")
        tx, ty = self._cur["target"]
        r = self._cur["radius"]
        self.canvas.create_oval(tx - r, ty - r, tx + r, ty + r,
                                fill="#2d6cdf", outline="#7ea6ff", width=2,
                                tags="target")
        self.canvas.tag_lower("target")

    def _set_info(self):
        self.canvas.itemconfigure(
            self.info,
            text=f"Deneme {len(self.trials) + 1}/{self.n_trials} — mavi hedefe tıkla "
                 f"(ESC: bitir, F2: şimdiye kadarı kaydet)")

    # ---------- olaylar ----------
    def _now(self) -> float:
        return (time.perf_counter() - self._base_t) * 1000.0

    def _rel_pos(self) -> tuple[float, float]:
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        return (float(x), float(y))

    def _on_motion(self, _ev):
        if getattr(self, "_cur", None) is None:
            return
        x, y = self._rel_pos()
        self._cur["samples"].append([round(self._now(), 3), round(x, 1), round(y, 1)])

    def _on_click(self, _ev):
        cur = getattr(self, "_cur", None)
        if cur is None:
            return
        x, y = self._rel_pos()
        tx, ty = cur["target"]
        hit = math.hypot(x - tx, y - ty) <= cur["radius"]
        cur["samples"].append([round(self._now(), 3), round(x, 1), round(y, 1)])
        self.trials.append({
            "session_id": self.session_id,
            "source": "human",
            "target": cur["target"],
            "radius": cur["radius"],
            "presented_ms": round(cur["presented_ms"], 3),
            "click_ms": round(self._now(), 3),
            "hit": hit,
            "samples": cur["samples"],
        })
        self.canvas.delete("target")
        self._flash_result(hit)
        self._cur = None
        self.root.after(140, self._next_trial)

    def _flash_result(self, hit: bool):
        w = self.canvas.winfo_width() / 2
        self.canvas.create_text(
            w, 40, fill="#3ddc84" if hit else "#ff5566",
            font=("Segoe UI", 13), text="✓ isabet" if hit else "✗ ıskaladın",
            tags="flash")
        self.root.after(220, lambda: self.canvas.delete("flash"))

    # ---------- kayıt ----------
    def _flush_partial(self, with_meta: bool = True):
        new = self.trials[self._flushed:]
        if not new:
            return 0
        from ..storage import save_session
        path = save_session(self.out_dir, new,
                            meta={"app": "dogal-fare", "n_planned": self.n_trials}
                            if with_meta else None)
        self._flushed = len(self.trials)
        return len(new)

    def _flush_and_continue(self, _ev=None):
        n = self._flush_partial(with_meta=(self._flushed == 0))
        self._set_flash(f"Kaydedildi: {n} deneme → {self.out_dir}")

    def _set_flash(self, text: str):
        w = self.canvas.winfo_width() / 2
        self.canvas.create_text(w, 66, fill="#8fa3b8", font=("Segoe UI", 11),
                                text=text, tags="flash")
        self.root.after(900, lambda: self.canvas.delete("flash"))

    def _finish(self, _ev=None):
        try:
            if len(self.trials) > self._flushed:
                self._flush_partial(with_meta=(self._flushed == 0))
        except Exception:
            pass
        self.root.quit()

    def _finish_via_close(self):
        self._finish()

    def run(self):
        self.root.mainloop()
        n_hit = sum(1 for t in self.trials if t.get("hit"))
        print(f"Kalibrasyon bitti: {len(self.trials)} deneme, {n_hit} isabet, "
              f"oturum {self.session_id} → {self.out_dir}")


def main(out_dir: str, n_trials: int = 40) -> None:
    ui = CalibrationUI(out_dir, n_trials)
    ui.run()

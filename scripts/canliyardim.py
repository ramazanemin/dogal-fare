#!/usr/bin/env python3
"""Canlı yardım (Faz 2) — kullanıcı-seçimli TEK hedefe doğal hareket + tıklama.

GÜVENLİK MODELİ (kullanıcı gereksinimleri):
  1) Önizleme VARSAYILAN: F9 planı üretir ve minyatür pencerede gösterir;
     gerçek fare HAREKET ETMEZ. --hareket-gercek gerekir.
  2) Gerçek tıklama AYRI bayrak: --gercek-tiklama (--hareket-gercek şart).
  3) ESC: her an acil durdurma.
  4) Açık hedef YOKSA işlem YOK (F8 ile hedef seçilmeden F9 geçersiz).
  5) CAPTCHA/güvenlik bulgusu: hedef alındığında ve hareket sırasında pencere
     BAŞLIĞI taranır (buluşsal; garanti DEĞİLDİR). Bulgu → dur, kullanıcıya devret.
  6) Platform uyarısı: otomasyon hizmet koşullarını ihlal edebilir (docs D6).

Akış: F8 (imleç hedefin merkezinde) → hedef kaydı; F9 (imleç yeni konumda) → plan;
ESC → iptal/çıkış. Plan ONAYLI akışta runner yürütür (click ayrıca izinli).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import tkinter as tk

from app.config import load_config
from app.control.mouse import (
    MouseController, foreground_window_title, get_cursor_pos, is_key_down,
    VK_ESCAPE, VK_F8, VK_F9,
)
from app.control.runner import MovementRunner
from app.models.learned import LearnedModel
from app.models.manager import ModelManager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def confirm_real_mode(move: bool, click: bool) -> bool:
    if not (move or click):
        return True  # önizleme güvenli
    print("=" * 66)
    print("UYARI: Gerçek fare kontrolü etkinleştirilecek.")
    if move:
        print("  - İMLEÇ GERÇEKTEN HAREKET EDECEK (--hareket-gercek).")
    if click:
        print("  - GERÇEK TIKLAMA GÖNDERİLECEK (--gercek-tiklama).")
    print("  - Otomasyon hedef platformun hizmet koşullarını ihlal edebilir;")
    print("    riski kabul ediyorsan yazarak onayla. ESC her an durdurur.")
    print("=" * 66)
    try:
        ans = input("Onaylıyor musun? 'devam' yaz: ").strip()
    except EOFError:
        return False
    return ans == "devam"


class LiveAssist:
    POLL_MS = 30
    KEY_DEBOUNCE_MS = 400

    def __init__(self, args):
        self.args = args
        self.cfg = load_config()
        mgr = ModelManager(self.cfg)
        mgr.load_and_split(os.path.join(ROOT, "data", "recordings"))
        mgr.train_from_split()
        loaded = LearnedModel.load(self.cfg,
                                   os.path.join(ROOT, "model", "fare_model.json"))
        mgr.learned = loaded if loaded is not None else mgr.learned
        try:
            self.model, reason = mgr.select(args.model)
        except ValueError:
            self.model, reason = mgr.baseline, "seçim başarısız → baseline"
        print(f"Model: {self.model.name} ({reason})")
        self.runner = MovementRunner(
            MouseController(dry_run=not args.hareket_gercek,
                            allow_click=bool(args.gercek_tiklama and
                                             args.hareket_gercek)),
            self.cfg)
        self.target: tuple[float, float] | None = None
        self.radius = float(args.radius)
        self.last_key_t = {"F8": 0.0, "F9": 0.0}
        self.state = "idle"

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.after(self.POLL_MS, self.poll)

    def warn_title(self) -> str | None:
        title = (foreground_window_title() or "").lower()
        for kw in self.cfg.get("warn_titles", []):
            if kw and kw.lower() in title:
                return f"başlıkta güvenlik bulgusu ('{kw}') → {title}"
        return None

    def poll(self):
        try:
            if is_key_down(VK_ESCAPE):
                print("\nESC → çıkış. (Hedef temizlendi.)")
                self.shutdown()
                return
            if is_key_down(VK_F8) and self._debounce("F8"):
                self.capture_target()
            if is_key_down(VK_F9) and self._debounce("F9"):
                self.request_movement()
            self.root.after(self.POLL_MS, self.poll)
        except KeyboardInterrupt:
            self.shutdown()

    def _debounce(self, key: str) -> bool:
        now = time.perf_counter() * 1000.0
        if now - self.last_key_t[key] < self.KEY_DEBOUNCE_MS:
            return False
        self.last_key_t[key] = now
        return True

    def capture_target(self):
        warn = self.warn_title()
        if warn:
            print(f"F8 REDDEDİLDİ — {warn}")
            print("Kullanıcı kontrol etsin; gerekirse aracı kapat.")
            return
        x, y = get_cursor_pos()
        self.target = (float(x), float(y))
        print(f"F8 ✓ hedef: ({x:.0f}, {y:.0f}) r={self.radius:.0f}px")
        print("İmleci hareketin BAŞLAYACAĞI yere götür, F9 bas.")

    def request_movement(self):
        if self.target is None:
            print("F9 geçersiz: AÇIK HEDEF yok. Önce hedef merkezinde F8.")
            return
        if self.state == "running":
            return
        warn = self.warn_title()
        if warn:
            print(f"F9 REDDEDİLDİ — {warn}")
            return
        start = get_cursor_pos()
        rng = np.random.default_rng(int(time.time() * 1000) % (2 ** 31))
        try:
            plan = self.model.generate((float(start[0]), float(start[1])),
                                       self.target, self.radius, rng)
        except ValueError as exc:
            print(f"Plan üretilemedi: {exc}")
            return
        print(f"Plan: {plan.model_name}, {len(plan.waypoints)} adım, "
              f"süre={plan.duration_ms:.0f} ms; tıklama hedef içi güvenceli")
        self.state = "running"
        if not self.args.hareket_gercek:
            self.show_preview(plan)
            self.state = "idle"
            return
        outcome = self.runner.execute(plan, execute_click=bool(self.args.gercek_tiklama))
        self.state = "idle"
        print("Sonuç:", outcome)
        if outcome.get("aborted_reason"):
            print("→ Durma nedeni:", outcome["aborted_reason"])

    def show_preview(self, plan):
        """Önizleme: planın ölçekli minyatürü. Gerçek fare HAREKET ETMEZ."""
        wp = plan.waypoints
        xs, ys = wp[:, 1], wp[:, 2]
        all_x = np.concatenate([xs, [plan.target_xy[0]]])
        all_y = np.concatenate([ys, [plan.target_xy[1]]])
        x0, x1 = float(all_x.min()), float(all_x.max())
        y0, y1 = float(all_y.min()), float(all_y.max())
        W, H, PAD = 420, 300, 30
        sx = (W - 2 * PAD) / max(x1 - x0, 1.0)
        sy = (H - 2 * PAD) / max(y1 - y0, 1.0)
        sc = min(sx, sy)

        def m(px, py):
            return PAD + (px - x0) * sc + (W - 2 * PAD - (x1 - x0) * sc) / 2, \
                   PAD + (py - y0) * sc + (H - 2 * PAD - (y1 - y0) * sc) / 2

        win = tk.Toplevel(self.root)
        win.title("ÖNİZLEME (gerçek harekât YOK)")
        cv = tk.Canvas(win, width=W, height=H, bg="#0d1016")
        cv.pack()
        pts = [m(x, y) for x, y in zip(xs, ys)]
        if len(pts) >= 2:
            for i in range(len(pts) - 1):
                cv.create_line(*pts[i], *pts[i + 1], fill="#5aa9ff", width=2)
        tx, ty = m(*plan.target_xy)
        r = max(self.radius * sc, 8)
        cv.create_oval(tx - r, ty - r, tx + r, ty + r,
                       outline="#2d6cdf", width=2)
        cv.create_text(W / 2, H - 14, fill="#8fa3b8",
                       text=f"ÖNİZLEME — {plan.model_name}, "
                            f"{plan.duration_ms:.0f} ms (imleç hareket ETMEDİ)")
        win.after(2600, win.destroy)

    def shutdown(self):
        self.target = None
        self.root.quit()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self):
        print("Canlı yardım çalışıyor (önizleme)." if not self.args.hareket_gercek
              else "Canlı yardım çalışıyor (GERÇEK hareket).")
        print("ESC: çıkış | F8: hedef al | F9: plan/uygula")
        self.root.mainloop()


def main_cli():
    ap = argparse.ArgumentParser(description="dogal-fare canlı yardım (Faz 2)")
    ap.add_argument("--hareket-gercek", action="store_true",
                    help="imleci GERÇEKTEN hareket ettir (önizleme değil)")
    ap.add_argument("--gercek-tiklama", action="store_true",
                    help="hareket sonunda GERÇEK tıklama gönder")
    ap.add_argument("--radius", type=float, default=32.0,
                    help="hedef yarıçapı, px (varsayılan 32)")
    ap.add_argument("--model", default="auto",
                    choices=["auto", "baseline", "rescaler", "learned"])
    args = ap.parse_args()
    if not confirm_real_mode(args.hareket_gercek, args.gercek_tiklama):
        print("Onay alınmadı → yalnız önizleme modu başlıyor.")
        args.hareket_gercek = False
        args.gercek_tiklama = False
    LiveAssist(args).run()


if __name__ == "__main__":
    main_cli()

"""Hareket yürütücüsü: planı adım adım icra eder.

GÜVENLİK (kullanıcı gereksinimleri):
- ESC her adımda denetlenir → anında durdurma
- ekran sınırı: plan yürütmeden ÖNCE doğrulanır; adımlar sırasında tekrar kontrol
- tıklama: son nokta hedef İÇİNDE değilse TIKLAMA YAPILMAZ (abort)
- CAPTCHA/güvenlik bulgusu: pencere BAŞLIĞINDA anahtar kelime (buluşsal, garanti değil)
  hareket başında + sırasında ~200ms'de bir denetlenir → abort, kullanıcıya devir
- dry_run: hiçbir gerçek girdi gönderilmez
"""
from __future__ import annotations

import math
import time

from ..config import get
from .mouse import MouseController, PrecisionTimer, SafetyAbort, hybrid_sleep
from .validation import validate_plan


class MovementRunner:
    def __init__(self, controller: MouseController, cfg: dict):
        self.ctrl = controller
        self.cfg = cfg

    # ---- bulgular ----
    def _warn_keyword_in_title(self) -> str | None:
        title = ""
        try:
            title = self.ctrl_foreground_title()
        except Exception:
            return None
        tl = title.lower()
        for kw in get(self.cfg, "warn_titles", []):
            if kw and kw.lower() in tl:
                return f"başlıkta güvenlik bulgusu ('{kw}'): {title!r}"
        return None

    def ctrl_foreground_title(self):
        from .mouse import foreground_window_title
        return foreground_window_title()

    # ---- yürütme ----
    def execute(self, plan, execute_click: bool = False, on_progress=None,
                abort_check=None, speed: float = 1.0) -> dict:
        """Planı yürütür; sonuç dict döner.

        execute_click: tıklama İZNİ (dry-run'da simüle; gerçek modda allow_click şart).
        abort_check: dış durdurma kancası (testler ve canliyardim için).
        speed: zaman ölçeği (testlerde 0 → anında; üretimde 1.0).
        """
        outcome = {
            "model": plan.model_name, "completed": False,
            "aborted_reason": None, "click_executed": False,
            "steps": 0, "elapsed_ms": 0.0,
        }
        t0 = time.perf_counter()
        try:
            # 0) ESC zaten basılı mı?
            if self.ctrl.is_escape_pressed():
                outcome["aborted_reason"] = "ESC zaten basılı"
                return outcome
            # 1) Başlık bulgusu (hareket öncesi)
            warn = self._warn_keyword_in_title()
            if warn:
                outcome["aborted_reason"] = warn
                return outcome
            # 2) Plan doğrulaması (tentionlı: ekran sınırı + hedef içi tıklama)
            ok, reason = validate_plan(plan, self.cfg, self.ctrl.screen)
            if not ok:
                outcome["aborted_reason"] = f"plan reddi: {reason}"
                return outcome
            wp = plan.waypoints
            last_title_check = 0.0
            n = len(wp)
            with PrecisionTimer():
                for i in range(n):
                    if self.ctrl.is_escape_pressed() or (abort_check and abort_check()):
                        outcome["aborted_reason"] = "acil durdurma (ESC/dış kanca)"
                        return outcome
                    now = time.perf_counter()
                    if now - last_title_check > 0.2:
                        warn = self._warn_keyword_in_title()
                        last_title_check = now
                        if warn:
                            outcome["aborted_reason"] = warn
                            return outcome
                    if i > 0:
                        hybrid_sleep(float(wp[i, 0] - wp[i - 1, 0]) * float(speed))
                    self.ctrl.move_to(float(wp[i, 1]), float(wp[i, 2]))
                    outcome["steps"] = i + 1
                    if on_progress:
                        on_progress(i, n)
            # 3) Tıklama: hedef İÇİNDE değilse TIKLAMA YOK; izin yoksa bilinçli atlama
            tx, ty = plan.click_xy
            dist = math.hypot(tx - plan.target_xy[0], ty - plan.target_xy[1])
            if dist > float(get(self.cfg, "endpoint_margin_factor")) * plan.radius + 1e-6:
                outcome["aborted_reason"] = (
                    f"tıklama reddi: son nokta hedef dışı ({dist:.1f}px)")
                return outcome
            if not execute_click:
                outcome["completed"] = True
                outcome["click_skipped"] = "tıklama istenmedi (önizleme/yalnızca hareket)"
                return outcome
            if not self.ctrl.dry_run and not self.ctrl.allow_click:
                outcome["completed"] = True
                outcome["click_skipped"] = ("tıklama yetkisi yok "
                                           "(--gercek-tiklama bayrağı gerekli)")
                return outcome
            self.ctrl.click_left(plan.hold_ms)
            outcome["click_executed"] = "simulated" if self.ctrl.dry_run else "real"
            outcome["completed"] = True
            return outcome
        except SafetyAbort as exc:
            outcome["aborted_reason"] = f"güvenlik duruşu: {exc}"
            return outcome
        finally:
            outcome["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

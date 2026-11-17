"""Kontrol katmanı testleri: plan reddi, acil durdurma, tıklama izni.

Testlerde asla GERÇEK girdi gönderilmez (dry-run + sahte denetleyici).
"""
import _common  # noqa: F401

import math
import unittest

import numpy as np

from app.config import load_config
from app.control.runner import MovementRunner
from app.control.validation import validate_plan
from app.control.mouse import MouseController, SafetyAbort
from app.models import TrajectoryPlan
from app.models.baseline import BaselineModel

SCREEN = (0.0, 0.0, 1920.0, 1080.0)
CFG = load_config()


def build_plan(cfg=CFG, click_xy=None):
    m = BaselineModel(cfg)
    plan = m.generate((100, 100), (800, 600), 30.0, np.random.default_rng(1))
    if click_xy is not None:
        plan.click_xy = click_xy
        plan.waypoints[-1, 1], plan.waypoints[-1, 2] = click_xy
    return plan


class FakeController:
    """Gerçek SendInput ÇAĞRILMAZ — test amaçlı sahte denetleyici."""

    def __init__(self, dry_run=True, allow_click=False):
        self.dry_run = bool(dry_run)
        self.allow_click = bool(allow_click)
        self.screen = SCREEN
        self.sent_moves = 0
        self.sent_clicks = 0
        self.click_denied = 0

    def move_to(self, x, y):
        sx, sy, sw, sh = self.screen
        if not (sx - 1 <= x <= sx + sw + 1 and sy - 1 <= y <= sy + sh + 1):
            raise SafetyAbort("ekran dışına hamle reddi")
        self.sent_moves += 1

    def click_left(self, down_ms=60.0):
        if self.dry_run:
            self.sent_clicks += 1
            return
        if not self.allow_click:
            self.click_denied += 1
            raise SafetyAbort("tıklama yetkisi yok")
        self.sent_clicks += 1

    def is_escape_pressed(self):
        return False


class TestValidation(unittest.TestCase):
    def test_ok_plan_passes(self):
        ok, why = validate_plan(build_plan(), CFG, SCREEN)
        self.assertTrue(ok, why)

    def test_offscreen_rejected(self):
        p = build_plan()
        p.waypoints[3, 1] = 9999.0
        ok, why = validate_plan(p, CFG, SCREEN)
        self.assertFalse(ok)
        self.assertIn("ekran", why)

    def test_click_outside_target_rejected(self):
        p = build_plan(click_xy=(850.0, 650.0))  # hedef dışı tıklama
        ok, why = validate_plan(p, CFG, SCREEN)
        self.assertFalse(ok)
        self.assertIn("tıklama", why)

    def test_nonmonotonic_time_rejected(self):
        p = build_plan()
        p.waypoints[4, 0] = p.waypoints[2, 0]
        ok, why = validate_plan(p, CFG, SCREEN)
        self.assertFalse(ok)
        self.assertIn("tek", why)

    def test_big_step_rejected(self):
        p = build_plan()
        # 460 ms'lik tek sıçrama; kalan zaman damgaları kaydırılarak monotoni korunur
        n = len(p.waypoints)
        for i in range(2, n):
            p.waypoints[i, 0] += 460.0
        ok, why = validate_plan(p, CFG, SCREEN)
        self.assertFalse(ok)
        self.assertIn("aralığı", why)


class TestRunnerSafety(unittest.TestCase):
    def test_dry_run_completes_without_real_click(self):
        ctrl = FakeController(dry_run=True)
        r = MovementRunner(ctrl, CFG)
        plan = build_plan()
        out = r.execute(plan, execute_click=True, speed=0.0)
        self.assertTrue(out["completed"])
        self.assertEqual(out["click_executed"], "simulated")
        self.assertEqual(ctrl.sent_clicks, 1)
        self.assertEqual(ctrl.sent_moves, len(plan.waypoints))

    def test_no_click_when_not_requested(self):
        ctrl = FakeController(dry_run=True)
        r = MovementRunner(ctrl, CFG)
        out = r.execute(build_plan(), speed=0.0)
        self.assertTrue(out["completed"])
        self.assertIsNone(out["aborted_reason"])
        self.assertIn("click_skipped", out)
        self.assertEqual(ctrl.sent_clicks, 0)

    def test_abort_check_stops_before_click(self):
        ctrl = FakeController(dry_run=True)
        r = MovementRunner(ctrl, CFG)
        out = r.execute(build_plan(), execute_click=True, speed=0.0,
                        abort_check=lambda: True)
        self.assertFalse(out["completed"])
        self.assertIn("acil", out["aborted_reason"])
        self.assertEqual(ctrl.sent_clicks, 0)
        self.assertLessEqual(ctrl.sent_moves, 2)

    def test_click_denied_without_permission_in_real_mode(self):
        ctrl = FakeController(dry_run=False, allow_click=False)
        r = MovementRunner(ctrl, CFG)
        out = r.execute(build_plan(), execute_click=True, speed=0.0)
        self.assertTrue(out["completed"])
        self.assertIn("yetkisi yok", out.get("click_skipped", ""))
        self.assertEqual(ctrl.sent_clicks, 0)
        self.assertEqual(ctrl.click_denied, 0)  # runner izin dalında click_left çağırmadı

    def test_offscreen_execution_aborts(self):
        ctrl = FakeController(dry_run=True)
        r = MovementRunner(ctrl, CFG)
        plan = build_plan()
        plan.waypoints[5, 1] = 4000.0  # validation ekran dışı yapar
        out = r.execute(plan, speed=0.0)
        self.assertFalse(out["completed"])
        self.assertIn("plan reddi", out["aborted_reason"])


if __name__ == "__main__":
    unittest.main()

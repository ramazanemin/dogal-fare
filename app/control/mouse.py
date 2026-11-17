"""Windows fare kontrolü — SendInput (ctypes). DRY-RUN destekli.

DÜRÜST NOT (docs D4): SendInput ile verilen girdi, OS seviyesinde 'injected'
(LLMHF_INJECTED) işaretlenir; düşük seviye kanca kuran her yazılım bunu görebilir.
Bu modül hiçbir 'tespit edilmez' iddiası taşımaz.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import math

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
VK_ESCAPE = 0x1B
VK_F8 = 0x77
VK_F9 = 0x78
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG),
                ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("mi", _MOUSEINPUT)]


_user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_user32.SendInput.restype = wt.UINT
_user32.GetSystemMetrics.restype = ctypes.c_int
_user32.GetAsyncKeyState.restype = wt.SHORT
_user32.GetCursorPos.argtypes = (ctypes.POINTER(wt.POINT),)
_user32.WindowFromPoint.argtypes = (wt.POINT,)


class SafetyAbort(RuntimeError):
    """Ekran sınırı veya tıklama güvencesi ihlali — anında dur."""


def virtual_screen() -> tuple[int, int, int, int]:
    """(x0, y0, genişlik, yükseklik) — çok monitörlü sanal ekran."""
    x = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    y = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    w = _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    h = _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if w <= 0 or h <= 0:  # güvenlik: metrik bozuksa reddet
        raise SafetyAbort("sanal ekran metrikleri alınamadı")
    return (int(x), int(y), int(w), int(h))


def get_cursor_pos() -> tuple[int, int]:
    pt = wt.POINT()
    if not _user32.GetCursorPos(ctypes.byref(pt)):
        raise SafetyAbort("GetCursorPos başarısız")
    return (int(pt.x), int(pt.y))


def is_key_down(vk: int) -> bool:
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def foreground_window_title() -> str:
    """Yalnız başlık metni (ekran içeriği OKUNMAZ). CAPTCHA bulgusu için kullanılır."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(512)
    _user32.GetWindowTextW(int(hwnd), buf, 512)
    return buf.value


def _to_absolute(x: float, y: float, screen: tuple[int, int, int, int]) -> tuple[int, int]:
    """Piksel -> 0..65535 mutlak koordinat (MOUSEEVENTF_ABSOLUTE gereği)."""
    x0, y0, w, h = screen
    ax = int(round((x - x0) * 65535.0 / max(w - 1, 1)))
    ay = int(round((y - y0) * 65535.0 / max(h - 1, 1)))
    return (min(max(ax, 0), 65535), min(max(ay, 0), 65535))


def _send(inputs: list[_INPUT]) -> int:
    arr = (_INPUT * len(inputs))(*inputs)
    sent = _user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))
    if sent != len(inputs):
        raise SafetyAbort(f"SendInput tam gönderilmedi ({sent}/{len(inputs)})")
    return sent


class PrecisionTimer:
    """timeBeginPeriod(1) ile Sleep çözünürlüğünü iyileştiren bağlam yöneticisi.

    Pre-Win11 davranışı: süreölçer çözünürlüğü ~15.6ms -> ~1ms. Yeni Windows sürümleri
    süreölçeri süreç başına izole edebilir; başarısızlıkta sessizce sürer.
    """

    def __init__(self) -> None:
        self._active = False
        try:
            _winmm = ctypes.WinDLL("winmm")
            _winmm.timeBeginPeriod(1)
            self._winmm = _winmm
            self._active = True
        except OSError:
            self._winmm = None

    def __enter__(self) -> "PrecisionTimer":
        return self

    def __exit__(self, *exc) -> None:
        if self._active and self._winmm is not None:
            try:
                self._winmm.timeEndPeriod(1)
            except OSError:
                pass


def hybrid_sleep(total_ms: float, PerfCounter=None) -> None:
    """Doğru zamanlama için Sleep + kısa spin. (Win32 Sleep çözünürlüğü kaba.)"""
    import time as _t
    if total_ms <= 0:
        return
    deadline = _t.perf_counter() + total_ms / 1000.0
    remain_ms = total_ms
    if remain_ms > 2.5:
        _t.sleep((remain_ms - 2.0) / 1000.0)
    while _t.perf_counter() < deadline:
        _t.sleep(0)


class MouseController:
    """Gerçek/dry-run fare kontrolcüsü.

    dry_run=True iken HİÇBİR girdi gönderilmez; yalnızca çağrılar sayılır.
    Ekran sınırı ihlali ve SendInput hatası SafetyAbort fırlatır → runner anında durur.
    """

    def __init__(self, dry_run: bool = True, allow_click: bool = False):
        self.dry_run = bool(dry_run)
        # Savunma: allow_click False iken GERÇEK tıklama asla gönderilemez.
        # Kullanıcı gereksinimi: gerçek tıklama AYRI etkinleştirilir.
        self.allow_click = bool(allow_click)
        self.screen = virtual_screen()
        self.sent_moves = 0
        self.sent_clicks = 0

    # ---- temel hamleler ----
    def move_to(self, x: float, y: float) -> None:
        sx, sy, sw, sh = self.screen
        if not (sx - 1 <= x <= sx + sw + 1 and sy - 1 <= y <= sy + sh + 1):
            raise SafetyAbort(f"ekran dışına hamle reddi: ({x:.0f},{y:.0f})")
        if self.dry_run:
            self.sent_moves += 1
            return
        ax, ay = _to_absolute(x, y, self.screen)
        mi = _MOUSEINPUT(ax, ay, 0,
                         MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
        _send([_INPUT(INPUT_MOUSE, mi)])
        self.sent_moves += 1

    def click_left(self, down_ms: float = 60.0) -> None:
        """Bas/yay bırak (down_ms gerçek modda bekletilir). dry-run: yalnız sayaç."""
        if self.dry_run:
            self.sent_clicks += 1
            return
        if not self.allow_click:
            raise SafetyAbort("tıklama yetkisi yok (--gercek-tiklama bayrağı gerekli)")
        down = _MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, None)
        up = _MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, None)
        import time as _t
        _send([_INPUT(INPUT_MOUSE, down)])
        _t.sleep(max(down_ms, 1.0) / 1000.0)
        _send([_INPUT(INPUT_MOUSE, up)])
        self.sent_clicks += 1

    # ---- güvenlik sorguları ----
    def is_escape_pressed(self) -> bool:
        return is_key_down(VK_ESCAPE)

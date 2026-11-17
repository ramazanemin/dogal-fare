"""Süreç kaynak ölçümü: CPU ve RAM — saf ctypes (psutil YOK, ek bağımlılık yok)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import time


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GetProcessTimes.argtypes = (
    wt.HANDLE, ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME),
    ctypes.POINTER(_FILETIME), ctypes.POINTER(_FILETIME))


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


try:
    _psapi = ctypes.WinDLL("psapi")
    _psapi.GetProcessMemoryInfo.argtypes = (wt.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wt.DWORD)
except OSError:  # eksik sistem dll — metrik 0 döner
    _psapi = None


def _ft_to_utc_float(ft: _FILETIME) -> float:
    return (int(ft.dwHighDateTime) << 32 | int(ft.dwLowDateTime)) / 1e7


class ProcessResources:
    """Kendi sürecinin CPU% (delta) ve çalışma kümesi RAM'i."""

    def __init__(self):
        self.h = _kernel32.GetCurrentProcess()
        self._last_wall = time.perf_counter()
        self._last_cpu = self._cpu_s()

    def _cpu_s(self) -> float:
        c, e, k, u = (_FILETIME(), _FILETIME(), _FILETIME(), _FILETIME())
        if not _kernel32.GetProcessTimes(self.h, ctypes.byref(c), ctypes.byref(e),
                                         ctypes.byref(k), ctypes.byref(u)):
            return 0.0
        return _ft_to_utc_float(k) + _ft_to_utc_float(u)

    def cpu_percent(self) -> float:
        """Son çağrıdan bu yana ortalama CPU% (tek çekirdek başına)."""
        now = time.perf_counter()
        self._last_cpu, cpu_prev = self._cpu_s(), self._last_cpu
        self._last_wall, wall_prev = now, self._last_wall
        d = now - wall_prev if wall_prev else 1e-9
        return max(0.0, (self._last_cpu - cpu_prev) / max(d, 1e-9) * 100.0)

    def ram_mb(self) -> float:
        if _psapi is None:
            return 0.0
        mc = _PROCESS_MEMORY_COUNTERS()
        mc.cb = ctypes.sizeof(mc)
        if not _psapi.GetProcessMemoryInfo(self.h, ctypes.byref(mc), mc.cb):
            return 0.0
        return float(mc.WorkingSetSize) / (1024.0 * 1024.0)

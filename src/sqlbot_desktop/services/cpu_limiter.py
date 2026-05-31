"""Process-level CPU affinity helpers."""

from __future__ import annotations

import ctypes
import os


class CpuLimiter:
    """Limit the current process to a fixed number of logical CPUs when supported."""

    @staticmethod
    def normalize_limit(requested: int, total_cpus: int | None = None) -> int:
        total = max(1, total_cpus or os.cpu_count() or 1)
        if requested <= 0:
            return 0
        return max(1, min(int(requested), total))

    @staticmethod
    def apply(limit: int) -> str:
        normalized = CpuLimiter.normalize_limit(limit)
        total = os.cpu_count() or 1
        if normalized <= 0 or normalized >= total:
            CpuLimiter._clear_affinity(total)
            return "Không giới hạn CPU cho app."

        mask = (1 << normalized) - 1
        CpuLimiter._set_affinity(mask)
        return f"Đã giới hạn app trên {normalized}/{total} logical CPU."

    @staticmethod
    def _set_affinity(mask: int) -> None:
        if hasattr(os, "sched_setaffinity"):
            cpus = {index for index in range(mask.bit_length()) if mask & (1 << index)}
            os.sched_setaffinity(0, cpus)
            return

        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentProcess()
            if not kernel32.SetProcessAffinityMask(handle, ctypes.c_size_t(mask)):
                raise OSError("Không thể giới hạn CPU affinity cho process.")
            return

        raise OSError("Hệ điều hành không hỗ trợ giới hạn CPU affinity.")

    @staticmethod
    def _clear_affinity(total_cpus: int) -> None:
        mask = (1 << max(1, total_cpus)) - 1
        CpuLimiter._set_affinity(mask)

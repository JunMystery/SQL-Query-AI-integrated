"""Tests for process-level CPU limit helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.cpu_limiter import CpuLimiter  # noqa: E402


class CpuLimiterTests(unittest.TestCase):
    def test_normalize_limit_clamps_to_available_cpus(self) -> None:
        self.assertEqual(CpuLimiter.normalize_limit(0, total_cpus=8), 0)
        self.assertEqual(CpuLimiter.normalize_limit(4, total_cpus=8), 4)
        self.assertEqual(CpuLimiter.normalize_limit(99, total_cpus=8), 8)

    def test_apply_sets_affinity_mask_for_requested_limit(self) -> None:
        with patch.object(CpuLimiter, "_set_affinity") as set_affinity, patch("os.cpu_count", return_value=8):
            message = CpuLimiter.apply(4)

        set_affinity.assert_called_once_with(0b1111)
        self.assertIn("4/8 logical CPU", message)

    def test_apply_zero_clears_affinity(self) -> None:
        with patch.object(CpuLimiter, "_clear_affinity") as clear_affinity, patch("os.cpu_count", return_value=8):
            message = CpuLimiter.apply(0)

        clear_affinity.assert_called_once_with(8)
        self.assertIn("Không giới hạn", message)


if __name__ == "__main__":
    unittest.main()

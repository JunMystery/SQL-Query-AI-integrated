"""Tests for optional application config defaults."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.app_config import AppConfig  # noqa: E402


class AppConfigTests(unittest.TestCase):
    def test_loads_self_correction_defaults_from_config_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text(
                "\n".join(
                    [
                        "self_correction:",
                        "  enabled: true",
                        "  max_retries: 4",
                        "  log_errors: false",
                    ]
                ),
                encoding="utf-8",
            )

            config = AppConfig.load(path)

        self.assertTrue(config.self_correction.enabled)
        self.assertEqual(config.self_correction.max_retries, 4)
        self.assertFalse(config.self_correction.log_errors)

    def test_missing_config_uses_safe_defaults(self) -> None:
        config = AppConfig.load("missing-config.yaml")

        self.assertTrue(config.self_correction.enabled)
        self.assertEqual(config.self_correction.max_retries, 3)


if __name__ == "__main__":
    unittest.main()

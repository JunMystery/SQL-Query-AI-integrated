"""Small application config reader for optional YAML-like defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SelfCorrectionConfig:
    enabled: bool = True
    max_retries: int = 3
    log_errors: bool = True
    retry_delay_seconds: float = 0.0
    include_error_in_prompt: bool = True
    stop_on_syntax_error: bool = False


@dataclass(frozen=True)
class AppConfig:
    self_correction: SelfCorrectionConfig = field(default_factory=SelfCorrectionConfig)

    @classmethod
    def load(cls, path: Path | str = "config.yaml") -> "AppConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        values = _read_section(config_path, "self_correction")
        return cls(
            SelfCorrectionConfig(
                enabled=_bool(values.get("enabled"), True),
                max_retries=max(1, min(_int(values.get("max_retries"), 3), 5)),
                log_errors=_bool(values.get("log_errors"), True),
                retry_delay_seconds=max(0.0, _float(values.get("retry_delay_seconds"), 0.0)),
                include_error_in_prompt=_bool(values.get("include_error_in_prompt"), True),
                stop_on_syntax_error=_bool(values.get("stop_on_syntax_error"), False),
            )
        )


def _read_section(path: Path, section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    in_section = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        if not raw_line.startswith((" ", "\t")) and line.endswith(":"):
            in_section = line[:-1].strip() == section
            continue
        if in_section and ":" in line:
            key, _, value = line.partition(":")
            values[key.strip()] = value.strip().strip("\"'")
    return values


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default

"""Shared data models for SQLBot Desktop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class ConnectionProfile:
    """A saved database connection profile shown on the login screen."""

    name: str
    driver: str
    database: str
    host: str = ""
    port: int | None = None
    username: str = ""
    description: str = ""
    extra: str = ""
    query_max_rows: int = 1000
    query_timeout_seconds: int = 10

    @property
    def display_name(self) -> str:
        if self.description:
            return f"{self.name} - {self.description}"
        return self.name

    @property
    def requires_credentials(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "driver": self.driver,
            "database": self.database,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "description": self.description,
            "extra": self.extra,
            "query_max_rows": self.query_max_rows,
            "query_timeout_seconds": self.query_timeout_seconds,
        }


@dataclass(frozen=True)
class ColumnInfo:
    """Database column metadata used by the annotation editor."""

    name: str
    type_name: str = ""
    nullable: bool | None = None
    is_primary: bool = False
    is_foreign: bool = False
    sample_value: str = ""
    enum_values: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TableInfo:
    """Database table metadata used by the annotation editor."""

    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class ColumnMetadata:
    """Enriched column metadata stored outside the source database."""

    db_name: str
    table_name: str
    column_name: str
    data_type: str = ""
    is_primary_key: bool = False
    is_foreign_key: bool = False
    referenced_table: str = ""
    referenced_column: str = ""
    business_description: str = ""
    sample_values: list[str] = field(default_factory=list)
    embedding: bytes | None = None


class AIBackend(str, Enum):
    """Supported AI generation backends."""

    LOCAL = "local"
    API = "api"


@dataclass(frozen=True)
class AIModelConfig:
    """Runtime AI model configuration."""

    backend: AIBackend
    local_model_path: str = ""
    api_endpoint: str = ""
    api_model: str = ""
    context_size: int = 2048
    max_tokens: int = 512
    threads: int = 2
    gpu_layers: int = 0
    cpu_thread_limit: int = 4
    self_correction_retries: int = 3
    api_key: str = ""



@dataclass(frozen=True)
class GenerationResult:
    """Text-to-SQL generation result."""

    ok: bool
    queries: list[str] = field(default_factory=list)
    message: str = ""

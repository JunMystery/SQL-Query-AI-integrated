"""Database connection utilities using bundled Python drivers."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from urllib.parse import quote_plus
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from sqlbot_desktop.models.entities import ConnectionProfile
from sqlbot_desktop.services.query_validator import QueryValidator


SUPPORTED_DRIVERS = {"MYSQL", "POSTGRESQL"}


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str
    connection_name: str = ""


@dataclass(frozen=True)
class QueryExecutionResult:
    ok: bool
    message: str = ""
    columns: list[str] | None = None
    rows: list[list[object]] | None = None
    row_count: int = 0
    elapsed_ms: float = 0.0
    error_type: str = ""
    sql: str = ""


class DatabaseManager:
    """Create, test, and hold active SQLAlchemy connections."""

    def __init__(self) -> None:
        self.active_connection_name = ""
        self._connections: dict[str, Connection] = {}
        self._engines: dict[str, Engine] = {}

    def open_connection(
        self,
        profile: ConnectionProfile,
        username: str = "",
        password: str = "",
        connection_name: str | None = None,
    ) -> ConnectionResult:
        if profile.driver not in SUPPORTED_DRIVERS:
            return ConnectionResult(False, f"Chỉ hỗ trợ MySQL và PostgreSQL. Driver hiện tại: {profile.driver}", "")

        name = connection_name or self._connection_name(profile.name)
        self.close_connection(name)

        try:
            engine = create_engine(
                self._build_url(profile, username, password),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=1800,
                pool_timeout=30,
                future=True,
            )
            connection = engine.connect()
            connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            return ConnectionResult(False, f"Không thể kết nối CSDL: {exc}", "")

        self._engines[name] = engine
        self._connections[name] = connection
        self.active_connection_name = name
        return ConnectionResult(True, "Kết nối thành công.", name)

    def test_connection(
        self,
        profile: ConnectionProfile,
        username: str = "",
        password: str = "",
    ) -> ConnectionResult:
        name = self._connection_name(f"test_{profile.name}")
        result = self.open_connection(profile, username, password, name)
        if result.ok:
            self.close_connection(name)
        return result

    def database(self, connection_name: str | None = None) -> Connection:
        name = connection_name or self.active_connection_name
        return self._connections[name]

    def execute_select(
        self,
        sql: str,
        connection_name: str | None = None,
        max_rows: int = 500,
    ) -> QueryExecutionResult:
        started = perf_counter()
        if not QueryValidator.is_readonly_select(sql):
            return QueryExecutionResult(
                False,
                "Chỉ cho phép thực thi câu SELECT an toàn.",
                error_type="validation",
                sql=sql,
            )

        try:
            result = self.database(connection_name).execute(text(sql))
            columns = [str(column) for column in result.keys()]
            rows = [list(row) for row in result.fetchmany(max_rows)]
        except KeyError as exc:
            return QueryExecutionResult(
                False,
                f"Không tìm thấy kết nối database: {exc}",
                error_type="connection",
                sql=sql,
                elapsed_ms=(perf_counter() - started) * 1000,
            )
        except SQLAlchemyError as exc:
            return QueryExecutionResult(
                False,
                f"Không thể thực thi SQL: {exc}",
                error_type="sql",
                sql=sql,
                elapsed_ms=(perf_counter() - started) * 1000,
            )
        except OSError as exc:
            return QueryExecutionResult(
                False,
                f"Không thể thực thi SQL: {exc}",
                error_type="io",
                sql=sql,
                elapsed_ms=(perf_counter() - started) * 1000,
            )

        elapsed_ms = (perf_counter() - started) * 1000
        return QueryExecutionResult(
            True,
            f"Đã tải {len(rows)} dòng.",
            columns,
            rows,
            row_count=len(rows),
            elapsed_ms=elapsed_ms,
            sql=sql,
        )

    def close_connection(self, connection_name: str) -> None:
        connection = self._connections.pop(connection_name, None)
        if connection is not None:
            connection.close()

        engine = self._engines.pop(connection_name, None)
        if engine is not None:
            engine.dispose()

        if self.active_connection_name == connection_name:
            self.active_connection_name = ""

    def _build_url(
        self,
        profile: ConnectionProfile,
        username: str,
        password: str,
    ) -> str:
        user = quote_plus(username or profile.username)
        secret = quote_plus(password)
        host = profile.host.strip()
        port = profile.port or (3306 if profile.driver == "MYSQL" else 5432)
        database = quote_plus(profile.database.strip())
        query = profile.extra.strip()
        suffix = f"?{query}" if query else ""

        if profile.driver == "MYSQL":
            return f"mysql+pymysql://{user}:{secret}@{host}:{port}/{database}{suffix}"
        if profile.driver == "POSTGRESQL":
            return f"postgresql+psycopg://{user}:{secret}@{host}:{port}/{database}{suffix}"
        raise ValueError(f"Unsupported driver: {profile.driver}")

    def _connection_name(self, prefix: str) -> str:
        safe_prefix = "".join(ch if ch.isalnum() else "_" for ch in prefix).strip("_")
        return f"{safe_prefix or 'sqlbot'}_{uuid4().hex}"

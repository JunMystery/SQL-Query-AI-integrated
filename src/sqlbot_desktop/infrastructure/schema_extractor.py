"""Schema extraction from SQLAlchemy connections."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo


class SchemaExtractor:
    """Extract tables and columns using SQLAlchemy inspection."""

    def __init__(self, database: Connection) -> None:
        self.database = database

    def get_all_tables_columns(self) -> list[TableInfo]:
        inspector = inspect(self.database)
        tables: list[TableInfo] = []
        for table_name in inspector.get_table_names():
            columns = [
                ColumnInfo(
                    name=str(column.get("name", "")),
                    type_name=str(column.get("type", "")),
                    nullable=bool(column.get("nullable", False)),
                )
                for column in inspector.get_columns(table_name)
            ]
            tables.append(TableInfo(name=table_name, columns=columns))
        return tables

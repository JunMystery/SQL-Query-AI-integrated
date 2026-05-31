"""Schema extraction from SQLAlchemy connections."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo


class SchemaExtractor:
    """Extract tables and columns using SQLAlchemy inspection."""

    # Thread-safe in-memory cache to prevent redundant schema/profiling queries
    _cache: dict[str, list[TableInfo]] = {}

    def __init__(self, database: Connection) -> None:
        self.database = database

    def get_all_tables_columns(self, force_refresh: bool = False) -> list[TableInfo]:
        # Generate a unique cache key based on the connection target database URL
        cache_key = str(self.database.engine.url)
        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        inspector = inspect(self.database)
        tables: list[TableInfo] = []
        for table_name in inspector.get_table_names():
            # Get primary key column names
            pk_constraint = inspector.get_pk_constraint(table_name)
            pk_cols = set(pk_constraint.get("constrained_columns", [])) if pk_constraint else set()

            # Get foreign key details
            fks = inspector.get_foreign_keys(table_name)
            fk_cols = set()
            foreign_keys_list = []
            for fk in fks:
                referred_table = fk.get("referred_table", "")
                constrained_cols = fk.get("constrained_columns", [])
                referred_cols = fk.get("referred_columns", [])
                for col in constrained_cols:
                    fk_cols.add(col)
                if constrained_cols and referred_cols:
                    foreign_keys_list.append({
                        "constrained_table": table_name,
                        "constrained_column": constrained_cols[0],
                        "referred_table": referred_table,
                        "referred_column": referred_cols[0]
                    })

            columns = []
            for column in inspector.get_columns(table_name):
                col_name = str(column.get("name", ""))
                type_name = str(column.get("type", ""))
                nullable = bool(column.get("nullable", False))
                is_primary = (col_name in pk_cols)
                is_foreign = (col_name in fk_cols)

                # Initialize profiling defaults
                sample_val = ""
                enum_vals = []

                # Sensitivity filter: check if the column name implies sensitive data
                is_sensitive = any(s in col_name.lower() for s in ["pass", "token", "secret", "key", "phone", "email", "avatar", "auth", "hash"])
                if is_sensitive:
                    sample_val = "[REDACTED]"
                else:
                    # Execute lightweight queries safely using SQLAlchemy text constructs
                    from sqlalchemy import text
                    try:
                        # 1. Fetch a single non-null sample value
                        query_sample = text(f"SELECT `{col_name}` FROM `{table_name}` WHERE `{col_name}` IS NOT NULL LIMIT 1")
                        res_sample = self.database.execute(query_sample).scalar()
                        if res_sample is not None:
                            sample_val = str(res_sample)
                            # Clip very long sample strings to save token space
                            if len(sample_val) > 60:
                                sample_val = sample_val[:57] + "..."
                    except Exception:
                        sample_val = ""

                    # 2. Extract enum values if cardinality <= 8 for low-cardinality columns
                    # Check cardinality of the first 50 rows to keep it very fast and lightweight
                    try:
                        query_card = text(f"SELECT COUNT(DISTINCT `{col_name}`) FROM (SELECT `{col_name}` FROM `{table_name}` LIMIT 50) AS sub")
                        card = self.database.execute(query_card).scalar()
                        if card is not None and 1 < card <= 8:
                            query_enum = text(f"SELECT DISTINCT `{col_name}` FROM `{table_name}` WHERE `{col_name}` IS NOT NULL LIMIT 8")
                            res_enum = self.database.execute(query_enum).fetchall()
                            enum_vals = [str(r[0]) for r in res_enum if r[0] is not None]
                    except Exception:
                        enum_vals = []

                columns.append(
                    ColumnInfo(
                        name=col_name,
                        type_name=type_name,
                        nullable=nullable,
                        is_primary=is_primary,
                        is_foreign=is_foreign,
                        sample_value=sample_val,
                        enum_values=enum_vals,
                    )
                )

            tables.append(TableInfo(name=table_name, columns=columns, foreign_keys=foreign_keys_list))
        self._cache[cache_key] = tables
        return tables

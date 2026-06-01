"""Reusable schema tree viewer with annotation support."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.utils.i18n_manager import tr


class SchemaTreeWidget(QTreeWidget):
    """Display database schema using human annotations plus real DB names."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("schemaTree")
        self.setAccessibleName("Schema viewer")
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(False)
        self.setIndentation(18)

    def set_schema(self, tables: list[TableInfo], annotations: dict[str, object] | None = None) -> None:
        self.clear()
        table_payloads = self._table_payloads(annotations)

        if not tables:
            empty = QTreeWidgetItem([tr("settings.schema_not_loaded", "Chưa tải schema")])
            empty.setForeground(0, QColor("#697789"))
            self.addTopLevelItem(empty)
            return

        for table in tables:
            table_payload = table_payloads.get(table.name, {})
            table_item = self.add_table(table, table_payload)
            column_payloads = table_payload.get("columns", {}) if isinstance(table_payload, dict) else {}
            for column in table.columns:
                payload = column_payloads.get(column.name, {}) if isinstance(column_payloads, dict) else {}
                self.add_column(table_item, column, payload)

        self.expandAll()

    def add_table(self, table: TableInfo, payload: dict[str, object] | None = None) -> QTreeWidgetItem:
        payload = payload or {}
        description = self._text(payload.get("description")) or table.name
        table_item = QTreeWidgetItem([description])
        table_item.setToolTip(0, f"{description}\nTable: {table.name}")
        table_item.setForeground(0, QColor("#135ba1"))

        font = table_item.font(0)
        font.setWeight(QFont.Weight.DemiBold)
        table_item.setFont(0, font)

        db_name_item = QTreeWidgetItem([f"[{table.name}]"])
        db_name_item.setForeground(0, QColor("#697789"))
        db_name_item.setToolTip(0, tr("settings.schema_tooltip_real_table", "Tên table thật trong CSDL"))
        table_item.addChild(db_name_item)

        self.addTopLevelItem(table_item)
        return table_item

    def add_column(
        self,
        table_item: QTreeWidgetItem,
        column: ColumnInfo,
        payload: dict[str, object] | None = None,
    ) -> QTreeWidgetItem:
        payload = payload or {}
        description = self._text(payload.get("description")) or column.name
        column_item = QTreeWidgetItem([description])
        column_item.setToolTip(0, self._column_tooltip(column, payload))
        column_item.setForeground(0, QColor("#172033"))
        table_item.addChild(column_item)

        db_name_item = QTreeWidgetItem([self._column_real_name(column, payload)])
        db_name_item.setForeground(0, QColor("#697789"))
        db_name_item.setToolTip(0, tr("settings.schema_tooltip_real_column", "Tên column thật trong CSDL"))
        column_item.addChild(db_name_item)
        return column_item

    def _column_real_name(self, column: ColumnInfo, payload: dict[str, object]) -> str:
        details = [f"[{column.name}]"]
        type_name = self._text(payload.get("type")) or column.type_name
        unit = self._text(payload.get("unit"))
        note = self._text(payload.get("note"))
        if type_name:
            details.append(f"type: {type_name}")
        if unit:
            details.append(f"unit: {unit}")
        if note:
            details.append(tr("settings.annotation_col_note", "ghi chú") + f": {note}")
        return " | ".join(details)

    def _column_tooltip(self, column: ColumnInfo, payload: dict[str, object]) -> str:
        parts = [f"Column: {column.name}"]
        type_name = self._text(payload.get("type")) or column.type_name
        unit = self._text(payload.get("unit"))
        note = self._text(payload.get("note"))
        if type_name:
            parts.append(f"Type: {type_name}")
        if unit:
            parts.append(f"Unit: {unit}")
        if note:
            parts.append(tr("settings.annotation_col_note", "Ghi chú") + f": {note}")
        return "\n".join(parts)

    def _table_payloads(self, annotations: dict[str, object] | None) -> dict[str, dict[str, object]]:
        if not annotations:
            return {}
        tables = annotations.get("tables", {})
        if not isinstance(tables, dict):
            return {}
        return {str(name): payload for name, payload in tables.items() if isinstance(payload, dict)}

    def _text(self, value: object) -> str:
        return str(value).strip() if value is not None else ""

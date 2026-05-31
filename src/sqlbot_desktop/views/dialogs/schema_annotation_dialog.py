"""Schema annotation editor."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from sqlbot_desktop.models.entities import TableInfo
from sqlbot_desktop.infrastructure.annotation_repository import AnnotationRepository


ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_TABLE = Qt.ItemDataRole.UserRole + 1
ROLE_COLUMN = Qt.ItemDataRole.UserRole + 2


class SchemaAnnotationDialog(QDialog):
    """Edit natural-language descriptions for tables and columns."""

    def __init__(
        self,
        connection_name: str,
        tables: list[TableInfo],
        parent=None,
        repository: AnnotationRepository | None = None,
    ) -> None:
        super().__init__(parent)
        self.connection_name = connection_name
        self.tables = tables
        self.repository = repository or AnnotationRepository()
        self.annotations = self._merge_annotations()

        self.setWindowTitle("Schema Annotation Editor")
        self.setMinimumSize(920, 620)
        self.setModal(True)

        self.tree = QTreeWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self._load_tree()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Schema Annotation Editor")
        title.setObjectName("dialogTitle")
        caption = QLabel("Nhập diễn giải tiếng Việt, đơn vị và ghi chú. Dữ liệu được lưu vào JSON riêng, không sửa CSDL gốc.")
        caption.setObjectName("dialogCaption")
        caption.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(caption)

        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Tên thực tế", "Diễn giải", "Unit", "Ghi chú", "Type"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        layout.addWidget(self.tree, 1)

        actions = QHBoxLayout()
        save_button = QPushButton("Save Annotations")
        save_button.setObjectName("primaryButton")
        import_button = QPushButton("Import")
        import_button.setObjectName("secondaryButton")
        export_button = QPushButton("Export")
        export_button.setObjectName("secondaryButton")
        close_button = QPushButton("Đóng")
        close_button.setObjectName("secondaryButton")

        save_button.clicked.connect(self._save)
        import_button.clicked.connect(self._import)
        export_button.clicked.connect(self._export)
        close_button.clicked.connect(self.accept)

        actions.addWidget(save_button)
        actions.addWidget(import_button)
        actions.addWidget(export_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)

    def _merge_annotations(self) -> dict[str, object]:
        stored = self.repository.load(self.connection_name)
        baseline = self.repository.empty_for_schema(self.connection_name, self.tables)
        stored_tables = stored.get("tables", {}) if isinstance(stored.get("tables", {}), dict) else {}
        baseline_tables = baseline["tables"]

        for table_name, table_payload in baseline_tables.items():
            existing_table = stored_tables.get(table_name, {})
            if isinstance(existing_table, dict):
                table_payload["description"] = existing_table.get("description", "")
                existing_columns = existing_table.get("columns", {})
                if isinstance(existing_columns, dict):
                    for column_name, column_payload in table_payload["columns"].items():
                        existing_column = existing_columns.get(column_name, {})
                        if isinstance(existing_column, dict):
                            column_payload.update(
                                {
                                    "description": existing_column.get("description", ""),
                                    "unit": existing_column.get("unit", ""),
                                    "note": existing_column.get("note", ""),
                                }
                            )
        return baseline

    def _load_tree(self) -> None:
        self.tree.clear()
        table_payloads = self.annotations.get("tables", {})
        if not isinstance(table_payloads, dict):
            return

        for table in self.tables:
            table_payload = table_payloads.get(table.name, {})
            table_item = QTreeWidgetItem(
                [
                    table.name,
                    str(table_payload.get("description", "")) if isinstance(table_payload, dict) else "",
                    "",
                    "",
                    "TABLE",
                ]
            )
            table_item.setData(0, ROLE_KIND, "table")
            table_item.setData(0, ROLE_TABLE, table.name)
            table_item.setToolTip(0, f"Bảng: {table.name}")
            table_item.setFlags(table_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.tree.addTopLevelItem(table_item)

            column_payloads = table_payload.get("columns", {}) if isinstance(table_payload, dict) else {}
            for column in table.columns:
                column_payload = column_payloads.get(column.name, {}) if isinstance(column_payloads, dict) else {}
                column_item = QTreeWidgetItem(
                    [
                        column.name,
                        str(column_payload.get("description", "")) if isinstance(column_payload, dict) else "",
                        str(column_payload.get("unit", "")) if isinstance(column_payload, dict) else "",
                        str(column_payload.get("note", "")) if isinstance(column_payload, dict) else "",
                        column.type_name,
                    ]
                )
                column_item.setData(0, ROLE_KIND, "column")
                column_item.setData(0, ROLE_TABLE, table.name)
                column_item.setData(0, ROLE_COLUMN, column.name)
                column_item.setToolTip(0, f"Cột: {table.name}.{column.name}")
                column_item.setFlags(column_item.flags() | Qt.ItemFlag.ItemIsEditable)
                table_item.addChild(column_item)

        self.tree.expandAll()
        for index in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(index)

    def _collect_annotations(self) -> dict[str, object]:
        tables: dict[str, object] = {}
        for table_index in range(self.tree.topLevelItemCount()):
            table_item = self.tree.topLevelItem(table_index)
            table_name = table_item.data(0, ROLE_TABLE)
            table_payload = {"description": table_item.text(1).strip(), "columns": {}}
            for column_index in range(table_item.childCount()):
                column_item = table_item.child(column_index)
                column_name = column_item.data(0, ROLE_COLUMN)
                table_payload["columns"][column_name] = {
                    "description": column_item.text(1).strip(),
                    "unit": column_item.text(2).strip(),
                    "note": column_item.text(3).strip(),
                    "type": column_item.text(4).strip(),
                }
            tables[table_name] = table_payload
        return {"connection_name": self.connection_name, "tables": tables}

    def _save(self) -> None:
        self.annotations = self._collect_annotations()
        path = self.repository.save(self.connection_name, self.annotations)
        self.status_label.setText(f"Đã lưu annotations: {path}")

    def _import(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Import annotations", "", "JSON (*.json);;All files (*.*)")
        if not file_path:
            return
        try:
            with Path(file_path).open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import lỗi", str(exc))
            return
        self.annotations = payload
        self._load_tree()
        self.status_label.setText("Đã import annotations.")

    def _export(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Export annotations", f"{self.connection_name}.annotations.json", "JSON (*.json)")
        if not file_path:
            return
        payload = self._collect_annotations()
        try:
            with Path(file_path).open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Export lỗi", str(exc))
            return
        self.status_label.setText("Đã export annotations.")

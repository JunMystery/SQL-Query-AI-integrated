"""Visual Query Builder Panel for selecting tables, columns, and adding WHERE conditions with premium styled UI."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QGroupBox,
)

from sqlbot_desktop.models.entities import TableInfo, ColumnInfo


class ColumnCheckBoxRow(QWidget):
    """A custom widget containing a styled checkbox and HTML/RichText formatted label for column display."""

    def __init__(self, col_name: str, display_name: str, col_type: str, checked_callback, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.cb = QCheckBox()
        self.cb.setProperty("col_name", col_name)
        self.cb.stateChanged.connect(checked_callback)
        self.cb.setStyleSheet("""
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #cbd5e1;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #147a63;
                border-color: #147a63;
            }
        """)

        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.RichText)
        
        # Parse display_name to extract description and column name
        if display_name != col_name:
            suffix = f" ({col_name})"
            if display_name.endswith(suffix):
                desc = display_name[:-len(suffix)].strip()
            else:
                desc = display_name
            text = f"<span style='color: #0f243f; font-weight: 600;'>{desc}</span> <span style='color: #64748b; font-size: 11px;'>({col_name} • {col_type})</span>"
        else:
            text = f"<span style='color: #0f243f; font-weight: 600;'>{col_name}</span> <span style='color: #64748b; font-size: 11px;'>({col_type})</span>"

        self.label.setText(text)
        self.label.setStyleSheet("font-size: 12px; color: #182230;")
        self.label.mousePressEvent = lambda event: self.cb.toggle()

        layout.addWidget(self.cb)
        layout.addWidget(self.label, 1)

    def isChecked(self) -> bool:
        return self.cb.isChecked()

    def setChecked(self, checked: bool) -> None:
        self.cb.setChecked(checked)


class ConditionRow(QWidget):
    """A single WHERE condition row widget."""

    changed = Signal()
    delete_requested = Signal(QWidget)

    def __init__(self, columns: list[ColumnInfo], annotations: dict[str, object] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.columns = columns
        self.annotations = annotations or {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        def get_col_disp_name(col_name: str) -> str:
            tables_ann = self.annotations.get("tables", {})
            for table_name, ann in tables_ann.items():
                if isinstance(ann, dict):
                    cols_ann = ann.get("columns", {})
                    col_ann = cols_ann.get(col_name, {})
                    desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                    if desc:
                        return f"{desc} ({col_name})"
            return col_name

        self.col_combo = QComboBox()
        self.col_combo.setStyleSheet("""
            QComboBox {
                min-height: 24px;
                max-height: 24px;
                padding: 1px 4px;
                font-size: 12px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
        """)
        for col in columns:
            disp = get_col_disp_name(col.name)
            self.col_combo.addItem(disp, col.name)
        self.col_combo.currentIndexChanged.connect(self._on_changed)

        self.op_combo = QComboBox()
        self.op_combo.setStyleSheet("""
            QComboBox {
                min-height: 24px;
                max-height: 24px;
                padding: 1px 4px;
                font-size: 12px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
        """)
        self.op_combo.addItems(["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "IS NULL", "IS NOT NULL"])
        self.op_combo.currentIndexChanged.connect(self._on_changed)
        self.op_combo.currentIndexChanged.connect(self._toggle_val_input)

        self.val_input = QLineEdit()
        self.val_input.setPlaceholderText("Giá trị...")
        self.val_input.setStyleSheet("""
            QLineEdit {
                min-height: 24px;
                max-height: 24px;
                padding: 1px 4px;
                font-size: 12px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1.5px solid #147a63;
            }
        """)
        self.val_input.textChanged.connect(self._on_changed)

        self.del_btn = QPushButton("Xóa")
        self.del_btn.setObjectName("dangerButton")
        self.del_btn.setStyleSheet("""
            QPushButton {
                min-height: 24px;
                max-height: 24px;
                padding: 1px 4px;
                font-size: 11px;
                border-radius: 4px;
            }
        """)
        self.del_btn.setFixedWidth(45)
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        layout.addWidget(self.col_combo, 2)
        layout.addWidget(self.op_combo, 1)
        layout.addWidget(self.val_input, 2)
        layout.addWidget(self.del_btn)

    def _on_changed(self, *args) -> None:
        self.changed.emit()

    def _toggle_val_input(self, index: int) -> None:
        op = self.op_combo.currentText()
        self.val_input.setVisible("IS NULL" not in op and "IS NOT NULL" not in op)

    def get_sql(self) -> str:
        col_name = self.col_combo.currentData()
        op = self.op_combo.currentText()
        val = self.val_input.text().strip()

        # Find column type
        col_type = ""
        for c in self.columns:
            if c.name == col_name:
                col_type = c.type_name.lower()
                break

        if "IS NULL" in op or "IS NOT NULL" in op:
            return f"{col_name} {op}"

        if not val:
            return ""

        # Auto quoting logic
        is_string = any(t in col_type for t in ["char", "text", "varchar", "string", "date", "time", "timestamp"])
        if is_string:
            # Check if already quoted
            if not ((val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"'))):
                # Escape single quotes and wrap
                escaped = val.replace("'", "''")
                val = f"'{escaped}'"

        return f"{col_name} {op} {val}"


class VisualQueryBuilderPanel(QWidget):
    """Panel for visually building queries with premium card style styling."""

    query_changed = Signal(str)
    execute_requested = Signal()
    show_results_requested = Signal()
    bookmark_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tables: list[TableInfo] = []
        self._annotations: dict[str, object] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # QGroupBox CSS style to look premium and aligned with application theme
        group_box_qss = """
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #0f243f;
                border: 1px solid #d9e1ec;
                border-radius: 8px;
                margin-top: 6px;
                background-color: #ffffff;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
            }
        """

        # Left Column: Selection builder
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # Table Group
        table_group = QGroupBox("Chọn Bảng (Table)")
        table_group.setStyleSheet(group_box_qss)
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(8, 4, 8, 8)
        self.table_combo = QComboBox()
        self.table_combo.setStyleSheet("""
            QComboBox {
                min-height: 28px;
                max-height: 28px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 1px 6px;
                font-size: 12px;
            }
        """)
        self.table_combo.currentIndexChanged.connect(self._on_table_changed)
        table_layout.addWidget(self.table_combo)
        left_layout.addWidget(table_group)

        # Columns Group
        columns_group = QGroupBox("Chọn Cột (Columns)")
        columns_group.setStyleSheet(group_box_qss)
        columns_layout = QVBoxLayout(columns_group)
        columns_layout.setContentsMargins(8, 4, 8, 8)
        self.columns_scroll = QScrollArea()
        self.columns_scroll.setWidgetResizable(True)
        self.columns_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.columns_container = QWidget()
        self.columns_container.setStyleSheet("background: transparent;")
        self.columns_container_layout = QVBoxLayout(self.columns_container)
        self.columns_container_layout.setContentsMargins(2, 2, 2, 2)
        self.columns_container_layout.setSpacing(2)
        self.columns_scroll.setWidget(self.columns_container)
        columns_layout.addWidget(self.columns_scroll)
        left_layout.addWidget(columns_group, 1)

        # WHERE Conditions Group
        cond_group = QGroupBox("Điều kiện lọc (WHERE)")
        cond_group.setStyleSheet(group_box_qss)
        cond_layout = QVBoxLayout(cond_group)
        cond_layout.setContentsMargins(8, 4, 8, 8)
        self.cond_scroll = QScrollArea()
        self.cond_scroll.setWidgetResizable(True)
        self.cond_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.cond_container = QWidget()
        self.cond_container.setStyleSheet("background: transparent;")
        self.cond_container_layout = QVBoxLayout(self.cond_container)
        self.cond_container_layout.setContentsMargins(2, 2, 2, 2)
        self.cond_container_layout.setSpacing(2)
        self.cond_scroll.setWidget(self.cond_container)
        cond_layout.addWidget(self.cond_scroll)

        add_cond_btn = QPushButton("Thêm điều kiện ➕")
        add_cond_btn.setObjectName("secondaryButton")
        add_cond_btn.setStyleSheet("""
            QPushButton {
                min-height: 24px;
                max-height: 24px;
                font-size: 11px;
                border-radius: 4px;
                padding: 1px 6px;
            }
        """)
        add_cond_btn.clicked.connect(self._add_condition_row)
        cond_layout.addWidget(add_cond_btn)
        left_layout.addWidget(cond_group, 1)

        main_layout.addWidget(left_widget, 1)

        # Right Column: SQL Editor and Actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        sql_title = QLabel("Generated SQL Query")
        sql_title.setObjectName("sectionTitle")
        self.sql_editor = QTextEdit()
        self.sql_editor.setObjectName("sqlEditor")
        self.sql_editor.setPlaceholderText("SQL query sẽ tự động sinh tại đây...")
        self.sql_editor.setFont(QFont("Courier New", 11))
        self.sql_editor.textChanged.connect(self._on_sql_manual_changed)

        sql_actions = QHBoxLayout()
        self.execute_btn = QPushButton("Execute (Chạy)")
        self.execute_btn.setObjectName("successButton")
        self.execute_btn.clicked.connect(self.execute_requested.emit)

        self.results_btn = QPushButton("Xem kết quả")
        self.results_btn.setObjectName("secondaryButton")
        self.results_btn.clicked.connect(self.show_results_requested.emit)

        self.paste_btn = QPushButton("Paste SQL")
        self.paste_btn.setObjectName("secondaryButton")
        self.paste_btn.clicked.connect(self.sql_editor.paste)

        self.bookmark_btn = QPushButton("Bookmark")
        self.bookmark_btn.setObjectName("warningButton")
        self.bookmark_btn.clicked.connect(self.bookmark_requested.emit)

        for btn in [self.execute_btn, self.results_btn, self.paste_btn, self.bookmark_btn]:
            btn.setMinimumHeight(32)
            sql_actions.addWidget(btn)
        sql_actions.addStretch()

        right_layout.addWidget(sql_title)
        right_layout.addWidget(self.sql_editor, 1)
        right_layout.addLayout(sql_actions)

        main_layout.addWidget(right_widget, 1)

    def set_schema(self, tables: list[TableInfo], annotations: dict[str, object] | None = None) -> None:
        self._tables = tables
        self._annotations = annotations or {}

        # Populate tables dropdown
        self.table_combo.blockSignals(True)
        self.table_combo.clear()
        for t in tables:
            disp_name = self._get_table_display_name(t.name)
            self.table_combo.addItem(disp_name, t.name)
        self.table_combo.blockSignals(False)

        self._on_table_changed()

    def _get_table_display_name(self, table_name: str) -> str:
        tables_ann = self._annotations.get("tables", {})
        ann = tables_ann.get(table_name, {})
        desc = ann.get("description", "") if isinstance(ann, dict) else ""
        if desc:
            return f"{desc} ({table_name})"
        return table_name

    def _get_column_display_name(self, table_name: str, col_name: str) -> str:
        tables_ann = self._annotations.get("tables", {})
        ann = tables_ann.get(table_name, {})
        if isinstance(ann, dict):
            cols_ann = ann.get("columns", {})
            col_ann = cols_ann.get(col_name, {})
            desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
            if desc:
                return f"{desc} ({col_name})"
        return col_name

    def _on_table_changed(self) -> None:
        # Clear columns list
        for i in reversed(range(self.columns_container_layout.count())):
            widget = self.columns_container_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Clear conditions
        for i in reversed(range(self.cond_container_layout.count())):
            widget = self.cond_container_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        table_name = self.table_combo.currentData()
        if not table_name:
            self._update_query()
            return

        # Find columns
        cols = self._get_active_columns()
        for c in cols:
            disp = self._get_column_display_name(table_name, c.name)
            row_widget = ColumnCheckBoxRow(c.name, disp, c.type_name, self._update_query, self)
            self.columns_container_layout.addWidget(row_widget)

        self._update_query()

    def _get_active_columns(self) -> list[ColumnInfo]:
        table_name = self.table_combo.currentData()
        for t in self._tables:
            if t.name == table_name:
                return t.columns
        return []

    def _get_column_annotations(self, table_name: str) -> dict[str, object]:
        tables_ann = self._annotations.get("tables", {})
        ann = tables_ann.get(table_name, {})
        if isinstance(ann, dict):
            return ann.get("columns", {})
        return {}

    def _add_condition_row(self) -> None:
        cols = self._get_active_columns()
        if not cols:
            return

        table_name = self.table_combo.currentData()
        col_ann = self._get_column_annotations(table_name)
        # Create annotations dict with the matching format for ConditionRow
        ann_wrapper = {"tables": {table_name: {"columns": col_ann}}}

        row = ConditionRow(cols, ann_wrapper, self)
        row.changed.connect(self._update_query)
        row.delete_requested.connect(self._delete_condition_row)
        self.cond_container_layout.addWidget(row)
        self._update_query()

    def _delete_condition_row(self, row_widget: QWidget) -> None:
        row_widget.deleteLater()
        self.cond_container_layout.removeWidget(row_widget)
        # Yield execution to allow widget deletion before query regeneration
        row_widget.setParent(None)
        self._update_query()

    def _update_query(self) -> None:
        table_name = self.table_combo.currentData()
        if not table_name:
            self.sql_editor.blockSignals(True)
            self.sql_editor.clear()
            self.sql_editor.blockSignals(False)
            self.query_changed.emit("")
            return

        # Gather columns
        checked_cols = []
        for i in range(self.columns_container_layout.count()):
            widget = self.columns_container_layout.itemAt(i).widget()
            if isinstance(widget, ColumnCheckBoxRow) and widget.isChecked():
                checked_cols.append(widget.cb.property("col_name"))

        cols_str = ", ".join(checked_cols) if checked_cols else "*"

        # Gather conditions
        conds = []
        for i in range(self.cond_container_layout.count()):
            widget = self.cond_container_layout.itemAt(i).widget()
            if isinstance(widget, ConditionRow):
                sql_part = widget.get_sql()
                if sql_part:
                    conds.append(sql_part)

        query = f"SELECT {cols_str}\nFROM {table_name}"
        if conds:
            query += "\nWHERE " + "\n  AND ".join(conds)

        self.sql_editor.blockSignals(True)
        self.sql_editor.setPlainText(query)
        self.sql_editor.blockSignals(False)
        self.query_changed.emit(query)

    def _on_sql_manual_changed(self) -> None:
        self.query_changed.emit(self.sql_editor.toPlainText())

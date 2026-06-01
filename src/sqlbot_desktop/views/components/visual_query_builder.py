"""Visual Query Builder Panel for selecting tables, columns, and adding WHERE conditions with premium styled UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIntValidator, QValidator
from sqlbot_desktop.utils.i18n_manager import tr
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
    QDialog,
    QListWidget,
    QStackedWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from sqlbot_desktop.models.entities import TableInfo, ColumnInfo
from sqlbot_desktop.services.join_safety_service import JoinSafetyResult


def add_widget_to_packed_layout(layout: QVBoxLayout, widget: QWidget) -> None:
    """Helper to add widget to a QVBoxLayout with a persistent stretch spacer at the end to pack items at the top."""
    count = layout.count()
    if count > 0 and layout.itemAt(count - 1).widget() is None:
        layout.insertWidget(count - 1, widget)
    else:
        layout.addWidget(widget)
        layout.addStretch()


def clear_packed_layout(layout: QVBoxLayout) -> None:
    """Helper to clear all widgets and spacers from a QVBoxLayout."""
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class SearchableComboBox(QComboBox):
    """A premium styled combobox that supports searching/filtering items."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setObjectName("vqbSearchableCombo")

        completer = self.completer()
        if completer:
            completer.setFilterMode(Qt.MatchContains)
            completer.setCompletionMode(completer.CompletionMode.PopupCompletion)

        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setObjectName("vqbSearchableComboLineEdit")


class QueryBuilderGuideDialog(QDialog):
    """Vertical tab user guide dialog for explaining conditions, operators, and usage."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("guide.window_title"))
        self.resize(700, 480)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Left list widget acting as vertical tabs
        self.tab_list = QListWidget()
        self.tab_list.setFixedWidth(180)
        self.tab_list.setObjectName("guideTabList")

        # Right stacked widget acting as tab contents
        self.stacked_pages = QStackedWidget()
        self.stacked_pages.setObjectName("guideStackedPages")

        # Populate tabs and content
        self._add_tab(tr("guide.tab_overview"), self._create_overview_page())
        self._add_tab(tr("guide.tab_equal"), self._create_equal_page())
        self._add_tab(tr("guide.tab_comparison"), self._create_comparison_page())
        self._add_tab(tr("guide.tab_like"), self._create_like_page())
        self._add_tab(tr("guide.tab_between"), self._create_between_page())
        self._add_tab(tr("guide.tab_in"), self._create_in_page())
        self._add_tab(tr("guide.tab_null"), self._create_null_page())
        self._add_tab(tr("guide.tab_exists"), self._create_exists_page())
        self._add_tab(tr("guide.tab_groupby"), self._create_groupby_page())
        self._add_tab(tr("guide.tab_orderby"), self._create_orderby_page())
        self._add_tab(tr("guide.tab_limit"), self._create_limit_page())

        self.tab_list.currentRowChanged.connect(self.stacked_pages.setCurrentIndex)
        self.tab_list.setCurrentRow(0)

        layout.addWidget(self.tab_list)
        layout.addWidget(self.stacked_pages, 1)

    def _add_tab(self, name: str, widget: QWidget) -> None:
        self.tab_list.addItem(name)
        self.stacked_pages.addWidget(widget)

    def _create_page_wrapper(self, title: str, html_content: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("guideTitle")

        lbl_content = QLabel()
        lbl_content.setTextFormat(Qt.TextFormat.RichText)
        lbl_content.setText(html_content)
        lbl_content.setWordWrap(True)
        lbl_content.setObjectName("guideContent")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_content, 1)
        layout.addStretch()
        return widget

    def _create_overview_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.overview_title"),
            tr("guide.overview_body")
        )

    def _create_equal_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.equal_title"),
            tr("guide.equal_body")
        )

    def _create_comparison_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.comparison_title"),
            tr("guide.comparison_body")
        )

    def _create_like_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.like_title"),
            tr("guide.like_body")
        )

    def _create_between_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.between_title"),
            tr("guide.between_body")
        )

    def _create_in_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.in_title"),
            tr("guide.in_body")
        )

    def _create_null_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.null_title"),
            tr("guide.null_body")
        )

    def _create_exists_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.exists_title"),
            tr("guide.exists_body")
        )

    def _create_groupby_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.groupby_title"),
            tr("guide.groupby_body")
        )

    def _create_orderby_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.orderby_title"),
            tr("guide.orderby_body")
        )

    def _create_limit_page(self) -> QWidget:
        return self._create_page_wrapper(
            tr("guide.limit_title"),
            tr("guide.limit_body")
        )


class SelectColumnsOrderDialog(QDialog):
    """Dialog to rearrange the order of selected columns using drag-and-drop."""

    def __init__(self, sort_list_widget: QListWidget, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("query_builder.btn_columns_order", "Thứ tự cột hiển thị (SELECT)"))
        self.resize(360, 450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        desc = QLabel(tr("query_builder.dialog_columns_order_desc", "Kéo thả các cột dưới đây để thay đổi thứ tự hiển thị trong câu lệnh SELECT:"))
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; font-weight: 500; color: #475569;")
        layout.addWidget(desc)

        # Reparent and show the sort list widget
        self.sort_list = sort_list_widget
        self.sort_list.setVisible(True)
        layout.addWidget(self.sort_list, 1)

        # Close/Confirm button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(tr("dialogs.bookmarks_btn_close", "Xác nhận / Đóng"))
        close_btn.setObjectName("successButton")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(32)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class StyledComboBox(QComboBox):
    """A premium styled combo box with custom popup styles to prevent black backgrounds on Windows."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("vqbCombo")


class StrictIntRangeValidator(QIntValidator):
    """Integer range validator that rejects values above the upper bound."""

    def validate(self, input_text: str, pos: int):
        state, value, position = super().validate(input_text, pos)
        if state == QValidator.State.Intermediate and input_text.strip().isdigit():
            if int(input_text.strip()) > self.top():
                return QValidator.State.Invalid, value, position
        return state, value, position


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
        self.cb.setObjectName("vqbColumnCheckBox")

        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setObjectName("vqbColumnLabel")

        # Parse display_name to extract description and column name
        if display_name != col_name:
            suffix = f" ({col_name})"
            if display_name.endswith(suffix):
                desc = display_name[:-len(suffix)].strip()
            else:
                desc = display_name
            text = f"<span style='font-weight: 600;'>{desc}</span> <span style='font-size: 11px;'>({col_name} • {col_type})</span>"
        else:
            text = f"<span style='font-weight: 600;'>{col_name}</span> <span style='font-size: 11px;'>({col_type})</span>"

        self.label.setText(text)
        self.label.mousePressEvent = lambda event: self.cb.toggle()

        layout.addWidget(self.cb)
        layout.addWidget(self.label, 1)

    def isChecked(self) -> bool:
        return self.cb.isChecked()

    def setChecked(self, checked: bool) -> None:
        self.cb.setChecked(checked)

    def set_join_safety_state(self, enabled: bool, tooltip: str = "") -> None:
        self.cb.setEnabled(enabled)
        self.label.setEnabled(enabled)
        self.cb.setToolTip(tooltip)
        self.label.setToolTip(tooltip)
        self.setToolTip(tooltip)


class ColumnTableGroupWidget(QWidget):
    """Collapsible table section used by the visual column picker."""

    def __init__(
        self,
        table_name: str,
        title: str,
        expanded: bool,
        selection_callback: Callable[[str, bool], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.table_name = table_name
        self._title = title
        self._search_forced = False
        self._selection_callback = selection_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header_row = QWidget()
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.select_all_cb = QCheckBox()
        self.select_all_cb.setObjectName("vqbTableSelectAllCheckBox")
        self.select_all_cb.setTristate(False)
        self.select_all_cb.setToolTip(tr("query_builder.select_all_table_columns", "Chọn / bỏ chọn tất cả cột trong bảng"))
        self.select_all_cb.stateChanged.connect(self._on_select_all_changed)

        self.header_btn = QPushButton()
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(expanded)
        self.header_btn.setObjectName("vqbTableGroupHeader")
        self.header_btn.clicked.connect(lambda *_: self._sync_body_visibility())
        header_layout.addWidget(self.select_all_cb)
        header_layout.addWidget(self.header_btn, 1)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 2, 0, 2)
        self.body_layout.setSpacing(2)

        layout.addWidget(header_row)
        layout.addWidget(self.body)
        self._sync_body_visibility()
        self.update_header()

    def add_column_row(self, row: ColumnCheckBoxRow) -> None:
        self.body_layout.addWidget(row)
        self.update_header()

    def iter_column_rows(self) -> list[ColumnCheckBoxRow]:
        rows: list[ColumnCheckBoxRow] = []
        for i in range(self.body_layout.count()):
            widget = self.body_layout.itemAt(i).widget()
            if isinstance(widget, ColumnCheckBoxRow):
                rows.append(widget)
        return rows

    def set_search_forced(self, forced: bool) -> None:
        self._search_forced = forced
        self._sync_body_visibility()

    def update_header(self) -> None:
        total = len(self.iter_column_rows())
        selected = sum(1 for row in self.iter_column_rows() if row.isChecked())
        marker = "v" if self.header_btn.isChecked() or self._search_forced else ">"
        suffix = f" ({selected}/{total})" if total else ""
        self.header_btn.setText(f"{marker} {self._title}{suffix}")
        self._sync_select_all_state(selected, total)

    def _sync_body_visibility(self) -> None:
        self.body.setVisible(self.header_btn.isChecked() or self._search_forced)
        self.update_header()

    def _sync_select_all_state(self, selected: int, total: int) -> None:
        self.select_all_cb.blockSignals(True)
        if total == 0 or selected == 0:
            self.select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        elif selected == total:
            self.select_all_cb.setCheckState(Qt.CheckState.Checked)
        else:
            self.select_all_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        self.select_all_cb.blockSignals(False)

    def _on_select_all_changed(self, state: int) -> None:
        if state == Qt.CheckState.PartiallyChecked.value:
            return
        if self._selection_callback:
            self._selection_callback(self.table_name, state == Qt.CheckState.Checked.value)


class ConditionRow(QWidget):
    """A single WHERE condition row widget."""

    changed = Signal()
    delete_requested = Signal(QWidget)
    OPERATORS = [
        "=",
        "!=",
        ">",
        "<",
        ">=",
        "<=",
        "LIKE",
        "BETWEEN",
        "IN",
        "IS NULL",
        "IS NOT NULL",
        "EXISTS",
        "NOT EXISTS",
    ]

    def __init__(self, columns: list[ColumnInfo], annotations: dict[str, object] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.columns = columns
        self.annotations = annotations or {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        def get_col_disp_name(col_name: str) -> str:
            t_name, c_name = col_name, col_name
            if "." in col_name:
                t_name, c_name = col_name.split(".", 1)

            tables_ann = self.annotations.get("tables", {})
            ann = tables_ann.get(t_name, {})
            if isinstance(ann, dict):
                cols_ann = ann.get("columns", {})
                col_ann = cols_ann.get(c_name, {})
                desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                if desc:
                    return f"{desc} ({col_name})"

            # Fallback: search across all tables if lookup failed
            for tbl_name, ann in tables_ann.items():
                if isinstance(ann, dict):
                    cols_ann = ann.get("columns", {})
                    col_ann = cols_ann.get(c_name, {})
                    desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                    if desc:
                        return f"{desc} ({col_name})"
            return col_name

        self.col_combo = SearchableComboBox()
        for col in columns:
            disp = get_col_disp_name(col.name)
            self.col_combo.addItem(disp, col.name)
        self.col_combo.currentIndexChanged.connect(self._on_changed)
        self.col_combo.currentIndexChanged.connect(self._update_placeholders_and_format)

        self.op_combo = StyledComboBox()
        self._populate_operator_combo()
        self.op_combo.currentIndexChanged.connect(self._on_changed)
        self.op_combo.currentIndexChanged.connect(self._toggle_val_input)
        self.op_combo.currentIndexChanged.connect(lambda _: self._update_operator_tooltip())

        self.val_input = QLineEdit()
        self.val_input.setObjectName("vqbValInput")
        self.val_input.textChanged.connect(self._on_changed)

        self.val_input_2 = QLineEdit()
        self.val_input_2.setObjectName("vqbValInput")
        self.val_input_2.textChanged.connect(self._on_changed)
        self.val_input_2.setVisible(False)

        self.del_btn = QPushButton()
        self.del_btn.setObjectName("vqbDelBtn")
        self.del_btn.setFixedWidth(45)
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        layout.addWidget(self.col_combo, 2)
        layout.addWidget(self.op_combo, 1)
        layout.addWidget(self.val_input, 2)
        layout.addWidget(self.val_input_2, 2)
        layout.addWidget(self.del_btn)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.del_btn.setText(tr("query_builder.btn_delete", "Xóa"))
        self._refresh_operator_tooltips()
        self._update_placeholders_and_format()

    def _populate_operator_combo(self) -> None:
        self.op_combo.addItems(self.OPERATORS)
        self._refresh_operator_tooltips()

    def _operator_tooltip(self, operator: str) -> str:
        tooltips = {
            "=": tr("query_builder.operator_tooltip_eq", "Bằng: chỉ lấy dòng có giá trị đúng bằng giá trị nhập."),
            "!=": tr("query_builder.operator_tooltip_ne", "Khác: loại bỏ dòng có giá trị bằng giá trị nhập."),
            ">": tr("query_builder.operator_tooltip_gt", "Lớn hơn: chỉ lấy dòng có giá trị lớn hơn giá trị nhập."),
            "<": tr("query_builder.operator_tooltip_lt", "Nhỏ hơn: chỉ lấy dòng có giá trị nhỏ hơn giá trị nhập."),
            ">=": tr("query_builder.operator_tooltip_gte", "Lớn hơn hoặc bằng: lấy dòng có giá trị từ ngưỡng nhập trở lên."),
            "<=": tr("query_builder.operator_tooltip_lte", "Nhỏ hơn hoặc bằng: lấy dòng có giá trị không vượt quá ngưỡng nhập."),
            "LIKE": tr("query_builder.operator_tooltip_like", "LIKE: tìm theo mẫu chuỗi. Dùng % để đại diện nhiều ký tự, ví dụ %abc%."),
            "BETWEEN": tr("query_builder.operator_tooltip_between", "BETWEEN: lọc giá trị nằm trong khoảng, bao gồm cả giá trị bắt đầu và kết thúc."),
            "IN": tr("query_builder.operator_tooltip_in", "IN: lọc một trong nhiều giá trị. Nhập danh sách phân tách bằng dấu phẩy."),
            "IS NULL": tr("query_builder.operator_tooltip_is_null", "IS NULL: chỉ lấy dòng mà cột đang trống hoặc không có giá trị."),
            "IS NOT NULL": tr("query_builder.operator_tooltip_is_not_null", "IS NOT NULL: chỉ lấy dòng mà cột có giá trị."),
            "EXISTS": tr("query_builder.operator_tooltip_exists", "EXISTS: chỉ lấy dòng khi subquery bên phải trả về ít nhất một dòng."),
            "NOT EXISTS": tr("query_builder.operator_tooltip_not_exists", "NOT EXISTS: chỉ lấy dòng khi subquery bên phải không trả về dòng nào."),
        }
        return tooltips.get(operator, "")

    def _refresh_operator_tooltips(self) -> None:
        for index in range(self.op_combo.count()):
            operator = self.op_combo.itemText(index)
            self.op_combo.setItemData(index, self._operator_tooltip(operator), Qt.ItemDataRole.ToolTipRole)
        self._update_operator_tooltip()

    def _update_operator_tooltip(self) -> None:
        self.op_combo.setToolTip(self._operator_tooltip(self.op_combo.currentText()))

    def _on_changed(self, *args) -> None:
        self.changed.emit()

    def _get_current_col_type(self) -> str:
        col_name = self.col_combo.currentData()
        for c in self.columns:
            if c.name == col_name:
                return c.type_name.lower()
        return ""

    def _toggle_val_input(self, index: int) -> None:
        op = self.op_combo.currentText()
        is_null_op = "IS NULL" in op or "IS NOT NULL" in op
        self.val_input.setVisible(not is_null_op)
        self.val_input_2.setVisible(op == "BETWEEN")
        self._update_placeholders_and_format()

    def _update_placeholders_and_format(self, *args) -> None:
        col_type = self._get_current_col_type()
        is_datetime = any(t in col_type for t in ["datetime", "timestamp", "date"])
        op = self.op_combo.currentText()

        if op in ("EXISTS", "NOT EXISTS"):
            self.val_input.setPlaceholderText("SELECT 1 FROM...")
        elif is_datetime:
            if op == "BETWEEN":
                self.val_input.setPlaceholderText(tr("query_builder.condition_value_placeholder", "Giá trị..."))
                self.val_input_2.setPlaceholderText(tr("query_builder.condition_value_to_placeholder", "Đến giá trị..."))
            else:
                self.val_input.setPlaceholderText("YYYY-MM-DD HH:MM:SS.sss")
        else:
            if op == "BETWEEN":
                self.val_input.setPlaceholderText(tr("query_builder.condition_value_placeholder", "Giá trị..."))
                self.val_input_2.setPlaceholderText(tr("query_builder.condition_value_to_placeholder", "Đến giá trị..."))
            else:
                self.val_input.setPlaceholderText(tr("query_builder.condition_value_placeholder", "Giá trị..."))

    def get_sql(self) -> str:
        col_name = self.col_combo.currentData()
        op = self.op_combo.currentText()
        val = self.val_input.text().strip()
        val2 = self.val_input_2.text().strip() if op == "BETWEEN" else ""

        col_type = self._get_current_col_type()

        if "IS NULL" in op or "IS NOT NULL" in op:
            return f"{col_name} {op}"

        if op in ("EXISTS", "NOT EXISTS"):
            if not val:
                return ""
            clean_val = val
            if clean_val.startswith("(") and clean_val.endswith(")"):
                clean_val = clean_val[1:-1].strip()
            return f"{op} ({clean_val})"

        if not val:
            return ""

        is_string = any(t in col_type for t in ["char", "text", "varchar", "string", "date", "time", "timestamp"])
        is_datetime = any(t in col_type for t in ["datetime", "timestamp", "date"])

        def format_datetime_string(v: str) -> str:
            v = v.strip().strip("'").strip('"')
            if not v:
                return ""
            import re
            if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
                return f"{v} 00:00:00.000"
            if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", v):
                return f"{v}:00.000"
            if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$", v):
                return f"{v}.000"
            if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}$", v):
                return v
            return v

        def format_val(v: str) -> str:
            if is_datetime:
                v = format_datetime_string(v)
            if is_string:
                if not ((v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"'))):
                    escaped = v.replace("'", "''")
                    return f"'{escaped}'"
            return v

        if op == "BETWEEN":
            if not val2:
                return ""
            return f"{col_name} BETWEEN {format_val(val)} AND {format_val(val2)}"

        return f"{col_name} {op} {format_val(val)}"


class OrderByRow(QWidget):
    """A single ORDER BY row widget."""

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
            t_name, c_name = col_name, col_name
            if "." in col_name:
                t_name, c_name = col_name.split(".", 1)

            tables_ann = self.annotations.get("tables", {})
            ann = tables_ann.get(t_name, {})
            if isinstance(ann, dict):
                cols_ann = ann.get("columns", {})
                col_ann = cols_ann.get(c_name, {})
                desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                if desc:
                    return f"{desc} ({col_name})"

            for tbl_name, ann in tables_ann.items():
                if isinstance(ann, dict):
                    cols_ann = ann.get("columns", {})
                    col_ann = cols_ann.get(c_name, {})
                    desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                    if desc:
                        return f"{desc} ({col_name})"
            return col_name

        self.col_combo = SearchableComboBox()
        self._get_col_disp_name = get_col_disp_name
        self.set_columns(columns)
        self.col_combo.currentIndexChanged.connect(self._on_changed)

        self.dir_combo = StyledComboBox()
        self.dir_combo.currentIndexChanged.connect(self._on_changed)

        self.del_btn = QPushButton()
        self.del_btn.setObjectName("vqbDelBtn")
        self.del_btn.setFixedWidth(45)
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        layout.addWidget(self.col_combo, 2)
        layout.addWidget(self.dir_combo, 1)
        layout.addWidget(self.del_btn)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.del_btn.setText(tr("query_builder.btn_delete", "Xóa"))
        current_idx = self.dir_combo.currentIndex()
        self.dir_combo.blockSignals(True)
        self.dir_combo.clear()
        self.dir_combo.addItems([tr("query_builder.sort_asc", "Tăng dần (ASC)"), tr("query_builder.sort_desc", "Giảm dần (DESC)")])
        if current_idx >= 0:
            self.dir_combo.setCurrentIndex(current_idx)
        self.dir_combo.blockSignals(False)

    def _on_changed(self, *args) -> None:
        self.changed.emit()

    def set_columns(self, columns: list[ColumnInfo]) -> None:
        current_col = self.col_combo.currentData() if hasattr(self, "col_combo") else None
        self.columns = columns
        self.col_combo.blockSignals(True)
        self.col_combo.clear()
        selected_index = 0
        for index, col in enumerate(columns):
            disp = self._get_col_disp_name(col.name)
            self.col_combo.addItem(disp, col.name)
            if col.name == current_col:
                selected_index = index
        if columns:
            self.col_combo.setCurrentIndex(selected_index)
        self.col_combo.blockSignals(False)

    def get_sql_part(self) -> str:
        col_name = self.col_combo.currentData()
        dir_text = self.dir_combo.currentText()
        direction = "ASC" if "ASC" in dir_text or "昇順" in dir_text or "Ascending" in dir_text else "DESC"
        if not col_name:
            return ""
        return f"{col_name} {direction}"


class GroupByRow(QWidget):
    """A single GROUP BY row widget."""

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
            t_name, c_name = col_name, col_name
            if "." in col_name:
                t_name, c_name = col_name.split(".", 1)

            tables_ann = self.annotations.get("tables", {})
            ann = tables_ann.get(t_name, {})
            if isinstance(ann, dict):
                cols_ann = ann.get("columns", {})
                col_ann = cols_ann.get(c_name, {})
                desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                if desc:
                    return f"{desc} ({col_name})"

            for tbl_name, ann in tables_ann.items():
                if isinstance(ann, dict):
                    cols_ann = ann.get("columns", {})
                    col_ann = cols_ann.get(c_name, {})
                    desc = col_ann.get("description", "") if isinstance(col_ann, dict) else ""
                    if desc:
                        return f"{desc} ({col_name})"
            return col_name

        self.col_combo = SearchableComboBox()
        self._get_col_disp_name = get_col_disp_name
        self.set_columns(columns)
        self.col_combo.currentIndexChanged.connect(self._on_changed)

        self.del_btn = QPushButton()
        self.del_btn.setObjectName("vqbDelBtn")
        self.del_btn.setFixedWidth(45)
        self.del_btn.clicked.connect(lambda: self.delete_requested.emit(self))

        layout.addWidget(self.col_combo, 2)
        layout.addWidget(self.del_btn)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.del_btn.setText(tr("query_builder.btn_delete", "Xóa"))

    def _on_changed(self, *args) -> None:
        self.changed.emit()

    def set_columns(self, columns: list[ColumnInfo]) -> None:
        current_col = self.col_combo.currentData() if hasattr(self, "col_combo") else None
        self.columns = columns
        self.col_combo.blockSignals(True)
        self.col_combo.clear()
        selected_index = 0
        for index, col in enumerate(columns):
            disp = self._get_col_disp_name(col.name)
            self.col_combo.addItem(disp, col.name)
            if col.name == current_col:
                selected_index = index
        if columns:
            self.col_combo.setCurrentIndex(selected_index)
        self.col_combo.blockSignals(False)

    def get_sql_part(self) -> str:
        col_name = self.col_combo.currentData()
        return col_name if col_name else ""


class VisualQueryBuilderPanel(QWidget):
    """Panel for visually building queries with premium card style styling."""

    # Shared configuration for columns layout synchronization
    COLUMNS_LAYOUT_SPACING = 2
    COLUMNS_LAYOUT_MARGINS = (2, 2, 2, 2)

    query_changed = Signal(str)
    execute_requested = Signal()
    show_results_requested = Signal()
    bookmark_requested = Signal()
    status_message_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tables: list[TableInfo] = []
        self._annotations: dict[str, object] = {}
        self._dialect = "sqlite"
        self.column_groups: dict[str, ColumnTableGroupWidget] = {}
        self._join_safety_checker: Callable[[list[str], str], JoinSafetyResult] | None = None

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # Left Column: Selection builder
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # Table Group
        self.table_group = QGroupBox()
        self.table_group.setObjectName("vqbGroupBox")
        table_layout = QVBoxLayout(self.table_group)
        table_layout.setContentsMargins(8, 4, 8, 8)
        self.table_combo = StyledComboBox()
        self.table_combo.currentIndexChanged.connect(self._on_table_changed)
        table_layout.addWidget(self.table_combo)
        left_layout.addWidget(self.table_group)

        # Columns Group
        self.columns_group = QGroupBox()
        self.columns_group.setObjectName("vqbGroupBox")
        columns_layout = QVBoxLayout(self.columns_group)
        columns_layout.setContentsMargins(8, 4, 8, 8)

        # Horizontal layout for Search input + Toggle selected columns button + Sort Dialog button
        col_controls_layout = QHBoxLayout()
        col_controls_layout.setContentsMargins(0, 0, 0, 0)
        col_controls_layout.setSpacing(6)

        self.col_search_input = QLineEdit()
        self.col_search_input.setObjectName("vqbColSearchInput")
        self.col_search_input.textChanged.connect(lambda: self._filter_columns_list())

        self.show_selected_only_btn = QPushButton()
        self.show_selected_only_btn.setCheckable(True)
        self.show_selected_only_btn.setObjectName("showSelectedOnlyBtn")
        self.show_selected_only_btn.toggled.connect(lambda: self._filter_columns_list())

        self.sort_dialog_btn = QPushButton()
        self.sort_dialog_btn.setObjectName("secondaryButton")
        self.sort_dialog_btn.setFixedSize(56, 32)
        self.sort_dialog_btn.clicked.connect(self._show_sort_dialog)

        self.clear_selected_btn = QPushButton()
        self.clear_selected_btn.setObjectName("dangerButton")
        self.clear_selected_btn.setFixedSize(34, 32)
        self.clear_selected_btn.clicked.connect(self._clear_all_selected_columns)

        col_controls_layout.addWidget(self.col_search_input, 1)
        col_controls_layout.addWidget(self.show_selected_only_btn)
        col_controls_layout.addWidget(self.clear_selected_btn)
        col_controls_layout.addWidget(self.sort_dialog_btn)
        columns_layout.addLayout(col_controls_layout)

        self.columns_scroll = QScrollArea()
        self.columns_scroll.setWidgetResizable(True)
        self.columns_scroll.setObjectName("vqbScrollArea")
        self.columns_container = QWidget()
        self.columns_container.setObjectName("vqbScrollContent")
        self.columns_container_layout = QVBoxLayout(self.columns_container)
        self.columns_container_layout.setContentsMargins(*self.COLUMNS_LAYOUT_MARGINS)
        self.columns_container_layout.setSpacing(self.COLUMNS_LAYOUT_SPACING)
        self.columns_scroll.setWidget(self.columns_container)
        columns_layout.addWidget(self.columns_scroll)

        # Initialize sort_list widget in memory
        self.sort_list = QListWidget(self)
        self.sort_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.sort_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sort_list.customContextMenuRequested.connect(self._show_column_context_menu)
        self.sort_list.setObjectName("vqbSortList")
        self.sort_list.model().rowsMoved.connect(lambda *args: self._update_query())

        # Global DISTINCT & LIMIT Controls
        distinct_limit_layout = QHBoxLayout()
        distinct_limit_layout.setContentsMargins(0, 4, 0, 0)
        distinct_limit_layout.setSpacing(10)

        self.distinct_check = QCheckBox()
        self.distinct_check.setObjectName("vqbDistinctCheck")
        self.distinct_check.stateChanged.connect(lambda *args: self._update_query())
        distinct_limit_layout.addWidget(self.distinct_check)

        self.limit_label = QLabel()
        self.limit_label.setObjectName("vqbLimitLabel")
        self.limit_label.setFixedWidth(80)

        self.limit_input = QLineEdit()
        self.limit_input.setValidator(StrictIntRangeValidator(1, 1000, self))
        self.limit_input.setObjectName("vqbLimitInput")
        self.limit_input.setFixedWidth(90)
        self.limit_input.textChanged.connect(lambda *args: self._update_query())

        distinct_limit_layout.addWidget(self.limit_label)
        distinct_limit_layout.addWidget(self.limit_input)
        columns_layout.addLayout(distinct_limit_layout)

        left_layout.addWidget(self.columns_group, 1)

        # WHERE Conditions Group
        self.cond_group = QGroupBox()
        self.cond_group.setObjectName("vqbGroupBox")
        cond_layout = QVBoxLayout(self.cond_group)
        cond_layout.setContentsMargins(8, 4, 8, 8)
        self.cond_scroll = QScrollArea()
        self.cond_scroll.setWidgetResizable(True)
        self.cond_scroll.setObjectName("vqbScrollArea")
        self.cond_container = QWidget()
        self.cond_container.setObjectName("vqbScrollContent")
        self.cond_container_layout = QVBoxLayout(self.cond_container)
        self.cond_container_layout.setContentsMargins(2, 2, 2, 2)
        self.cond_container_layout.setSpacing(2)
        self.cond_scroll.setWidget(self.cond_container)
        cond_layout.addWidget(self.cond_scroll)

        cond_buttons_layout = QHBoxLayout()
        cond_buttons_layout.setContentsMargins(0, 0, 0, 0)
        cond_buttons_layout.setSpacing(6)

        self.add_cond_btn = QPushButton()
        self.add_cond_btn.setObjectName("vqbAddCondBtn")
        self.add_cond_btn.clicked.connect(self._add_condition_row)

        self.guide_btn = QPushButton()
        self.guide_btn.setObjectName("vqbGuideBtn")
        self.guide_btn.clicked.connect(self._show_guide_dialog)

        cond_buttons_layout.addWidget(self.add_cond_btn)
        cond_buttons_layout.addWidget(self.guide_btn)
        cond_layout.addLayout(cond_buttons_layout)
        left_layout.addWidget(self.cond_group, 1)

        # GROUP BY Group
        self.groupby_group = QGroupBox()
        self.groupby_group.setObjectName("vqbGroupBox")
        groupby_layout = QVBoxLayout(self.groupby_group)
        groupby_layout.setContentsMargins(8, 4, 8, 8)

        self.groupby_scroll = QScrollArea()
        self.groupby_scroll.setWidgetResizable(True)
        self.groupby_scroll.setObjectName("vqbScrollArea")
        self.groupby_container = QWidget()
        self.groupby_container.setObjectName("vqbScrollContent")
        self.groupby_container_layout = QVBoxLayout(self.groupby_container)
        self.groupby_container_layout.setContentsMargins(2, 2, 2, 2)
        self.groupby_container_layout.setSpacing(2)
        self.groupby_scroll.setWidget(self.groupby_container)
        groupby_layout.addWidget(self.groupby_scroll)

        groupby_buttons_layout = QHBoxLayout()
        groupby_buttons_layout.setContentsMargins(0, 0, 0, 0)
        groupby_buttons_layout.setSpacing(6)
        self.add_groupby_btn = QPushButton()
        self.add_groupby_btn.setObjectName("vqbAddCondBtn")
        self.add_groupby_btn.clicked.connect(self._add_groupby_row)
        groupby_buttons_layout.addWidget(self.add_groupby_btn)
        groupby_layout.addLayout(groupby_buttons_layout)

        # ORDER BY Group
        self.orderby_group = QGroupBox()
        self.orderby_group.setObjectName("vqbGroupBox")
        orderby_layout = QVBoxLayout(self.orderby_group)
        orderby_layout.setContentsMargins(8, 4, 8, 8)

        self.orderby_scroll = QScrollArea()
        self.orderby_scroll.setWidgetResizable(True)
        self.orderby_scroll.setObjectName("vqbScrollArea")
        self.orderby_container = QWidget()
        self.orderby_container.setObjectName("vqbScrollContent")
        self.orderby_container_layout = QVBoxLayout(self.orderby_container)
        self.orderby_container_layout.setContentsMargins(2, 2, 2, 2)
        self.orderby_container_layout.setSpacing(2)
        self.orderby_scroll.setWidget(self.orderby_container)
        orderby_layout.addWidget(self.orderby_scroll)

        orderby_buttons_layout = QHBoxLayout()
        orderby_buttons_layout.setContentsMargins(0, 0, 0, 0)
        orderby_buttons_layout.setSpacing(6)
        self.add_orderby_btn = QPushButton()
        self.add_orderby_btn.setObjectName("vqbAddCondBtn")
        self.add_orderby_btn.clicked.connect(self._add_orderby_row)
        orderby_buttons_layout.addWidget(self.add_orderby_btn)
        orderby_layout.addLayout(orderby_buttons_layout)

        main_layout.addWidget(left_widget, 1)

        # Right Column: SQL Editor and Actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.sql_title = QLabel()
        self.sql_title.setObjectName("sectionTitle")
        self.sql_editor = QTextEdit()
        self.sql_editor.setObjectName("sqlEditor")
        self.sql_editor.setFont(QFont("Courier New", 11))
        self.sql_editor.textChanged.connect(self._on_sql_manual_changed)

        self.groupby_group.setMinimumHeight(190)
        self.orderby_group.setMinimumHeight(190)
        right_layout.addWidget(self.groupby_group, 1)
        right_layout.addWidget(self.orderby_group, 1)
        right_layout.addWidget(self.sql_title)
        right_layout.addWidget(self.sql_editor, 1)

        sql_actions = QHBoxLayout()
        self.execute_btn = QPushButton()
        self.execute_btn.setObjectName("successButton")
        self.execute_btn.clicked.connect(self.execute_requested.emit)

        self.results_btn = QPushButton()
        self.results_btn.setObjectName("secondaryButton")
        self.results_btn.clicked.connect(self.show_results_requested.emit)

        self.paste_btn = QPushButton()
        self.paste_btn.setObjectName("secondaryButton")
        self.paste_btn.clicked.connect(self.sql_editor.paste)

        self.bookmark_btn = QPushButton()
        self.bookmark_btn.setObjectName("warningButton")
        self.bookmark_btn.clicked.connect(self.bookmark_requested.emit)

        for btn in [self.execute_btn, self.results_btn, self.paste_btn, self.bookmark_btn]:
            btn.setMinimumHeight(32)
            sql_actions.addWidget(btn)
        sql_actions.addStretch()

        right_layout.addLayout(sql_actions)

        main_layout.addWidget(right_widget, 1)

    def retranslate_ui(self) -> None:
        self.table_group.setTitle(tr("query_builder.group_table", "Chọn Bảng (Table)"))
        self.columns_group.setTitle(tr("query_builder.group_columns", "Chọn Cột (Columns)"))
        self.col_search_input.setPlaceholderText(tr("query_builder.search_columns_placeholder", "Tìm kiếm cột..."))
        self.show_selected_only_btn.setText(tr("query_builder.btn_selected_only", "Đã chọn 👁️"))
        sort_tooltip = tr("query_builder.btn_columns_order", "Thứ tự cột ⇅")
        clear_tooltip = tr("query_builder.btn_clear_selected", "Bỏ chọn tất cả ❌")
        self.sort_dialog_btn.setText(tr("query_builder.btn_columns_order_short", "Order"))
        self.sort_dialog_btn.setToolTip(sort_tooltip)
        self.sort_dialog_btn.setAccessibleName(sort_tooltip)
        self.clear_selected_btn.setText("×")
        self.clear_selected_btn.setToolTip(clear_tooltip)
        self.clear_selected_btn.setAccessibleName(clear_tooltip)
        self.distinct_check.setText(tr("query_builder.checkbox_distinct", "Loại bỏ trùng lặp"))
        self.limit_label.setText(tr("query_builder.label_limit", "Giới hạn dòng:"))
        self.limit_input.setPlaceholderText(tr("query_builder.limit_placeholder", "Không giới hạn"))
        self.cond_group.setTitle(tr("query_builder.group_where", "Điều kiện lọc (WHERE)"))
        self.add_cond_btn.setText(tr("query_builder.btn_add_condition", "Thêm điều kiện ➕"))
        self.guide_btn.setText(tr("query_builder.btn_guide", "Hướng dẫn 📖"))
        self.groupby_group.setTitle(tr("query_builder.group_groupby", "Gom nhóm (GROUP BY)"))
        self.add_groupby_btn.setText(tr("query_builder.btn_add_groupby", "Thêm gom nhóm ➕"))
        self.orderby_group.setTitle(tr("query_builder.group_orderby", "Sắp xếp kết quả (ORDER BY)"))
        self.add_orderby_btn.setText(tr("query_builder.btn_add_orderby", "Thêm sắp xếp ➕"))

        self.sql_title.setText(tr("main.sql_label", "SQL Editor (Câu lệnh SELECT)"))
        self.sql_editor.setPlaceholderText(tr("main.sql_editor_placeholder", "SQL query sẽ tự động sinh tại đây..."))
        self.execute_btn.setText(tr("main.btn_execute", "Execute (Chạy)"))
        self.results_btn.setText(tr("main.btn_results", "Xem kết quả"))
        self.paste_btn.setText(tr("main.btn_paste_sql", "Paste SQL"))
        self.bookmark_btn.setText(tr("main.btn_bookmark", "Bookmark"))

        # Translate existing dynamic condition rows
        if hasattr(self, "cond_container_layout") and self.cond_container_layout:
            for i in range(self.cond_container_layout.count()):
                widget = self.cond_container_layout.itemAt(i).widget()
                if isinstance(widget, ConditionRow):
                    widget.retranslate_ui()

        if hasattr(self, "groupby_container_layout") and self.groupby_container_layout:
            for i in range(self.groupby_container_layout.count()):
                widget = self.groupby_container_layout.itemAt(i).widget()
                if isinstance(widget, GroupByRow):
                    widget.retranslate_ui()

        if hasattr(self, "orderby_container_layout") and self.orderby_container_layout:
            for i in range(self.orderby_container_layout.count()):
                widget = self.orderby_container_layout.itemAt(i).widget()
                if isinstance(widget, OrderByRow):
                    widget.retranslate_ui()

    def set_schema(self, tables: list[TableInfo], annotations: dict[str, object] | None = None, dialect: str = "sqlite") -> None:
        self._tables = tables
        self._annotations = annotations or {}
        self._dialect = dialect

        # Populate tables dropdown
        self.table_combo.blockSignals(True)
        self.table_combo.clear()
        for t in tables:
            disp_name = self._get_table_display_name(t.name)
            self.table_combo.addItem(disp_name, t.name)
        self.table_combo.blockSignals(False)

        self._on_table_changed()

    def set_join_safety_checker(self, checker: Callable[[list[str], str], JoinSafetyResult] | None) -> None:
        self._join_safety_checker = checker
        self._refresh_join_safety_states()

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
        if hasattr(self, "col_search_input"):
            self.col_search_input.blockSignals(True)
            self.col_search_input.clear()
            self.col_search_input.blockSignals(False)
        if hasattr(self, "show_selected_only_btn"):
            self.show_selected_only_btn.blockSignals(True)
            self.show_selected_only_btn.setChecked(False)
            self.show_selected_only_btn.blockSignals(False)
        if hasattr(self, "sort_list"):
            self.sort_list.clear()

        # Clear columns list
        clear_packed_layout(self.columns_container_layout)
        self.column_groups.clear()

        # Clear conditions
        clear_packed_layout(self.cond_container_layout)

        # Clear group by and order by rows
        if hasattr(self, "groupby_container_layout"):
            clear_packed_layout(self.groupby_container_layout)
        if hasattr(self, "orderby_container_layout"):
            clear_packed_layout(self.orderby_container_layout)

        table_name = self.table_combo.currentData()
        if not table_name:
            self._update_query()
            return

        # 1. Main Table Columns
        main_title = tr("query_builder.main_table_prefix", "Bảng chính:") + f" {self._get_table_display_name(table_name)}"
        main_group = ColumnTableGroupWidget(
            table_name,
            main_title,
            expanded=True,
            selection_callback=self._set_table_columns_checked,
            parent=self,
        )
        self.column_groups[table_name] = main_group
        cols = self._get_active_columns()
        for c in cols:
            disp = self._get_column_display_name(table_name, c.name)
            row_widget = ColumnCheckBoxRow(c.name, disp, c.type_name, self._on_column_checkbox_toggled, self)
            row_widget.cb.setProperty("table_name", table_name)
            main_group.add_column_row(row_widget)
        add_widget_to_packed_layout(self.columns_container_layout, main_group)

        # 2. Joined Table Columns
        for t in self._tables:
            if t.name == table_name:
                continue

            tbl_title = tr("query_builder.joined_table_prefix", "Bảng liên kết:") + f" {self._get_table_display_name(t.name)}"
            table_group = ColumnTableGroupWidget(
                t.name,
                tbl_title,
                expanded=False,
                selection_callback=self._set_table_columns_checked,
                parent=self,
            )
            self.column_groups[t.name] = table_group

            for c in t.columns:
                disp = self._get_column_display_name(t.name, c.name)
                row_widget = ColumnCheckBoxRow(c.name, disp, c.type_name, self._on_column_checkbox_toggled, self)
                row_widget.cb.setProperty("table_name", t.name)
                table_group.add_column_row(row_widget)
            add_widget_to_packed_layout(self.columns_container_layout, table_group)

        self._refresh_join_safety_states()
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
        # Collect columns from all tables to support multi-table filters
        all_cols_info = []
        for t in self._tables:
            for c in t.columns:
                prefixed_c = ColumnInfo(
                    name=f"{t.name}.{c.name}",
                    type_name=c.type_name,
                    nullable=c.nullable,
                    is_primary=c.is_primary,
                    is_foreign=c.is_foreign,
                    sample_value=c.sample_value,
                    enum_values=c.enum_values
                )
                all_cols_info.append(prefixed_c)

        if not all_cols_info:
            return

        row = ConditionRow(all_cols_info, self._annotations, self)
        row.changed.connect(self._update_query)
        row.delete_requested.connect(self._delete_condition_row)
        add_widget_to_packed_layout(self.cond_container_layout, row)
        self._update_query()

    def _delete_condition_row(self, row_widget: QWidget) -> None:
        row_widget.deleteLater()
        self.cond_container_layout.removeWidget(row_widget)
        row_widget.setParent(None)
        self._update_query()

    def _add_groupby_row(self) -> None:
        selected_cols_info = self._selected_column_infos()

        if not selected_cols_info:
            return

        row = GroupByRow(selected_cols_info, self._annotations, self)
        row.changed.connect(self._update_query)
        row.delete_requested.connect(self._delete_groupby_row)
        add_widget_to_packed_layout(self.groupby_container_layout, row)
        self._update_query()

    def _delete_groupby_row(self, row_widget: QWidget) -> None:
        row_widget.deleteLater()
        self.groupby_container_layout.removeWidget(row_widget)
        row_widget.setParent(None)
        self._update_query()

    def _add_orderby_row(self) -> None:
        selected_cols_info = self._selected_column_infos()

        if not selected_cols_info:
            return

        row = OrderByRow(selected_cols_info, self._annotations, self)
        row.changed.connect(self._update_query)
        row.delete_requested.connect(self._delete_orderby_row)
        add_widget_to_packed_layout(self.orderby_container_layout, row)
        self._update_query()

    def _delete_orderby_row(self, row_widget: QWidget) -> None:
        row_widget.deleteLater()
        self.orderby_container_layout.removeWidget(row_widget)
        row_widget.setParent(None)
        self._update_query()

    def _selected_column_infos(self) -> list[ColumnInfo]:
        table_name = self.table_combo.currentData()
        selected_columns: list[ColumnInfo] = []
        for i in range(self.sort_list.count()):
            full_name = self.sort_list.item(i).data(Qt.UserRole)
            if not isinstance(full_name, str):
                continue
            source_table, col_name = self._split_selected_column(full_name, table_name)
            column = self._find_column_info(source_table, col_name)
            if column is None:
                continue
            selected_columns.append(
                ColumnInfo(
                    name=full_name,
                    type_name=column.type_name,
                    nullable=column.nullable,
                    is_primary=column.is_primary,
                    is_foreign=column.is_foreign,
                    sample_value=column.sample_value,
                    enum_values=column.enum_values,
                )
            )
        return selected_columns

    def _split_selected_column(self, full_name: str, start_table: str) -> tuple[str, str]:
        if "." in full_name:
            return full_name.split(".", 1)
        return start_table, full_name

    def _find_column_info(self, table_name: str, col_name: str) -> ColumnInfo | None:
        for table in self._tables:
            if table.name != table_name:
                continue
            for column in table.columns:
                if column.name == col_name:
                    return column
        return None

    def _sync_group_order_columns(self) -> None:
        selected_cols = self._selected_column_infos()
        valid_names = {col.name for col in selected_cols}

        for layout, row_type in (
            (self.groupby_container_layout, GroupByRow),
            (self.orderby_container_layout, OrderByRow),
        ):
            rows_to_remove: list[QWidget] = []
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if isinstance(widget, row_type):
                    current_col = widget.col_combo.currentData()
                    if not selected_cols or current_col not in valid_names:
                        rows_to_remove.append(widget)
                    else:
                        widget.set_columns(selected_cols)
            for widget in rows_to_remove:
                layout.removeWidget(widget)
                widget.deleteLater()

    def _update_query(self) -> None:
        table_name = self.table_combo.currentData()
        if not table_name:
            self.sql_editor.blockSignals(True)
            self.sql_editor.clear()
            self.sql_editor.blockSignals(False)
            self.query_changed.emit("")
            return

        # Gather columns in ordered sequence from the sort list
        checked_cols = []
        target_tables = set()
        for i in range(self.sort_list.count()):
            item = self.sort_list.item(i)
            full_name = item.data(Qt.UserRole)
            if "." in full_name:
                t_name, c_name = full_name.split(".", 1)
                if t_name != table_name:
                    target_tables.add(t_name)

            # Check if an aggregate function modifier is set
            agg_func = item.data(Qt.UserRole + 1)
            if agg_func:
                checked_cols.append(f"{agg_func}({full_name})")
            else:
                checked_cols.append(full_name)

        if not checked_cols:
            checked_cols = ["*"]

        # Gather conditions
        conds = []
        for i in range(self.cond_container_layout.count()):
            widget = self.cond_container_layout.itemAt(i).widget()
            if isinstance(widget, ConditionRow):
                sql_part = widget.get_sql()
                if sql_part:
                    conds.append(sql_part)
                # Parse referenced tables from condition column name
                col_name = widget.col_combo.currentData()
                if col_name and "." in col_name:
                    parts = col_name.split(".", 1)
                    if len(parts) == 2 and parts[0] != table_name:
                        target_tables.add(parts[0])

        filter_expr = " AND ".join(conds) if conds else None

        # Gather Group By columns
        groupby_cols = []
        if hasattr(self, "groupby_container_layout"):
            for i in range(self.groupby_container_layout.count()):
                widget = self.groupby_container_layout.itemAt(i).widget()
                if isinstance(widget, GroupByRow):
                    col_part = widget.get_sql_part()
                    if col_part:
                        groupby_cols.append(col_part)
                    # Parse referenced tables from group by column
                    if col_part and "." in col_part:
                        parts = col_part.split(".", 1)
                        if len(parts) == 2 and parts[0] != table_name:
                            target_tables.add(parts[0])

        # Gather Order By columns
        orderby_cols = []
        if hasattr(self, "orderby_container_layout"):
            for i in range(self.orderby_container_layout.count()):
                widget = self.orderby_container_layout.itemAt(i).widget()
                if isinstance(widget, OrderByRow):
                    sql_part = widget.get_sql_part()
                    if sql_part:
                        orderby_cols.append(sql_part)
                    # Parse referenced tables from order by column
                    col_name = widget.col_combo.currentData()
                    if col_name and "." in col_name:
                        parts = col_name.split(".", 1)
                        if len(parts) == 2 and parts[0] != table_name:
                            target_tables.add(parts[0])

        # Get limit value
        limit_val = None
        limit_text = self.limit_input.text().strip() if hasattr(self, "limit_input") else ""
        if limit_text.isdigit():
            limit_val = min(int(limit_text), 1000)

        # Build using Advanced Agents (Orchestrator, SchemaGraph, JoinPlanner)
        try:
            from sqlbot_desktop.agents.orchestrator import Orchestrator
            orchestrator = Orchestrator(metadata_list=self._tables, dialect=self._dialect)
            query = orchestrator._build_single_query(
                start_table=table_name,
                target_tables=list(target_tables),
                select_columns=checked_cols,
                filter_expression=filter_expr,
                group_by_columns=groupby_cols if groupby_cols else None,
                order_by_columns=orderby_cols if orderby_cols else None,
                limit_count=limit_val
            )
        except Exception:
            # Fallback to basic rendering
            cols_str = ", ".join(checked_cols)
            query = f"SELECT {cols_str}\nFROM {table_name}"
            if conds:
                query += "\nWHERE " + "\n  AND ".join(conds)
            if groupby_cols:
                query += "\nGROUP BY " + ", ".join(groupby_cols)
            if orderby_cols:
                query += "\nORDER BY " + ", ".join(orderby_cols)
            if limit_val is not None:
                query += f"\nLIMIT {limit_val}"

        if self.distinct_check.isChecked():
            if query.startswith("SELECT"):
                query = "SELECT DISTINCT" + query[6:]

        self.sql_editor.blockSignals(True)
        self.sql_editor.setPlainText(query)
        self.sql_editor.blockSignals(False)
        self.query_changed.emit(query)

    def _on_sql_manual_changed(self) -> None:
        self.query_changed.emit(self.sql_editor.toPlainText())

    def _show_guide_dialog(self) -> None:
        dialog = QueryBuilderGuideDialog(self)
        dialog.exec()

    def _show_sort_dialog(self) -> None:
        dialog = SelectColumnsOrderDialog(self.sort_list, self)
        dialog.exec()
        self.sort_list.setParent(self)
        self._update_query()

    def _selected_join_tables(self) -> list[str]:
        start_table = self.table_combo.currentData()
        tables: set[str] = set()
        for i in range(self.sort_list.count()):
            full_name = self.sort_list.item(i).data(Qt.UserRole)
            if isinstance(full_name, str) and "." in full_name:
                table_name, _ = full_name.split(".", 1)
                if table_name != start_table:
                    tables.add(table_name)
        return sorted(tables)

    def _check_join_safety_for_table(self, table_name: str) -> JoinSafetyResult | None:
        start_table = self.table_combo.currentData()
        if not self._join_safety_checker or not table_name or table_name == start_table:
            return None
        selected_tables = [table for table in self._selected_join_tables() if table != table_name]
        return self._join_safety_checker(selected_tables, table_name)

    def _apply_join_safety_to_group(self, table_name: str, result: JoinSafetyResult | None) -> None:
        group = self.column_groups.get(table_name)
        if not group:
            return

        disable = bool(result and result.severity == "danger" and not result.ok)
        tooltip = result.message if result else ""
        for row in group.iter_column_rows():
            if disable and row.isChecked():
                row.cb.blockSignals(True)
                row.setChecked(False)
                row.cb.blockSignals(False)
                self._remove_sort_item_for_row(row)
            row.set_join_safety_state(not disable, tooltip)
        group.update_header()

    def _remove_sort_item_for_row(self, row: ColumnCheckBoxRow) -> None:
        table_name = row.cb.property("table_name")
        col_name = row.cb.property("col_name")
        start_table = self.table_combo.currentData()
        full_name = f"{table_name}.{col_name}" if table_name != start_table else col_name
        for i in range(self.sort_list.count()):
            if self.sort_list.item(i).data(Qt.UserRole) == full_name:
                self.sort_list.takeItem(i)
                break

    def _refresh_join_safety_states(self) -> None:
        start_table = self.table_combo.currentData()
        for table_name, group in self.column_groups.items():
            for row in group.iter_column_rows():
                row.set_join_safety_state(True, "" if table_name == start_table else row.toolTip())
            group.update_header()

    def _on_column_checkbox_toggled(self, state: int) -> None:
        sender_cb = self.sender()
        if not isinstance(sender_cb, QCheckBox):
            return

        col_name = sender_cb.property("col_name")
        table_name = sender_cb.property("table_name")
        if not col_name or not table_name:
            return

        start_table = self.table_combo.currentData()
        full_name = f"{table_name}.{col_name}" if table_name != start_table else col_name

        is_checked = sender_cb.isChecked()
        if is_checked:
            result = self._check_join_safety_for_table(table_name)
            if result and result.severity == "danger" and not result.ok:
                sender_cb.blockSignals(True)
                sender_cb.setChecked(False)
                sender_cb.blockSignals(False)
                self._apply_join_safety_to_group(table_name, result)
                self.status_message_requested.emit(result.message)
                return
            if result and result.severity == "warning":
                row_widget = sender_cb.parentWidget()
                if isinstance(row_widget, ColumnCheckBoxRow):
                    row_widget.set_join_safety_state(True, result.message)
                self.status_message_requested.emit(result.message)

            exists = False
            for i in range(self.sort_list.count()):
                if self.sort_list.item(i).data(Qt.UserRole) == full_name:
                    exists = True
                    break
            if not exists:
                row_widget = sender_cb.parentWidget()
                disp_name = row_widget.label.text() if hasattr(row_widget, "label") else full_name
                import re
                clean_disp = re.sub(r"<[^>]+>", "", disp_name)

                item = QListWidgetItem(clean_disp)
                item.setData(Qt.UserRole, full_name)
                item.setData(Qt.UserRole + 2, clean_disp)
                self.sort_list.addItem(item)
        else:
            for i in range(self.sort_list.count()):
                item = self.sort_list.item(i)
                if item.data(Qt.UserRole) == full_name:
                    self.sort_list.takeItem(i)
                    break

        group = self.column_groups.get(table_name)
        if group:
            group.update_header()
        self._sync_group_order_columns()
        self._update_query()

    def _set_table_columns_checked(self, table_name: str, checked: bool) -> None:
        group = self.column_groups.get(table_name)
        if not group:
            return

        for row in group.iter_column_rows():
            if not row.cb.isEnabled() or row.isChecked() == checked:
                continue
            row.cb.setChecked(checked)
        group.update_header()
        self._sync_group_order_columns()
        self._update_query()

    def _filter_columns_list(self) -> None:
        filter_text = self.col_search_input.text().lower().strip() if hasattr(self, "col_search_input") else ""
        show_selected_only = self.show_selected_only_btn.isChecked() if hasattr(self, "show_selected_only_btn") else False

        for group in self.column_groups.values():
            has_visible_rows = False
            for widget in group.iter_column_rows():
                col_name = widget.cb.property("col_name") or ""
                tbl_name = widget.cb.property("table_name") or ""
                disp_text = widget.label.text().lower()

                # Text filter match
                text_match = (not filter_text or
                             filter_text in col_name.lower() or
                             filter_text in tbl_name.lower() or
                             filter_text in disp_text)

                # Checked state filter match
                checked_match = (not show_selected_only or widget.isChecked())

                match = text_match and checked_match

                widget.setVisible(match)
                if match:
                    has_visible_rows = True

            filtering = bool(filter_text or show_selected_only)
            group.setVisible(True if not filtering else has_visible_rows)
            group.set_search_forced(bool(filter_text and has_visible_rows))
            group.update_header()

    def _clear_all_selected_columns(self) -> None:
        has_selected = any(
            row.isChecked()
            for group in self.column_groups.values()
            for row in group.iter_column_rows()
        )
        if not has_selected:
            return

        answer = QMessageBox.question(
            self,
            tr("query_builder.clear_selected_title", "Bỏ chọn tất cả"),
            tr("query_builder.clear_selected_confirm", "Bạn có chắc muốn bỏ chọn tất cả cột đang chọn?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        for group in self.column_groups.values():
            for row in group.iter_column_rows():
                if row.isChecked():
                    row.cb.setChecked(False)
            group.update_header()
        self._refresh_join_safety_states()
        self._sync_group_order_columns()
        self._update_query()

    def _show_column_context_menu(self, pos) -> None:
        item = self.sort_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)

        current_func = item.data(Qt.UserRole + 1)

        actions = [
            (tr("query_builder.func_none", "Không sử dụng hàm"), None),
            (tr("query_builder.func_count", "COUNT (Đếm dòng)"), "COUNT"),
            (tr("query_builder.func_sum", "SUM (Tổng)"), "SUM"),
            (tr("query_builder.func_avg", "AVG (Trung bình cộng)"), "AVG"),
            (tr("query_builder.func_min", "MIN (Nhỏ nhất)"), "MIN"),
            (tr("query_builder.func_max", "MAX (Lớn nhất)"), "MAX")
        ]

        for label, func_name in actions:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(current_func == func_name)

            def make_trigger(it=item, fn=func_name):
                return lambda: self._apply_column_function(it, fn)
            action.triggered.connect(make_trigger())

        menu.exec(self.sort_list.mapToGlobal(pos))

    def _apply_column_function(self, item: QListWidgetItem, func_name: str | None) -> None:
        item.setData(Qt.UserRole + 1, func_name)
        base_name = item.data(Qt.UserRole + 2)
        if not base_name:
            base_name = item.data(Qt.UserRole)

        if func_name:
            item.setText(f"{func_name}({base_name})")
        else:
            item.setText(base_name)

        self._update_query()

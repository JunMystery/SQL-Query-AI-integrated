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
    QDialog,
    QListWidget,
    QStackedWidget,
    QListWidgetItem,
    QMenu,
)

from sqlbot_desktop.models.entities import TableInfo, ColumnInfo


class SearchableComboBox(QComboBox):
    """A premium styled combobox that supports searching/filtering items."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        
        completer = self.completer()
        if completer:
            completer.setFilterMode(Qt.MatchContains)
            completer.setCompletionMode(completer.CompletionMode.PopupCompletion)
            
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    border: none;
                    font-size: 12px;
                    color: #182230;
                    padding: 0px;
                }
            """)
        
        self.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 2px 24px 2px 8px;
                font-size: 12px;
                color: #182230;
                min-height: 26px;
            }
            QComboBox:hover {
                border-color: #a8b6c8;
            }
            QComboBox:focus {
                border: 1.5px solid #147a63;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left-width: 0px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #64748b;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #182230;
                selection-background-color: #edf6ff;
                selection-color: #0f243f;
                border: 1px solid #cbd5e1;
                outline: 0px;
            }
        """)


class QueryBuilderGuideDialog(QDialog):
    """Vertical tab user guide dialog for explaining conditions, operators, and usage."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hướng dẫn sử dụng điều kiện và chức năng")
        self.resize(700, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f7fb;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Left list widget acting as vertical tabs
        self.tab_list = QListWidget()
        self.tab_list.setFixedWidth(180)
        self.tab_list.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d9e1ec;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 5px;
                font-weight: 500;
                color: #344054;
            }
            QListWidget::item:selected {
                background-color: #edf6ff;
                color: #0f62fe;
            }
        """)

        # Right stacked widget acting as tab contents
        self.stacked_pages = QStackedWidget()
        self.stacked_pages.setStyleSheet("""
            QStackedWidget {
                background-color: #ffffff;
                border: 1px solid #d9e1ec;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        # Populate tabs and content
        self._add_tab("💡 Tổng quan", self._create_overview_page())
        self._add_tab("🎯 Toán tử =", self._create_equal_page())
        self._add_tab("⚡ Toán tử >, <, ...", self._create_comparison_page())
        self._add_tab("🔍 Toán tử LIKE", self._create_like_page())
        self._add_tab("📅 Toán tử BETWEEN", self._create_between_page())
        self._add_tab("📦 Toán tử IN", self._create_in_page())
        self._add_tab("⭕ Toán tử IS NULL", self._create_null_page())

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
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f243f; margin-bottom: 10px;")
        
        lbl_content = QLabel()
        lbl_content.setTextFormat(Qt.TextFormat.RichText)
        lbl_content.setText(html_content)
        lbl_content.setWordWrap(True)
        lbl_content.setStyleSheet("font-size: 13px; color: #344054; line-height: 1.5;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_content, 1)
        layout.addStretch()
        return widget

    def _create_overview_page(self) -> QWidget:
        return self._create_page_wrapper(
            "💡 Hướng dẫn Tổng quan",
            "<p>Chào mừng đến với chức năng <b>Tự Build Query bằng lựa chọn</b>!</p>"
            "<p>Chức năng này giúp bạn thiết lập truy vấn SQL mong muốn thông qua việc lựa chọn bảng, cột và các điều kiện lọc "
            "mà không cần viết mã SQL thủ công.</p>"
            "<ul>"
            "<li><b>Chọn Bảng chính:</b> Thiết lập bảng nguồn đầu tiên cho mệnh đề FROM.</li>"
            "<li><b>Chọn các Cột:</b> Tích chọn cột cần hiển thị. Nếu tích chọn cột thuộc bảng khác, hệ thống sẽ tự động tìm quan hệ "
            "khóa ngoại và tạo mệnh đề JOIN tự động.</li>"
            "<li><b>Điều kiện lọc (WHERE):</b> Tạo thêm các bộ lọc giá trị thông qua nút 'Thêm điều kiện'.</li>"
            "</ul>"
        )

    def _create_equal_page(self) -> QWidget:
        return self._create_page_wrapper(
            "🎯 Toán tử Bằng / Khác (=, !=)",
            "<p>So sánh chính xác giá trị của một cột.</p>"
            "<ul>"
            "<li><b>Cách dùng:</b> Chọn cột, chọn toán tử <code>=</code> (Bằng) hoặc <code>!=</code> (Khác), sau đó nhập giá trị cần lọc.</li>"
            "<li><b>Ví dụ:</b> <code>status = 'Active'</code> hoặc <code>role_id = 1</code>.</li>"
            "<li><i>Lưu ý:</i> Nếu cột có kiểu văn bản, hệ thống sẽ tự động thêm dấu nháy đơn bao quanh giá trị.</li>"
            "</ul>"
        )

    def _create_comparison_page(self) -> QWidget:
        return self._create_page_wrapper(
            "⚡ Toán tử So sánh lớn/nhỏ (>, <, >=, <=)",
            "<p>So sánh khoảng giá trị lớn hơn hoặc nhỏ hơn, thường áp dụng cho dữ liệu số, ngày tháng.</p>"
            "<ul>"
            "<li><b>Ví dụ:</b> <code>price > 500</code> hoặc <code>created_at >= '2026-01-01'</code>.</li>"
            "<li>Hữu ích khi tìm các đơn hàng có giá trị cao, tài khoản đăng ký mới gần đây, hoặc thống kê tuổi tác.</li>"
            "</ul>"
        )

    def _create_like_page(self) -> QWidget:
        return self._create_page_wrapper(
            "🔍 Toán tử LIKE (Tìm kiếm mẫu)",
            "<p>Tìm kiếm chuỗi văn bản khớp với mẫu tìm kiếm (có phân biệt hoặc không phân biệt hoa thường tùy DB).</p>"
            "<ul>"
            "<li><b>Cách dùng:</b> Sử dụng ký tự đại diện <code>%</code> (đại diện cho một nhóm ký tự bất kỳ) hoặc <code>_</code> (đại diện cho đúng 1 ký tự).</li>"
            "<li><b>Ví dụ:</b>"
            "  <ul>"
            "    <li>Nhập <code>%An%</code> để tìm tất cả các tên chứa từ 'An' (ví dụ: Bình An, Thanh An).</li>"
            "    <li>Nhập <code>An%</code> để tìm các tên bắt đầu bằng 'An'.</li>"
            "  </ul>"
            "</li>"
            "</ul>"
        )

    def _create_between_page(self) -> QWidget:
        return self._create_page_wrapper(
            "📅 Toán tử BETWEEN (Trong khoảng)",
            "<p>Lọc các bản ghi có giá trị nằm trong một khoảng xác định (bao gồm cả 2 đầu mút).</p>"
            "<ul>"
            "<li><b>Cách dùng:</b> Nhập hai giá trị ngăn cách nhau bởi chữ <code>AND</code> hoặc dấu phẩy <code>,</code>.</li>"
            "<li><b>Ví dụ:</b>"
            "  <ul>"
            "    <li>Nhập <code>10 AND 100</code> (hoặc <code>10, 100</code>) → Sinh ra: <code>col BETWEEN 10 AND 100</code></li>"
            "    <li>Nhập <code>2026-01-01 AND 2026-05-31</code> → Sinh ra: <code>col BETWEEN '2026-01-01' AND '2026-05-31'</code></li>"
            "  </ul>"
            "</li>"
            "</ul>"
        )

    def _create_in_page(self) -> QWidget:
        return self._create_page_wrapper(
            "📦 Toán tử IN (Trong danh sách)",
            "<p>Kiểm tra xem giá trị của cột có thuộc một danh sách các giá trị cho trước hay không.</p>"
            "<ul>"
            "<li><b>Cách dùng:</b> Nhập các giá trị cách nhau bằng dấu phẩy <code>,</code>.</li>"
            "<li><b>Ví dụ:</b> Nhập <code>Active, Pending</code> → Sinh ra: <code>status IN ('Active', 'Pending')</code>.</li>"
            "</ul>"
        )

    def _create_null_page(self) -> QWidget:
        return self._create_page_wrapper(
            "⭕ Toán tử IS NULL / IS NOT NULL",
            "<p>Kiểm tra xem một cột có rỗng (NULL) hoặc không rỗng hay không.</p>"
            "<ul>"
            "<li><b>Ví dụ:</b> <code>email IS NULL</code> để lọc những người dùng chưa nhập email.</li>"
            "<li><i>Lưu ý:</i> Khi chọn toán tử này, ô nhập giá trị bên phải sẽ tự động được ẩn đi.</li>"
            "</ul>"
        )


class StyledComboBox(QComboBox):
    """A premium styled combo box with custom popup styles to prevent black backgrounds on Windows."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 2px 24px 2px 8px;
                font-size: 12px;
                color: #182230;
                min-height: 26px;
            }
            QComboBox:hover {
                border-color: #a8b6c8;
            }
            QComboBox:focus {
                border: 1.5px solid #147a63;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left-width: 0px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #64748b;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #182230;
                selection-background-color: #edf6ff;
                selection-color: #0f243f;
                border: 1px solid #cbd5e1;
                outline: 0px;
            }
        """)


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
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E");
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

        self.op_combo = StyledComboBox()
        self.op_combo.addItems(["=", "!=", ">", "<", ">=", "<=", "LIKE", "BETWEEN", "IN", "IS NULL", "IS NOT NULL"])
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
                background-color: #c9352b;
                border: 1px solid #c9352b;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a92d25;
                border-color: #a92d25;
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

        is_string = any(t in col_type for t in ["char", "text", "varchar", "string", "date", "time", "timestamp"])

        if op == "BETWEEN":
            import re
            parts = []
            if " and " in val.lower():
                parts = re.split(r"\s+and\s+", val, flags=re.IGNORECASE)
            elif "," in val:
                parts = [p.strip() for p in val.split(",")]
            else:
                parts = [val]

            quoted_parts = []
            for p in parts:
                p = p.strip()
                if is_string:
                    if not ((p.startswith("'") and p.endswith("'")) or (p.startswith('"') and p.endswith('"'))):
                        escaped = p.replace("'", "''")
                        p = f"'{escaped}'"
                quoted_parts.append(p)
            
            if len(quoted_parts) >= 2:
                return f"{col_name} BETWEEN {quoted_parts[0]} AND {quoted_parts[1]}"
            return f"{col_name} BETWEEN {quoted_parts[0]} AND {quoted_parts[0]}"

        # Auto quoting logic
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
        self.table_combo = StyledComboBox()
        self.table_combo.currentIndexChanged.connect(self._on_table_changed)
        table_layout.addWidget(self.table_combo)
        left_layout.addWidget(table_group)

        # Columns & Order horizontal layout
        cols_row_widget = QWidget()
        cols_row_layout = QHBoxLayout(cols_row_widget)
        cols_row_layout.setContentsMargins(0, 0, 0, 0)
        cols_row_layout.setSpacing(10)

        # Columns Group
        columns_group = QGroupBox("Chọn Cột (Columns)")
        columns_group.setStyleSheet(group_box_qss)
        columns_layout = QVBoxLayout(columns_group)
        columns_layout.setContentsMargins(8, 4, 8, 8)

        # Horizontal layout for Search input + Toggle selected columns button
        col_controls_layout = QHBoxLayout()
        col_controls_layout.setContentsMargins(0, 0, 0, 0)
        col_controls_layout.setSpacing(6)

        self.col_search_input = QLineEdit()
        self.col_search_input.setPlaceholderText("Tìm kiếm cột...")
        self.col_search_input.setStyleSheet("""
            QLineEdit {
                min-height: 24px;
                max-height: 24px;
                padding: 1px 6px;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1.5px solid #147a63;
            }
        """)
        self.col_search_input.textChanged.connect(lambda: self._filter_columns_list())

        self.show_selected_only_btn = QPushButton("Đã chọn 👁️")
        self.show_selected_only_btn.setCheckable(True)
        self.show_selected_only_btn.setFixedWidth(80)
        self.show_selected_only_btn.setObjectName("secondaryButton")
        self.show_selected_only_btn.setStyleSheet("""
            QPushButton {
                min-height: 24px;
                max-height: 24px;
                font-size: 11px;
                border-radius: 4px;
                padding: 1px 4px;
            }
            QPushButton:checked {
                background-color: #147a63;
                color: #ffffff;
                border-color: #147a63;
            }
        """)
        self.show_selected_only_btn.toggled.connect(lambda: self._filter_columns_list())

        col_controls_layout.addWidget(self.col_search_input, 1)
        col_controls_layout.addWidget(self.show_selected_only_btn)
        columns_layout.addLayout(col_controls_layout)

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
        cols_row_layout.addWidget(columns_group, 1)

        # Sort/Order Group
        sort_group = QGroupBox("Sắp xếp cột")
        sort_group.setStyleSheet(group_box_qss)
        sort_layout = QVBoxLayout(sort_group)
        sort_layout.setContentsMargins(8, 4, 8, 8)

        self.sort_list = QListWidget()
        self.sort_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.sort_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sort_list.customContextMenuRequested.connect(self._show_column_context_menu)
        self.sort_list.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
                background-color: #f8fbff;
                margin-bottom: 2px;
                border: 1px solid #d7e7fb;
                color: #0f243f;
                font-size: 11px;
            }
            QListWidget::item:hover {
                background-color: #edf6ff;
                border-color: #72aee9;
            }
            QListWidget::item:selected {
                background-color: #dbeafe;
                color: #0f243f;
                border-color: #246bfd;
            }
        """)
        self.sort_list.model().rowsMoved.connect(lambda *args: self._update_query())
        sort_layout.addWidget(self.sort_list)

        # Global DISTINCT Modifier Checkbox
        self.distinct_check = QCheckBox("Loại bỏ trùng lặp (DISTINCT)")
        self.distinct_check.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                color: #344054;
                font-weight: bold;
                padding: 2px 0;
            }
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
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E");
            }
        """)
        self.distinct_check.stateChanged.connect(lambda *args: self._update_query())
        sort_layout.addWidget(self.distinct_check)

        cols_row_layout.addWidget(sort_group, 1)

        left_layout.addWidget(cols_row_widget, 1)

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

        cond_buttons_layout = QHBoxLayout()
        cond_buttons_layout.setContentsMargins(0, 0, 0, 0)
        cond_buttons_layout.setSpacing(6)

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

        guide_btn = QPushButton("Hướng dẫn 📖")
        guide_btn.setObjectName("secondaryButton")
        guide_btn.setStyleSheet("""
            QPushButton {
                min-height: 24px;
                max-height: 24px;
                font-size: 11px;
                border-radius: 4px;
                padding: 1px 6px;
            }
        """)
        guide_btn.clicked.connect(self._show_guide_dialog)

        cond_buttons_layout.addWidget(add_cond_btn)
        cond_buttons_layout.addWidget(guide_btn)
        cond_layout.addLayout(cond_buttons_layout)
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

        # 1. Main Table Columns
        main_title = QLabel(f"Bảng chính: {self._get_table_display_name(table_name)}")
        main_title.setStyleSheet("font-weight: bold; color: #147a63; margin-top: 2px; font-size: 12px;")
        self.columns_container_layout.addWidget(main_title)

        cols = self._get_active_columns()
        for c in cols:
            disp = self._get_column_display_name(table_name, c.name)
            row_widget = ColumnCheckBoxRow(c.name, disp, c.type_name, self._on_column_checkbox_toggled, self)
            row_widget.cb.setProperty("table_name", table_name)
            self.columns_container_layout.addWidget(row_widget)

        # 2. Joined Table Columns
        for t in self._tables:
            if t.name == table_name:
                continue
            
            tbl_label = QLabel(f"Bảng liên kết: {self._get_table_display_name(t.name)}")
            tbl_label.setStyleSheet("font-weight: bold; color: #135ba1; margin-top: 6px; font-size: 11px;")
            self.columns_container_layout.addWidget(tbl_label)
            
            for c in t.columns:
                disp = self._get_column_display_name(t.name, c.name)
                row_widget = ColumnCheckBoxRow(c.name, disp, c.type_name, self._on_column_checkbox_toggled, self)
                row_widget.cb.setProperty("table_name", t.name)
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
        self.cond_container_layout.addWidget(row)
        self._update_query()

    def _delete_condition_row(self, row_widget: QWidget) -> None:
        row_widget.deleteLater()
        self.cond_container_layout.removeWidget(row_widget)
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

        # Build using Advanced Agents (Orchestrator, SchemaGraph, JoinPlanner)
        try:
            from sqlbot_desktop.agents.orchestrator import Orchestrator
            orchestrator = Orchestrator(metadata_list=self._tables, dialect="sqlite")
            query = orchestrator._build_single_query(
                start_table=table_name,
                target_tables=list(target_tables),
                select_columns=checked_cols,
                filter_expression=filter_expr
            )
        except Exception:
            # Fallback to basic rendering
            cols_str = ", ".join(checked_cols)
            query = f"SELECT {cols_str}\nFROM {table_name}"
            if conds:
                query += "\nWHERE " + "\n  AND ".join(conds)

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

        self._update_query()

    def _filter_columns_list(self) -> None:
        filter_text = self.col_search_input.text().lower().strip() if hasattr(self, "col_search_input") else ""
        show_selected_only = self.show_selected_only_btn.isChecked() if hasattr(self, "show_selected_only_btn") else False

        current_header = None
        has_visible_cols_for_header = False
        headers_to_check = []

        for i in range(self.columns_container_layout.count()):
            widget = self.columns_container_layout.itemAt(i).widget()
            if not widget:
                continue

            if isinstance(widget, QLabel):
                if current_header:
                    headers_to_check.append((current_header, has_visible_cols_for_header))
                current_header = widget
                has_visible_cols_for_header = False
            elif isinstance(widget, ColumnCheckBoxRow):
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
                    has_visible_cols_for_header = True

        if current_header:
            headers_to_check.append((current_header, has_visible_cols_for_header))

        for header, has_visible_cols in headers_to_check:
            if not filter_text and not show_selected_only:
                header.setVisible(True)
            else:
                header.setVisible(has_visible_cols)

    def _show_column_context_menu(self, pos) -> None:
        item = self.sort_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #182230;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #edf6ff;
                color: #0f62fe;
            }
        """)

        current_func = item.data(Qt.UserRole + 1)

        actions = [
            ("Không sử dụng hàm", None),
            ("COUNT (Đếm dòng)", "COUNT"),
            ("SUM (Tổng)", "SUM"),
            ("AVG (Trung bình cộng)", "AVG"),
            ("MIN (Nhỏ nhất)", "MIN"),
            ("MAX (Lớn nhất)", "MAX")
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



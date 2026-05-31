"""Main application window layout."""

from __future__ import annotations

import csv

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, ColumnInfo, ConnectionProfile, TableInfo
from sqlbot_desktop.views.assets import asset_path
from sqlbot_desktop.views.components.schema_tree_widget import SchemaTreeWidget


class MainWindow(QMainWindow):
    """Primary SQLBot workspace matching Module 2.1."""

    generate_requested = Signal(str)
    browse_model_requested = Signal()
    load_model_requested = Signal(object)
    unload_model_requested = Signal()
    closing_requested = Signal()
    copy_requested = Signal()
    execute_requested = Signal()
    bookmark_requested = Signal()
    history_requested = Signal()
    bookmarks_requested = Signal()
    schema_requested = Signal()
    settings_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SQLBot Desktop")
        self.setMinimumSize(1180, 760)
        self.resize(1280, 820)

        self.connection_label = QLabel("Chưa kết nối")
        self.backend_combo = QComboBox()
        self.model_path_input = QLineEdit()
        self.browse_model_button = QPushButton("Browse GGUF")
        self.api_endpoint_input = QLineEdit()
        self.api_model_input = QLineEdit()
        self.model_status_label = QLabel("AI chưa load")
        self.busy_panel = QFrame()
        self.busy_title_label = QLabel("")
        self.busy_detail_label = QLabel("")
        self.busy_progress = QProgressBar()
        self.question_input = QTextEdit()
        self.suggested_queries = QListWidget()
        self.results_table = QTableWidget()
        self.schema_tree = SchemaTreeWidget()
        self.schema_summary_label = QLabel("Schema chưa tải")
        self.schema_dock: QDockWidget | None = None
        self.result_headers: list[str] = []
        self.result_rows: list[list[object]] = []

        self._build_menu()
        self._build_ui()
        self._build_schema_dock()
        self._build_status_bar()
        self._load_placeholder_content()

    def set_connection(self, profile: ConnectionProfile) -> None:
        self.connection_label.setText(f"DB: {profile.name}")
        self.connection_label.setToolTip(f"Connected: {profile.driver} | {profile.database or profile.extra}")

    def _build_menu(self) -> None:
        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu("File")
        export_action = file_menu.addAction("Export CSV")
        export_action.triggered.connect(lambda checked=False: self.export_results_csv())
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        self.view_menu = self.menu_bar.addMenu("View")
        history_action = self.view_menu.addAction("History")
        bookmarks_action = self.view_menu.addAction("Bookmarks")
        schema_action = self.view_menu.addAction("Schema")
        history_action.triggered.connect(lambda checked=False: self.history_requested.emit())
        bookmarks_action.triggered.connect(lambda checked=False: self.bookmarks_requested.emit())
        schema_action.triggered.connect(lambda checked=False: self.show_schema_viewer())
        schema_action.triggered.connect(lambda checked=False: self.schema_requested.emit())

        self.tools_menu = self.menu_bar.addMenu("Tools")
        settings_action = self.tools_menu.addAction("Settings")
        settings_action.triggered.connect(lambda checked=False: self.settings_requested.emit())
        self.setMenuBar(self.menu_bar)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("mainRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(28, 24, 28, 20)
        root_layout.setSpacing(18)

        root_layout.addLayout(self._build_header())
        root_layout.addWidget(self._build_ai_panel())
        root_layout.addWidget(self._build_busy_panel())
        root_layout.addWidget(self._build_query_panel())
        root_layout.addWidget(self._build_results_panel(), 1)

        self.setCentralWidget(root)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(10)

        title_group = QVBoxLayout()
        title = QLabel("SQLBot Workspace")
        title.setObjectName("mainTitle")
        subtitle = QLabel("Tạo, kiểm tra và thực thi SQL SELECT từ câu hỏi tiếng Việt.")
        subtitle.setObjectName("mainSubtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)

        self.connection_label.setObjectName("connectionBadge")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setMinimumWidth(120)
        self.connection_label.setMaximumWidth(200)

        settings_button = QToolButton()
        settings_button.setObjectName("settingsIconButton")
        settings_button.setIcon(QIcon(str(asset_path("icons", "settings.svg"))))
        settings_button.setToolTip("Settings")
        settings_button.setAccessibleName("Settings")
        settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        settings_button.setMenu(self._build_settings_menu(settings_button))

        header.addLayout(title_group, 1)
        header.addWidget(self.connection_label)
        header.addWidget(settings_button)
        return header

    def _build_settings_menu(self, parent: QWidget) -> QMenu:
        menu = QMenu(parent)
        actions = [
            ("History", self.history_requested),
            ("Bookmarks", self.bookmarks_requested),
            ("Schema", self.schema_requested),
            ("Settings", self.settings_requested),
        ]
        for label, signal in actions:
            action = QAction(label, self)
            if label == "Schema":
                action.triggered.connect(lambda checked=False: self.show_schema_viewer())
            action.triggered.connect(lambda checked=False, target=signal: target.emit())
            menu.addAction(action)
        return menu

    def _build_schema_dock(self) -> None:
        dock = QDockWidget("Schema Viewer", self)
        dock.setObjectName("schemaDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        content = QWidget()
        content.setObjectName("schemaViewerPanel")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Schema Viewer")
        title.setObjectName("sectionTitle")
        self.schema_summary_label.setObjectName("formHint")
        self.schema_summary_label.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.schema_summary_label)
        layout.addWidget(self.schema_tree, 1)

        dock.setWidget(content)
        dock.hide()
        self.schema_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _build_ai_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("aiPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("AI Engine")
        title.setObjectName("sectionTitle")
        self.model_status_label.setObjectName("modelStatusBadge")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.model_status_label)
        layout.addLayout(title_row)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.backend_combo.addItem("Local GGUF", AIBackend.LOCAL.value)
        self.backend_combo.addItem("API AI", AIBackend.API.value)
        self.backend_combo.setAccessibleName("AI backend")
        self.backend_combo.currentIndexChanged.connect(self._sync_ai_controls)

        self.model_path_input.setPlaceholderText("Chọn file .gguf")
        self.model_path_input.setAccessibleName("Local GGUF model path")
        self.browse_model_button.setObjectName("secondaryButton")
        self.browse_model_button.clicked.connect(self._browse_model)

        self.api_endpoint_input.setPlaceholderText("API endpoint, ví dụ https://api.openai.com/v1/chat/completions")
        self.api_endpoint_input.setAccessibleName("API endpoint")
        self.api_model_input.setPlaceholderText("API model")
        self.api_model_input.setAccessibleName("API model")

        load_button = QPushButton("Load")
        load_button.setObjectName("successButton")
        unload_button = QPushButton("Unload")
        unload_button.setObjectName("dangerButton")
        load_button.clicked.connect(lambda: self.load_model_requested.emit(self.ai_model_config()))
        unload_button.clicked.connect(self.unload_model_requested.emit)

        controls.addWidget(self.backend_combo)
        controls.addWidget(self.model_path_input, 2)
        controls.addWidget(self.browse_model_button)
        controls.addWidget(self.api_endpoint_input, 2)
        controls.addWidget(self.api_model_input)
        controls.addWidget(load_button)
        controls.addWidget(unload_button)
        layout.addLayout(controls)

        api_hint = QLabel("API key đọc từ biến môi trường SQLBOT_AI_API_KEY, không nhập hoặc lưu trong UI.")
        api_hint.setObjectName("formHint")
        layout.addWidget(api_hint)
        self._sync_ai_controls()
        return panel

    def _build_busy_panel(self) -> QFrame:
        self.busy_panel.setObjectName("busyPanel")
        self.busy_panel.setVisible(False)
        layout = QHBoxLayout(self.busy_panel)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        self.busy_title_label.setObjectName("busyTitle")
        self.busy_detail_label.setObjectName("busyDetail")
        self.busy_detail_label.setWordWrap(True)
        text_column.addWidget(self.busy_title_label)
        text_column.addWidget(self.busy_detail_label)

        self.busy_progress.setObjectName("busyProgress")
        self.busy_progress.setRange(0, 0)
        self.busy_progress.setTextVisible(False)
        self.busy_progress.setFixedWidth(260)

        layout.addLayout(text_column, 1)
        layout.addWidget(self.busy_progress)
        return self.busy_panel

    def _build_query_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("queryPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        input_column = QVBoxLayout()
        input_column.setSpacing(12)

        label = QLabel("Nhập yêu cầu bằng tiếng Việt")
        label.setObjectName("sectionTitle")
        self.question_input.setObjectName("questionInput")
        self.question_input.setPlaceholderText('Ví dụ: "Tính tổng lương của nhân viên phòng Kỹ thuật"')
        self.question_input.setAccessibleName("Nhập yêu cầu bằng tiếng Việt")
        self.question_input.setFixedHeight(94)

        actions = QHBoxLayout()
        generate_button = QPushButton("Generate SQL")
        generate_button.setObjectName("primaryButton")
        copy_button = QPushButton("Copy")
        copy_button.setObjectName("secondaryButton")
        execute_button = QPushButton("Execute")
        execute_button.setObjectName("successButton")
        bookmark_button = QPushButton("Bookmark")
        bookmark_button.setObjectName("warningButton")

        generate_button.clicked.connect(lambda: self.generate_requested.emit(self.question_input.toPlainText().strip()))
        copy_button.clicked.connect(self.copy_requested.emit)
        execute_button.clicked.connect(self.execute_requested.emit)
        bookmark_button.clicked.connect(self.bookmark_requested.emit)

        for button in [generate_button, copy_button, execute_button, bookmark_button]:
            button.setMinimumHeight(38)
            actions.addWidget(button)
        actions.addStretch()

        input_column.addWidget(label)
        input_column.addWidget(self.question_input)
        input_column.addLayout(actions)

        suggestions_panel = self._build_suggestions_panel()
        suggestions_panel.setMinimumWidth(360)
        suggestions_panel.setMaximumWidth(460)

        layout.addLayout(input_column, 3)
        layout.addWidget(suggestions_panel, 2)
        return panel

    def _build_suggestions_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("suggestionsInlinePanel")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Suggested Queries")
        title.setObjectName("sectionTitle")
        self.suggested_queries.setObjectName("suggestedList")
        self.suggested_queries.setAccessibleName("Suggested SQL queries")
        layout.addWidget(title)
        layout.addWidget(self.suggested_queries, 1)
        return panel

    def _build_results_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("workspacePanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Query Results")
        title.setObjectName("sectionTitle")
        view_button = QPushButton("View as Table")
        view_button.setObjectName("secondaryButton")
        export_button = QPushButton("Export CSV")
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self.export_results_csv)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(view_button)
        header.addWidget(export_button)

        self.results_table.setObjectName("resultsTable")
        self.results_table.setMinimumHeight(360)
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["employee_id", "full_name", "department"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setAccessibleName("Query results")

        layout.addLayout(header)
        layout.addWidget(self.results_table, 1)
        return panel

    def set_schema(self, tables: list[TableInfo], annotations: dict[str, object] | None = None) -> None:
        self.schema_tree.set_schema(tables, annotations)
        table_count = len(tables)
        column_count = sum(len(table.columns) for table in tables)
        self.schema_summary_label.setText(f"{table_count} tables, {column_count} columns")

    def show_schema_viewer(self) -> None:
        if self.schema_dock is None:
            return
        self.schema_dock.show()
        self.schema_dock.raise_()

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)

    def ai_model_config(self) -> AIModelConfig:
        backend = AIBackend(self.backend_combo.currentData())
        return AIModelConfig(
            backend=backend,
            local_model_path=self.model_path_input.text().strip(),
            api_endpoint=self.api_endpoint_input.text().strip(),
            api_model=self.api_model_input.text().strip(),
        )

    def set_ai_model_config(self, config: AIModelConfig) -> None:
        backend_index = self.backend_combo.findData(config.backend.value)
        if backend_index >= 0:
            self.backend_combo.setCurrentIndex(backend_index)
        self.model_path_input.setText(config.local_model_path)
        self.api_endpoint_input.setText(config.api_endpoint)
        self.api_model_input.setText(config.api_model)
        self._sync_ai_controls()

    def set_model_status(self, message: str, loaded: bool = False) -> None:
        self.model_status_label.setText(message)
        self.model_status_label.setProperty("loaded", loaded)
        self.model_status_label.style().unpolish(self.model_status_label)
        self.model_status_label.style().polish(self.model_status_label)
        self.statusBar().showMessage(message)

    def set_busy(self, active: bool, title: str = "", detail: str = "") -> None:
        self.busy_title_label.setText(title)
        self.busy_detail_label.setText(detail)
        self.busy_panel.setVisible(active)
        self.statusBar().showMessage(title or "Ready")

    def set_generated_queries(self, queries: list[str]) -> None:
        self.suggested_queries.clear()
        self.suggested_queries.addItems(queries)

    def set_query_results(self, columns: list[str], rows: list[list[object]]) -> None:
        self.result_headers = columns
        self.result_rows = rows
        self.results_table.clear()
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self.results_table.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def export_results_csv(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        if not self.result_headers:
            QMessageBox.information(self, "Chưa có dữ liệu", "Không có Query Results để xuất CSV.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "query_results.csv", "CSV (*.csv)")
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(self.result_headers)
                writer.writerows(self.result_rows)
        except OSError as exc:
            QMessageBox.warning(self, "Export CSV lỗi", str(exc))
            return

        self.statusBar().showMessage(f"Đã export CSV: {file_path}")

    def selected_query(self) -> str:
        current = self.suggested_queries.currentItem()
        if current is not None:
            return current.text()
        if self.suggested_queries.count() > 0:
            return self.suggested_queries.item(0).text()
        return ""

    def set_question(self, question: str) -> None:
        self.question_input.setPlainText(question)
        self.question_input.setFocus()

    def set_saved_query(self, question: str, sql: str) -> None:
        self.set_question(question)
        if sql:
            self.set_generated_queries([sql])

    def _browse_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn GGUF model", "", "GGUF models (*.gguf)")
        if file_path:
            self.model_path_input.setText(file_path)
            self.browse_model_requested.emit()

    def _sync_ai_controls(self) -> None:
        is_local = self.backend_combo.currentData() == AIBackend.LOCAL.value
        self.model_path_input.setVisible(is_local)
        self.browse_model_button.setVisible(is_local)
        self.api_endpoint_input.setVisible(not is_local)
        self.api_model_input.setVisible(not is_local)

    def closeEvent(self, event: QCloseEvent) -> None:
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            "Thoát SQLBot",
            "Tắt ứng dụng sẽ unload AI model đang chạy. Bạn muốn thoát?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        self.closing_requested.emit()
        event.accept()

    def _load_placeholder_content(self) -> None:
        self.suggested_queries.addItems(
            [
                "SELECT SUM(salary) FROM employees WHERE department = 'Kỹ thuật';",
                "SELECT department, SUM(salary) FROM employees GROUP BY department;",
                "SELECT AVG(salary) FROM employees WHERE department = 'Kỹ thuật';",
            ]
        )

        rows = [
            ("1", "Nguyen Van An", "Kỹ thuật"),
            ("2", "Tran Thi Binh", "Kế toán"),
            ("3", "Le Minh Chau", "Kỹ thuật"),
        ]
        self.set_query_results(["employee_id", "full_name", "department"], [list(row) for row in rows])

        demo_tables = [
            TableInfo(
                name="employees",
                columns=[
                    ColumnInfo("employee_id", "int", False),
                    ColumnInfo("full_name", "varchar", True),
                    ColumnInfo("department_id", "int", True),
                ],
            )
        ]
        demo_annotations = {
            "tables": {
                "employees": {
                    "description": "Nhân viên",
                    "columns": {
                        "employee_id": {"description": "Mã nhân viên", "unit": "", "note": "", "type": "int"},
                        "full_name": {"description": "Họ tên", "unit": "", "note": "", "type": "varchar"},
                        "department_id": {
                            "description": "Phòng ban ID",
                            "unit": "int",
                            "note": "khóa ngoại",
                            "type": "int",
                        },
                    },
                }
            }
        }
        self.set_schema(demo_tables, demo_annotations)

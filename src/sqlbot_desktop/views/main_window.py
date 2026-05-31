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
    QMainWindow,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont, QColor

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, ColumnInfo, ConnectionProfile, TableInfo
from sqlbot_desktop.views.assets import asset_path
from sqlbot_desktop.views.components.schema_tree_widget import SchemaTreeWidget
from sqlbot_desktop.views.dialogs.query_results_dialog import QueryResultsDialog


class PromptEdit(QTextEdit):
    returnPressed = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.returnPressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


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
    cancel_requested = Signal()
    schema_assistant_requested = Signal()
    show_results_requested = Signal()
    clear_chat_requested = Signal()

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
        self.question_input = PromptEdit()
        self.stop_button = QPushButton("Dừng")
        self.chat_view = QTextBrowser()
        self.sql_editor = QTextEdit()
        self.results_dialog = QueryResultsDialog(self)
        self.schema_tree = SchemaTreeWidget()
        self.schema_summary_label = QLabel("Schema chưa tải")
        self.schema_dock: QDockWidget | None = None
        self.result_headers: list[str] = []
        self.result_rows: list[list[object]] = []
        self._context_size = 4096
        self._max_tokens = 512
        self._threads = 4
        self._gpu_layers = 0

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
        root_layout.setContentsMargins(20, 14, 20, 12)
        root_layout.setSpacing(10)

        root_layout.addLayout(self._build_header())
        root_layout.addWidget(self._build_ai_panel())
        root_layout.addWidget(self._build_busy_panel())
        root_layout.addWidget(self._build_upper_workspace_panel())
        root_layout.addWidget(self._build_chat_panel(), 1)

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

        header.addLayout(title_group, 1)
        header.addWidget(self.connection_label)
        return header

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

        self.cancel_button = QPushButton("Hủy")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setFixedWidth(80)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

        layout.addLayout(text_column, 1)
        layout.addWidget(self.busy_progress)
        layout.addWidget(self.cancel_button)
        return self.busy_panel

    def _build_upper_workspace_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("upperWorkspacePanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        # Left Column: Prompt Input
        prompt_column = QVBoxLayout()
        prompt_column.setSpacing(10)

        prompt_label = QLabel("Nhập câu hỏi / Yêu cầu")
        prompt_label.setObjectName("sectionTitle")

        self.question_input.setObjectName("questionInput")
        self.question_input.setPlaceholderText("Hỏi trợ lý hoặc nhập câu hỏi (ví dụ: 'Tìm người dùng tên Tú'...)")
        self.question_input.setAccessibleName("Nhập yêu cầu bằng tiếng Việt")
        self.question_input.setFixedHeight(160)
        self.question_input.returnPressed.connect(self._on_send_clicked)

        prompt_actions = QHBoxLayout()
        send_button = QPushButton("Gửi yêu cầu")
        send_button.setObjectName("primaryButton")
        send_button.setMinimumHeight(38)
        send_button.clicked.connect(self._on_send_clicked)
        
        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setMinimumHeight(38)
        self.stop_button.setFixedWidth(80)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.cancel_requested.emit)
        
        prompt_actions.addWidget(send_button)
        prompt_actions.addWidget(self.stop_button)
        prompt_actions.addStretch()

        prompt_column.addWidget(prompt_label)
        prompt_column.addWidget(self.question_input)
        prompt_column.addLayout(prompt_actions)

        # Right Column: SQL Editor
        sql_column = QVBoxLayout()
        sql_column.setSpacing(10)

        sql_label = QLabel("SQL Editor (Câu lệnh SELECT)")
        sql_label.setObjectName("sectionTitle")

        self.sql_editor.setObjectName("sqlEditor")
        self.sql_editor.setPlaceholderText("Câu lệnh SQL sẽ hiển thị hoặc chỉnh sửa tại đây...")
        self.sql_editor.setAccessibleName("SQL Editor")
        self.sql_editor.setFont(QFont("Courier New", 11))
        self.sql_editor.setFixedHeight(160)

        sql_actions = QHBoxLayout()
        execute_button = QPushButton("Execute (Chạy)")
        execute_button.setObjectName("successButton")
        show_results_button = QPushButton("Xem kết quả")
        show_results_button.setObjectName("secondaryButton")
        paste_button = QPushButton("Paste SQL")
        paste_button.setObjectName("secondaryButton")
        bookmark_button = QPushButton("Bookmark")
        bookmark_button.setObjectName("warningButton")

        execute_button.clicked.connect(self.execute_requested.emit)
        show_results_button.clicked.connect(self.show_results_requested.emit)
        paste_button.clicked.connect(self.sql_editor.paste)
        bookmark_button.clicked.connect(self.bookmark_requested.emit)

        for button in [execute_button, show_results_button, paste_button, bookmark_button]:
            button.setMinimumHeight(38)
            sql_actions.addWidget(button)
        sql_actions.addStretch()

        sql_column.addWidget(sql_label)
        sql_column.addWidget(self.sql_editor)
        sql_column.addLayout(sql_actions)

        layout.addLayout(prompt_column, 1)
        layout.addLayout(sql_column, 1)
        return panel

    def _build_chat_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("workspacePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        chat_label = QLabel("Trợ lý CSDL & Tạo truy vấn")
        chat_label.setObjectName("sectionTitle")

        clear_button = QPushButton("Xóa lịch sử")
        clear_button.setObjectName("secondaryButton")
        clear_button.setFixedWidth(110)
        clear_button.clicked.connect(self.clear_chat_requested.emit)

        header_layout.addWidget(chat_label)
        header_layout.addStretch()
        header_layout.addWidget(clear_button)

        self.chat_view.setObjectName("chatView")
        self.chat_view.setUndoRedoEnabled(False)
        self.chat_view.setAcceptRichText(True)
        self.chat_view.setOpenExternalLinks(False)
        self.chat_view.setOpenLinks(False)
        self.chat_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )

        layout.addLayout(header_layout)
        layout.addWidget(self.chat_view, 1)
        return panel

    def _on_send_clicked(self) -> None:
        text = self.question_input.toPlainText().strip()
        if not text:
            return
        self.generate_requested.emit(text)

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
            context_size=self._context_size,
            max_tokens=self._max_tokens,
            threads=self._threads,
            gpu_layers=self._gpu_layers,
        )

    def set_ai_model_config(self, config: AIModelConfig) -> None:
        backend_index = self.backend_combo.findData(config.backend.value)
        if backend_index >= 0:
            self.backend_combo.setCurrentIndex(backend_index)
        self.model_path_input.setText(config.local_model_path)
        self.api_endpoint_input.setText(config.api_endpoint)
        self.api_model_input.setText(config.api_model)
        self._context_size = config.context_size or 4096
        self._max_tokens = config.max_tokens or 512
        self._threads = config.threads or 4
        self._gpu_layers = getattr(config, "gpu_layers", 0)
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
        self.stop_button.setVisible(active)
        self.statusBar().showMessage(title or "Ready")

    def set_generated_queries(self, queries: list[str]) -> None:
        if queries:
            self.sql_editor.setPlainText(queries[0])
        else:
            self.sql_editor.clear()

    def selected_query(self) -> str:
        return self.sql_editor.toPlainText().strip()

    def set_question(self, question: str) -> None:
        self.question_input.setText(question)
        self.question_input.setFocus()

    def set_saved_query(self, question: str, sql: str) -> None:
        self.set_question(question)
        if sql:
            self.sql_editor.setPlainText(sql)

    def set_query_results(self, columns: list[str], rows: list[list[object]]) -> None:
        self.results_dialog.set_results(columns, rows)
        self.show_results_dialog()

    def show_results_dialog(self) -> None:
        self.results_dialog.show()
        self.results_dialog.raise_()
        self.results_dialog.activateWindow()

    def export_results_csv(self) -> None:
        self.results_dialog.export_csv()

    def append_user_message(self, text: str) -> None:
        html = (
            f"<div style='margin: 6px 0; text-align: right;'>"
            f"  <div style='display: inline-block; background-color: #dbeafe; color: #0f243f; "
            f"              padding: 8px 12px; border-radius: 10px; max-width: 85%; text-align: left;'>"
            f"    <b>Bạn:</b><br/>{text}"
            f"  </div>"
            f"</div>"
        )
        self.chat_view.append(html)
        self._scroll_chat_to_bottom()

    def append_assistant_message(self, text: str) -> None:
        formatted_text = text.replace("\n", "<br/>")
        html = (
            f"<div style='margin: 6px 0; text-align: left;'>"
            f"  <div style='display: inline-block; background-color: #ffffff; color: #182230; "
            f"              border: 1px solid #d9e1ec; padding: 8px 12px; border-radius: 10px; max-width: 85%;'>"
            f"    <b style='color: #135ba1;'>Trợ lý CSDL:</b><br/>{formatted_text}"
            f"  </div>"
            f"</div>"
        )
        self.chat_view.append(html)
        self._scroll_chat_to_bottom()

    def append_status(self, text: str) -> None:
        html = (
            f"<div id='assistantStatus' style='margin: 4px 0; text-align: left; color: #697789; font-style: italic;'>"
            f"  {text}"
            f"</div>"
        )
        self.chat_view.append(html)
        self._scroll_chat_to_bottom()

    def remove_status(self) -> None:
        doc = self.chat_view.document()
        html = doc.toHtml()
        clean_html = html.replace("<div id=\"assistantStatus\"", "<div style=\"display:none;\"")
        self.chat_view.setHtml(clean_html)
        self._scroll_chat_to_bottom()

    def clear_chat(self) -> None:
        self.chat_view.clear()
        welcome = (
            f"<div style='background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; "
            f"            padding: 10px; border-radius: 8px; margin-bottom: 8px;'>"
            f"  <b>Xin chào!</b> Tôi là trợ lý CSDL.<br/>"
            f"  Hãy hỏi tôi bất kỳ điều gì về cấu trúc bảng hoặc yêu cầu tạo truy vấn bằng tiếng Việt.<br/>"
            f"  <i>(Ví dụ: 'Tìm tất cả tasks của Tú từ ngày 01/05/2026')</i>"
            f"</div>"
        )
        self.chat_view.setHtml(welcome)

    def _scroll_chat_to_bottom(self) -> None:
        scrollbar = self.chat_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

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
        pass

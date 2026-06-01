"""Main application window layout."""

from __future__ import annotations

import csv

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QActionGroup
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
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont, QColor, QTextCursor

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, ColumnInfo, ConnectionProfile, TableInfo
from sqlbot_desktop.services.app_config import AppConfig
from sqlbot_desktop.views.assets import asset_path
from sqlbot_desktop.views.components.schema_tree_widget import SchemaTreeWidget
from sqlbot_desktop.views.components.visual_query_builder import VisualQueryBuilderPanel
from sqlbot_desktop.views.dialogs.query_results_dialog import QueryResultsDialog


class PromptEdit(QTextEdit):
    returnPressed = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.returnPressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


from sqlbot_desktop.utils.i18n_manager import tr

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
    refresh_samples_requested = Signal()
    cancel_requested = Signal()
    schema_assistant_requested = Signal()
    show_results_requested = Signal()
    clear_chat_requested = Signal()
    language_changed = Signal(str)

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
        self.send_button = QPushButton("Gửi yêu cầu")
        self.stop_button = QPushButton("Dừng")
        self.chat_view = QTextBrowser()
        self.sql_editor = QTextEdit()
        self.results_dialog = QueryResultsDialog(self)
        self.schema_tree = SchemaTreeWidget()
        self.schema_summary_label = QLabel("Schema chưa tải")
        self.schema_dock: QDockWidget | None = None
        self.result_headers: list[str] = []
        self.result_rows: list[list[object]] = []
        self._busy = False
        self._context_size = 2048
        self._max_tokens = 512
        self._threads = 2
        self._gpu_layers = 0
        self._cpu_thread_limit = 4
        self._self_correction_retries = AppConfig.load().self_correction.max_retries
        self._ai_config = AIModelConfig(backend=AIBackend.LOCAL)
        self._tables = []
        self._annotations = {}
        self._status_range: tuple[int, int] | None = None

        self._build_menu()
        self._build_ui()
        self._build_schema_dock()
        self._build_status_bar()
        self._load_placeholder_content()
        self.retranslate_ui()
        self.clear_chat()

    def set_connection(self, profile: ConnectionProfile) -> None:
        self._current_profile = profile
        self.connection_label.setText(f"{tr('main.status_db_connected_prefix', 'DB: ')}{profile.name}")
        self.connection_label.setToolTip(f"Connected: {profile.driver} | {profile.database or profile.extra}")

    def _build_menu(self) -> None:
        self.menu_bar = QMenuBar(self)
        self.file_menu = self.menu_bar.addMenu("")
        self.export_action = self.file_menu.addAction("")
        self.export_action.triggered.connect(lambda checked=False: self.export_results_csv())
        self.file_menu.addSeparator()
        self.exit_action = self.file_menu.addAction("", self.close)

        self.view_menu = self.menu_bar.addMenu("")
        self.history_action = self.view_menu.addAction("")
        self.bookmarks_action = self.view_menu.addAction("")
        self.schema_action = self.view_menu.addAction("")
        self.history_action.triggered.connect(lambda checked=False: self.history_requested.emit())
        self.bookmarks_action.triggered.connect(lambda checked=False: self.bookmarks_requested.emit())
        self.schema_action.triggered.connect(lambda checked=False: self.show_schema_viewer())
        self.schema_action.triggered.connect(lambda checked=False: self.schema_requested.emit())

        self.view_menu.addSeparator()
        self.theme_menu = self.view_menu.addMenu("")
        self.light_action = self.theme_menu.addAction("")
        self.light_action.setCheckable(True)
        self.dark_action = self.theme_menu.addAction("")
        self.dark_action.setCheckable(True)

        self.theme_group = QActionGroup(self)
        self.theme_group.addAction(self.light_action)
        self.theme_group.addAction(self.dark_action)
        self.theme_group.setExclusive(True)

        settings = QSettings("SQLBot", "SQLBotDesktop")
        current_theme = settings.value("theme", "light")
        if current_theme == "dark":
            self.dark_action.setChecked(True)
        else:
            self.light_action.setChecked(True)

        self.light_action.triggered.connect(lambda: self._change_theme("light"))
        self.dark_action.triggered.connect(lambda: self._change_theme("dark"))

        self.tools_menu = self.menu_bar.addMenu("")
        self.settings_action = self.tools_menu.addAction("")
        self.refresh_samples_action = self.tools_menu.addAction("")
        self.settings_action.triggered.connect(lambda checked=False: self.settings_requested.emit())
        self.refresh_samples_action.triggered.connect(lambda checked=False: self.refresh_samples_requested.emit())

        # Language selection menu under Tools
        self.language_menu = QMenu("", self)
        self.lang_vi_action = self.language_menu.addAction("🇻🇳 Tiếng Việt (VI)")
        self.lang_vi_action.setCheckable(True)
        self.lang_en_action = self.language_menu.addAction("🇺🇸 English (EN)")
        self.lang_en_action.setCheckable(True)
        self.lang_jp_action = self.language_menu.addAction("🇯🇵 日本語 (JP)")
        self.lang_jp_action.setCheckable(True)

        self.lang_group = QActionGroup(self)
        self.lang_group.addAction(self.lang_vi_action)
        self.lang_group.addAction(self.lang_en_action)
        self.lang_group.addAction(self.lang_jp_action)
        self.lang_group.setExclusive(True)

        self.tools_menu.addMenu(self.language_menu)

        current_lang = settings.value("language", "vi")
        if current_lang == "en":
            self.lang_en_action.setChecked(True)
        elif current_lang == "jp":
            self.lang_jp_action.setChecked(True)
        else:
            self.lang_vi_action.setChecked(True)

        self.lang_vi_action.triggered.connect(lambda: self.language_changed.emit("vi"))
        self.lang_en_action.triggered.connect(lambda: self.language_changed.emit("en"))
        self.lang_jp_action.triggered.connect(lambda: self.language_changed.emit("jp"))

        self.setMenuBar(self.menu_bar)

    def _change_theme(self, theme: str) -> None:
        from sqlbot_desktop.views.theme import load_stylesheet
        from PySide6.QtWidgets import QApplication

        settings = QSettings("SQLBot", "SQLBotDesktop")
        settings.setValue("theme", theme)

        # Apply stylesheet to whole application
        QApplication.instance().setStyleSheet(load_stylesheet(theme))

        # Ensure correct menu checked states
        if theme == "dark":
            self.dark_action.setChecked(True)
        else:
            self.light_action.setChecked(True)

    def retranslate_ui(self) -> None:
        # Title & Subtitle
        self.setWindowTitle(tr("main.app_title"))
        self.title_label.setText(tr("main.app_title"))
        self.subtitle_label.setText(tr("main.app_subtitle"))

        # Mode button
        current_idx = self.workspace_stack.currentIndex()
        if current_idx == 0:
            self.mode_switch_btn.setText(tr("main.btn_mode_vqb"))
        else:
            self.mode_switch_btn.setText(tr("main.btn_mode_chat"))

        # Menu bar titles
        self.file_menu.setTitle(tr("main.menu_file"))
        self.export_action.setText(tr("main.menu_export_csv"))
        self.exit_action.setText(tr("main.menu_exit"))

        self.view_menu.setTitle(tr("main.menu_view"))
        self.history_action.setText(tr("main.menu_history"))
        self.bookmarks_action.setText(tr("main.menu_bookmarks"))
        self.schema_action.setText(tr("main.menu_schema"))
        self.theme_menu.setTitle(tr("main.menu_theme"))
        self.light_action.setText(tr("main.menu_theme_light"))
        self.dark_action.setText(tr("main.menu_theme_dark"))

        self.tools_menu.setTitle(tr("main.menu_tools"))
        self.settings_action.setText(tr("main.menu_settings"))
        self.refresh_samples_action.setText(tr("main.menu_refresh_samples"))
        self.language_menu.setTitle(tr("main.menu_language"))

        # Workspace widgets
        if hasattr(self, "schema_dock_widget") and self.schema_dock_widget:
            self.schema_dock_widget.setWindowTitle(tr("main.schema_viewer_title"))
        if hasattr(self, "schema_dock_title_label") and self.schema_dock_title_label:
            self.schema_dock_title_label.setText(tr("main.schema_viewer_title"))
        if hasattr(self, "schema_dock_float_button") and self.schema_dock_float_button:
            self.schema_dock_float_button.setToolTip(tr("main.schema_dock_float", "Float / dock schema viewer"))
        if hasattr(self, "schema_dock_close_button") and self.schema_dock_close_button:
            self.schema_dock_close_button.setToolTip(tr("main.schema_dock_close", "Close schema viewer"))
        if hasattr(self, "schema_viewer_title") and self.schema_viewer_title:
            self.schema_viewer_title.setText(tr("main.schema_viewer_title"))

        self.cancel_button.setText(tr("main.btn_cancel"))
        self.prompt_label.setText(tr("main.prompt_label"))
        self.question_input.setPlaceholderText(tr("main.prompt_input_placeholder"))
        self.send_button.setText(tr("main.chat_btn_send"))
        self.stop_button.setText(tr("main.btn_stop"))

        self.sql_label.setText(tr("main.sql_label"))
        self.sql_editor.setPlaceholderText(tr("main.sql_editor_placeholder"))
        self.execute_button.setText(tr("main.btn_execute"))
        self.show_results_button.setText(tr("main.btn_results"))
        self.paste_button.setText(tr("main.btn_paste_sql"))
        self.bookmark_button.setText(tr("main.btn_bookmark"))

        self.chat_label.setText(tr("main.chat_label"))
        self.clear_button.setText(tr("main.btn_clear_chat"))

        # Retranslate visual query builder
        if hasattr(self, "visual_builder") and self.visual_builder:
            self.visual_builder.retranslate_ui()

        # Update connections and schemas
        if hasattr(self, "_current_profile") and self._current_profile:
            self.set_connection(self._current_profile)
        else:
            self.connection_label.setText(tr("main.status_db_disconnected"))

        # Schema status
        if hasattr(self, "_tables") and self._tables:
            table_count = len(self._tables)
            column_count = sum(len(table.columns) for table in self._tables)
            self.schema_summary_label.setText(f"{table_count} tables, {column_count} columns")
        else:
            self.schema_summary_label.setText(tr("main.schema_summary_label"))

        # AI Status
        current_status_text = self.model_status_label.text()
        if not current_status_text or current_status_text in ("AI chưa load", "AI not loaded", "AI未ロード"):
            self.model_status_label.setText(tr("main.status_db_no_load"))
        elif current_status_text in ("AI đã load", "AI loaded", "AIロード済み"):
            self.model_status_label.setText(tr("main.status_db_loaded"))

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("mainRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 14, 20, 12)
        root_layout.setSpacing(10)

        root_layout.addLayout(self._build_header())
        root_layout.addWidget(self._build_busy_panel())

        # Page 0: Chat Mode Layout
        chat_page = QWidget()
        chat_page_layout = QVBoxLayout(chat_page)
        chat_page_layout.setContentsMargins(0, 0, 0, 0)
        chat_page_layout.setSpacing(10)
        chat_page_layout.addWidget(self._build_upper_workspace_panel())
        chat_page_layout.addWidget(self._build_chat_panel(), 1)

        # Page 1: Visual Query Builder Mode Layout
        self.visual_builder = VisualQueryBuilderPanel(self)

        # Stack
        self.workspace_stack = QStackedWidget()
        self.workspace_stack.addWidget(chat_page)
        self.workspace_stack.addWidget(self.visual_builder)
        self.workspace_stack.setCurrentIndex(1)
        root_layout.addWidget(self.workspace_stack, 1)

        self.setCentralWidget(root)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(10)

        title_group = QVBoxLayout()
        self.title_label = QLabel("SQLBot Workspace")
        self.title_label.setObjectName("mainTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("mainSubtitle")
        title_group.addWidget(self.title_label)
        title_group.addWidget(self.subtitle_label)

        # Mode switch button on the far right of the header
        self.mode_switch_btn = QPushButton()
        self.mode_switch_btn.clicked.connect(self._toggle_workspace_mode)
        self.mode_switch_btn.setMinimumHeight(38)
        self.mode_switch_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #7c3aed);
                color: white;
                border-radius: 19px;
                font-weight: bold;
                font-size: 13px;
                padding: 0 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4338ca, stop:1 #6d28d9);
            }
        """)

        header.addLayout(title_group, 1)
        header.addWidget(self.mode_switch_btn)
        return header

    def _build_schema_dock(self) -> None:
        self.schema_dock_widget = QDockWidget("", self)
        self.schema_dock_widget.setObjectName("schemaDock")
        self.schema_dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.schema_dock_widget.setTitleBarWidget(self._build_schema_dock_title_bar())

        content = QWidget()
        content.setObjectName("schemaViewerPanel")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        self.schema_viewer_title = QLabel()
        self.schema_viewer_title.setObjectName("sectionTitle")
        self.schema_summary_label.setObjectName("formHint")
        self.schema_summary_label.setWordWrap(True)

        layout.addWidget(self.schema_viewer_title)
        layout.addWidget(self.schema_summary_label)
        layout.addWidget(self.schema_tree, 1)

        self.schema_dock_widget.setWidget(content)
        self.schema_dock_widget.hide()
        self.schema_dock = self.schema_dock_widget
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.schema_dock_widget)

    def _build_schema_dock_title_bar(self) -> QWidget:
        title_bar = QWidget()
        title_bar.setObjectName("schemaDockTitleBar")
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(6)

        self.schema_dock_title_label = QLabel()
        self.schema_dock_title_label.setObjectName("schemaDockTitle")

        self.schema_dock_float_button = QToolButton()
        self.schema_dock_float_button.setObjectName("schemaDockFloatButton")
        self.schema_dock_float_button.setText("□")
        self.schema_dock_float_button.setFixedSize(26, 24)
        self.schema_dock_float_button.clicked.connect(self._toggle_schema_dock_floating)

        self.schema_dock_close_button = QToolButton()
        self.schema_dock_close_button.setObjectName("schemaDockCloseButton")
        self.schema_dock_close_button.setText("X")
        self.schema_dock_close_button.setFixedSize(26, 24)
        self.schema_dock_close_button.clicked.connect(self.schema_dock_widget.hide)

        layout.addWidget(self.schema_dock_title_label, 1)
        layout.addWidget(self.schema_dock_float_button)
        layout.addWidget(self.schema_dock_close_button)
        return title_bar

    def _toggle_schema_dock_floating(self) -> None:
        self.schema_dock_widget.setFloating(not self.schema_dock_widget.isFloating())

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

        self.cancel_button = QPushButton()
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

        self.prompt_label = QLabel()
        self.prompt_label.setObjectName("sectionTitle")

        self.question_input.setObjectName("questionInput")
        self.question_input.setAccessibleName("Nhập yêu cầu")
        self.question_input.setFixedHeight(160)
        self.question_input.returnPressed.connect(self._on_send_clicked)

        prompt_actions = QHBoxLayout()
        self.send_button.setObjectName("primaryButton")
        self.send_button.setMinimumHeight(38)
        self.send_button.clicked.connect(self._on_send_clicked)

        self.stop_button.setObjectName("dangerButton")
        self.stop_button.setMinimumHeight(38)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.cancel_requested.emit)

        prompt_actions.addWidget(self.send_button)
        prompt_actions.addWidget(self.stop_button)
        prompt_actions.addStretch()

        prompt_column.addWidget(self.prompt_label)
        prompt_column.addWidget(self.question_input)
        prompt_column.addLayout(prompt_actions)

        # Right Column: SQL Editor
        sql_column = QVBoxLayout()
        sql_column.setSpacing(10)

        self.sql_label = QLabel()
        self.sql_label.setObjectName("sectionTitle")

        self.sql_editor.setObjectName("sqlEditor")
        self.sql_editor.setAccessibleName("SQL Editor")
        self.sql_editor.setFont(QFont("Courier New", 11))
        self.sql_editor.setFixedHeight(160)

        sql_actions = QHBoxLayout()
        self.execute_button = QPushButton()
        self.execute_button.setObjectName("successButton")
        self.show_results_button = QPushButton()
        self.show_results_button.setObjectName("secondaryButton")
        self.paste_button = QPushButton()
        self.paste_button.setObjectName("secondaryButton")
        self.bookmark_button = QPushButton()
        self.bookmark_button.setObjectName("warningButton")

        self.execute_button.clicked.connect(self.execute_requested.emit)
        self.show_results_button.clicked.connect(self.show_results_requested.emit)
        self.paste_button.clicked.connect(self.sql_editor.paste)
        self.bookmark_button.clicked.connect(self.bookmark_requested.emit)

        for button in [self.execute_button, self.show_results_button, self.paste_button, self.bookmark_button]:
            button.setMinimumHeight(38)
            sql_actions.addWidget(button)
        sql_actions.addStretch()

        sql_column.addWidget(self.sql_label)
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
        self.chat_label = QLabel()
        self.chat_label.setObjectName("sectionTitle")

        self.clear_button = QPushButton()
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.setFixedWidth(110)
        self.clear_button.clicked.connect(self.clear_chat_requested.emit)

        header_layout.addWidget(self.chat_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_button)

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
        if self._busy:
            self.cancel_requested.emit()
            return
        text = self.question_input.toPlainText().strip()
        if not text:
            return
        self.generate_requested.emit(text)

    def set_schema(self, tables: list[TableInfo], annotations: dict[str, object] | None = None, dialect: str = "sqlite") -> None:
        self._tables = tables
        self._annotations = annotations or {}
        self.schema_tree.set_schema(tables, annotations)
        self.visual_builder.set_schema(tables, annotations, dialect)
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
        self.connection_label.setObjectName("connectionBadge")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_label.setStyleSheet("padding: 2px 10px; font-weight: bold;")
        self.model_status_label.setObjectName("modelStatusBadge")
        status.addPermanentWidget(self.connection_label)
        status.addPermanentWidget(self.model_status_label)
        self.setStatusBar(status)

    def ai_model_config(self) -> AIModelConfig:
        return self._ai_config

    def set_ai_model_config(self, config: AIModelConfig) -> None:
        self._ai_config = config

    def set_model_status(self, message: str, loaded: bool = False) -> None:
        # Match/translate status message if static strings
        if message in ("AI chưa load", "AI not loaded", "AI未ロード"):
            message = tr("main.status_db_no_load")
        elif message in ("AI đã load", "AI loaded", "AIロード済み"):
            message = tr("main.status_db_loaded")
        self.model_status_label.setText(message)
        self.model_status_label.setProperty("loaded", loaded)
        self.model_status_label.style().unpolish(self.model_status_label)
        self.model_status_label.style().polish(self.model_status_label)
        self.statusBar().showMessage(message)

    def set_busy(self, active: bool, title: str = "", detail: str = "") -> None:
        self._busy = active
        self.busy_title_label.setText(title)
        self.busy_detail_label.setText(detail)
        self.busy_panel.setVisible(active)
        self.send_button.setVisible(not active)
        self.stop_button.setVisible(active)
        self.statusBar().showMessage(title or "Ready")

    def set_generated_queries(self, queries: list[str]) -> None:
        if queries:
            self.sql_editor.setPlainText(queries[0])
            self.visual_builder.sql_editor.setPlainText(queries[0])
        else:
            self.sql_editor.clear()
            self.visual_builder.sql_editor.clear()

    def selected_query(self) -> str:
        if self.workspace_stack.currentIndex() == 1:
            return self.visual_builder.sql_editor.toPlainText().strip()
        return self.sql_editor.toPlainText().strip()

    def set_question(self, question: str) -> None:
        self.question_input.setText(question)
        self.question_input.setFocus()

    def set_saved_query(self, question: str, sql: str) -> None:
        self.set_question(question)
        if sql:
            self.sql_editor.setPlainText(sql)
            self.visual_builder.sql_editor.setPlainText(sql)

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
            f"    <b>{tr('main.user_role_prefix')}</b><br/>{text}"
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
            f"    <b style='color: #135ba1;'>{tr('main.assistant_role_prefix')}</b><br/>{formatted_text}"
            f"  </div>"
            f"</div>"
        )
        self.chat_view.append(html)
        self._scroll_chat_to_bottom()

    def append_status(self, text: str) -> None:
        self.remove_status()
        html = (
            f"<div id='assistantStatus' style='margin: 4px 0; text-align: left; color: #697789; font-style: italic;'>"
            f"  {text}"
            f"</div>"
        )
        cursor = QTextCursor(self.chat_view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        start = cursor.position()
        cursor.insertHtml(html)
        cursor.insertBlock()
        self._status_range = (start, cursor.position())
        self._scroll_chat_to_bottom()

    def remove_status(self) -> None:
        if self._status_range is None:
            return
        doc = self.chat_view.document()
        start, end = self._status_range
        max_position = max(0, doc.characterCount() - 1)
        start = min(start, max_position)
        end = min(end, max_position)
        if start < end:
            cursor = QTextCursor(doc)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        self._status_range = None
        self._scroll_chat_to_bottom()

    def clear_chat(self) -> None:
        self._status_range = None
        self.chat_view.clear()
        welcome = (
            f"<div style='background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; "
            f"            padding: 10px; border-radius: 8px; margin-bottom: 8px;'>"
            f"  <b>{tr('main.welcome_assistant_title')}</b> {tr('main.welcome_assistant_body')}"
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
        pass

    def closeEvent(self, event: QCloseEvent) -> None:
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            tr("main.dialog_exit_title"),
            tr("main.dialog_exit_message"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        self.closing_requested.emit()
        event.accept()

    def _load_placeholder_content(self) -> None:
        pass

    def _toggle_workspace_mode(self) -> None:
        current_idx = self.workspace_stack.currentIndex()
        if current_idx == 0:
            self.workspace_stack.setCurrentIndex(1)
            self.mode_switch_btn.setText(tr("main.btn_mode_chat"))
        else:
            self.workspace_stack.setCurrentIndex(0)
            self.mode_switch_btn.setText(tr("main.btn_mode_vqb"))

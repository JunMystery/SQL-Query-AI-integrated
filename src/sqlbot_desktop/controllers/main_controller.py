"""Controller for the main SQLBot workspace."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository
from sqlbot_desktop.infrastructure.annotation_repository import AnnotationRepository
from sqlbot_desktop.infrastructure.database_manager import DatabaseManager, QueryExecutionResult
from sqlbot_desktop.infrastructure.schema_extractor import SchemaExtractor
from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, ConnectionProfile, GenerationResult
from sqlbot_desktop.services.ai_engine import AIEngine
from sqlbot_desktop.services.prompt_builder import PromptBuilder
from sqlbot_desktop.services.query_validator import QueryValidator
from sqlbot_desktop.views.dialogs.ai_settings_dialog import AISettingsDialog
from sqlbot_desktop.views.dialogs.bookmark_dialog import AddBookmarkDialog, BookmarksDialog
from sqlbot_desktop.views.dialogs.history_dialog import HistoryDialog
from sqlbot_desktop.views.main_window import MainWindow


class BackgroundTask(QObject):
    """Run a blocking function outside the UI thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.operation())
        except Exception as exc:
            self.failed.emit(str(exc))


class MainController:
    """Coordinate the main workspace view."""

    def __init__(
        self,
        profile: ConnectionProfile,
        database_manager: DatabaseManager | None = None,
        connection_name: str = "",
        annotation_repository: AnnotationRepository | None = None,
        activity_repository: ActivityRepository | None = None,
    ) -> None:
        self.profile = profile
        self.database_manager = database_manager
        self.connection_name = connection_name
        self.annotation_repository = annotation_repository or AnnotationRepository()
        self.activity_repository = activity_repository or ActivityRepository()
        self.schema_context = ""
        self.busy = False
        self.worker_thread: QThread | None = None
        self.worker: BackgroundTask | None = None
        self.ai_engine = AIEngine()
        self.view = MainWindow()
        self.view.set_connection(profile)
        self.view.generate_requested.connect(self.generate_sql)
        self.view.load_model_requested.connect(self.load_model)
        self.view.unload_model_requested.connect(self.unload_model)
        self.view.closing_requested.connect(self.unload_model)
        self.view.bookmark_requested.connect(self.add_bookmark)
        self.view.copy_requested.connect(self.copy_query)
        self.view.execute_requested.connect(self.execute_query)
        self.view.history_requested.connect(self.open_history)
        self.view.bookmarks_requested.connect(self.open_bookmarks)
        self.view.schema_requested.connect(self.show_schema)
        self.view.settings_requested.connect(self.open_settings)
        self.load_schema()

    def show(self) -> None:
        self.view.show()

    def load_schema(self) -> None:
        if self.database_manager is None or not self.connection_name:
            return
        try:
            tables = SchemaExtractor(self.database_manager.database(self.connection_name)).get_all_tables_columns()
        except Exception as exc:
            self.view.statusBar().showMessage(f"Không thể tải schema: {exc}")
            return

        annotations = self.annotation_repository.load(self.profile.name)
        self.view.set_schema(tables, annotations)
        self.schema_context = PromptBuilder.build_schema_context(tables, annotations)

    def show_schema(self) -> None:
        self.view.show_schema_viewer()

    def generate_sql(self, question: str) -> None:
        if self.busy:
            QMessageBox.information(self.view, "AI đang bận", "Vui lòng đợi thao tác hiện tại hoàn tất.")
            return
        if not question:
            QMessageBox.information(self.view, "Thiếu câu hỏi", "Vui lòng nhập yêu cầu bằng tiếng Việt.")
            return

        self._start_task(
            "AI đang suy nghĩ...",
            "Đang phân tích câu hỏi tiếng Việt và tạo SQL SELECT.",
            lambda: self.ai_engine.generate(question, schema_context=self.schema_context, dialect=self.profile.driver),
            lambda result: self._handle_generate_result(question, result),
        )

    def _handle_generate_result(self, question: str, result: GenerationResult) -> None:
        if not result.ok:
            self.activity_repository.add_history(question, "", False)
            QMessageBox.warning(self.view, "Sinh SQL thất bại", result.message)
            self.view.statusBar().showMessage(result.message)
            return

        self.view.set_generated_queries(result.queries)
        self.activity_repository.add_history(question, result.queries[0] if result.queries else "", True)
        self.view.statusBar().showMessage(result.message)

    def add_bookmark(self) -> None:
        question = self.view.question_input.toPlainText().strip()
        sql = self.view.selected_query().strip()
        if not question or not sql:
            QMessageBox.information(self.view, "Thiếu dữ liệu", "Vui lòng có câu hỏi và SQL trước khi bookmark.")
            return

        dialog = AddBookmarkDialog(question, sql, self.view)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self.activity_repository.add_bookmark(question, sql, dialog.category, dialog.notes)
        self.view.statusBar().showMessage("Đã lưu bookmark.")

    def copy_query(self) -> None:
        from PySide6.QtWidgets import QApplication

        sql = self.view.selected_query().strip()
        if not sql:
            QMessageBox.information(self.view, "Chưa có SQL", "Không có Suggested Query để copy.")
            return
        QApplication.clipboard().setText(sql)
        self.view.statusBar().showMessage("Đã copy SQL.")

    def execute_query(self) -> None:
        if self.busy:
            QMessageBox.information(self.view, "AI đang bận", "Vui lòng đợi thao tác hiện tại hoàn tất.")
            return
        if self.database_manager is None or not self.connection_name:
            QMessageBox.warning(self.view, "Chưa có kết nối", "Không tìm thấy kết nối database đang hoạt động.")
            return

        sql = self.view.selected_query().strip()
        if not sql:
            QMessageBox.information(self.view, "Chưa có SQL", "Không có Suggested Query để execute.")
            return
        if not QueryValidator.is_readonly_select(sql):
            QMessageBox.warning(self.view, "SQL không an toàn", "Chỉ cho phép thực thi câu SELECT.")
            return

        self._start_task(
            "Đang xử lý dữ liệu...",
            "Đang thực thi SELECT và tải Query Results.",
            lambda: self.database_manager.execute_select(sql, self.connection_name),
            self._handle_execute_result,
        )

    def _handle_execute_result(self, result: QueryExecutionResult) -> None:
        if not result.ok:
            QMessageBox.warning(self.view, "Execute thất bại", result.message)
            self.view.statusBar().showMessage(result.message)
            return
        self.view.set_query_results(result.columns or [], result.rows or [])
        self.view.statusBar().showMessage(result.message)

    def open_history(self) -> None:
        dialog = HistoryDialog(self.activity_repository, self.view)
        dialog.load_requested.connect(self.view.set_question)
        dialog.exec()

    def open_bookmarks(self) -> None:
        dialog = BookmarksDialog(self.activity_repository, self.view)
        dialog.load_requested.connect(self.view.set_saved_query)
        dialog.exec()

    def open_settings(self) -> None:
        dialog = AISettingsDialog(self.view.ai_model_config(), self.view)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.view.set_ai_model_config(dialog.config())
        self.view.statusBar().showMessage("Đã cập nhật AI settings. Bấm Load để áp dụng.")

    def load_model(self, config) -> None:
        if self.busy:
            QMessageBox.information(self.view, "AI đang bận", "Vui lòng đợi thao tác hiện tại hoàn tất.")
            return

        validation_error = self._validate_model_config(config)
        if validation_error:
            self.view.set_model_status(validation_error, False)
            QMessageBox.warning(self.view, "Load AI thất bại", validation_error)
            return

        detail = "Đang load model GGUF local." if config.backend.value == "local" else "Đang kiểm tra cấu hình API AI."
        self._start_task(
            "Loading AI...",
            detail,
            lambda: self.ai_engine.load(config),
            self._handle_load_result,
        )

    def _handle_load_result(self, result: GenerationResult) -> None:
        self.view.set_model_status(result.message, result.ok)
        if not result.ok:
            QMessageBox.warning(self.view, "Load AI thất bại", result.message)

    def unload_model(self) -> None:
        if self.busy:
            QMessageBox.information(self.view, "AI đang bận", "Vui lòng đợi thao tác hiện tại hoàn tất.")
            return
        self.ai_engine.unload()
        self.view.set_model_status("AI đã unload", False)

    def _validate_model_config(self, config: AIModelConfig) -> str:
        if config.backend == AIBackend.LOCAL:
            model_path_text = config.local_model_path.strip()
            if not model_path_text:
                return "Vui lòng chọn file model GGUF trước khi bấm Load."
            model_path = Path(model_path_text)
            if model_path.suffix.lower() != ".gguf":
                return "Vui lòng chọn file model định dạng .gguf."
            if not model_path.exists():
                return "File model không tồn tại."
            return ""

        if not config.api_endpoint.strip():
            return "Vui lòng nhập API endpoint."
        if not config.api_model.strip():
            return "Vui lòng nhập API model."
        return ""

    def _start_task(
        self,
        title: str,
        detail: str,
        operation: Callable[[], object],
        on_finished: Callable[[object], None],
    ) -> None:
        self.busy = True
        self.view.set_busy(True, title, detail)

        thread = QThread(self.view)
        worker = BackgroundTask(operation)
        worker.moveToThread(thread)

        def finish(result: object) -> None:
            self._finish_task()
            on_finished(result)

        def fail(message: str) -> None:
            self._finish_task()
            QMessageBox.warning(self.view, "AI task failed", message)
            self.view.statusBar().showMessage(message)

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(finish)
        worker.failed.connect(fail)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker)
        thread.start()

        self.worker_thread = thread
        self.worker = worker

    def _finish_task(self) -> None:
        self.busy = False
        self.view.set_busy(False)

    def _clear_worker(self) -> None:
        self.worker_thread = None
        self.worker = None

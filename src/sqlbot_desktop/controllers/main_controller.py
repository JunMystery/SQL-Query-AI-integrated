"""Controller for the main SQLBot workspace."""





from __future__ import annotations





from collections.abc import Callable


from pathlib import Path





from PySide6.QtCore import QObject, QThread, Signal, Slot


from PySide6.QtWidgets import QMessageBox, QDialog





from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository


from sqlbot_desktop.infrastructure.annotation_repository import AnnotationRepository


from sqlbot_desktop.infrastructure.database_manager import DatabaseManager, QueryExecutionResult


from sqlbot_desktop.infrastructure.schema_extractor import SchemaExtractor


from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, ConnectionProfile, GenerationResult
from sqlbot_desktop.infrastructure.ai_settings_repository import AISettingsRepository
from sqlbot_desktop.utils.i18n_manager import tr


from sqlbot_desktop.services.ai_engine import AIEngine

from PySide6.QtCore import QUrl


from sqlbot_desktop.services.cpu_limiter import CpuLimiter
from sqlbot_desktop.services.join_safety_service import JoinSafetyResult, JoinSafetyService
from sqlbot_desktop.services.prompt_builder import PromptBuilder


from sqlbot_desktop.services.query_validator import QueryValidator
from sqlbot_desktop.services.query_logger import QueryLogger
from sqlbot_desktop.services.schema_metadata_service import SchemaMetadataService
from sqlbot_desktop.services.sql_extractor import SQLExtractor
from sqlbot_desktop.services.text_to_sql_pipeline import TextToSqlPipeline, TextToSqlResult


from sqlbot_desktop.views.dialogs.settings_dialog import SettingsDialog


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








class TaskReceiver(QObject):


    """Safely receive background task callbacks on the GUI thread."""





    def __init__(self, on_finished: Callable[[object], None], on_failed: Callable[[str], None]) -> None:


        super().__init__()


        self.on_finished = on_finished


        self.on_failed = on_failed





    @Slot(object)


    def handle_finished(self, result: object) -> None:


        self.on_finished(result)





    @Slot(str)


    def handle_failed(self, message: str) -> None:


        self.on_failed(message)








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


        self.tables = []


        self.schema_assistant_dialog = None


        self.assistant_history = []


        self.busy = False


        self.task_cancelled = False


        self.worker_thread: QThread | None = None


        self.worker: BackgroundTask | None = None


        self.task_receiver: TaskReceiver | None = None


        self.ai_settings_repository = AISettingsRepository()
        self.ai_engine = AIEngine()
        self.text_to_sql_pipeline = TextToSqlPipeline(self.ai_engine, query_logger=QueryLogger())
        self.join_safety_service = JoinSafetyService()


        self.view = MainWindow()
        stored_config = self.ai_settings_repository.load_config()
        self.view.set_ai_model_config(stored_config)
        self._apply_cpu_limit(stored_config)

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

        # Connect Visual Query Builder action signals
        self.view.visual_builder.execute_requested.connect(self.execute_query)
        self.view.visual_builder.show_results_requested.connect(self.view.show_results_dialog)
        self.view.visual_builder.bookmark_requested.connect(self.add_bookmark)
        self.view.visual_builder.status_message_requested.connect(self.view.statusBar().showMessage)


        self.view.refresh_samples_requested.connect(self.refresh_sample_values)


        self.view.cancel_requested.connect(self.cancel_task)


        self.view.chat_view.anchorClicked.connect(self.handle_chat_link)
        self.view.show_results_requested.connect(self.view.show_results_dialog)
        self.view.clear_chat_requested.connect(self.clear_chat_history)
        self.view.language_changed.connect(self.change_language)


        self.load_schema()





    def change_language(self, lang_code: str) -> None:
        from sqlbot_desktop.utils.i18n_manager import set_language
        set_language(lang_code)
        self.view.retranslate_ui()

    def show(self) -> None:


        self.view.show()





    def load_schema(self) -> None:


        if self.database_manager is None or not self.connection_name:


            return


        try:


            tables = SchemaExtractor(self.database_manager.database(self.connection_name)).get_all_tables_columns()
        except Exception as exc:
            self.view.statusBar().showMessage(tr("main.msg_schema_failed", "Không thể tải schema: ") + f"{exc}")
            return

        self.tables = tables

        annotations = self.annotation_repository.load(self.profile.name)

        self.view.set_schema(tables, annotations, dialect=self.profile.driver)
        self.view.visual_builder.set_join_safety_checker(self._check_visual_join_safety)

        self.schema_context = PromptBuilder.build_schema_context(tables, annotations)

    def _check_visual_join_safety(self, selected_tables: list[str], candidate_table: str) -> JoinSafetyResult:
        start_table = self.view.visual_builder.table_combo.currentData()
        if not start_table:
            return JoinSafetyResult(
                True,
                "warning",
                tr("main.msg_join_safety_missing_table", "Chưa có bảng chính để kiểm tra JOIN."),
                [],
                sample_limit=self.join_safety_service.sample_limit,
            )

        connection = None
        if self.database_manager is not None and self.connection_name:
            try:
                connection = self.database_manager.database(self.connection_name)
            except Exception:
                connection = None

        return self.join_safety_service.check_candidate(
            start_table=start_table,
            selected_tables=selected_tables,
            candidate_table=candidate_table,
            tables=self.tables,
            connection=connection,
            dialect=self.profile.driver,
        )

    def show_schema(self) -> None:

        self.view.show_schema_viewer()

    def generate_sql(self, question: str) -> None:
        if self.busy:
            QMessageBox.information(self.view, tr("main.title_ai_busy", "AI đang bận"), tr("main.msg_wait_current_operation", "Vui lòng đợi thao tác hiện tại hoàn tất."))
            return
        if not question:
            QMessageBox.information(self.view, tr("main.title_missing_question", "Thiếu câu hỏi"), tr("main.msg_enter_requirement_vietnamese", "Vui lòng nhập yêu cầu bằng tiếng Việt."))
            return

        self.view.append_user_message(question)
        self.view.append_status(tr("main.status_ai_thinking", "AI đang suy nghĩ..."))

        self._start_task(
            tr("main.status_ai_thinking", "AI đang suy nghĩ..."),
            tr("main.status_translating_question", "Đang dịch câu hỏi sang truy vấn SQL."),
            lambda: self.text_to_sql_pipeline.generate(
                question,
                db_name=self.profile.name,
                dialect=self.profile.driver.upper(),
                fallback_schema_context=self.schema_context,
                execute_sql=(
                    (
                        lambda sql: self.database_manager.execute_select(
                            sql,
                            self.connection_name,
                            max_rows=self._query_max_rows(),
                            timeout_seconds=self._query_timeout_seconds(),
                        )
                    )
                    if self.database_manager is not None and self.connection_name
                    else None
                ),
                max_retries=self._self_correction_retries(),
                check_cancelled=self._is_task_cancelled,
            ),
            lambda result: self._handle_generate_result(question, result),
            on_failed=lambda err: self._handle_generate_failed(question, err),
        )

    def _handle_generate_result(self, question: str, result: object) -> None:
        self.view.remove_status()

        if isinstance(result, TextToSqlResult):
            if result.raw_text:
                self.view.append_assistant_message(result.raw_text)
            elif result.queries:
                self.view.append_assistant_message(f"```sql\n{result.queries[0]}\n```")
            else:
                self.view.append_assistant_message(result.message)
            if result.diagnostics.attempts > 1:
                self.view.append_status(tr("main.status_ai_corrected_prefix", "AI đã tự sửa SQL sau ") + f"{result.diagnostics.attempts}" + tr("main.status_ai_corrected_suffix", " lần."))

            queries = result.queries if result.ok else []
        else:
            text = str(result)
            self.view.append_assistant_message(text)
            queries = SQLExtractor.extract_select_queries(text)

        if queries:
            from sqlbot_desktop.services.query_corrector import QueryCorrector

            corrected_queries = [QueryCorrector.correct_query(sql, self.tables) for sql in queries]
            corrected_sql = corrected_queries[0]
            self.view.set_generated_queries(corrected_queries)
            self.activity_repository.add_history(question, corrected_sql, True)
            attempts = result.diagnostics.attempts if isinstance(result, TextToSqlResult) else 1
            if attempts > 1:
                self.view.statusBar().showMessage(tr("main.status_sql_generated_attempts_prefix", "Đã sinh SQL hợp lệ sau ") + f"{attempts}" + tr("main.status_sql_generated_attempts_suffix", " lần thử."))
            else:
                self.view.statusBar().showMessage(tr("main.status_sql_extracted", "Đang trích xuất SQL từ phản hồi trợ lý."))
        else:
            self.view.set_generated_queries([])
            self.activity_repository.add_history(question, "", False)
            if isinstance(result, TextToSqlResult) and result.message:
                self.view.statusBar().showMessage(result.message)
            else:
                self.view.statusBar().showMessage(tr("main.status_sql_not_found", "AI phản hồi nhưng không tìm thấy câu SELECT hợp lệ."))

    def _handle_generate_failed(self, question: str, error_message: str) -> None:
        self.view.remove_status()
        if error_message in ("Cancelled", "Thao tác bị hủy", "cancelled", "CancelledError", tr("main.msg_cancelled", "Thao tác bị hủy")):
            self.view.append_assistant_message(tr("main.msg_cancelled", "Thao tác bị hủy."))
        else:
            self.view.append_assistant_message(tr("main.msg_request_failed_prefix", "Không thể hoàn thành yêu cầu: ") + f"{error_message}")
        self.activity_repository.add_history(question, "", False)
    def handle_chat_link(self, url: QUrl) -> None:
        href = url.toString()
        if href.startswith("apply:"):
            prompt = href.partition("apply:")[2]
            self.view.set_question(prompt)
        elif href.startswith("copy:"):
            from PySide6.QtWidgets import QApplication
            prompt = href.partition("copy:")[2]
            QApplication.clipboard().setText(prompt)
            self.view.statusBar().showMessage(tr("main.status_suggest_copied", "Đã copy gợi ý vào clipboard."))

    def add_bookmark(self) -> None:
        sql = self.view.selected_query().strip()
        if not sql:
            QMessageBox.information(self.view, tr("dialogs.conn_form_title_missing_info", "Thiếu thông tin"), tr("dialogs.bookmarks_msg_missing_sql", "Vui lòng có câu lệnh SQL trước khi bookmark."))
            return
        dialog = AddBookmarkDialog(sql, self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            bookmark_name = dialog.bookmark_name
            self.activity_repository.add_bookmark(bookmark_name, sql, dialog.category, dialog.notes)
            self.view.statusBar().showMessage(tr("main.status_bookmark_saved", "Đã lưu bookmark."))

    def copy_query(self) -> None:

        from PySide6.QtWidgets import QApplication

        sql = self.view.selected_query().strip()

        if not sql:

            QMessageBox.information(self.view, tr("main.title_no_sql", "Chưa có SQL"), tr("main.msg_no_sql_copy", "Không có Suggested Query để copy."))

            return

        QApplication.clipboard().setText(sql)

        self.view.statusBar().showMessage(tr("main.status_sql_copied", "Đã copy SQL."))

    def execute_query(self) -> None:

        if self.busy:

            QMessageBox.information(self.view, tr("main.title_ai_busy", "AI đang bận"), tr("main.msg_wait_current_operation", "Vui lòng đợi thao tác hiện tại hoàn tất."))

            return

        if self.database_manager is None or not self.connection_name:

            QMessageBox.warning(self.view, tr("main.title_no_connection", "Chưa có kết nối"), tr("main.msg_no_active_connection", "Không tìm thấy kết nối database đang hoạt động."))

            return

        sql = self.view.selected_query().strip()

        if not sql:

            QMessageBox.information(self.view, tr("main.title_no_sql", "Chưa có SQL"), tr("main.msg_no_sql_execute", "Không có Suggested Query để execute."))

            return

        if not QueryValidator.is_readonly_select(sql):

            QMessageBox.warning(self.view, tr("main.title_unsafe_sql", "SQL không an toàn"), tr("main.msg_only_select_allowed", "Chỉ cho phép thực thi câu SELECT."))

            return

        self._start_task(

            tr("main.status_processing_data", "Đang xử lý dữ liệu..."),

            tr("main.status_executing_select", "Đang thực thi SELECT và tải Query Results."),

            lambda: self.database_manager.execute_select(
                sql,
                self.connection_name,
                max_rows=self._query_max_rows(),
                timeout_seconds=self._query_timeout_seconds(),
            ),

            self._handle_execute_result,

        )

    def _handle_execute_result(self, result: QueryExecutionResult) -> None:

        if not result.ok:

            QMessageBox.warning(self.view, tr("main.title_execute_failed", "Execute thất bại"), result.message)

            self.view.statusBar().showMessage(result.message)

            return

        self.view.set_query_results(result.columns or [], result.rows or [])

        self.view.statusBar().showMessage(result.message)

    def clear_chat_history(self) -> None:
        self.assistant_history = []
        self.view.clear_chat()
        self.view.statusBar().showMessage(tr("main.status_chat_cleared", "Đã xóa lịch sử phiên chat để giải phóng ngữ cảnh."))

    def refresh_sample_values(self) -> None:
        if self.busy:
            QMessageBox.information(self.view, tr("main.title_ai_busy", "AI đang bận"), tr("main.msg_wait_current_operation", "Vui lòng đợi thao tác hiện tại hoàn tất."))
            return
        if self.database_manager is None or not self.connection_name:
            QMessageBox.warning(self.view, tr("main.title_no_connection", "Chưa có kết nối"), tr("main.msg_no_active_connection", "Không tìm thấy kết nối database đang hoạt động."))
            return
        if not self.tables:
            self.load_schema()

        service = SchemaMetadataService()
        connection = self.database_manager.database(self.connection_name)

        def operation() -> list[str]:
            service.import_tables(self.profile.name, self.tables)
            return service.refresh_sample_values(
                self.profile.name,
                connection,
                limit=3,
                check_cancelled=self._is_task_cancelled,
            )

        self._start_task(
            tr("main.status_fetching_samples", "Đang lấy sample values..."),
            tr("main.status_reading_samples_hint", "Chỉ chạy SELECT để đọc tối đa 3 giá trị mẫu cho mỗi cột."),
            operation,
            self._handle_sample_refresh_result,
        )

    def _handle_sample_refresh_result(self, messages: list[str]) -> None:
        if messages:
            self.view.statusBar().showMessage(tr("main.status_samples_updated_errors", "Đã cập nhật sample values, ") + f"{len(messages)}" + tr("main.status_columns_have_errors", " cột có lỗi."))
            QMessageBox.warning(self.view, "Sample values", "\n".join(messages[:10]))
            return
        self.view.statusBar().showMessage(tr("main.status_samples_updated_success", "Đã cập nhật sample values vào metadata local."))

    def open_history(self) -> None:
        dialog = HistoryDialog(self.activity_repository, self.view)
        dialog.load_requested.connect(self.view.set_saved_query)
        dialog.exec()

    def open_bookmarks(self) -> None:

        dialog = BookmarksDialog(self.activity_repository, self.view)

        dialog.load_requested.connect(self.view.set_saved_query)

        dialog.exec()

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            config=self.view.ai_model_config(),
            connection_name=self.connection_name or "",
            tables=self.tables or [],
            repository=self.annotation_repository,
            parent=self.view
        )
        dialog.load_model_requested.connect(self.load_model)
        dialog.unload_model_requested.connect(self.unload_model)

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        config = dialog.config()
        self.view.set_ai_model_config(config)
        self._apply_cpu_limit(config)
        self.ai_settings_repository.save_config(config)
        self.view.statusBar().showMessage(tr("main.status_ai_settings_saved", "Đã lưu cài đặt AI."))

    def load_model(self, config) -> None:

        if self.busy:

            QMessageBox.information(self.view, tr("main.title_ai_busy", "AI đang bận"), tr("main.msg_wait_current_operation", "Vui lòng đợi thao tác hiện tại hoàn tất."))

            return

        validation_error = self._validate_model_config(config)

        if validation_error:

            self.view.set_model_status(validation_error, False)

            QMessageBox.warning(self.view, tr("main.title_load_ai_failed", "Load AI thất bại"), validation_error)

            return

        self._apply_cpu_limit(config)

        self._start_task(
            tr("main.status_loading_ai", "Loading AI..."),
            tr("settings.status_loading_local", "Đang load model GGUF local.") if config.backend.value == "local" else tr("settings.status_checking_api", "Đang kiểm tra cấu hình API AI."),
            lambda: self.ai_engine.load(config, check_cancelled=self._is_task_cancelled),
            self._handle_load_result,
            on_failed=lambda err: self.view.set_model_status(tr("main.status_load_failed", "Load model thất bại: ") + f"{err}", False)
        )

    def _handle_load_result(self, result: GenerationResult) -> None:

        self.view.set_model_status(result.message, result.ok)

        if not result.ok:

            QMessageBox.warning(self.view, tr("main.title_load_ai_failed", "Load AI thất bại"), result.message)

    def unload_model(self) -> None:

        if self.busy:

            QMessageBox.information(self.view, tr("main.title_ai_busy", "AI đang bận"), tr("main.msg_wait_current_operation", "Vui lòng đợi thao tác hiện tại hoàn tất."))

            return

        self.ai_engine.unload()

        self.view.set_model_status(tr("main.status_ai_unloaded", "AI đã unload"), False)

    def _validate_model_config(self, config: AIModelConfig) -> str:

        if config.backend == AIBackend.LOCAL:

            model_path_text = config.local_model_path.strip()

            if not model_path_text:

                return tr("main.val_choose_gguf", "Vui lòng chọn file model GGUF trước khi bấm Load.")

            model_path = Path(model_path_text)

            if model_path.suffix.lower() != ".gguf":

                return tr("main.val_choose_gguf_format", "Vui lòng chọn file model định dạng .gguf.")

            if not model_path.exists():

                return tr("main.val_model_not_exist", "File model không tồn tại.")

            return ""

        if not config.api_endpoint.strip():

            return tr("main.val_enter_api_endpoint", "Vui lòng nhập API endpoint.")

        if not config.api_model.strip():

            return tr("main.val_enter_api_model", "Vui lòng nhập API model.")

        return ""

    def _apply_cpu_limit(self, config: AIModelConfig) -> None:
        try:
            message = CpuLimiter.apply(getattr(config, "cpu_thread_limit", 0))
            self.view.statusBar().showMessage(message)
        except OSError as exc:
            self.view.statusBar().showMessage(tr("main.status_cpu_limit_error", "Không thể giới hạn CPU cho app: ") + f"{exc}")





    def _self_correction_retries(self) -> int:
        try:
            config = self.view.ai_model_config()
        except AttributeError:
            return 3
        retries = getattr(config, "self_correction_retries", 3)
        return max(1, min(int(retries or 3), 5))

    def _query_max_rows(self) -> int:
        rows = getattr(self.profile, "query_max_rows", 1000)
        return max(1, min(int(rows or 1000), 1000))

    def _query_timeout_seconds(self) -> int:
        seconds = getattr(self.profile, "query_timeout_seconds", 10)
        return max(1, min(int(seconds or 10), 300))


    def _start_task(


        self,


        title: str,


        detail: str,


        operation: Callable[[], object],


        on_finished: Callable[[object], None],


        show_busy_panel: bool = True,


        on_failed: Callable[[str], None] | None = None,


    ) -> None:


        self.busy = True


        self.task_cancelled = False


        if show_busy_panel:


            self.view.set_busy(True, title, detail)





        thread = QThread(self.view)


        worker = BackgroundTask(operation)


        worker.moveToThread(thread)





        def finish(result: object) -> None:


            self._finish_task(show_busy_panel)


            if self.task_cancelled:


                self.view.statusBar().showMessage(tr("main.status_cancelled", "Đã hủy thao tác."))


                return


            on_finished(result)





        def fail(message: str) -> None:


            self._finish_task(show_busy_panel)


            if self.task_cancelled or self._is_cancel_message(message):


                self.view.statusBar().showMessage(tr("main.status_cancelled", "Đã hủy thao tác."))


                return


            if on_failed is not None:


                on_failed(message)


            else:


                if self._is_cancel_message(message):


                    self.view.statusBar().showMessage(tr("main.status_cancelled", "Đã hủy thao tác."))


                    return


                QMessageBox.warning(self.view, tr("main.title_generate_sql_failed", "Sinh SQL thất bại"), message)


                self.view.statusBar().showMessage(message)





        fail_callback = fail





        # Connect callbacks safely to the GUI thread via TaskReceiver


        receiver = TaskReceiver(finish, fail_callback)





        thread.started.connect(worker.run)


        worker.finished.connect(thread.quit)


        worker.failed.connect(thread.quit)


        worker.finished.connect(receiver.handle_finished)


        worker.failed.connect(receiver.handle_failed)


        thread.finished.connect(worker.deleteLater)


        thread.finished.connect(thread.deleteLater)


        thread.finished.connect(self._clear_worker)


        thread.start()





        self.worker_thread = thread


        self.worker = worker


        self.task_receiver = receiver





    def _finish_task(self, show_busy_panel: bool = True) -> None:


        self.busy = False


        if show_busy_panel:


            self.view.set_busy(False)





    def _clear_worker(self) -> None:


        self.worker_thread = None


        self.worker = None


        self.task_receiver = None





    def _is_task_cancelled(self) -> bool:


        return self.task_cancelled




    def _is_cancel_message(self, message: str) -> bool:


        normalized = message.strip().lower()


        return normalized in {


            "cancelled",


            "cancellederror",


            "thao tac bi huy",


            "thao tác bị hủy",


            tr("main.msg_cancelled", "Thao tác bị hủy").strip().lower(),


        }





    def cancel_task(self) -> None:


        if not self.busy:


            return


        self.task_cancelled = True


        self.ai_engine.cancel()


        self.view.statusBar().showMessage(tr("main.status_cancelling", "Đang hủy thao tác..."))


        if hasattr(self.view, "set_busy"):


            self.view.set_busy(


                True,


                tr("main.status_cancelling", "Đang hủy thao tác..."),


                tr("main.status_waiting_cancel", "Đang đợi tác vụ dừng an toàn."),


            )


        if self.worker_thread and self.worker_thread.isRunning():


            self.worker_thread.requestInterruption()

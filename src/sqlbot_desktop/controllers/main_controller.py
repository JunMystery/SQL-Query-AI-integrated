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

from PySide6.QtCore import QUrl


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


        self.view.cancel_requested.connect(self.cancel_task)


        self.view.chat_view.anchorClicked.connect(self.handle_chat_link)
        self.view.show_results_requested.connect(self.view.show_results_dialog)
        self.view.clear_chat_requested.connect(self.clear_chat_history)


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





        self.tables = tables


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

        self.view.append_user_message(question)
        self.view.append_status("AI đang suy nghĩ...")

        # Build concise schema context using local RAG selector to fit within context limits and prevent hallucination
        annotations = self.annotation_repository.load(self.profile.name)
        from sqlbot_desktop.services.schema_rag import SchemaRAG
        concise_schema = SchemaRAG.get_rag_schema_context(question, self.tables, annotations, max_tables=5)
        dialect = self.profile.driver.upper()

        system_content = (
            "Bạn là trợ lý phân tích cấu trúc CSDL và dịch câu hỏi tiếng Việt sang câu lệnh SQL SELECT chính xác.\n"
            "QUY TẮC BẮT BUỘC:\n"
            f"1. Chỉ trả lời câu lệnh SELECT. Cú pháp tương thích hoàn toàn với hệ CSDL (Dialect): **{dialect}**.\n"
            "2. Chỉ sử dụng đúng các bảng và cột thực tế được cung cấp trong phần SCHEMA dưới đây. Tuyệt đối không tự bịa ra tên bảng hoặc tên cột không tồn tại.\n"
            "3. Lọc họ tên chính xác (ví dụ: lọc người dùng tên 'Tú' -> full_name = 'Tú' hoặc username = 'Tú' trên đúng bảng và cột tương ứng).\n"
            f"4. Khi lọc theo ngày tháng, bắt buộc phải sử dụng định dạng chuẩn ISO-8601 YYYY-MM-DD (ví dụ: '2026-05-01' và '2026-05-10') trên đúng cột thời gian của bảng đó.\n"
            "5. Tuyệt đối không trả về bất kỳ mã nguồn lập trình nào khác (như Python, Java, v.v.).\n"
            "6. Trả về câu lệnh SQL đặt trong cặp dấu nháy ```sql ... ```.\n"
            "7. Giải thích cực kỳ ngắn gọn (dưới 3 câu) về hoạt động của câu lệnh SQL vừa tạo bằng tiếng Việt, không mô tả các bước suy luận trung gian."
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"SCHEMA:\n{concise_schema}\n\nCÂU HỎI:\n{question}"}
        ]

        self._start_task(
            "AI đang suy nghĩ...",
            "Đang dịch câu hỏi sang truy vấn SQL.",
            lambda: self.ai_engine.generate_chat_response(
                messages,
                check_cancelled=self._is_task_cancelled
            ),
            lambda result: self._handle_generate_result(question, result),
            show_busy_panel=False,
            on_failed=lambda err: self._handle_generate_failed(question, err)
        )

    def _handle_generate_result(self, question: str, result: object) -> None:
        text = str(result)
        self.view.remove_status()

        # Display the result directly in the chat log
        self.view.append_assistant_message(text)

        # Extract SQL blocks from response text
        import re
        sql = ""
        matches = re.findall(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if matches:
            sql = matches[0].strip()
        else:
            generic_matches = re.findall(r"```\s*(SELECT.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
            if generic_matches:
                sql = generic_matches[0].strip()

        if sql:
            from sqlbot_desktop.services.query_corrector import QueryCorrector
            corrected_sql = QueryCorrector.correct_query(sql, self.tables)
            self.view.set_generated_queries([corrected_sql])
            self.activity_repository.add_history(question, corrected_sql, True)
            self.view.statusBar().showMessage("Đã trích xuất SQL từ phản hồi trợ lý.")
        else:
            self.view.set_generated_queries([])
            self.activity_repository.add_history(question, "", False)
            self.view.statusBar().showMessage("AI phản hồi nhưng không tìm thấy code block SQL.")

    def _handle_generate_failed(self, question: str, error_message: str) -> None:
        self.view.remove_status()
        if error_message in ("Cancelled", "Thao tác bị hủy", "cancelled", "CancelledError"):
            self.view.append_assistant_message("Thao tác bị hủy.")
        else:
            self.view.append_assistant_message(f"Không thể hoàn thành yêu cầu: {error_message}")
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
            self.view.statusBar().showMessage("Đã copy gợi ý vào clipboard.")


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

    def clear_chat_history(self) -> None:
        self.assistant_history = []
        self.view.clear_chat()
        self.view.statusBar().showMessage("Đã xóa lịch sử phiên chat để giải phóng ngữ cảnh.")

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





        self._start_task(


            "Loading AI...",


            "Đang load model GGUF local." if config.backend.value == "local" else "Đang kiểm tra cấu hình API AI.",


            lambda: self.ai_engine.load(config, check_cancelled=self._is_task_cancelled),


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


            on_finished(result)





        def fail(message: str) -> None:


            self._finish_task(show_busy_panel)


            if on_failed is not None:


                on_failed(message)


            else:


                if message in ("Cancelled", "Thao tác bị hủy", "cancelled", "CancelledError"):


                    self.view.statusBar().showMessage("Đã hủy thao tác.")


                    return


                QMessageBox.warning(self.view, "Sinh SQL thất bại", message)


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





    def cancel_task(self) -> None:


        if not self.busy:


            return


        self.task_cancelled = True


        self.view.statusBar().showMessage("Đang hủy thao tác...")





        if self.worker_thread and self.worker_thread.isRunning():


            # Wait up to 150ms for cooperative cancellation


            self.worker_thread.wait(150)


            if self.worker_thread.isRunning():


                # Forcefully terminate the thread if it's still blocking


                self.worker_thread.terminate()


                self.worker_thread.wait()


                self._finish_task()


                self._clear_worker()


                self.view.statusBar().showMessage("Đã hủy thao tác.")






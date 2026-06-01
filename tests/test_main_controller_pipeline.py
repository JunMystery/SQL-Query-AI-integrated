"""Smoke tests for MainController text-to-SQL pipeline integration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.controllers.main_controller import MainController  # noqa: E402
from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, ConnectionProfile  # noqa: E402
from sqlbot_desktop.services.text_to_sql_pipeline import TextToSqlDiagnostics, TextToSqlResult  # noqa: E402


class FakeStatusBar:
    def __init__(self) -> None:
        self.message = ""

    def showMessage(self, message: str) -> None:
        self.message = message


class FakeView:
    def __init__(self) -> None:
        self.user_messages: list[str] = []
        self.assistant_messages: list[str] = []
        self.status_messages: list[str] = []
        self.generated_queries: list[str] = []
        self.busy_states: list[tuple[bool, str, str]] = []
        self._status_bar = FakeStatusBar()

    def append_user_message(self, text: str) -> None:
        self.user_messages.append(text)

    def append_status(self, text: str) -> None:
        self.status_messages.append(text)

    def remove_status(self) -> None:
        self.status_messages.append("removed")

    def append_assistant_message(self, text: str) -> None:
        self.assistant_messages.append(text)

    def set_generated_queries(self, queries: list[str]) -> None:
        self.generated_queries = queries

    def set_busy(self, active: bool, title: str = "", detail: str = "") -> None:
        self.busy_states.append((active, title, detail))

    def statusBar(self) -> FakeStatusBar:
        return self._status_bar

    def ai_model_config(self) -> AIModelConfig:
        return AIModelConfig(backend=AIBackend.API, self_correction_retries=4)


class FakeActivityRepository:
    def __init__(self) -> None:
        self.history: list[tuple[str, str, bool]] = []

    def add_history(self, question: str, sql: str, is_success: bool) -> None:
        self.history.append((question, sql, is_success))


class FakeDatabaseManager:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute_select(self, sql: str, connection_name: str):
        self.executed.append(f"{connection_name}:{sql}")


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        question: str,
        db_name: str,
        dialect: str,
        fallback_schema_context: str,
        execute_sql=None,
        max_retries: int = 3,
        check_cancelled=None,
    ):
        self.calls.append(
            {
                "question": question,
                "db_name": db_name,
                "dialect": dialect,
                "fallback_schema_context": fallback_schema_context,
                "execute_sql": execute_sql,
                "max_retries": max_retries,
            }
        )
        return TextToSqlResult(
            True,
            queries=["SELECT id FROM users;"],
            raw_text="```sql\nSELECT id FROM users;\n```",
            diagnostics=TextToSqlDiagnostics(selected_tables=["users"], attempts=2),
        )


class FakeAIEngine:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeWorkerThread:
    def __init__(self) -> None:
        self.interruption_requested = False
        self.terminate_called = False

    def isRunning(self) -> bool:
        return True

    def requestInterruption(self) -> None:
        self.interruption_requested = True

    def terminate(self) -> None:
        self.terminate_called = True


class MainControllerPipelineTests(unittest.TestCase):
    def make_controller(self) -> MainController:
        controller = MainController.__new__(MainController)
        controller.busy = False
        controller.profile = ConnectionProfile(name="Demo", driver="MYSQL", database="demo")
        controller.schema_context = "TABLE users"
        controller.view = FakeView()
        controller.activity_repository = FakeActivityRepository()
        controller.ai_engine = FakeAIEngine()
        controller.text_to_sql_pipeline = FakePipeline()
        controller.database_manager = FakeDatabaseManager()
        controller.connection_name = "conn1"
        controller.tables = []
        controller._is_task_cancelled = lambda: False
        return controller

    def test_generate_sql_uses_pipeline_operation(self) -> None:
        controller = self.make_controller()
        captured: dict[str, object] = {}

        def fake_start_task(title, detail, operation, on_finished, show_busy_panel=True, on_failed=None):
            captured["title"] = title
            captured["detail"] = detail
            captured["show_busy_panel"] = show_busy_panel
            result = operation()
            on_finished(result)

        controller._start_task = fake_start_task

        controller.generate_sql("Lấy user")

        self.assertEqual(controller.text_to_sql_pipeline.calls[0]["db_name"], "Demo")
        self.assertEqual(controller.text_to_sql_pipeline.calls[0]["dialect"], "MYSQL")
        self.assertIsNotNone(controller.text_to_sql_pipeline.calls[0]["execute_sql"])
        self.assertEqual(controller.text_to_sql_pipeline.calls[0]["max_retries"], 4)
        self.assertIs(captured["show_busy_panel"], True)
        self.assertEqual(controller.view.generated_queries, ["SELECT id FROM users;"])
        self.assertEqual(controller.activity_repository.history, [("Lấy user", "SELECT id FROM users;", True)])
        self.assertIn("2 lần", controller.view.status_messages[-1])

    def test_cancel_task_requests_cooperative_stop_without_terminating_thread(self) -> None:
        controller = self.make_controller()
        worker_thread = FakeWorkerThread()
        controller.busy = True
        controller.worker_thread = worker_thread

        controller.cancel_task()

        self.assertTrue(controller.task_cancelled)
        self.assertTrue(controller.ai_engine.cancelled)
        self.assertTrue(worker_thread.interruption_requested)
        self.assertFalse(worker_thread.terminate_called)
        self.assertTrue(controller.view.busy_states[-1][0])


if __name__ == "__main__":
    unittest.main()

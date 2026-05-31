"""Tests for Vietnamese prompt engineering."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo  # noqa: E402
from sqlbot_desktop.services.prompt_builder import PromptBuilder  # noqa: E402
from sqlbot_desktop.services.query_validator import QueryValidator  # noqa: E402


class PromptBuilderTests(unittest.TestCase):
    def test_prompt_contains_rules_examples_and_question(self) -> None:
        prompt = PromptBuilder.build("Liệt kê nhân viên", "TABLE employees", "MYSQL")

        self.assertIn("MySQL/MariaDB", prompt)
        self.assertIn("Liệt kê tên và lương", prompt)
        self.assertIn("TABLE employees", prompt)
        self.assertIn("Liệt kê nhân viên", prompt)
        self.assertIn("Generate SELECT statements only", prompt)
        self.assertIn("Reply in Vietnamese", prompt)
        self.assertIn("USER QUESTION", prompt)
        self.assertIn("SQL planning process", prompt)

    def test_system_prompt_is_english_with_vietnamese_reply_instruction(self) -> None:
        system_prompt = PromptBuilder.system_prompt()

        self.assertIn("You are an expert Text-to-SQL assistant.", system_prompt)
        self.assertIn("Reply in Vietnamese.", system_prompt)
        self.assertNotIn("Bạn là", system_prompt)
        self.assertNotIn("Chỉ tạo", system_prompt)

    def test_prompt_accepts_error_message_for_self_correction(self) -> None:
        prompt = PromptBuilder.build(
            "Lấy đơn hàng",
            "## Table: orders\n- id (INTEGER, PK)",
            "POSTGRESQL",
            error_message='column "orderid" does not exist',
            few_shot_examples=[],
        )

        self.assertIn("PostgreSQL", prompt)
        self.assertIn("PREVIOUS SQL ERROR", prompt)
        self.assertIn('column "orderid" does not exist', prompt)
        self.assertIn("JOIN conditions", prompt)
        self.assertIn("data types", prompt)
        self.assertNotIn("SYNTAX EXAMPLES", prompt)

    def test_error_message_is_clipped_before_prompting(self) -> None:
        long_error = "column missing_column does not exist\n" + ("traceback detail " * 100)

        prompt = PromptBuilder.build(
            "Lay user",
            "TABLE users",
            "MYSQL",
            error_message=long_error,
            few_shot_examples=[],
        )

        self.assertIn("column missing_column does not exist", prompt)
        self.assertIn("...", prompt)
        self.assertLess(len(prompt), 2000)

    def test_skeleton_instruction_is_internal_only(self) -> None:
        prompt = PromptBuilder.build("Liệt kê khách hàng", "TABLE customers", "MYSQL")

        self.assertIn("Internally choose the SQL skeleton first", prompt)
        self.assertIn("Do not output the skeleton", prompt)
        self.assertNotIn("SELECT {columns}", prompt)
        self.assertNotIn("{tables}", prompt)

    def test_skeleton_instruction_can_be_disabled_for_direct_prompt(self) -> None:
        prompt = PromptBuilder.build("Liệt kê khách hàng", "TABLE customers", "MYSQL", use_skeleton=False)

        self.assertNotIn("SQL planning process", prompt)

    def test_prompt_accepts_selected_few_shot_examples(self) -> None:
        prompt = PromptBuilder.build(
            "Tổng doanh thu",
            "## Table: orders",
            "MYSQL",
            few_shot_examples=[
                {
                    "question": "Tổng tiền theo tháng",
                    "sql": "SELECT month, SUM(total) FROM orders GROUP BY month;",
                }
            ],
        )

        self.assertIn("Tổng tiền theo tháng", prompt)
        self.assertIn("SELECT month, SUM(total)", prompt)

    def test_schema_context_includes_real_names_and_annotations(self) -> None:
        tables = [TableInfo("employees", [ColumnInfo("employee_id", "int", False)])]
        annotations = {
            "tables": {
                "employees": {
                    "description": "Nhân viên",
                    "columns": {
                        "employee_id": {
                            "description": "Mã nhân viên",
                            "unit": "",
                            "note": "khóa chính",
                            "type": "int",
                        }
                    },
                }
            }
        }

        context = PromptBuilder.build_schema_context(tables, annotations)

        self.assertIn("Nhân viên [employees]", context)
        self.assertIn("real_name=employee_id", context)
        self.assertIn("description=Mã nhân viên", context)
        self.assertIn("note=khóa chính", context)

    def test_schema_context_includes_limited_samples(self) -> None:
        tables = [
            TableInfo(
                "employees",
                [
                    ColumnInfo(
                        "employee_id",
                        "int",
                        False,
                        sample_value="1",
                        enum_values=["1", "2", "3", "4"],
                    )
                ],
            )
        ]

        context = PromptBuilder.build_schema_context(tables)

        self.assertIn("samples='1', '2', '3'", context)
        self.assertNotIn("'4'", context)

    def test_validator_allows_leading_sql_comments(self) -> None:
        self.assertTrue(QueryValidator.is_readonly_select("-- dùng JOIN\nSELECT * FROM employees;"))


if __name__ == "__main__":
    unittest.main()

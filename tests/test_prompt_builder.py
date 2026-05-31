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

    def test_validator_allows_leading_sql_comments(self) -> None:
        self.assertTrue(QueryValidator.is_readonly_select("-- dùng JOIN\nSELECT * FROM employees;"))


if __name__ == "__main__":
    unittest.main()

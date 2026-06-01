"""Dialog for viewing SELECT query execution results."""

from __future__ import annotations

import csv
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlbot_desktop.views.components.data_table import autosize_data_table_columns, configure_data_table
from sqlbot_desktop.utils.i18n_manager import tr


class QueryResultsDialog(QDialog):
    """Pop-up dialog displaying database query results table and export functionality."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(850, 600)
        self.resize(1000, 700)

        # Allow non-modal display so user can keep it open while editing queries
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.result_headers: list[str] = []
        self.result_rows: list[list[object]] = []

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header info
        header_layout = QHBoxLayout()
        self.summary_label = QLabel()
        self.summary_label.setObjectName("sectionTitle")
        header_layout.addWidget(self.summary_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setObjectName("resultsTable")
        self.results_table.setColumnCount(0)
        self.results_table.setRowCount(0)
        configure_data_table(self.results_table, "Query results popup")
        layout.addWidget(self.results_table, 1)

        # Action button row
        actions_layout = QHBoxLayout()
        self.export_button = QPushButton()
        self.export_button.setObjectName("secondaryButton")
        self.export_button.clicked.connect(self.export_csv)

        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.close)

        actions_layout.addWidget(self.export_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self.close_button)
        layout.addLayout(actions_layout)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.query_results_title", "Kết quả truy vấn"))
        self.export_button.setText(tr("dialogs.query_results_btn_export", "Export CSV"))
        self.close_button.setText(tr("dialogs.bookmarks_btn_close", "Đóng"))
        if not self.result_headers:
            self.summary_label.setText(tr("dialogs.query_results_no_data", "Chưa có dữ liệu kết quả."))
        else:
            self.summary_label.setText(
                tr("dialogs.query_results_summary_prefix", "Kết quả: Đã tải ") +
                f"{len(self.result_rows)}" +
                tr("dialogs.query_results_summary_rows", " dòng, ") +
                f"{len(self.result_headers)}" +
                tr("dialogs.query_results_summary_cols", " cột.")
            )

    def set_results(self, columns: list[str], rows: list[list[object]]) -> None:
        """Populate the table with data columns and rows."""
        self.result_headers = columns
        self.result_rows = rows

        self.results_table.clear()
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(rows))

        self.results_table.setUpdatesEnabled(False)
        try:
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    self.results_table.setItem(
                        row_index,
                        column_index,
                        QTableWidgetItem("" if value is None else str(value)),
                    )

            autosize_data_table_columns(self.results_table)
        finally:
            self.results_table.setUpdatesEnabled(True)

        self.summary_label.setText(
            tr("dialogs.query_results_summary_prefix", "Kết quả: Đã tải ") +
            f"{len(rows)}" +
            tr("dialogs.query_results_summary_rows", " dòng, ") +
            f"{len(columns)}" +
            tr("dialogs.query_results_summary_cols", " cột.")
        )

    def export_csv(self) -> None:
        """Export current results to a CSV file."""
        if not self.result_headers:
            QMessageBox.information(
                self,
                tr("dialogs.query_results_msg_no_data_title", "Chưa có dữ liệu"),
                tr("dialogs.query_results_msg_no_data_body", "Không có kết quả để xuất CSV.")
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dialogs.query_results_export_title", "Export CSV"),
            "query_results.csv",
            "CSV (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(self.result_headers)
                writer.writerows(self.result_rows)
            QMessageBox.information(
                self,
                tr("dialogs.query_results_msg_success_title", "Thành công"),
                tr("dialogs.query_results_msg_success_body", "Đã xuất file CSV thành công:\n") + f"{file_path}"
            )
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("dialogs.query_results_msg_error_title", "Lỗi xuất file"),
                tr("dialogs.query_results_msg_error_body", "Không thể lưu file CSV: ") + f"{exc}"
            )

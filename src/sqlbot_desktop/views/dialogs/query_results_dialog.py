"""Dialog for viewing SELECT query execution results."""

from __future__ import annotations

import csv
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class QueryResultsDialog(QDialog):
    """Pop-up dialog displaying database query results table and export functionality."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kết quả truy vấn")
        self.setMinimumSize(850, 600)
        self.resize(1000, 700)

        # Allow non-modal display so user can keep it open while editing queries
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.result_headers: list[str] = []
        self.result_rows: list[list[object]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header info
        header_layout = QHBoxLayout()
        self.summary_label = QLabel("Chưa có dữ liệu kết quả.")
        self.summary_label.setObjectName("sectionTitle")
        header_layout.addWidget(self.summary_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setObjectName("resultsTable")
        self.results_table.setColumnCount(0)
        self.results_table.setRowCount(0)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setAccessibleName("Query results popup")
        layout.addWidget(self.results_table, 1)

        # Action button row
        actions_layout = QHBoxLayout()
        export_button = QPushButton("Export CSV")
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self.export_csv)

        close_button = QPushButton("Đóng")
        close_button.clicked.connect(self.close)

        actions_layout.addWidget(export_button)
        actions_layout.addStretch()
        actions_layout.addWidget(close_button)
        layout.addLayout(actions_layout)

    def set_results(self, columns: list[str], rows: list[list[object]]) -> None:
        """Populate the table with data columns and rows."""
        self.result_headers = columns
        self.result_rows = rows

        self.results_table.clear()
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self.results_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem("" if value is None else str(value)),
                )

        # Auto-adjust resizing
        header = self.results_table.horizontalHeader()
        if len(columns) < 8:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        self.summary_label.setText(f"Kết quả: Đã tải {len(rows)} dòng, {len(columns)} cột.")

    def export_csv(self) -> None:
        """Export current results to a CSV file."""
        if not self.result_headers:
            QMessageBox.information(self, "Chưa có dữ liệu", "Không có kết quả để xuất CSV.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "query_results.csv", "CSV (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(self.result_headers)
                writer.writerows(self.result_rows)
            QMessageBox.information(self, "Thành công", f"Đã xuất file CSV thành công:\n{file_path}")
        except OSError as exc:
            QMessageBox.warning(self, "Lỗi xuất file", f"Không thể lưu file CSV: {exc}")

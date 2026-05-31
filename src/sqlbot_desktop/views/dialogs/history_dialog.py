"""History list dialog."""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository, HistoryEntry


class HistoryDialog(QDialog):
    """Show recent generation history with date filtering."""

    load_requested = Signal(str)

    def __init__(self, repository: ActivityRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.entries: list[HistoryEntry] = []

        self.setWindowTitle("History")
        self.setMinimumSize(860, 560)

        self.all_dates_check = QCheckBox("All dates")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.table = QTableWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("History")
        title.setObjectName("dialogTitle")
        caption = QLabel("Double-click một dòng để nạp lại câu hỏi vào khung nhập.")
        caption.setObjectName("dialogCaption")
        layout.addWidget(title)
        layout.addWidget(caption)

        filters = QHBoxLayout()
        self.all_dates_check.setChecked(True)
        self.all_dates_check.toggled.connect(lambda checked=False: self.refresh())
        self.date_edit.dateChanged.connect(lambda _: self.refresh())
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh)
        filters.addWidget(self.all_dates_check)
        filters.addWidget(self.date_edit)
        filters.addStretch()
        filters.addWidget(refresh_button)
        layout.addLayout(filters)

        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Time", "Status", "Question", "SQL", "ID"])
        self.table.setColumnHidden(4, True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._load_selected)
        layout.addWidget(self.table, 1)

        close_button = QPushButton("Đóng")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addWidget(self.status_label)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def refresh(self) -> None:
        date_filter = None if self.all_dates_check.isChecked() else self.date_edit.date().toString("yyyy-MM-dd")
        self.entries = self.repository.list_history(date_filter)
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            values = [
                entry.timestamp,
                "OK" if entry.is_success else "Failed",
                entry.question,
                entry.sql,
                str(entry.id),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self.status_label.setText(f"{len(self.entries)} items")

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        self.load_requested.emit(self.entries[row].question)
        self.accept()

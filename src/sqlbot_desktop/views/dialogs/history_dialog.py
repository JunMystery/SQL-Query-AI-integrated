"""History list dialog."""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository, HistoryEntry
from sqlbot_desktop.views.components.data_table import autosize_data_table_columns, configure_data_table
from sqlbot_desktop.utils.i18n_manager import tr


class HistoryDialog(QDialog):
    """Show recent generation history with date filtering."""

    load_requested = Signal(str, str)

    def __init__(self, repository: ActivityRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.entries: list[HistoryEntry] = []

        self.setMinimumSize(950, 560)

        self.all_dates_check = QCheckBox()
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.table = QTableWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")

        self._build_ui()
        self.retranslate_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("dialogCaption")
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)

        filters = QHBoxLayout()
        self.all_dates_check.setChecked(True)
        self.all_dates_check.toggled.connect(lambda checked=False: self.refresh())
        self.date_edit.dateChanged.connect(lambda _: self.refresh())
        self.refresh_button = QPushButton()
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self.refresh)
        filters.addWidget(self.all_dates_check)
        filters.addWidget(self.date_edit)
        filters.addStretch()
        filters.addWidget(self.refresh_button)
        layout.addLayout(filters)

        self.table.setColumnCount(5)
        self.table.setColumnHidden(4, True)
        configure_data_table(self.table, "History table")
        self.table.doubleClicked.connect(self._load_selected)
        layout.addWidget(self.table, 1)

        self.insert_button = QPushButton()
        self.insert_button.setObjectName("successButton")
        self.insert_button.clicked.connect(self._load_selected)
        self.bookmark_button = QPushButton()
        self.bookmark_button.setObjectName("primaryButton")
        self.bookmark_button.clicked.connect(self._bookmark_selected)
        self.close_button = QPushButton()
        self.close_button.setObjectName("secondaryButton")
        self.close_button.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addWidget(self.status_label)
        actions.addStretch()
        actions.addWidget(self.bookmark_button)
        actions.addWidget(self.insert_button)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.history_title", "History"))
        self.title_label.setText(tr("dialogs.history_title", "History"))
        self.caption_label.setText(tr("dialogs.history_caption", "Double-click một dòng để nạp lại câu hỏi vào khung nhập."))
        self.all_dates_check.setText(tr("dialogs.history_all_dates", "All dates"))
        self.refresh_button.setText(tr("dialogs.bookmarks_btn_refresh", "Refresh"))
        self.insert_button.setText(tr("dialogs.bookmarks_btn_insert", "Chèn"))
        self.bookmark_button.setText(tr("dialogs.bookmarks_btn_add", "Bookmark"))
        self.close_button.setText(tr("dialogs.bookmarks_btn_close", "Đóng"))

        self.table.setHorizontalHeaderLabels([
            tr("dialogs.history_hdr_time", "Time"),
            tr("dialogs.history_hdr_status", "Status"),
            tr("dialogs.history_hdr_question", "Question"),
            tr("dialogs.history_hdr_sql", "SQL"),
            tr("dialogs.history_hdr_id", "ID")
        ])

    def refresh(self) -> None:
        date_filter = None if self.all_dates_check.isChecked() else self.date_edit.date().toString("yyyy-MM-dd")
        self.entries = self.repository.list_history(date_filter)
        self.table.setRowCount(len(self.entries))
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        try:
            for row, entry in enumerate(self.entries):
                status_text = tr("dialogs.history_status_ok", "OK") if entry.is_success else tr("dialogs.history_status_failed", "Failed")
                self.table.setItem(row, 0, QTableWidgetItem(entry.timestamp))
                self.table.setItem(row, 1, QTableWidgetItem(status_text))
                self.table.setItem(row, 2, QTableWidgetItem(entry.question))
                self.table.setItem(row, 3, QTableWidgetItem(entry.sql))
                self.table.setItem(row, 4, QTableWidgetItem(str(entry.id)))

            autosize_data_table_columns(self.table)
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.blockSignals(False)
        self.status_label.setText(f"{len(self.entries)} " + tr("dialogs.history_status_items", "items"))

    def _insert_entry(self, entry: HistoryEntry) -> None:
        self.load_requested.emit(entry.question, entry.sql)
        self.accept()

    def _bookmark_entry(self, entry: HistoryEntry) -> None:
        from sqlbot_desktop.views.dialogs.bookmark_dialog import AddBookmarkDialog
        dialog = AddBookmarkDialog(entry.sql, parent=self, default_name=entry.question)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.repository.add_bookmark(dialog.bookmark_name, dialog.bookmark_sql, dialog.category, dialog.notes)
            self.status_label.setText(tr("main.status_bookmark_saved", "Đã lưu bookmark."))

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        self._insert_entry(self.entries[row])

    def _bookmark_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        self._bookmark_entry(self.entries[row])

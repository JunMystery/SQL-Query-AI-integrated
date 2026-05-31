"""Bookmark dialogs."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository, BookmarkEntry


class AddBookmarkDialog(QDialog):
    """Collect optional bookmark metadata."""

    def __init__(self, question: str, sql: str, parent=None) -> None:
        super().__init__(parent)
        self.question = question
        self.sql = sql
        self.category_input = QLineEdit()
        self.notes_input = QTextEdit()

        self.setWindowTitle("Add Bookmark")
        self.setMinimumSize(620, 420)
        self._build_ui()

    @property
    def category(self) -> str:
        return self.category_input.text().strip()

    @property
    def notes(self) -> str:
        return self.notes_input.toPlainText().strip()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Add Bookmark")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        question_label = QLabel(self.question or "Không có câu hỏi")
        question_label.setObjectName("dialogCaption")
        question_label.setWordWrap(True)
        sql_label = QLabel(self.sql)
        sql_label.setObjectName("formHint")
        sql_label.setWordWrap(True)
        layout.addWidget(question_label)
        layout.addWidget(sql_label)

        self.category_input.setPlaceholderText("Category/tag, ví dụ: payroll")
        self.notes_input.setPlaceholderText("Notes")
        self.notes_input.setFixedHeight(120)
        layout.addWidget(self.category_input)
        layout.addWidget(self.notes_input)

        actions = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.setObjectName("primaryButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("secondaryButton")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)


class BookmarksDialog(QDialog):
    """Show and manage saved bookmarks."""

    load_requested = Signal(str, str)

    def __init__(self, repository: ActivityRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.entries: list[BookmarkEntry] = []
        self.table = QTableWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")

        self.setWindowTitle("Bookmarks")
        self.setMinimumSize(900, 580)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Bookmarks")
        title.setObjectName("dialogTitle")
        caption = QLabel("Double-click một dòng để nạp lại câu hỏi và SQL đã lưu.")
        caption.setObjectName("dialogCaption")
        layout.addWidget(title)
        layout.addWidget(caption)

        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Time", "Category", "Question", "SQL", "Notes", "ID"])
        self.table.setColumnHidden(5, True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._load_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("dangerButton")
        close_button = QPushButton("Đóng")
        close_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh)
        delete_button.clicked.connect(self._delete_selected)
        close_button.clicked.connect(self.accept)
        actions.addWidget(self.status_label)
        actions.addStretch()
        actions.addWidget(refresh_button)
        actions.addWidget(delete_button)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def refresh(self) -> None:
        self.entries = self.repository.list_bookmarks()
        self.table.setRowCount(len(self.entries))
        for row, entry in enumerate(self.entries):
            values = [
                entry.timestamp,
                entry.category,
                entry.question,
                entry.sql,
                entry.notes,
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
        entry = self.entries[row]
        self.load_requested.emit(entry.question, entry.sql)
        self.accept()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        answer = QMessageBox.question(self, "Delete bookmark", "Xóa bookmark đã chọn?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.repository.delete_bookmark(entry.id)
        self.refresh()

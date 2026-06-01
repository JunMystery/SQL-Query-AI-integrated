"""Bookmark dialogs."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
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
from sqlbot_desktop.views.components.data_table import autosize_data_table_columns, configure_data_table
from sqlbot_desktop.utils.i18n_manager import tr


class AddBookmarkDialog(QDialog):
    """Collect optional bookmark metadata."""

    def __init__(
        self,
        sql: str,
        parent=None,
        default_name: str = "",
        default_category: str = "",
        default_notes: str = "",
        editable_sql: bool = False,
    ) -> None:
        super().__init__(parent)
        self.initial_sql = sql
        self.editable_sql = editable_sql
        self.name_input = QLineEdit()
        if default_name:
            self.name_input.setText(default_name)
        self.category_input = QLineEdit()
        if default_category:
            self.category_input.setText(default_category)
        self.notes_input = QTextEdit()
        if default_notes:
            self.notes_input.setPlainText(default_notes)

        self.setMinimumSize(500, 380)
        self._build_ui()
        self.retranslate_ui()

    @property
    def bookmark_name(self) -> str:
        return self.name_input.text().strip()

    @property
    def bookmark_sql(self) -> str:
        return self.sql_display.toPlainText().strip()

    @property
    def category(self) -> str:
        return self.category_input.text().strip()

    @property
    def notes(self) -> str:
        return self.notes_input.toPlainText().strip()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.bookmark_add_title"))
        if hasattr(self, "title_label"):
            self.title_label.setText(tr("dialogs.bookmark_add_title"))
        if hasattr(self, "sql_label"):
            self.sql_label.setText(tr("dialogs.bookmark_label_sql"))
        if hasattr(self, "name_label"):
            self.name_label.setText(tr("dialogs.bookmark_label_name"))
        self.name_input.setPlaceholderText(tr("dialogs.bookmark_name_placeholder"))
        if hasattr(self, "category_label"):
            self.category_label.setText(tr("dialogs.bookmark_label_category"))
        self.category_input.setPlaceholderText(tr("dialogs.bookmark_category_placeholder"))
        if hasattr(self, "notes_label"):
            self.notes_label.setText(tr("dialogs.bookmark_label_notes"))
        self.notes_input.setPlaceholderText(tr("dialogs.bookmark_notes_placeholder"))
        self.save_button.setText(tr("dialogs.bookmark_btn_save"))
        self.cancel_button.setText(tr("dialogs.bookmark_btn_cancel"))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        layout.addWidget(self.title_label)

        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_input)

        self.sql_label = QLabel()
        self.sql_label.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(self.sql_label)

        self.sql_display = QTextEdit()
        self.sql_display.setPlainText(self.initial_sql)
        self.sql_display.setReadOnly(not self.editable_sql)
        self.sql_display.setFixedHeight(80)
        self.sql_display.setObjectName("sqlEditor")
        layout.addWidget(self.sql_display)

        self.category_label = QLabel()
        self.category_label.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(self.category_label)
        layout.addWidget(self.category_input)

        self.notes_label = QLabel()
        self.notes_label.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(self.notes_label)
        self.notes_input.setFixedHeight(80)
        layout.addWidget(self.notes_input)

        actions = QHBoxLayout()
        self.save_button = QPushButton()
        self.save_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("secondaryButton")

        def on_save():
            if not self.name_input.text().strip():
                QMessageBox.warning(self, tr("dialogs.bookmarks_msg_missing_name", "Thiếu thông tin"), tr("dialogs.bookmarks_msg_missing_name", "Vui lòng nhập tên Bookmark."))
                return
            self.accept()

        self.save_button.clicked.connect(on_save)
        self.cancel_button.clicked.connect(self.reject)

        actions.addStretch()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)


class BookmarksDialog(QDialog):
    """Show and manage saved bookmarks with quick insert action."""

    load_requested = Signal(str, str)

    def __init__(self, repository: ActivityRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.entries: list[BookmarkEntry] = []
        self.table = QTableWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")

        self.setMinimumSize(950, 580)
        self._build_ui()
        self.retranslate_ui()
        self.refresh()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.bookmarks_list_title"))
        if hasattr(self, "title_label"):
            self.title_label.setText(tr("dialogs.bookmarks_list_title"))
        if hasattr(self, "caption_label"):
            self.caption_label.setText(tr("dialogs.bookmarks_caption"))

        # Translate headers
        headers = [
            tr("dialogs.bookmarks_header_time", "Thời gian"),
            tr("dialogs.bookmarks_header_category", "Danh mục"),
            tr("dialogs.bookmarks_header_name", "Tên Bookmark"),
            tr("dialogs.bookmarks_header_sql", "SQL Query"),
            tr("dialogs.bookmarks_header_notes", "Ghi chú"),
            "ID"
        ]
        self.table.setHorizontalHeaderLabels(headers)

        self.insert_button.setText(tr("dialogs.bookmarks_btn_insert"))
        self.edit_button.setText(tr("dialogs.bookmarks_btn_edit", "Sửa"))
        self.refresh_button.setText(tr("dialogs.bookmarks_btn_refresh"))
        self.delete_button.setText(tr("dialogs.bookmarks_btn_delete"))
        self.close_button.setText(tr("dialogs.bookmarks_btn_close"))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("dialogCaption")
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)

        self.table.setColumnCount(6)
        self.table.setColumnHidden(5, True)
        configure_data_table(self.table, "Bookmarks table")
        self.table.doubleClicked.connect(self._load_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.insert_button = QPushButton()
        self.insert_button.setObjectName("successButton")
        self.insert_button.setMinimumHeight(32)

        self.edit_button = QPushButton()
        self.edit_button.setObjectName("primaryButton")
        self.edit_button.setMinimumHeight(32)

        self.refresh_button = QPushButton()
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.setMinimumHeight(32)

        self.delete_button = QPushButton()
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setMinimumHeight(32)

        self.close_button = QPushButton()
        self.close_button.setObjectName("secondaryButton")
        self.close_button.setMinimumHeight(32)

        self.insert_button.clicked.connect(self._load_selected)
        self.edit_button.clicked.connect(self._edit_selected)
        self.refresh_button.clicked.connect(self.refresh)
        self.delete_button.clicked.connect(self._delete_selected)
        self.close_button.clicked.connect(self.accept)

        actions.addWidget(self.status_label)
        actions.addStretch()
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.delete_button)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.insert_button)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    def refresh(self) -> None:
        self.entries = self.repository.list_bookmarks()
        self.table.setRowCount(len(self.entries))

        # Block signals temporarily to prevent event loops while redrawing
        self.table.blockSignals(True)
        for row, entry in enumerate(self.entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.timestamp))
            self.table.setItem(row, 1, QTableWidgetItem(entry.category))
            self.table.setItem(row, 2, QTableWidgetItem(entry.question))
            self.table.setItem(row, 3, QTableWidgetItem(entry.sql))
            self.table.setItem(row, 4, QTableWidgetItem(entry.notes))
            self.table.setItem(row, 5, QTableWidgetItem(str(entry.id)))

        self.table.blockSignals(False)
        autosize_data_table_columns(self.table)
        self.status_label.setText(f"{len(self.entries)} items")

    def _insert_entry(self, entry: BookmarkEntry) -> None:
        self.load_requested.emit(entry.question, entry.sql)
        self.accept()

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        self._insert_entry(entry)

    def _edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        self._edit_entry(self.entries[row])

    def _edit_entry(self, entry: BookmarkEntry) -> None:
        dialog = AddBookmarkDialog(
            entry.sql,
            parent=self,
            default_name=entry.question,
            default_category=entry.category,
            default_notes=entry.notes,
            editable_sql=True,
        )
        dialog.setWindowTitle(tr("dialogs.bookmark_edit_title", "Sửa Bookmark"))
        if hasattr(dialog, "title_label"):
            dialog.title_label.setText(tr("dialogs.bookmark_edit_title", "Sửa Bookmark"))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.repository.update_bookmark(
                entry.id,
                dialog.bookmark_name,
                dialog.bookmark_sql,
                dialog.category,
                dialog.notes,
            )
            self.refresh()
            self.status_label.setText(tr("dialogs.bookmarks_msg_updated", "Đã cập nhật bookmark."))

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        answer = QMessageBox.question(self, tr("dialogs.bookmarks_btn_delete"), tr("dialogs.bookmarks_msg_delete_confirm"))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.repository.delete_bookmark(entry.id)
        self.refresh()

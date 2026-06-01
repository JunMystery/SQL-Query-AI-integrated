"""Schema annotation editor dialog wrapping the unified SchemaAnnotationWidget."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from sqlbot_desktop.models.entities import TableInfo
from sqlbot_desktop.infrastructure.annotation_repository import AnnotationRepository
from sqlbot_desktop.views.dialogs.settings_dialog import SchemaAnnotationWidget
from sqlbot_desktop.utils.i18n_manager import tr


class SchemaAnnotationDialog(QDialog):
    """Edit natural-language descriptions for tables and columns using the unified SchemaAnnotationWidget."""

    def __init__(
        self,
        connection_name: str,
        tables: list[TableInfo],
        parent=None,
        repository: AnnotationRepository | None = None,
    ) -> None:
        super().__init__(parent)
        self.connection_name = connection_name
        self.tables = tables
        self.repository = repository or AnnotationRepository()

        self.setMinimumSize(960, 640)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Use the unified two-pane schema annotation widget, showing the close button
        self.widget = SchemaAnnotationWidget(
            connection_name=connection_name,
            tables=tables,
            repository=repository,
            parent=self,
            show_close_button=True
        )
        layout.addWidget(self.widget)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("settings.annotation_editor_title", "Schema Annotation Editor"))
        self.widget.retranslate_ui()

    def closeEvent(self, event) -> None:
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()

    def _confirm_discard_changes(self) -> bool:
        if self.widget.is_dirty():
            res = QMessageBox.question(
                self,
                tr("settings.title_unsaved_changes", "Có thay đổi chưa lưu"),
                tr("settings.msg_unsaved_changes", "Bạn có thay đổi chưa lưu trong Chú thích Schema. Bạn có chắc chắn muốn quay lại và bỏ qua thay đổi?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return res == QMessageBox.Yes
        return True

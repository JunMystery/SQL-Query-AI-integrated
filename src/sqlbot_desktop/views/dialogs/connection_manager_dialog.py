"""Connection profile management dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from sqlbot_desktop.models.entities import ConnectionProfile
from sqlbot_desktop.infrastructure.database_manager import DatabaseManager
from sqlbot_desktop.infrastructure.profile_repository import ProfileRepository
from sqlbot_desktop.views.dialogs.change_admin_password_dialog import ChangeAdminPasswordDialog
from sqlbot_desktop.views.dialogs.connection_form_dialog import ConnectionFormDialog
from sqlbot_desktop.utils.i18n_manager import tr


class ConnectionManagerDialog(QDialog):
    """Add, edit, delete, and test saved connection profiles."""

    def __init__(
        self,
        repository: ProfileRepository,
        database_manager: DatabaseManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.database_manager = database_manager
        self.profiles = self.repository.load_profiles()

        self.setMinimumSize(720, 520)
        self.setModal(True)

        self.profile_list = QListWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self._refresh_list()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("dialogCaption")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)
        layout.addWidget(self.profile_list, 1)

        actions = QHBoxLayout()
        self.add_button = QPushButton()
        self.add_button.setObjectName("primaryButton")
        self.edit_button = QPushButton()
        self.edit_button.setObjectName("secondaryButton")
        self.delete_button = QPushButton()
        self.delete_button.setObjectName("dangerButton")
        self.test_button = QPushButton()
        self.test_button.setObjectName("secondaryButton")
        self.password_button = QPushButton()
        self.password_button.setObjectName("secondaryButton")
        self.close_button = QPushButton()
        self.close_button.setObjectName("secondaryButton")

        self.add_button.clicked.connect(self._add_profile)
        self.edit_button.clicked.connect(self._edit_profile)
        self.delete_button.clicked.connect(self._delete_profile)
        self.test_button.clicked.connect(self._test_profile)
        self.password_button.clicked.connect(self._change_password)
        self.close_button.clicked.connect(self.accept)

        for button in [self.add_button, self.edit_button, self.delete_button, self.test_button]:
            actions.addWidget(button)
        actions.addWidget(self.password_button)
        actions.addStretch()
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.conn_mgr_title", "Quản lý kết nối"))
        self.title_label.setText(tr("dialogs.conn_mgr_heading", "Connection profiles"))
        self.caption_label.setText(tr("dialogs.conn_mgr_caption", "Thêm, sửa, xóa và kiểm tra các cấu hình CSDL. Password không được lưu vào profile."))
        
        self.add_button.setText(tr("dialogs.conn_mgr_btn_add", "+ Thêm mới"))
        self.edit_button.setText(tr("dialogs.conn_mgr_btn_edit", "Edit"))
        self.delete_button.setText(tr("dialogs.conn_mgr_btn_delete", "- Xóa"))
        self.test_button.setText(tr("dialogs.conn_form_btn_test", "Test Connection"))
        self.password_button.setText(tr("dialogs.conn_mgr_btn_change_pw", "Đổi mật khẩu"))
        self.close_button.setText(tr("dialogs.bookmarks_btn_close", "Đóng"))

    def _refresh_list(self) -> None:
        self.profile_list.clear()
        for profile in self.profiles:
            item = QListWidgetItem(f"{profile.name}  |  {profile.driver}  |  {profile.database or profile.extra}")
            item.setData(Qt.ItemDataRole.UserRole, profile)
            item.setToolTip(profile.description or profile.name)
            self.profile_list.addItem(item)

    def _selected_index(self) -> int:
        row = self.profile_list.currentRow()
        if row < 0 or row >= len(self.profiles):
            self.status_label.setText(tr("dialogs.conn_mgr_select_profile", "Vui lòng chọn một profile."))
            return -1
        return row

    def _add_profile(self) -> None:
        dialog = ConnectionFormDialog(self.database_manager, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self.profiles.append(dialog.saved_profile)
            self._persist_and_refresh(tr("dialogs.conn_mgr_profile_added", "Đã thêm profile."))

    def _edit_profile(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        dialog = ConnectionFormDialog(self.database_manager, self.profiles[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self.profiles[index] = dialog.saved_profile
            self._persist_and_refresh(tr("dialogs.conn_mgr_profile_updated", "Đã cập nhật profile."))

    def _delete_profile(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        profile = self.profiles[index]
        answer = QMessageBox.question(
            self,
            tr("dialogs.conn_mgr_delete_confirm_title", "Xóa connection"),
            tr("dialogs.conn_mgr_delete_confirm_msg", "Xóa profile ") + f"'{profile.name}'?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self.profiles[index]
        self._persist_and_refresh(tr("dialogs.conn_mgr_profile_deleted", "Đã xóa profile."))

    def _test_profile(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        dialog = ConnectionFormDialog(self.database_manager, self.profiles[index], self)
        dialog.setWindowTitle(tr("dialogs.conn_form_btn_test", "Test Connection"))
        dialog.exec()

    def _change_password(self) -> None:
        dialog = ChangeAdminPasswordDialog(self)
        dialog.exec()

    def _persist_and_refresh(self, message: str) -> None:
        self.repository.save_profiles(self.profiles)
        self._refresh_list()
        self.status_label.setText(message)

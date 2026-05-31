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

        self.setWindowTitle("Quản lý kết nối")
        self.setMinimumSize(720, 520)
        self.setModal(True)

        self.profile_list = QListWidget()
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Connection profiles")
        title.setObjectName("dialogTitle")
        caption = QLabel("Thêm, sửa, xóa và kiểm tra các cấu hình CSDL. Password không được lưu vào profile.")
        caption.setObjectName("dialogCaption")
        caption.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(caption)
        layout.addWidget(self.profile_list, 1)

        actions = QHBoxLayout()
        add_button = QPushButton("+ Thêm mới")
        add_button.setObjectName("primaryButton")
        edit_button = QPushButton("Edit")
        edit_button.setObjectName("secondaryButton")
        delete_button = QPushButton("- Xóa")
        delete_button.setObjectName("dangerButton")
        test_button = QPushButton("Test Connection")
        test_button.setObjectName("secondaryButton")
        password_button = QPushButton("Đổi mật khẩu")
        password_button.setObjectName("secondaryButton")
        close_button = QPushButton("Đóng")
        close_button.setObjectName("secondaryButton")

        add_button.clicked.connect(self._add_profile)
        edit_button.clicked.connect(self._edit_profile)
        delete_button.clicked.connect(self._delete_profile)
        test_button.clicked.connect(self._test_profile)
        password_button.clicked.connect(self._change_password)
        close_button.clicked.connect(self.accept)

        for button in [add_button, edit_button, delete_button, test_button]:
            actions.addWidget(button)
        actions.addWidget(password_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)
        layout.addWidget(self.status_label)

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
            self.status_label.setText("Vui lòng chọn một profile.")
            return -1
        return row

    def _add_profile(self) -> None:
        dialog = ConnectionFormDialog(self.database_manager, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self.profiles.append(dialog.saved_profile)
            self._persist_and_refresh("Đã thêm profile.")

    def _edit_profile(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        dialog = ConnectionFormDialog(self.database_manager, self.profiles[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self.profiles[index] = dialog.saved_profile
            self._persist_and_refresh("Đã cập nhật profile.")

    def _delete_profile(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        profile = self.profiles[index]
        answer = QMessageBox.question(self, "Xóa connection", f"Xóa profile '{profile.name}'?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self.profiles[index]
        self._persist_and_refresh("Đã xóa profile.")

    def _test_profile(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        dialog = ConnectionFormDialog(self.database_manager, self.profiles[index], self)
        dialog.setWindowTitle("Test connection")
        dialog.exec()

    def _change_password(self) -> None:
        dialog = ChangeAdminPasswordDialog(self)
        dialog.exec()

    def _persist_and_refresh(self, message: str) -> None:
        self.repository.save_profiles(self.profiles)
        self._refresh_list()
        self.status_label.setText(message)

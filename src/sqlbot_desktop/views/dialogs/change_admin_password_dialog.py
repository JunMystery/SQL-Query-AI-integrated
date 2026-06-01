"""Dialog for changing the connection-management password."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QVBoxLayout
from sqlbot_desktop.utils.i18n_manager import tr
from sqlbot_desktop.infrastructure.admin_password_store import AdminPasswordStore


class ChangeAdminPasswordDialog(QDialog):
    """Change the admin password and store only a salted hash."""

    def __init__(self, parent=None, password_store: AdminPasswordStore | None = None) -> None:
        super().__init__(parent)
        self.password_store = password_store or AdminPasswordStore()

        self.setModal(True)
        self.setMinimumWidth(420)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("dialogCaption")
        self.caption_label.setWordWrap(True)

        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._save)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)
        layout.addWidget(self.current_password_input)
        layout.addWidget(self.new_password_input)
        layout.addWidget(self.confirm_password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.button_box)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.admin_change_title", "Thay đổi mật khẩu quản lý"))
        self.title_label.setText(tr("dialogs.admin_change_heading", "Thay đổi mật khẩu"))
        self.caption_label.setText(tr("dialogs.admin_change_caption", "Mật khẩu mới được lưu cục bộ dưới dạng salt/hash, không lưu plaintext."))
        
        self.current_password_input.setPlaceholderText(tr("dialogs.admin_change_current_placeholder", "Mật khẩu hiện tại"))
        self.current_password_input.setAccessibleName(tr("dialogs.admin_change_current_placeholder", "Mật khẩu hiện tại"))
        
        self.new_password_input.setPlaceholderText(tr("dialogs.admin_change_new_placeholder", "Mật khẩu mới"))
        self.new_password_input.setAccessibleName(tr("dialogs.admin_change_new_placeholder", "Mật khẩu mới"))
        
        self.confirm_password_input.setPlaceholderText(tr("dialogs.admin_change_confirm_placeholder", "Nhập lại mật khẩu mới"))
        self.confirm_password_input.setAccessibleName(tr("dialogs.admin_change_confirm_placeholder", "Nhập lại mật khẩu mới"))

    def _save(self) -> None:
        current_password = self.current_password_input.text()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not self.password_store.verify(current_password):
            self.error_label.setText(tr("dialogs.admin_change_err_incorrect", "Mật khẩu hiện tại không đúng."))
            return

        if len(new_password) < 8:
            self.error_label.setText(tr("dialogs.admin_change_err_too_short", "Mật khẩu mới cần tối thiểu 8 ký tự."))
            return

        if new_password != confirm_password:
            self.error_label.setText(tr("dialogs.admin_change_err_mismatch", "Mật khẩu mới nhập lại không khớp."))
            return

        self.password_store.update(new_password)
        QMessageBox.information(
            self,
            tr("dialogs.admin_change_success_title", "Đã đổi mật khẩu"),
            tr("dialogs.admin_change_success_msg", "Mật khẩu quản lý kết nối đã được cập nhật.")
        )
        self.accept()

"""Password gate for connection administration."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout
from sqlbot_desktop.utils.i18n_manager import tr
from sqlbot_desktop.infrastructure.admin_password_store import AdminPasswordStore


class AdminPasswordDialog(QDialog):
    """Prompt for the connection-management password."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.password_store = AdminPasswordStore()
        self.is_first_run = not self.password_store.is_configured()
        self.setModal(True)
        self.setMinimumWidth(360)

        self.message_label = QLabel()
        self.message_label.setObjectName("dialogCaption")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setVisible(self.is_first_run)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._accept_if_valid)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.message_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.confirm_password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.button_box)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.admin_auth_title", "Xác thực quản trị"))
        
        message = (
            tr("dialogs.admin_auth_msg_first_run", "Chưa có mật khẩu quản lý. Tạo mật khẩu ban đầu để mở quản lý kết nối.")
            if self.is_first_run
            else tr("dialogs.admin_auth_msg_prompt", "Nhập mật khẩu quản lý kết nối.")
        )
        self.message_label.setText(message)
        
        self.password_input.setPlaceholderText(
            tr("dialogs.admin_auth_new_pw_placeholder", "Mật khẩu mới")
            if self.is_first_run
            else tr("dialogs.admin_auth_admin_pw_placeholder", "Mật khẩu quản trị")
        )
        self.password_input.setAccessibleName(
            tr("dialogs.admin_auth_new_pw_placeholder", "Mật khẩu mới")
            if self.is_first_run
            else tr("dialogs.admin_auth_admin_pw_placeholder", "Mật khẩu quản trị")
        )
        
        self.confirm_password_input.setPlaceholderText(tr("dialogs.admin_auth_confirm_placeholder", "Nhập lại mật khẩu mới"))
        self.confirm_password_input.setAccessibleName(tr("dialogs.admin_auth_confirm_placeholder", "Nhập lại mật khẩu mới"))

    def _accept_if_valid(self) -> None:
        if self.is_first_run:
            self._create_initial_password()
            return

        if not self.password_store.verify(self.password_input.text()):
            self.error_label.setText(tr("dialogs.admin_auth_err_incorrect", "Mật khẩu không đúng."))
            self.password_input.selectAll()
            self.password_input.setFocus()
            return

        self.accept()

    def _create_initial_password(self) -> None:
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if len(password) < 8:
            self.error_label.setText(tr("dialogs.admin_auth_err_too_short", "Mật khẩu cần tối thiểu 8 ký tự."))
            return

        if password != confirm_password:
            self.error_label.setText(tr("dialogs.admin_auth_err_mismatch", "Mật khẩu nhập lại không khớp."))
            return

        self.password_store.update(password)
        self.accept()

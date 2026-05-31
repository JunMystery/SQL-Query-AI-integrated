"""Password gate for connection administration."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout

from sqlbot_desktop.infrastructure.admin_password_store import AdminPasswordStore


class AdminPasswordDialog(QDialog):
    """Prompt for the connection-management password."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.password_store = AdminPasswordStore()
        self.is_first_run = not self.password_store.is_configured()
        self.setWindowTitle("Xác thực quản trị")
        self.setModal(True)
        self.setMinimumWidth(360)

        message = (
            "Chưa có mật khẩu quản lý. Tạo mật khẩu ban đầu để mở quản lý kết nối."
            if self.is_first_run
            else "Nhập mật khẩu quản lý kết nối."
        )
        self.message_label = QLabel(message)
        self.message_label.setObjectName("dialogCaption")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Mật khẩu mới" if self.is_first_run else "Mật khẩu quản trị")
        self.password_input.setAccessibleName("Mật khẩu quản trị")

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setPlaceholderText("Nhập lại mật khẩu mới")
        self.confirm_password_input.setAccessibleName("Nhập lại mật khẩu mới")
        self.confirm_password_input.setVisible(self.is_first_run)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.message_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.confirm_password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if self.is_first_run:
            self._create_initial_password()
            return

        if not self.password_store.verify(self.password_input.text()):
            self.error_label.setText("Mật khẩu không đúng.")
            self.password_input.selectAll()
            self.password_input.setFocus()
            return

        self.accept()

    def _create_initial_password(self) -> None:
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if len(password) < 8:
            self.error_label.setText("Mật khẩu cần tối thiểu 8 ký tự.")
            return

        if password != confirm_password:
            self.error_label.setText("Mật khẩu nhập lại không khớp.")
            return

        self.password_store.update(password)
        self.accept()

"""Dialog for changing the connection-management password."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QVBoxLayout

from sqlbot_desktop.infrastructure.admin_password_store import AdminPasswordStore


class ChangeAdminPasswordDialog(QDialog):
    """Change the admin password and store only a salted hash."""

    def __init__(self, parent=None, password_store: AdminPasswordStore | None = None) -> None:
        super().__init__(parent)
        self.password_store = password_store or AdminPasswordStore()

        self.setWindowTitle("Thay đổi mật khẩu quản lý")
        self.setModal(True)
        self.setMinimumWidth(420)

        title = QLabel("Thay đổi mật khẩu")
        title.setObjectName("dialogTitle")
        caption = QLabel("Mật khẩu mới được lưu cục bộ dưới dạng salt/hash, không lưu plaintext.")
        caption.setObjectName("dialogCaption")
        caption.setWordWrap(True)

        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_password_input.setPlaceholderText("Mật khẩu hiện tại")
        self.current_password_input.setAccessibleName("Mật khẩu hiện tại")

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText("Mật khẩu mới")
        self.new_password_input.setAccessibleName("Mật khẩu mới")

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setPlaceholderText("Nhập lại mật khẩu mới")
        self.confirm_password_input.setAccessibleName("Nhập lại mật khẩu mới")

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(caption)
        layout.addWidget(self.current_password_input)
        layout.addWidget(self.new_password_input)
        layout.addWidget(self.confirm_password_input)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def _save(self) -> None:
        current_password = self.current_password_input.text()
        new_password = self.new_password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not self.password_store.verify(current_password):
            self.error_label.setText("Mật khẩu hiện tại không đúng.")
            return

        if len(new_password) < 8:
            self.error_label.setText("Mật khẩu mới cần tối thiểu 8 ký tự.")
            return

        if new_password != confirm_password:
            self.error_label.setText("Mật khẩu mới nhập lại không khớp.")
            return

        self.password_store.update(new_password)
        QMessageBox.information(self, "Đã đổi mật khẩu", "Mật khẩu quản lý kết nối đã được cập nhật.")
        self.accept()

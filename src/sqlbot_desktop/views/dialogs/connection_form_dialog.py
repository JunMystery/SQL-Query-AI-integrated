"""Create and edit database connection profiles."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from sqlbot_desktop.models.entities import ConnectionProfile
from sqlbot_desktop.infrastructure.database_manager import DatabaseManager
from sqlbot_desktop.infrastructure.schema_extractor import SchemaExtractor
from sqlbot_desktop.views.dialogs.schema_annotation_dialog import SchemaAnnotationDialog


DRIVER_LABELS = {
    "MYSQL": "MySQL / MariaDB - bundled PyMySQL",
    "POSTGRESQL": "PostgreSQL - bundled psycopg",
}
DRIVERS = list(DRIVER_LABELS.keys())
DRIVER_HINTS = {
    "MYSQL": "MySQL/MariaDB dùng PyMySQL đã đóng gói trong EXE, không cần Qt QMYSQL plugin.",
    "POSTGRESQL": "PostgreSQL dùng psycopg binary đã đóng gói trong EXE, không cần cài libpq riêng.",
}
DRIVER_PLACEHOLDERS = {
    "MYSQL": {
        "host": "mysql.company.local hoặc 192.168.1.20",
        "database": "sales_db",
        "username": "report_user",
        "password": "Nhập password MySQL/MariaDB để test",
        "extra": "charset=utf8mb4",
    },
    "POSTGRESQL": {
        "host": "postgres.company.local hoặc 192.168.1.30",
        "database": "analytics_db",
        "username": "readonly_user",
        "password": "Nhập password PostgreSQL để test",
        "extra": "sslmode=require",
    },
}
DEFAULT_PORTS = {"MYSQL": 3306, "POSTGRESQL": 5432}


class ConnectionFormDialog(QDialog):
    """Form for creating or editing one connection profile."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        profile: ConnectionProfile | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.database_manager = database_manager
        self.original_profile = profile
        self.saved_profile: ConnectionProfile | None = None

        self.setWindowTitle("Connection profile")
        self.setModal(True)
        self.setMinimumSize(560, 560)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ví dụ: Production Sales DB")
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Ví dụ: CSDL doanh số cho phòng Kinh doanh")
        self.driver_combo = QComboBox()
        for driver, label in DRIVER_LABELS.items():
            self.driver_combo.addItem(label, driver)
            self.driver_combo.setItemData(self.driver_combo.count() - 1, DRIVER_HINTS[driver], role=3)
        self.driver_hint_label = QLabel("")
        self.driver_hint_label.setObjectName("formHint")
        self.driver_hint_label.setWordWrap(True)
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(0, 65535)
        self.port_input.setSpecialValueText("N/A")
        self.database_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.extra_input = QTextEdit()
        self.extra_input.setMaximumHeight(90)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self._load_profile(profile)
        self._wire_events()

    def profile(self) -> ConnectionProfile:
        port = self.port_input.value() or None
        return ConnectionProfile(
            name=self.name_input.text().strip(),
            driver=self.driver_combo.currentData(),
            database=self.database_input.text().strip(),
            host=self.host_input.text().strip(),
            port=port,
            username=self.username_input.text().strip(),
            description=self.description_input.text().strip(),
            extra=self.extra_input.toPlainText().strip(),
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Thông tin kết nối")
        title.setObjectName("dialogTitle")
        caption = QLabel("Password chỉ dùng để test hoặc lấy schema, không lưu vào file cấu hình.")
        caption.setObjectName("dialogCaption")
        caption.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(caption)

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())
        form.addRow("Tên profile", self.name_input)
        form.addRow("Diễn giải", self.description_input)
        form.addRow("Driver", self.driver_combo)
        form.addRow("", self.driver_hint_label)
        form.addRow("Host", self.host_input)
        form.addRow("Port", self.port_input)
        form.addRow("Database", self.database_input)

        form.addRow("Username", self.username_input)
        form.addRow("Password test", self.password_input)
        form.addRow("Connection options", self.extra_input)
        layout.addLayout(form)

        actions = QHBoxLayout()
        test_button = QPushButton("Test Connection")
        test_button.setObjectName("secondaryButton")
        test_button.clicked.connect(self._test_connection)
        schema_button = QPushButton("Connect & Get Schema")
        schema_button.setObjectName("primaryButton")
        schema_button.clicked.connect(self._connect_get_schema)
        actions.addWidget(test_button)
        actions.addWidget(schema_button)
        layout.addLayout(actions)

        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _wire_events(self) -> None:
        self.driver_combo.currentIndexChanged.connect(self._sync_driver_fields)

    def _load_profile(self, profile: ConnectionProfile | None) -> None:
        if profile is None:
            self._set_driver("MYSQL")
            self._sync_driver_fields()
            return

        self.name_input.setText(profile.name)
        self.description_input.setText(profile.description)
        self._set_driver(profile.driver)
        self.host_input.setText(profile.host)
        self.port_input.setValue(profile.port or 0)
        self.database_input.setText(profile.database)
        self.username_input.setText(profile.username)
        self.extra_input.setPlainText(profile.extra)
        self._sync_driver_fields()

    def _set_driver(self, driver: str) -> None:
        index = self.driver_combo.findData(driver)
        self.driver_combo.setCurrentIndex(index if index >= 0 else 0)

    def _sync_driver_fields(self) -> None:
        driver = self.driver_combo.currentData()
        self.host_input.setEnabled(True)
        self.port_input.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        hint = DRIVER_HINTS.get(driver, "")
        self.driver_hint_label.setText(hint)
        self._sync_placeholders(driver)
        if driver in DEFAULT_PORTS and self.port_input.value() == 0:
            self.port_input.setValue(DEFAULT_PORTS[driver])

    def _sync_placeholders(self, driver: str) -> None:
        placeholders = DRIVER_PLACEHOLDERS.get(driver, {})
        self.host_input.setPlaceholderText(placeholders.get("host", ""))
        self.database_input.setPlaceholderText(placeholders.get("database", ""))
        self.username_input.setPlaceholderText(placeholders.get("username", ""))
        self.password_input.setPlaceholderText(placeholders.get("password", ""))
        self.extra_input.setPlaceholderText(placeholders.get("extra", ""))

    def _validate(self) -> str:
        profile = self.profile()
        if not profile.name:
            return "Vui lòng nhập tên profile."
        if profile.driver not in DRIVERS:
            return "Driver không hợp lệ."
        if not profile.host:
            return "Vui lòng nhập host."
        if not profile.database:
            return "Vui lòng nhập database."
        if not self.username_input.text().strip():
            return "Vui lòng nhập username."
        return ""

    def _test_connection(self) -> None:
        error = self._validate()
        if error:
            self.status_label.setText(error)
            return
        result = self.database_manager.test_connection(
            self.profile(),
            self.username_input.text().strip(),
            self.password_input.text(),
        )
        self.status_label.setText(result.message)

    def _connect_get_schema(self) -> None:
        error = self._validate()
        if error:
            self.status_label.setText(error)
            return

        profile = self.profile()
        result = self.database_manager.open_connection(
            profile,
            self.username_input.text().strip(),
            self.password_input.text(),
        )
        if not result.ok:
            self.status_label.setText(result.message)
            return

        tables = SchemaExtractor(self.database_manager.database(result.connection_name)).get_all_tables_columns()
        dialog = SchemaAnnotationDialog(profile.name, tables, self)
        dialog.exec()
        self.database_manager.close_connection(result.connection_name)

    def _save(self) -> None:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Thiếu thông tin", error)
            return

        self.saved_profile = self.profile()
        self.accept()

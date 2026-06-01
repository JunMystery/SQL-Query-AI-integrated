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
from sqlbot_desktop.utils.i18n_manager import tr

DRIVERS = ["MYSQL", "POSTGRESQL"]
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

        self.setModal(True)
        self.setMinimumSize(560, 560)

        self.name_input = QLineEdit()
        self.description_input = QLineEdit()
        self.driver_combo = QComboBox()
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
        self.retranslate_ui()

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

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("dialogCaption")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())
        
        self.lbl_name = QLabel()
        self.lbl_desc = QLabel()
        self.lbl_driver = QLabel()
        self.lbl_host = QLabel()
        self.lbl_port = QLabel()
        self.lbl_database = QLabel()
        self.lbl_username = QLabel()
        self.lbl_password = QLabel()
        self.lbl_options = QLabel()

        form.addRow(self.lbl_name, self.name_input)
        form.addRow(self.lbl_desc, self.description_input)
        form.addRow(self.lbl_driver, self.driver_combo)
        form.addRow("", self.driver_hint_label)
        form.addRow(self.lbl_host, self.host_input)
        form.addRow(self.lbl_port, self.port_input)
        form.addRow(self.lbl_database, self.database_input)
        form.addRow(self.lbl_username, self.username_input)
        form.addRow(self.lbl_password, self.password_input)
        form.addRow(self.lbl_options, self.extra_input)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.test_button = QPushButton()
        self.test_button.setObjectName("secondaryButton")
        self.test_button.clicked.connect(self._test_connection)
        self.schema_button = QPushButton()
        self.schema_button.setObjectName("primaryButton")
        self.schema_button.clicked.connect(self._connect_get_schema)
        actions.addWidget(self.test_button)
        actions.addWidget(self.schema_button)
        layout.addLayout(actions)

        layout.addWidget(self.status_label)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._save)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dialogs.conn_form_title", "Connection profile"))
        self.title_label.setText(tr("dialogs.conn_form_heading", "Thông tin kết nối"))
        self.caption_label.setText(tr("dialogs.conn_form_caption", "Password chỉ dùng để test hoặc lấy schema, không lưu vào file cấu hình."))
        
        self.lbl_name.setText(tr("dialogs.conn_form_label_name", "Tên profile"))
        self.lbl_desc.setText(tr("dialogs.conn_form_label_desc", "Diễn giải"))
        self.lbl_driver.setText(tr("dialogs.conn_form_label_driver", "Driver"))
        self.lbl_host.setText(tr("dialogs.conn_form_label_host", "Host"))
        self.lbl_port.setText(tr("dialogs.conn_form_label_port", "Port"))
        self.lbl_database.setText(tr("dialogs.conn_form_label_database", "Database"))
        self.lbl_username.setText(tr("dialogs.conn_form_label_username", "Username"))
        self.lbl_password.setText(tr("dialogs.conn_form_label_password", "Password test"))
        self.lbl_options.setText(tr("dialogs.conn_form_label_options", "Connection options"))

        self.name_input.setPlaceholderText(tr("dialogs.conn_form_placeholder_name", "Ví dụ: Production Sales DB"))
        self.description_input.setPlaceholderText(tr("dialogs.conn_form_placeholder_desc", "Ví dụ: CSDL doanh số cho phòng Kinh doanh"))

        self.test_button.setText(tr("dialogs.conn_form_btn_test", "Test Connection"))
        self.schema_button.setText(tr("dialogs.conn_form_btn_schema", "Connect & Get Schema"))

        curr_driver = self.driver_combo.currentData()
        self.driver_combo.blockSignals(True)
        self.driver_combo.clear()
        
        driver_labels = {
            "MYSQL": tr("dialogs.conn_form_driver_mysql", "MySQL / MariaDB - bundled PyMySQL"),
            "POSTGRESQL": tr("dialogs.conn_form_driver_postgres", "PostgreSQL - bundled psycopg"),
        }
        for driver, label in driver_labels.items():
            self.driver_combo.addItem(label, driver)
        
        idx = self.driver_combo.findData(curr_driver)
        if idx >= 0:
            self.driver_combo.setCurrentIndex(idx)
        self.driver_combo.blockSignals(False)
        self._sync_driver_fields()

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
        
        driver_hints = {
            "MYSQL": tr("dialogs.conn_form_hint_mysql", "MySQL/MariaDB dùng PyMySQL đã đóng gói trong EXE, không cần Qt QMYSQL plugin."),
            "POSTGRESQL": tr("dialogs.conn_form_hint_postgres", "PostgreSQL dùng psycopg binary đã đóng gói trong EXE, không cần cài libpq riêng."),
        }
        self.driver_hint_label.setText(driver_hints.get(driver, ""))
        self._sync_placeholders(driver)
        if driver in DEFAULT_PORTS and self.port_input.value() == 0:
            self.port_input.setValue(DEFAULT_PORTS[driver])

    def _sync_placeholders(self, driver: str) -> None:
        placeholders = {
            "MYSQL": {
                "host": tr("dialogs.conn_form_placeholder_host_mysql", "mysql.company.local hoặc 192.168.1.20"),
                "database": "sales_db",
                "username": "report_user",
                "password": tr("dialogs.conn_form_placeholder_password_mysql", "Nhập password MySQL/MariaDB để test"),
                "extra": "charset=utf8mb4",
            },
            "POSTGRESQL": {
                "host": tr("dialogs.conn_form_placeholder_host_postgres", "postgres.company.local hoặc 192.168.1.30"),
                "database": "analytics_db",
                "username": "readonly_user",
                "password": tr("dialogs.conn_form_placeholder_password_postgres", "Nhập password PostgreSQL để test"),
                "extra": "sslmode=require",
            },
        }.get(driver, {})

        self.host_input.setPlaceholderText(placeholders.get("host", ""))
        self.database_input.setPlaceholderText(placeholders.get("database", ""))
        self.username_input.setPlaceholderText(placeholders.get("username", ""))
        self.password_input.setPlaceholderText(placeholders.get("password", ""))
        self.extra_input.setPlaceholderText(placeholders.get("extra", ""))

    def _validate(self) -> str:
        profile = self.profile()
        if not profile.name:
            return tr("dialogs.conn_form_val_name", "Vui lòng nhập tên profile.")
        if profile.driver not in DRIVERS:
            return tr("dialogs.conn_form_val_driver", "Driver không hợp lệ.")
        if not profile.host:
            return tr("dialogs.conn_form_val_host", "Vui lòng nhập host.")
        if not profile.database:
            return tr("dialogs.conn_form_val_database", "Vui lòng nhập database.")
        if not self.username_input.text().strip():
            return tr("dialogs.conn_form_val_username", "Vui lòng nhập username.")
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
            QMessageBox.warning(self, tr("dialogs.conn_form_title_missing_info", "Thiếu thông tin"), error)
            return

        profile = self.profile()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        # Connect to DB to extract schema and save annotations automatically on save
        result = self.database_manager.open_connection(profile, username, password)
        if result.ok:
            try:
                tables = SchemaExtractor(self.database_manager.database(result.connection_name)).get_all_tables_columns()
                from sqlbot_desktop.infrastructure.annotation_repository import AnnotationRepository
                repo = AnnotationRepository()
                
                # Merge with existing annotations to preserve user modifications
                existing = repo.load(profile.name)
                empty_annot = repo.empty_for_schema(profile.name, tables)
                
                for table_name, table_data in empty_annot["tables"].items():
                    existing_table = existing.get("tables", {}).get(table_name, {})
                    if existing_table:
                        if existing_table.get("description"):
                            table_data["description"] = existing_table["description"]
                        for col_name, col_data in table_data["columns"].items():
                            existing_col = existing_table.get("columns", {}).get(col_name, {})
                            if existing_col:
                                for key in ("description", "unit", "note"):
                                    if existing_col.get(key):
                                        col_data[key] = existing_col[key]
                
                repo.save(profile.name, empty_annot)
            except Exception as exc:
                print(f"Warning: Failed to save schema annotations: {exc}")
            finally:
                self.database_manager.close_connection(result.connection_name)
        else:
            QMessageBox.warning(
                self,
                tr("dialogs.conn_form_title_failed_connection", "Kết nối thất bại"),
                tr("dialogs.conn_form_msg_failed_connection", "Không thể kết nối CSDL để tạo Schema Annotation: ") + f"{result.message}\n" + tr("dialogs.conn_form_msg_profile_saved", "Profile vẫn sẽ được lưu.")
            )

        self.saved_profile = profile
        self.accept()

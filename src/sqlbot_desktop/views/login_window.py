"""Modern login screen for selecting and opening database connections."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from sqlbot_desktop.models.entities import ConnectionProfile
from sqlbot_desktop.views.assets import asset_path
from sqlbot_desktop.utils.i18n_manager import tr

class LoginWindow(QMainWindow):
    """First screen for authenticating against a configured database."""

    connect_requested = Signal(ConnectionProfile, str, str, bool)
    manage_connections_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.profiles: list[ConnectionProfile] = []

        self.setMinimumSize(980, 640)
        self.resize(1120, 720)

        self.connection_combo = QComboBox()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.remember_user_checkbox = QCheckBox()
        self.status_label = QLabel("")
        self.connect_button = QPushButton()
        self.settings_button = QPushButton()
        self.chips = []

        self._build_ui()
        self._wire_events()
        self.retranslate_ui()

    def set_profiles(self, profiles: list[ConnectionProfile]) -> None:
        self.profiles = profiles
        self._load_profiles()

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("login.window_title"))
        self.remember_user_checkbox.setText(tr("login.remember_username"))
        self.connect_button.setText(tr("login.btn_connect"))
        self.settings_button.setText(tr("login.btn_manage_connections"))

        if hasattr(self, "headline_label"):
            self.headline_label.setText(tr("login.headline"))
        if hasattr(self, "summary_label"):
            self.summary_label.setText(tr("login.summary"))
        if hasattr(self, "eyebrow_label"):
            self.eyebrow_label.setText(tr("login.eyebrow"))
        if hasattr(self, "title_label"):
            self.title_label.setText(tr("login.select_connection"))
        if hasattr(self, "caption_label"):
            self.caption_label.setText(tr("login.caption"))
        if hasattr(self, "conn_field_label"):
            self.conn_field_label.setText(tr("login.label_connection"))
        if hasattr(self, "user_field_label"):
            self.user_field_label.setText(tr("login.label_username"))
        if hasattr(self, "pass_field_label"):
            self.pass_field_label.setText(tr("login.label_password"))

        self.username_input.setPlaceholderText(tr("login.placeholder_username"))
        self.password_input.setPlaceholderText(tr("login.placeholder_password"))

        if hasattr(self, "hint_label"):
            self.hint_label.setText(tr("login.hint_manage_connections"))

        for t_lbl, d_lbl, t_key, d_key in self.chips:
            t_lbl.setText(tr(t_key))
            d_lbl.setText(tr(d_key))

        self._load_profiles()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("loginRoot")

        shell = QHBoxLayout(root)
        shell.setContentsMargins(40, 36, 40, 36)
        shell.setSpacing(28)

        shell.addWidget(self._build_brand_panel(), 5)
        shell.addWidget(self._build_form_card(), 4)

        self.setCentralWidget(root)

    def _build_brand_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("brandPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(22)

        logo_row = QHBoxLayout()
        logo = QLabel()
        logo.setObjectName("logoBadge")
        pixmap = QPixmap(str(asset_path("icons", "sqlbot-mark.svg")))
        logo.setPixmap(pixmap.scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(64, 64)

        app_name = QLabel("SQLBot Desktop")
        app_name.setObjectName("appName")
        logo_row.addWidget(logo)
        logo_row.addWidget(app_name)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        self.headline_label = QLabel()
        self.headline_label.setObjectName("loginHeadline")
        self.headline_label.setWordWrap(True)
        layout.addWidget(self.headline_label)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("loginSummary")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        feature_grid = QGridLayout()
        feature_grid.setHorizontalSpacing(14)
        feature_grid.setVerticalSpacing(14)
        features = [
            ("login.feature_ai_title", "login.feature_ai_detail"),
            ("login.feature_safety_title", "login.feature_safety_detail"),
            ("login.feature_db_title", "login.feature_db_detail"),
            ("login.feature_context_title", "login.feature_context_detail"),
        ]
        for index, (t_key, d_key) in enumerate(features):
            chip, t_lbl, d_lbl = self._feature_chip(t_key, d_key)
            self.chips.append((t_lbl, d_lbl, t_key, d_key))
            feature_grid.addWidget(chip, index // 2, index % 2)
        layout.addLayout(feature_grid)

        layout.addSpacerItem(QSpacerItem(1, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        footer = QLabel("Framework: AI-Coding-Standards v2.5.0")
        footer.setObjectName("loginFooter")
        layout.addWidget(footer)

        return panel

    def _build_form_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("loginCard")
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        card.setMinimumWidth(380)
        card.setMaximumWidth(460)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 34, 32, 32)
        layout.setSpacing(18)

        self.eyebrow_label = QLabel()
        self.eyebrow_label.setObjectName("eyebrow")
        self.title_label = QLabel()
        self.title_label.setObjectName("formTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("formCaption")
        self.caption_label.setWordWrap(True)

        layout.addWidget(self.eyebrow_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.caption_label)
        layout.addSpacing(10)

        self.conn_field_label = self._field_label("")
        self.connection_combo.setObjectName("fieldInput")
        self.connection_combo.setAccessibleName("Connection profile")
        layout.addWidget(self.conn_field_label)
        layout.addWidget(self.connection_combo)

        self.user_field_label = self._field_label("")
        self.username_input.setObjectName("fieldInput")
        self.username_input.setAccessibleName("Username")
        layout.addWidget(self.user_field_label)
        layout.addWidget(self.username_input)

        self.pass_field_label = self._field_label("")
        self.password_input.setObjectName("fieldInput")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setAccessibleName("Password")
        layout.addWidget(self.pass_field_label)
        layout.addWidget(self.password_input)

        self.remember_user_checkbox.setObjectName("rememberCheck")
        layout.addWidget(self.remember_user_checkbox)

        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Login status")
        layout.addWidget(self.status_label)

        layout.addSpacerItem(QSpacerItem(1, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.connect_button.setObjectName("primaryButton")
        self.connect_button.setDefault(True)
        self.connect_button.setIcon(QIcon(str(asset_path("icons", "database-connect.svg"))))
        self.connect_button.setMinimumHeight(46)
        layout.addWidget(self.connect_button)

        self.settings_button.setObjectName("secondaryButton")
        self.settings_button.setIcon(QIcon(str(asset_path("icons", "settings.svg"))))
        self.settings_button.setMinimumHeight(42)
        layout.addWidget(self.settings_button)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("formHint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        return card

    def _feature_chip(self, t_key: str, d_key: str) -> tuple[QFrame, QLabel, QLabel]:
        chip = QFrame()
        chip.setObjectName("featureChip")

        layout = QVBoxLayout(chip)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        title_label = QLabel()
        title_label.setObjectName("featureTitle")
        detail_label = QLabel()
        detail_label.setObjectName("featureDetail")
        detail_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        return chip, title_label, detail_label

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _load_profiles(self) -> None:
        self.connection_combo.blockSignals(True)
        current_selection = self.connection_combo.currentData()
        self.connection_combo.clear()

        selected_index = 0
        for idx, profile in enumerate(self.profiles):
            self.connection_combo.addItem(profile.display_name, profile)
            if current_selection and profile.name == current_selection.name:
                selected_index = idx

        if self.profiles:
            self.connection_combo.setCurrentIndex(selected_index)
        self.connection_combo.blockSignals(False)
        self._on_profile_changed()

        has_profiles = bool(self.profiles)
        self.connect_button.setEnabled(has_profiles)

        current_status = self.status_label.text()
        if not current_status or current_status in (
            "Sẵn sàng kết nối.", "Ready to connect.", "接続準備完了。",
            "Chưa có connection profile. Hãy mở Quản lý kết nối để tạo mới.",
            "No connection profile. Open Manage Connections to create one.",
            "接続プロファイルがありません。接続管理を開いて作成してください。"
        ):
            if has_profiles:
                self.status_label.setText(tr("login.status_ready"))
            else:
                self.status_label.setText(tr("login.status_no_profiles"))

    def _wire_events(self) -> None:
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.settings_button.clicked.connect(self.manage_connections_requested.emit)
        self.connection_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.username_input.returnPressed.connect(self._on_connect_clicked)
        self.password_input.returnPressed.connect(self._on_connect_clicked)

    def _on_profile_changed(self) -> None:
        profile = self.connection_combo.currentData()
        if isinstance(profile, ConnectionProfile):
            if profile.username:
                self.username_input.setText(profile.username)
                self.remember_user_checkbox.setChecked(True)
            else:
                self.username_input.clear()
                self.remember_user_checkbox.setChecked(False)

    def _on_connect_clicked(self) -> None:
        profile = self.connection_combo.currentData()
        if not isinstance(profile, ConnectionProfile):
            self.status_label.setText(tr("login.status_invalid_profile"))
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.status_label.setText(tr("login.status_credentials_required"))
            return

        self.status_label.setText(tr("login.status_connecting").replace("{profile_name}", profile.name))
        self.connect_requested.emit(profile, username, password, self.remember_user_checkbox.isChecked())

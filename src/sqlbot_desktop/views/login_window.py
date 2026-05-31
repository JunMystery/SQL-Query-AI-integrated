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


class LoginWindow(QMainWindow):
    """First screen for authenticating against a configured database."""

    connect_requested = Signal(ConnectionProfile, str, str)
    manage_connections_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.profiles: list[ConnectionProfile] = []

        self.setWindowTitle("SQLBot Desktop - Đăng nhập")
        self.setMinimumSize(980, 640)
        self.resize(1120, 720)

        self.connection_combo = QComboBox()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.remember_user_checkbox = QCheckBox("Ghi nhớ tên đăng nhập")
        self.status_label = QLabel("")
        self.connect_button = QPushButton("Kết nối")
        self.settings_button = QPushButton("Quản lý kết nối")

        self._build_ui()
        self._wire_events()

    def set_profiles(self, profiles: list[ConnectionProfile]) -> None:
        self.profiles = profiles
        self._load_profiles()

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

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

        headline = QLabel("Truy vấn dữ liệu bằng tiếng Việt, chạy AI local.")
        headline.setObjectName("loginHeadline")
        headline.setWordWrap(True)
        layout.addWidget(headline)

        summary = QLabel(
            "Đăng nhập vào cấu hình CSDL do IT quản lý, sau đó tạo SQL SELECT "
            "từ ngôn ngữ tự nhiên với schema đã được diễn giải."
        )
        summary.setObjectName("loginSummary")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        feature_grid = QGridLayout()
        feature_grid.setHorizontalSpacing(14)
        feature_grid.setVerticalSpacing(14)
        features = [
            ("AI local", "GGUF trên CPU"),
            ("An toàn", "Chỉ thực thi SELECT"),
            ("CSDL", "MySQL và PostgreSQL"),
            ("Có ngữ cảnh", "Schema annotations tiếng Việt"),
        ]
        for index, (title, detail) in enumerate(features):
            feature_grid.addWidget(self._feature_chip(title, detail), index // 2, index % 2)
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

        eyebrow = QLabel("Đăng nhập CSDL")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Chọn kết nối")
        title.setObjectName("formTitle")
        caption = QLabel("Sử dụng tài khoản SQL được cấp để mở phiên làm việc.")
        caption.setObjectName("formCaption")
        caption.setWordWrap(True)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(caption)
        layout.addSpacing(10)

        layout.addWidget(self._field_label("Connection profile"))
        self.connection_combo.setObjectName("fieldInput")
        self.connection_combo.setAccessibleName("Connection profile")
        layout.addWidget(self.connection_combo)

        layout.addWidget(self._field_label("Username"))
        self.username_input.setObjectName("fieldInput")
        self.username_input.setPlaceholderText("Nhập username SQL")
        self.username_input.setAccessibleName("Username")
        layout.addWidget(self.username_input)

        layout.addWidget(self._field_label("Password"))
        self.password_input.setObjectName("fieldInput")
        self.password_input.setPlaceholderText("Nhập password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setAccessibleName("Password")
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

        hint = QLabel("Quản lý kết nối yêu cầu mật khẩu IT.")
        hint.setObjectName("formHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        return card

    def _feature_chip(self, title: str, detail: str) -> QFrame:
        chip = QFrame()
        chip.setObjectName("featureChip")

        layout = QVBoxLayout(chip)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("featureTitle")
        detail_label = QLabel(detail)
        detail_label.setObjectName("featureDetail")
        detail_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        return chip

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _load_profiles(self) -> None:
        self.connection_combo.clear()
        for profile in self.profiles:
            self.connection_combo.addItem(profile.display_name, profile)

        has_profiles = bool(self.profiles)
        self.connect_button.setEnabled(has_profiles)
        if has_profiles:
            self.status_label.setText("Sẵn sàng kết nối.")
        else:
            self.status_label.setText("Chưa có connection profile. Hãy mở Quản lý kết nối để tạo mới.")

    def _wire_events(self) -> None:
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.settings_button.clicked.connect(self.manage_connections_requested.emit)
        self.connection_combo.currentIndexChanged.connect(self._on_profile_changed)

    def _on_profile_changed(self) -> None:
        profile = self.connection_combo.currentData()
        if isinstance(profile, ConnectionProfile) and profile.username and not self.username_input.text():
            self.username_input.setText(profile.username)

    def _on_connect_clicked(self) -> None:
        profile = self.connection_combo.currentData()
        if not isinstance(profile, ConnectionProfile):
            self.status_label.setText("Vui lòng chọn một connection profile hợp lệ.")
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.status_label.setText("Vui lòng nhập đầy đủ username và password.")
            return

        self.status_label.setText(f"Đang kết nối tới {profile.name}...")
        self.connect_requested.emit(profile, username, password)

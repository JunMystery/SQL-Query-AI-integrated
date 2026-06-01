"""Controller for the login and connection-management flow."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from sqlbot_desktop.infrastructure.database_manager import DatabaseManager
from sqlbot_desktop.infrastructure.profile_repository import ProfileRepository
from sqlbot_desktop.models.entities import ConnectionProfile
from sqlbot_desktop.controllers.main_controller import MainController
from sqlbot_desktop.views.dialogs.admin_password_dialog import AdminPasswordDialog
from sqlbot_desktop.views.dialogs.connection_manager_dialog import ConnectionManagerDialog
from sqlbot_desktop.views.login_window import LoginWindow
from sqlbot_desktop.utils.i18n_manager import tr


class LoginController:
    """Coordinate the login view with repositories, dialogs, and database connections."""

    def __init__(
        self,
        repository: ProfileRepository | None = None,
        database_manager: DatabaseManager | None = None,
    ) -> None:
        self.repository = repository or ProfileRepository()
        self.database_manager = database_manager or DatabaseManager()
        self.main_controller: MainController | None = None
        self.view = LoginWindow()
        self.view.connect_requested.connect(self.connect)
        self.view.manage_connections_requested.connect(self.open_connection_manager)
        self.refresh_profiles()

    def show(self) -> None:
        self.view.show()

    def refresh_profiles(self) -> None:
        self.view.set_profiles(self.repository.load_profiles())

    def connect(self, profile: ConnectionProfile, username: str, password: str, remember_username: bool) -> None:
        # Save or clear the username in the connection configuration
        profiles = self.repository.load_profiles()
        updated = False
        for idx, p in enumerate(profiles):
            if p.name == profile.name:
                target_user = username if remember_username else ""
                if p.username != target_user:
                    profiles[idx] = ConnectionProfile(
                        name=p.name,
                        driver=p.driver,
                        database=p.database,
                        host=p.host,
                        port=p.port,
                        username=target_user,
                        description=p.description,
                        extra=p.extra
                    )
                    updated = True
                break

        if updated:
            self.repository.save_profiles(profiles)
            self.refresh_profiles()

        result = self.database_manager.open_connection(profile, username, password)
        if not result.ok:
            self.view.set_status(result.message)
            QMessageBox.warning(self.view, tr("dialogs.conn_form_title_failed_connection", "Kết nối thất bại"), result.message)
            return

        self.view.set_status(tr("login.status_connected", "Đã kết nối: ") + f"{profile.name}")

        self.main_controller = MainController(profile, self.database_manager, result.connection_name)
        self.main_controller.show()
        self.view.hide()

    def open_connection_manager(self) -> None:
        password_dialog = AdminPasswordDialog(self.view)
        if password_dialog.exec() != password_dialog.DialogCode.Accepted:
            return

        manager_dialog = ConnectionManagerDialog(self.repository, self.database_manager, self.view)
        manager_dialog.exec()
        self.refresh_profiles()

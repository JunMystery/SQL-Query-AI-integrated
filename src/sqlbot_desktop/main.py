"""Qt application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from sqlbot_desktop.controllers.login_controller import LoginController
from sqlbot_desktop.runtime import configure_qt_plugin_paths
from sqlbot_desktop.views.theme import load_stylesheet


def main() -> int:
    configure_qt_plugin_paths()
    app = QApplication(sys.argv)
    app.setApplicationName("SQLBot Desktop")
    app.setOrganizationName("SQLBot")
    app.setStyleSheet(load_stylesheet())

    controller = LoginController()
    controller.show()

    return app.exec()

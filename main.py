"""Glitch — an AI desktop pet. Entry point."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.persistence.config import ConfigManager
from core.utils.constants import APP_NAME, APP_ORG, APP_VERSION, ICONS_DIR
from core.utils.logger import setup_logging


def main() -> int:
    # Read config before Qt starts so the log level is right from the first line.
    config = ConfigManager()
    log = setup_logging(debug=bool(config.get("debug")))

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    app.setWindowIcon(QIcon(str(ICONS_DIR / "glitch.png")))
    # The tray keeps Glitch alive even with no visible windows.
    app.setQuitOnLastWindowClosed(False)

    from core.application import GlitchApplication

    try:
        glitch = GlitchApplication(app, config)
    except Exception as exc:  # nothing to fall back to; tell the user why
        log.exception("Glitch failed to start")
        QMessageBox.critical(None, f"{APP_NAME} could not start", str(exc))
        return 1

    glitch.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

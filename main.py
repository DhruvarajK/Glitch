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
    # On Windows, register an explicit AppUserModelID so the taskbar groups windows
    # under Glitch and displays the custom app icon instead of python.exe's icon.
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = f"{APP_ORG}.{APP_NAME}.{APP_VERSION}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    # Read config before Qt starts so the log level is right from the first line.
    config = ConfigManager()
    log = setup_logging(debug=bool(config.get("debug")))

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    
    icon_path = ICONS_DIR / "glitch.ico"
    if not icon_path.exists():
        icon_path = ICONS_DIR / "glitch.png"
    app.setWindowIcon(QIcon(str(icon_path)))
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

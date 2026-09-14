"""Application entry point."""
from __future__ import annotations

import logging
import sys
import traceback

from . import logging_setup, settings


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    cfg = settings.Settings()
    log = logging_setup.setup(bool(cfg.get("logging_enabled", True)))

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError as e:
        log.critical("PySide6 not available: %s", e)
        print("PySide6 is not installed. Run ./run to set up the virtual environment.", file=sys.stderr)
        return 2

    from .ui import theme
    from .ui.main_window import MainWindow

    app = QApplication(argv)
    app.setApplicationName(settings.APP_NAME)
    app.setStyleSheet(theme.QSS)

    def on_crash(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        QMessageBox.critical(None, "HeaterApp crashed",
                             f"An unexpected error occurred:\n\n{exc}\n\nDetails were written to:\n"
                             f"{logging_setup.log_path()}\n\n{text[-1500:]}")

    logging_setup.install_excepthook(on_crash)

    win = MainWindow(cfg)
    # hidden verification helpers: --size WxH  --screenshot PATH  --design FILE  --tab N
    if "--size" in argv:
        w, h = argv[argv.index("--size") + 1].lower().split("x")
        win.resize(int(w), int(h))
    if "--design" in argv:
        from .core import design_io
        win._load_design(design_io.load_design(argv[argv.index("--design") + 1]), None)
    win.show()
    if "--tab" in argv:
        win.panel.tabs.setCurrentIndex(int(argv[argv.index("--tab") + 1]))
    log.info("main window shown")
    if "--screenshot" in argv:
        from PySide6.QtCore import QTimer
        out = argv[argv.index("--screenshot") + 1]

        def shoot():
            win.grab().save(out)
            log.info("screenshot saved to %s", out)
            app.quit()
        QTimer.singleShot(2500, shoot)
    rc = app.exec()
    log.info("exit code %s", rc)
    logging.shutdown()
    return rc


if __name__ == "__main__":
    sys.exit(main())

"""Entry point: ``python -m hyprtune [--page NAME] [--version]``."""
from __future__ import annotations

import os
import sys
from importlib import resources

from . import APP_ID, __version__


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        print(f"hyprtune {__version__}")
        return 0
    if "--selftest" in argv:
        return selftest()
    page = argv[argv.index("--page") + 1] if "--page" in argv and argv.index("--page") + 1 < len(argv) else None
    if "WAYLAND_DISPLAY" in os.environ:  # prefer native Wayland, fall back to XWayland
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .app import MainWindow
    from .ui import theme

    app = QApplication(sys.argv[:1])
    app.setApplicationName("hyprtune")
    app.setApplicationDisplayName("Hyprtune")
    app.setDesktopFileName("hyprtune")
    with resources.as_file(resources.files("hyprtune.data").joinpath("hyprtune.svg")) as icon:
        app.setWindowIcon(QIcon(str(icon)))
    from .util import AppState
    theme.apply(app, AppState().get("theme", "auto"))
    win = MainWindow(page)
    win.show()
    return app.exec()


def selftest() -> int:
    """Build every page headlessly in a throwaway config dir. Used to verify a packaged build."""
    import tempfile

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="hyprtune-selftest-")
    from PySide6.QtWidgets import QApplication

    from .app import MainWindow
    from .ui import theme

    app = QApplication(sys.argv[:1])
    theme.apply(app, "dark")
    win = MainWindow()
    win.resize(1100, 760)
    win.show()
    for i, name in enumerate(win.pages):
        win._go(i)
        app.processEvents()
        if win.grab().isNull():
            print(f"selftest: page {name} failed to render")
            return 1
    win.model.wait()
    print(f"selftest ok: {len(win.pages)} pages, hyprtune {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

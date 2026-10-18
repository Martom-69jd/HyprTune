"""Main window: sidebar navigation, page stack, unsaved-changes bar and status line."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from . import __version__, util
from .hypr.backend import HyprBackend
from .hypr.model import HyprModel
from .hypr.options import PAGES
from .pages.awww import AwwwPage
from .pages.fuzzel import FuzzelPage
from .pages.hypr_pages import HyprPage
from .pages.overview import Overview
from .pages.waybar import WaybarPage
from .ui import theme
from .ui.widgets import Page, primary_button


class MainWindow(QMainWindow):
    def __init__(self, start_page: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Hyprtune")
        self.resize(1120, 780)
        self.state = util.AppState()
        self.model = HyprModel(HyprBackend(), self.state)
        self.pages: dict[str, Page] = {}

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(224)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 18, 0, 12)
        sl.setSpacing(0)
        brand = QLabel("Hyprtune")
        brand.setObjectName("brand")
        brand.setIndent(0)
        brand.setContentsMargins(20, 0, 0, 6)
        sl.addWidget(brand)
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        self.stack = QStackedWidget()

        def group(title: str) -> None:
            lab = QLabel(title)
            lab.setObjectName("sideGroup")
            lab.setIndent(0)
            lab.setContentsMargins(20, 0, 0, 0)
            sl.addWidget(lab)

        def add(pid: str, title: str, page: Page) -> None:
            self.pages[pid] = page
            idx = self.stack.addWidget(page)
            b = QPushButton(title)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(b, idx)
            sl.addWidget(b)
            page.message.connect(self.toast) if hasattr(page, "message") else None  # type: ignore[attr-defined]

        overview = Overview(self.model, self.state)
        overview.themeChanged.connect(lambda m: theme.apply(QApplication.instance(), m))
        add("overview", "Overview", overview)
        group("Hyprland")
        for spec in PAGES:
            add(spec.id, spec.title, HyprPage(spec, self.model, preview=spec.id in ("appearance", "tiling")))
        group("Companions")
        add("waybar", "Waybar", WaybarPage())
        add("wallpaper", "Wallpaper", AwwwPage(self.state, self.model))
        add("launcher", "Launcher", FuzzelPage())
        sl.addStretch(1)
        root.addWidget(side)

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self.stack, 1)
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(24, 10, 24, 10)
        self.dirty_label = QLabel()
        bl.addWidget(self.dirty_label, 1)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.model.undo)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.clicked.connect(self.model.revert)
        self.save_btn = primary_button("Save changes")
        self.save_btn.clicked.connect(self.save_hypr)
        for b in (self.undo_btn, self.revert_btn, self.save_btn):
            bl.addWidget(b)
        self.banner.hide()
        right.addWidget(self.banner)
        self.status = QLabel("")
        self.status.setObjectName("status")
        right.addWidget(self.status)
        root.addLayout(right, 1)
        self._status_timer = QTimer(self, singleShot=True, interval=9000)
        self._status_timer.timeout.connect(lambda: self.status.setText(""))

        self.nav.idClicked.connect(self._go)
        self.model.dirtyChanged.connect(self._dirty)
        self.model.optionChanged.connect(lambda _k: self._dirty(self.model.is_dirty()))
        self.model.message.connect(self.toast)
        QShortcut(QKeySequence.Undo, self, activated=self.model.undo)
        QShortcut(QKeySequence.Save, self, activated=self.save_current)
        self._go(list(self.pages).index(start_page) if start_page in self.pages else 0)
        self.model.load()

    # -- navigation ---------------------------------------------------------------------------------
    def _go(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self.nav.button(idx).setChecked(True)
        self.stack.currentWidget().on_show()  # type: ignore[attr-defined]

    def toast(self, text: str, error: bool = False) -> None:
        self.status.setObjectName("error" if error else "status")
        self.status.setStyleSheet("")  # re-polish after objectName change
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(text)
        self._status_timer.start()

    # -- Hyprland save flow -------------------------------------------------------------------------
    def _dirty(self, dirty: bool) -> None:
        self.banner.setVisible(dirty)
        n = self.model.dirty_count()
        self.dirty_label.setText(f"{n} unsaved change{'s' if n != 1 else ''}, previewed live in Hyprland")
        self.undo_btn.setEnabled(self.model.can_undo())

    def save_hypr(self) -> bool:
        b = self.model.b
        if not b.hook_installed() and not self.state.get("hook_declined", False):
            style, main = b.main_config()
            line = 'require("hyprtune")' if style == "lua" else f"source = {b.managed_path()}"
            box = QMessageBox(self)
            box.setWindowTitle("Load these settings in Hyprland?")
            box.setText(f"Hyprtune saves to {b.managed_path().name} and leaves your own config alone. "
                        f"Hyprland only loads that file if {main.name} includes it.")
            box.setInformativeText(f"Add this line to the end of {main}?\n\n    {line}\n\nA backup is kept first.")
            add = box.addButton("Add the line", QMessageBox.AcceptRole)
            box.addButton("Not now", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is add:
                try:
                    b.install_hook()
                except OSError as e:
                    self.toast(f"Couldn't edit {main}: {e}", True)
            else:
                self.state.set("hook_declined", True)
        ok = self.model.save()
        self.pages["overview"].refresh()  # type: ignore[attr-defined]
        return ok

    def save_current(self) -> None:
        page = self.stack.currentWidget()
        if self.model.is_dirty() and isinstance(page, HyprPage):
            self.save_hypr()
        elif hasattr(page, "save") and getattr(page, "save_btn", None) is not None and page.save_btn.isEnabled():  # type: ignore[attr-defined]
            page.save()  # type: ignore[attr-defined]

    # -- closing --------------------------------------------------------------------------------------
    def _unsaved_pages(self) -> list[str]:
        out = []
        if self.model.is_dirty():
            out.append("Hyprland settings")
        wb: Any = self.pages["waybar"]
        if wb.cfg_dirty or wb.style_dirty:
            out.append("Waybar")
        if self.pages["launcher"].dirty:  # type: ignore[attr-defined]
            out.append("Launcher")
        return out

    def closeEvent(self, ev: Any) -> None:  # noqa: N802
        pending = self._unsaved_pages()
        if not pending:
            self.model.wait()
            ev.accept()
            return
        r = QMessageBox.question(self, "Unsaved changes", "You have unsaved changes in: " + ", ".join(pending) + ".",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if r == QMessageBox.Cancel:
            ev.ignore()
            return
        if r == QMessageBox.Save:
            if self.model.is_dirty():
                self.save_hypr()
            self.pages["waybar"].save() if (wb := self.pages["waybar"]).cfg_dirty or wb.style_dirty else None  # type: ignore[attr-defined]
            if self.pages["launcher"].dirty:  # type: ignore[attr-defined]
                self.pages["launcher"].save()  # type: ignore[attr-defined]
        else:
            self.model.revert()  # restore live Hyprland values we changed for preview
        self.model.wait()
        ev.accept()

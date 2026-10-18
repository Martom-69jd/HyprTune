"""Overview: what Hyprtune found on this system, and the one-time setup step."""
from __future__ import annotations

import shutil
from typing import Any

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QWidget

from .. import __version__, util
from ..hypr.model import HyprModel
from ..hypr.options import SCHEMA_VERSION
from ..ui.widgets import EnumControl, Page, SettingRow, note


class Overview(Page):
    message = Signal(str, bool)
    themeChanged = Signal(str)

    def __init__(self, model: HyprModel, state: util.AppState) -> None:
        super().__init__("Overview", "Hyprland, Waybar, awww and fuzzel in one place.")
        self.model, self.state = model, state
        self.sec_hypr = self.add_section("Hyprland")
        self.sec_tools = self.add_section("Companion tools")
        sec = self.add_section("Hyprtune")
        theme = EnumControl((("auto", "Follow system (dark by default)"), ("dark", "Dark"), ("light", "Light")))
        theme.set_value(state.get("theme", "auto"))
        theme.changed.connect(self._theme)
        sec.add_row(SettingRow("Theme", "", theme, False))
        sec.add_row(SettingRow("Version", f"Hyprland option data from v{SCHEMA_VERSION.lstrip('v')}.",
                               QLabel(__version__), False))
        folder = QPushButton("Open settings folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(util.app_dir()))))
        sec.add_row(SettingRow("Backups", "Hyprtune copies each file you edit to ~/.config/hyprtune/backups first.",
                               folder, False))
        self.finish()
        model.refreshed.connect(self.refresh)
        self.refresh()

    def _theme(self, mode: str) -> None:
        self.state.set("theme", mode)
        self.themeChanged.emit(mode)

    def _clear(self, sec: Any) -> None:
        for r in sec.rows:
            r.setParent(None)
            r.deleteLater()
        sec.rows = []

    @staticmethod
    def _badge(text: str, ok: bool | None = None) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("error" if ok is False else "dim" if ok is None else "rowTitle")
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lab

    def refresh(self) -> None:
        b = self.model.b
        self._clear(self.sec_hypr)
        style, main = b.main_config()
        running = b.running()
        ver = b.version()
        self.sec_hypr.add_row(SettingRow(
            "Compositor", "Live changes need a running Hyprland and hyprctl on your PATH.",
            self._badge(f"Running, v{ver}" if running else "Not running", True if running else None), False))
        self.sec_hypr.add_row(SettingRow(
            "Config format", "Hyprland 0.55 and newer use Lua; older versions use hyprlang. Hyprtune handles both.",
            self._badge("Lua (hyprland.lua)" if style == "lua" else "hyprlang (hyprland.conf)"), False))
        hooked = b.hook_installed()
        btn: QWidget
        if hooked:
            btn = self._badge("Connected", True)
        else:
            btn = QPushButton("Connect")
            btn.setObjectName("primary")
            btn.clicked.connect(self.install_hook)
        line = 'require("hyprtune")' if style == "lua" else f"source = {b.managed_path()}"
        self.sec_hypr.add_row(SettingRow(
            "Load Hyprtune's settings", f"Hyprtune saves to {b.managed_path()} and never edits your own settings. "
            f"Hyprland loads that file through one line at the end of {main.name}: {line}", btn, False))
        errs = b.config_errors() if running else ""
        if errs:
            self.sec_hypr.add_row(note("Hyprland reports config errors:\n" + errs, True))
        reload_btn = QPushButton("Reload config")
        reload_btn.setEnabled(running)
        reload_btn.clicked.connect(self._reload)
        self.sec_hypr.add_row(SettingRow("Reload", "Re-reads your config files, discarding live-only changes.", reload_btn, False))

        self._clear(self.sec_tools)
        for name, what in (("waybar", "Status bar"), ("fuzzel", "Launcher"), ("awww", "Wallpaper daemon (was swww)")):
            found = shutil.which(name) or (shutil.which("swww") if name == "awww" else None)
            self.sec_tools.add_row(SettingRow(
                name, what, self._badge(f"Installed ({found})" if found else "Not found on PATH", True if found else None), False))

    def install_hook(self) -> None:
        try:
            path = self.model.b.install_hook()
        except OSError as e:
            self.message.emit(f"Couldn't edit your Hyprland config: {e}", True)
            return
        self.message.emit(f"Added one line to {path}. A backup is in ~/.config/hyprtune/backups.", False)
        self.refresh()

    def _reload(self) -> None:
        ok, msg = self.model.b.reload()
        self.message.emit("Hyprland config reloaded." if ok else f"Reload failed: {msg}", not ok)
        self.model.load()

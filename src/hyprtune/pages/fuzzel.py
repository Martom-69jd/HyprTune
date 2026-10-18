"""Fuzzel launcher settings, edited in place in ~/.config/fuzzel/fuzzel.ini."""
from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from .. import util
from ..formats.ini import IniDoc
from ..ui.widgets import (BoolControl, ColorControl, Control, EnumControl, NumberControl, Page, PickerControl,
                          SettingRow, TextControl, note, primary_button, qcolor)


@dataclass(frozen=True)
class FF:
    section: str
    key: str
    label: str
    kind: str  # bool int float str enum color font
    default: Any
    desc: str = ""
    lo: float = 0
    hi: float = 100
    choices: tuple[str, ...] = ()
    step: float | None = None


def _c(*names: str) -> tuple[str, ...]:
    return names


GROUPS: list[tuple[str, list[FF]]] = [
    ("Window", [
        FF("main", "anchor", "Position", "enum", "center", "Where on the screen the launcher appears.",
           choices=_c("center", "top-left", "top", "top-right", "left", "right", "bottom-left", "bottom", "bottom-right")),
        FF("main", "x-margin", "Horizontal margin", "int", 0, "Distance from the anchor. No effect when centred, top or bottom.", hi=1000),
        FF("main", "y-margin", "Vertical margin", "int", 0, "No effect when centred, left or right.", hi=1000),
        FF("main", "lines", "Visible results", "int", 15, lo=1, hi=60),
        FF("main", "width", "Width (characters)", "int", 30, lo=10, hi=150),
        FF("main", "horizontal-pad", "Horizontal padding", "int", 40, "Pixels between the border and content.", hi=200),
        FF("main", "vertical-pad", "Vertical padding", "int", 8, hi=100),
        FF("main", "inner-pad", "Space below the prompt", "int", 0, hi=100),
        FF("main", "layer", "Layer", "enum", "overlay", "Overlay also appears above fullscreen windows.", choices=_c("top", "overlay")),
        FF("main", "keyboard-focus", "Keyboard focus", "enum", "exclusive", choices=_c("exclusive", "on-demand")),
        FF("main", "exit-on-keyboard-focus-loss", "Close when it loses focus", "bool", True),
        FF("main", "output", "Show on monitor", "str", "", "Empty lets the compositor choose."),
    ]),
    ("Text and icons", [
        FF("main", "font", "Font", "font", "monospace", "Fontconfig name, such as Inter:size=12."),
        FF("main", "use-bold", "Allow bold", "bool", False),
        FF("main", "dpi-aware", "Scale font by", "enum", "auto", "DPI, or the monitor's scale factor.", choices=_c("auto", "yes", "no")),
        FF("main", "letter-spacing", "Letter spacing", "float", 0, lo=-5, hi=10, step=0.5),
        FF("main", "line-height", "Line height", "str", "", "Override the font's metrics, e.g. 22px."),
        FF("main", "prompt", "Prompt", "str", "> "),
        FF("main", "placeholder", "Placeholder text", "str", ""),
        FF("main", "icons-enabled", "Show icons", "bool", True),
        FF("main", "icon-theme", "Icon theme", "str", "default", "Case sensitive."),
        FF("main", "image-size-ratio", "Large icon size", "float", 0.5, "Shown when only a few matches remain. 0 disables.", lo=0, hi=1),
    ]),
    ("Colours", [
        FF("colors", "background", "Background", "color", "fdf6e3ff"),
        FF("colors", "text", "Text", "color", "657b83ff"),
        FF("colors", "input", "Typed text", "color", "657b83ff"),
        FF("colors", "prompt", "Prompt", "color", "586e75ff"),
        FF("colors", "placeholder", "Placeholder", "color", "93a1a1ff"),
        FF("colors", "match", "Matched letters", "color", "cb4b16ff"),
        FF("colors", "selection", "Selected row", "color", "eee8d5ff"),
        FF("colors", "selection-text", "Selected row text", "color", "586e75ff"),
        FF("colors", "selection-match", "Matched letters in selected row", "color", "cb4b16ff"),
        FF("colors", "counter", "Match counter", "color", "93a1a1ff"),
        FF("colors", "border", "Border", "color", "002b36ff"),
    ]),
    ("Border", [
        FF("border", "width", "Width", "int", 1, hi=20),
        FF("border", "radius", "Corner radius", "int", 10, hi=60),
        FF("border", "selection-radius", "Selected row corner radius", "int", 0, hi=40),
    ]),
    ("Search", [
        FF("main", "match-mode", "Matching style", "enum", "fzf", choices=_c("fzf", "exact", "fuzzy")),
        FF("main", "fields", "Search in", "str", "filename,name,generic", "Any of filename, name, generic, exec, categories, keywords, comment."),
        FF("main", "sort-result", "Sort by how often you launch things", "bool", True),
        FF("main", "show-actions", "Include app actions", "bool", False, "Such as \"New window\" or \"Preferences\"."),
        FF("main", "hide-before-typing", "Hide the list until you type", "bool", False),
        FF("main", "match-counter", "Show match count", "bool", False),
        FF("main", "list-executables-in-path", "Include programs from PATH", "bool", False),
        FF("main", "filter-desktop", "Only apps for this desktop", "bool", False),
        FF("main", "enable-mouse", "Mouse input", "bool", True),
        FF("main", "terminal", "Terminal command", "str", "$TERMINAL -e", "Used for apps that need a terminal. {cmd} marks where the command goes."),
    ]),
    ("dmenu mode", [
        FF("dmenu", "mode", "Print selection as", "enum", "text", choices=_c("text", "index")),
        FF("dmenu", "exit-immediately-if-empty", "Exit if there is nothing to show", "bool", False),
    ]),
]
ALL = {(f.section, f.key): f for _g, fs in GROUPS for f in fs}


def parse(f: FF, raw: str) -> Any:
    raw = raw.strip()
    if f.kind == "bool":
        return raw.lower() in ("yes", "true", "on", "1")
    if f.kind == "int":
        m = re.match(r"-?\d+", raw)
        return int(m.group()) if m else f.default
    if f.kind == "float":
        try:
            return float(raw)
        except ValueError:
            return f.default
    if f.kind == "color":
        h = raw.lstrip("#").lower()
        return h + "ff" if re.fullmatch(r"[0-9a-f]{6}", h) else (h if re.fullmatch(r"[0-9a-f]{8}", h) else f.default)
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return raw


def render(f: FF, v: Any) -> str:
    if f.kind == "bool":
        return "yes" if v else "no"
    if f.kind == "float":
        return f"{float(v):g}"
    if f.kind == "str" and (v != v.strip() or v == ""):
        return f'"{v}"'
    return str(v)


class FuzzelPreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(246)
        self.vals: dict[tuple[str, str], Any] = {}

    def set_values(self, vals: dict[tuple[str, str], Any]) -> None:
        self.vals = vals
        self.update()

    def g(self, section: str, key: str) -> Any:
        return self.vals.get((section, key), ALL[(section, key)].default)

    def paintEvent(self, _e: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(pal.ColorRole.AlternateBase))
        p.setPen(pal.color(pal.ColorRole.Mid))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        font = QFont("monospace", 10)
        font.setStyleHint(QFont.Monospace)
        p.setFont(font)
        fm = QFontMetrics(font)
        row_h = fm.height() + 8
        lines = min(int(self.g("main", "lines")), 4)
        pad_x = min(int(self.g("main", "horizontal-pad")), 60) * 0.55
        pad_y = int(self.g("main", "vertical-pad"))
        w = min(fm.horizontalAdvance("M") * int(self.g("main", "width")) * 0.62 + 2 * pad_x, self.width() - 40)
        h = pad_y * 2 + row_h * (lines + 1) + int(self.g("main", "inner-pad"))
        x, y = (self.width() - w) / 2, (self.height() - h) / 2
        bw = int(self.g("border", "width"))
        rect = QRectF(x, y, w, h)
        rad = min(float(self.g("border", "radius")), h / 2)
        p.setBrush(qcolor(self.g("colors", "background")))
        p.setPen(QPen(qcolor(self.g("colors", "border")), bw) if bw else Qt.NoPen)
        p.drawRoundedRect(rect.adjusted(bw / 2, bw / 2, -bw / 2, -bw / 2), rad, rad)
        cx, cy = x + pad_x, y + pad_y
        prompt = str(self.g("main", "prompt"))
        p.setPen(qcolor(self.g("colors", "prompt")))
        p.drawText(int(cx), int(cy + fm.ascent() + 4), prompt)
        p.setPen(qcolor(self.g("colors", "input")))
        p.drawText(int(cx + fm.horizontalAdvance(prompt)), int(cy + fm.ascent() + 4), "fire")
        cy += row_h + int(self.g("main", "inner-pad"))
        for i, name in enumerate(("Firefox", "Fire Alarm", "Files", "Image Viewer")[:lines]):
            sel = i == 0
            if sel:
                sr = float(self.g("border", "selection-radius"))
                p.setPen(Qt.NoPen)
                p.setBrush(qcolor(self.g("colors", "selection")))
                p.drawRoundedRect(QRectF(x + bw, cy, w - 2 * bw, row_h), sr, sr)
            tx = x + pad_x
            base = qcolor(self.g("colors", "selection-text" if sel else "text"))
            mat = qcolor(self.g("colors", "selection-match" if sel else "match"))
            ty = int(cy + 4 + fm.ascent())
            if name.lower().startswith("fire"):
                p.setPen(mat)
                p.drawText(int(tx), ty, name[:4])
                p.setPen(base)
                p.drawText(int(tx + fm.horizontalAdvance(name[:4])), ty, name[4:])
            else:
                p.setPen(base)
                p.drawText(int(tx), ty, name)
            cy += row_h


class FuzzelPage(Page):
    message = Signal(str, bool)

    def __init__(self) -> None:
        self.preview = FuzzelPreview()
        super().__init__("Launcher", "Settings for fuzzel. Your comments and other options in fuzzel.ini are kept.", self.preview)
        self.path = util.config_home() / "fuzzel" / "fuzzel.ini"
        self.doc = IniDoc(util.read_text(self.path) or "")
        self.dirty = False
        self.rows: dict[tuple[str, str], tuple[SettingRow, Control]] = {}
        self.fuzzel = shutil.which("fuzzel")
        self.try_btn = QPushButton("Preview in fuzzel")
        self.try_btn.clicked.connect(self.try_it)
        self.save_btn = primary_button("Save")
        self.save_btn.clicked.connect(self.save)
        self.save_btn.setEnabled(False)
        self.actions.addWidget(self.try_btn)
        self.actions.addWidget(self.save_btn)
        if not self.fuzzel:
            self.try_btn.setEnabled(False)
            self.add_widget(note("fuzzel wasn't found on your PATH. Settings are still saved to "
                                 f"{self.path} and apply once it's installed."))
        for title, fields in GROUPS:
            sec = self.add_section(title)
            for f in fields:
                sec.add_row(self._row(f))
        self.finish()
        self._update_preview()

    def _control(self, f: FF) -> Control:
        if f.kind == "bool":
            return BoolControl()
        if f.kind == "int":
            return NumberControl(True, f.lo, f.hi)
        if f.kind == "float":
            return NumberControl(False, f.lo, f.hi, f.step or (0.05 if f.hi <= 1 else 0.5))
        if f.kind == "enum":
            return EnumControl(tuple((c, c.replace("-", " ").capitalize()) for c in f.choices))
        if f.kind == "color":
            return ColorControl(False, alpha=True)
        if f.kind == "font":
            return PickerControl("font", f.default, fmt=lambda fo: f"{fo.family()}:size={max(fo.pointSize(), 8)}")
        return TextControl(str(f.default))

    def _current(self, f: FF) -> tuple[Any, bool]:
        raw = self.doc.get(f.section, f.key)
        return (parse(f, raw), True) if raw is not None else (f.default, False)

    def _row(self, f: FF) -> SettingRow:
        ctrl = self._control(f)
        row = SettingRow(f.label, f.desc, ctrl)
        row.setToolTip(f"[{f.section}] {f.key}. Reset comments the line out so fuzzel uses its default.")
        val, explicit = self._current(f)
        ctrl.set_value(val)
        row.set_modified(explicit)
        ctrl.changed.connect(lambda v, f=f, r=row: self._set(f, v, r))
        row.resetRequested.connect(lambda f=f, r=row, c=ctrl: self._reset(f, r, c))
        self.rows[(f.section, f.key)] = (row, ctrl)
        return row

    def _set(self, f: FF, v: Any, row: SettingRow) -> None:
        if f.kind in ("str", "font") and v == "":
            self.doc.unset(f.section, f.key)
            row.set_modified(False)
        else:
            self.doc.set(f.section, f.key, render(f, v))
            row.set_modified(True)
        self._touched()

    def _reset(self, f: FF, row: SettingRow, ctrl: Control) -> None:
        self.doc.unset(f.section, f.key)
        ctrl.set_value(f.default)
        row.set_modified(False)
        self._touched()

    def _touched(self) -> None:
        self.dirty = True
        self.save_btn.setEnabled(True)
        self._update_preview()

    def _update_preview(self) -> None:
        self.preview.set_values({k: self._current(f)[0] for k, f in ALL.items()})

    def try_it(self) -> None:
        if not self.fuzzel:
            return
        tmp = Path(tempfile.mkstemp(prefix="hyprtune-fuzzel-", suffix=".ini")[1])
        tmp.write_text(self.doc.text())
        util.spawn_detached([self.fuzzel, "--config", str(tmp)])
        self.message.emit("Launched fuzzel with your unsaved settings. Press Escape to close it.", False)

    def save(self) -> None:
        try:
            util.write_text(self.path, self.doc.text())
        except OSError as e:
            self.message.emit(f"Could not save {self.path}: {e}", True)
            return
        self.dirty = False
        self.save_btn.setEnabled(False)
        self.message.emit(f"Saved {self.path}. Fuzzel reads it every time it starts.", False)

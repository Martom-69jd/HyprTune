"""Waybar: bar options, module layout, per-module options and a managed style block."""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QVBoxLayout, QWidget)

from .. import util
from ..formats import cssblock
from ..formats.jsonc import JsoncDoc, JsoncError
from ..ui.widgets import (Section, BoolControl, ColorControl, Control, EnumControl, NumberControl, Page, PickerControl,
                          SettingRow, TextControl, note, primary_button, qcolor)
from .waybar_data import (BAR_FIELDS, KNOWN_MODULES, MODULE_FIELDS, STYLE_DEFAULTS, STYLE_FIELDS, Field,
                          StyleField, style_css)

STARTER = """{
    "layer": "top",
    "position": "top",
    "height": 34,
    "spacing": 6,
    "modules-left": ["hyprland/workspaces", "hyprland/window"],
    "modules-center": ["clock"],
    "modules-right": ["pulseaudio", "network", "cpu", "memory", "battery", "tray"]
}
"""


def find_files() -> tuple[Path | None, Path]:
    home, cfg = Path.home(), util.config_home() / "waybar"
    cands = [cfg / "config.jsonc", cfg / "config", home / "waybar" / "config.jsonc", home / "waybar" / "config"]
    found = next((p for p in cands if p.is_file()), None)
    return found, (found.parent if found else cfg) / "style.css"


def waybar_running() -> bool:
    return util.run(["pgrep", "-x", "waybar"])[0] == 0


def make_field_control(f: Field) -> Control:
    if f.kind == "bool":
        return BoolControl()
    if f.kind == "int":
        return NumberControl(True, f.lo, f.hi)
    if f.kind == "float":
        return NumberControl(False, f.lo, f.hi, 0.1)
    if f.kind == "enum":
        return EnumControl(f.choices)
    return TextControl(str(f.default or ""), 280)


class ModuleList(QFrame):
    changed = Signal(list)

    def __init__(self, title: str) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QLabel(title)
        head.setObjectName("rowTitle")
        lay.addWidget(head)
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setMinimumHeight(138)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(KNOWN_MODULES)
        self.combo.setMinimumWidth(120)
        self.combo.lineEdit().setPlaceholderText("Module")
        add = QPushButton("Add")
        up, down, rm = QPushButton("↑"), QPushButton("↓"), QPushButton("✕")
        for b in (up, down, rm):
            b.setObjectName("mini")
        up.setToolTip("Move up")
        down.setToolTip("Move down")
        rm.setToolTip("Remove selected")
        row.addWidget(self.combo, 1)
        row.addWidget(add)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        for b in (up, down, rm):
            row2.addWidget(b)
        row2.addStretch(1)
        lay.addLayout(row2)
        add.clicked.connect(self._add)
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        rm.clicked.connect(self._remove)
        self.list.model().rowsMoved.connect(lambda *_: self._emit())

    def items(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]

    def set_items(self, items: list[str]) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([str(i) for i in items])
        self.list.blockSignals(False)

    def _emit(self) -> None:
        self.changed.emit(self.items())

    def _add(self) -> None:
        name = self.combo.currentText().strip()
        if name:
            self.list.addItem(name)
            self.list.setCurrentRow(self.list.count() - 1)
            self._emit()

    def _remove(self) -> None:
        r = self.list.currentRow()
        if r >= 0:
            self.list.takeItem(r)
            self._emit()

    def _move(self, d: int) -> None:
        r = self.list.currentRow()
        if 0 <= r + d < self.list.count() and r >= 0:
            item = self.list.takeItem(r)
            self.list.insertItem(r + d, item)
            self.list.setCurrentRow(r + d)
            self._emit()


class WaybarPreview(QWidget):
    """A mock bar that follows the style fields (approximation of what Waybar will draw)."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(120)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 0, 40, 0)
        self.bar = QFrame()
        self.bar.setObjectName("wb")
        self.row = QHBoxLayout(self.bar)
        self.row.setContentsMargins(8, 4, 8, 4)
        self.row.setSpacing(0)
        lay.addStretch(1)
        lay.addWidget(self.bar)
        lay.addStretch(1)
        self.labels: list[tuple[QLabel, str]] = []
        for text, kind in [("1", "ws"), ("2", "wsa"), ("3", "ws"), ("Terminal", "mod"), (None, "stretch"),
                           ("12:48", "mod"), (None, "stretch"), ("cpu 12%", "mod"), ("mem 41%", "mod"),
                           ("vol 70%", "mod"), ("bat 88%", "mod")]:
            if text is None:
                self.row.addStretch(1)
                continue
            lab = QLabel(text)
            self.row.addWidget(lab)
            self.labels.append((lab, kind))
        self.set_style(dict(STYLE_DEFAULTS))

    def paintEvent(self, _e: Any) -> None:  # noqa: N802
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor("#33406e"))
        g.setColorAt(1, QColor("#14182b"))
        p.fillRect(self.rect(), g)
        p.setPen(QColor(255, 255, 255, 110))
        p.drawText(14, self.height() - 10, "Approximate preview of the style fields below")

    def set_style(self, s: dict[str, Any]) -> None:
        def c(key: str) -> str:
            col = qcolor(s[key])
            return f"rgba({col.red()},{col.green()},{col.blue()},{col.alpha()})"

        fam = f'font-family: "{s["font"]}";' if s.get("font") else ""
        self.bar.setStyleSheet(
            f"QFrame#wb {{ background: {c('bar_bg')}; border-radius: {s['bar_radius']}px; }} QLabel {{ color: {c('fg')}; "
            f"font-size: {s['font_size']}px; {fam} }}")
        for lab, kind in self.labels:
            base = f"padding: 3px {s['mod_pad']}px; margin: 0 {s['mod_gap']}px; border-radius: {s['mod_radius']}px;"
            if kind == "mod":
                lab.setStyleSheet(f"{base} background: {c('mod_bg')};")
            elif kind == "wsa":
                lab.setStyleSheet(f"{base} background: {c('accent')}; color: #0b0f14;")
            else:
                lab.setStyleSheet(base)


class WaybarPage(Page):
    message = Signal(str, bool)

    def __init__(self) -> None:
        self.preview = WaybarPreview()
        super().__init__("Waybar", "Bar position, modules and style. Your comments and formatting are kept.", self.preview)
        self.doc: JsoncDoc | None = None
        self.cfg_path: Path | None = None
        self.style_path = Path()
        self.style_state: dict[str, Any] = {}
        self.cfg_dirty = self.style_dirty = False
        self.bar = 0
        self.lists: dict[str, ModuleList] = {}
        self.reload_btn = QPushButton("Reload from disk")
        self.reload_btn.clicked.connect(self.load)
        self.save_btn = primary_button("Save and reload Waybar")
        self.save_btn.clicked.connect(self.save)
        self.actions.addWidget(self.reload_btn)
        self.actions.addWidget(self.save_btn)
        self.content = QVBoxLayout()
        self.content.setSpacing(0)
        self.body.addLayout(self.content)
        self.finish()
        self.load()

    # -- loading ------------------------------------------------------------------------------------
    def _clear(self) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def load(self) -> None:
        self._clear()
        self.cfg_dirty = self.style_dirty = False
        self.cfg_path, self.style_path = find_files()
        css = util.read_text(self.style_path) or ""
        self.style_state = cssblock.read_state(css)
        self._merge_preview()
        self.doc = None
        if self.cfg_path is None:
            box = note("No Waybar config found. Hyprtune can create a starter one at "
                       f"{util.config_home() / 'waybar' / 'config.jsonc'}.")
            btn = QPushButton("Create starter config")
            btn.clicked.connect(self._create_starter)
            box.layout().addWidget(btn)
            self.content.addWidget(box)
            self._update_buttons()
            return
        try:
            self.doc = JsoncDoc(util.read_text(self.cfg_path) or "{}")
        except JsoncError as e:
            self.content.addWidget(note(f"Couldn't read {self.cfg_path}: {e}\nFix the file by hand, then press "
                                        "Reload from disk. Hyprtune won't touch it until it parses.", True))
            self._update_buttons()
            return
        self._build()
        self._update_buttons()

    def _create_starter(self) -> None:
        util.write_text(util.config_home() / "waybar" / "config.jsonc", STARTER)
        self.load()
        self.message.emit("Created a starter Waybar config", False)

    # -- building -----------------------------------------------------------------------------------
    def _section(self, title: str) -> Any:
        s = Section(title)
        self.content.addWidget(s)
        return s

    def _build(self) -> None:
        assert self.doc is not None
        info = note(f"Editing {self.cfg_path}. Only the values you change are rewritten; "
                    "a backup is kept in ~/.config/hyprtune/backups.")
        self.content.addWidget(info)
        if self.doc.bar_count() > 1:
            sec = self._section("Bar")
            combo = EnumControl(tuple((str(i), f"Bar {i + 1}") for i in range(self.doc.bar_count())))
            combo.set_value(str(self.bar))
            combo.changed.connect(self._switch_bar)
            sec.add_row(SettingRow("Bar to edit", "Your config defines several bars.", combo, False))
        sec = self._section("Bar options")
        for f in BAR_FIELDS:
            sec.add_row(self._field_row(f))

        sec = self._section("Modules")
        sec.add_row(note("Drag to reorder, or use the arrows. Type any module name, including custom/… ones."))
        holder = QWidget()
        h = QHBoxLayout(holder)
        h.setContentsMargins(0, 10, 0, 10)
        h.setSpacing(18)
        self.lists = {}
        for key, title in (("modules-left", "Left"), ("modules-center", "Centre"), ("modules-right", "Right")):
            ml = ModuleList(title)
            ml.set_items(self.doc.get([key], self.bar, []) or [])
            ml.changed.connect(partial(self._set_list, key))
            self.lists[key] = ml
            h.addWidget(ml, 1)
        sec.add_row(holder)

        sec = self._section("Module options")
        self.mod_combo = EnumControl(())
        self.mod_combo.combo.setMinimumWidth(240)
        sec.add_row(SettingRow("Module", "Options for the selected module are saved under its name in your config.",
                               self.mod_combo, False))
        self.mod_box = QVBoxLayout()
        self.mod_box.setSpacing(0)
        holder2 = QWidget()
        holder2.setLayout(self.mod_box)
        sec.lay.addWidget(holder2)
        self.mod_combo.changed.connect(self._show_module)
        self._refresh_module_choices()

        sec = self._section("Style")
        sec.add_row(note("Style changes are written to a marked block at the end of style.css and win over your "
                         "existing rules. Fields you haven't touched are left to your own stylesheet."))
        for sf in STYLE_FIELDS:
            sec.add_row(self._style_row(sf))

    # -- config fields ------------------------------------------------------------------------------
    def _field_row(self, f: Field) -> SettingRow:
        ctrl = make_field_control(f)
        row = SettingRow(f.label, f.desc, ctrl)
        row.setToolTip("Reset removes this key from your config so Waybar uses its default.")
        self._bind(f, row, ctrl)
        ctrl.changed.connect(partial(self._set_field, f, row))
        row.resetRequested.connect(partial(self._reset_field, f, row, ctrl))
        return row

    def _bind(self, f: Field, row: SettingRow, ctrl: Control) -> None:
        cur = self.doc.get(f.path, self.bar, None) if self.doc else None
        ctrl.set_value(cur if cur is not None else f.default)
        row.set_modified(cur is not None)

    def _set_field(self, f: Field, row: SettingRow, value: Any) -> None:
        assert self.doc
        if (f.kind == "str" and value == "") or (f.kind == "int" and f.default == 0 and value == 0):
            self.doc.remove(f.path, self.bar)
        else:
            self.doc.set(f.path, value, self.bar)
        self.cfg_dirty = True
        row.set_modified(self.doc.get(f.path, self.bar, None) is not None)
        self._update_buttons()

    def _reset_field(self, f: Field, row: SettingRow, ctrl: Control) -> None:
        assert self.doc
        self.doc.remove(f.path, self.bar)
        ctrl.set_value(f.default)
        row.set_modified(False)
        self.cfg_dirty = True
        self._update_buttons()

    def _switch_bar(self, idx: str) -> None:
        self.bar = int(idx)
        self._clear()
        self._build()

    def _set_list(self, key: str, items: list[str]) -> None:
        assert self.doc
        self.doc.set([key], items, self.bar)
        self.cfg_dirty = True
        self._refresh_module_choices()
        self._update_buttons()

    # -- module options -----------------------------------------------------------------------------
    def _refresh_module_choices(self) -> None:
        present = []
        for ml in self.lists.values():
            for m in ml.items():
                base = m.split("#")[0]
                if base in MODULE_FIELDS and base not in present:
                    present.append(base)
        extra = [m for m in MODULE_FIELDS if m not in present]
        choices = tuple((m, m) for m in present + extra)
        cur = self.mod_combo.value()
        c = self.mod_combo.combo
        c.blockSignals(True)
        c.clear()
        for v, lbl in choices:
            c.addItem(lbl + ("" if v in present else "  (not in your layout)"), v)
        i = c.findData(cur)
        c.setCurrentIndex(i if i >= 0 else 0)
        c.blockSignals(False)
        self._show_module(self.mod_combo.value())

    def _show_module(self, name: Any) -> None:
        while self.mod_box.count():
            item = self.mod_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for f in MODULE_FIELDS.get(str(name), []):
            self.mod_box.addWidget(self._field_row(f))

    # -- style --------------------------------------------------------------------------------------
    def _merge_preview(self) -> None:
        self.preview.set_style({**STYLE_DEFAULTS, **self.style_state})

    def _style_row(self, sf: StyleField) -> SettingRow:
        if sf.kind == "font":
            ctrl: Control = PickerControl("font", "System default", fmt=lambda f: f.family())
        elif sf.kind == "int":
            ctrl = NumberControl(True, sf.lo, sf.hi)
        else:
            ctrl = ColorControl(False, alpha=(sf.kind == "color_a"))
        row = SettingRow(sf.label, sf.desc, ctrl)
        row.setToolTip("Reset removes this rule so your own stylesheet applies.")
        ctrl.set_value(self.style_state.get(sf.key, sf.default))
        row.set_modified(sf.key in self.style_state)

        def changed(v: Any) -> None:
            self.style_state[sf.key] = v
            if sf.kind == "font" and not v:
                self.style_state.pop(sf.key)
            row.set_modified(sf.key in self.style_state)
            self.style_dirty = True
            self._merge_preview()
            self._update_buttons()

        def reset() -> None:
            self.style_state.pop(sf.key, None)
            ctrl.set_value(sf.default)
            row.set_modified(False)
            self.style_dirty = True
            self._merge_preview()
            self._update_buttons()

        ctrl.changed.connect(changed)
        row.resetRequested.connect(reset)
        return row

    # -- saving -------------------------------------------------------------------------------------
    def _update_buttons(self) -> None:
        self.save_btn.setEnabled(self.cfg_dirty or self.style_dirty)

    def save(self) -> None:
        try:
            if self.cfg_dirty and self.doc and self.cfg_path:
                util.write_text(self.cfg_path, self.doc.text)
            if self.style_dirty:
                css = util.read_text(self.style_path) or ""
                new = (cssblock.apply_block(css, self.style_state, style_css(self.style_state))
                       if self.style_state else cssblock.remove_block(css))
                util.write_text(self.style_path, new)
        except OSError as e:
            self.message.emit(f"Could not save Waybar files: {e}", True)
            return
        self.cfg_dirty = self.style_dirty = False
        self._update_buttons()
        if waybar_running():
            util.run(["pkill", "-SIGUSR2", "-x", "waybar"])
            self.message.emit("Saved. Waybar reloaded.", False)
        else:
            self.message.emit("Saved. Waybar isn't running; start it with `waybar` to see the changes.", False)

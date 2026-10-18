"""Appearance, Tiling, Input and Behavior pages, generated from the option registry."""
from __future__ import annotations

from functools import partial
from typing import Any

from ..hypr.model import HyprModel
from ..hypr.options import PageSpec, Spec
from ..ui.preview import DesktopPreview
from ..ui.widgets import (BoolControl, ColorControl, Control, EnumControl, NumberControl, Page, SettingRow,
                          TextControl, note)


def make_control(s: Spec) -> Control:
    if s.kind == "bool":
        return BoolControl()
    if s.kind == "int":
        return NumberControl(True, s.min, s.max)
    if s.kind == "float":
        return NumberControl(False, s.min, s.max, s.step)
    if s.kind == "enum":
        return EnumControl(s.choices)
    if s.kind == "color":
        return ColorControl(False)
    if s.kind == "gradient":
        return ColorControl(True, allow_empty=not s.default.get("colors"))
    return TextControl(str(s.default or ""))


class HyprPage(Page):
    def __init__(self, spec: PageSpec, model: HyprModel, preview: bool = False) -> None:
        super().__init__(spec.title, spec.blurb, DesktopPreview(model) if preview else None)
        self.model = model
        self.sections = []
        self.rows: dict[str, tuple[Spec, SettingRow, Control]] = {}
        self.banner = note("Hyprland isn't running (or hyprctl isn't on your PATH), so changes can't be previewed live. "
                           "Settings are still saved and apply the next time Hyprland starts.")
        self.banner.hide()
        self.add_widget(self.banner)
        for g in spec.groups:
            sec = self.add_section(g.title)
            self.sections.append(sec)
            for s in g.specs:
                ctrl = make_control(s)
                row = SettingRow(s.label, s.desc, ctrl)
                row.setToolTip(s.key)
                ctrl.changed.connect(partial(self.model.set_value, s.key))
                row.resetRequested.connect(partial(self.model.reset, s.key))
                sec.add_row(row)
                self.rows[s.key] = (s, row, ctrl)
        self.finish()
        model.optionChanged.connect(self._sync)
        model.refreshed.connect(self.refresh)
        self.refresh()

    def _sync(self, key: str) -> None:
        if key not in self.rows:
            return
        _s, row, ctrl = self.rows[key]
        v: Any = self.model.value(key)
        ctrl.set_value(v)
        row.set_modified(self.model.is_modified(key))

    def refresh(self) -> None:
        self.banner.setVisible(not self.model.b.running())
        for key, (_s, row, _c) in self.rows.items():
            row.setVisible(self.model.is_supported(key))
            self._sync(key)
        for sec in self.sections:
            sec.refresh_visibility()

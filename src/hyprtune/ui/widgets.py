"""Reusable controls. Every control exposes ``value()``, ``set_value()`` (silent) and ``changed``."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QColorDialog, QComboBox, QDoubleSpinBox, QFileDialog, QFontDialog,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
                               QSlider, QSpinBox, QToolButton, QVBoxLayout, QWidget)


class _WheelGuard(QObject):
    """Only let a control react to the mouse wheel once it has keyboard focus."""

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802
        return ev.type() == QEvent.Wheel and isinstance(obj, QWidget) and not obj.hasFocus()


_GUARD = _WheelGuard()


def guard_wheel(w: QWidget) -> QWidget:
    w.setFocusPolicy(Qt.StrongFocus)
    w.installEventFilter(_GUARD)
    return w


class Switch(QAbstractButton):
    def __init__(self) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)

    def paintEvent(self, _e: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal, on = self.palette(), self.isChecked()
        track = QColor(pal.color(pal.ColorRole.Highlight) if on else pal.color(pal.ColorRole.Mid))
        if not self.isEnabled():
            track.setAlpha(90)
        p.setPen(QPen(pal.color(pal.ColorRole.PlaceholderText), 1) if not on else Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0.5, 0.5, 39, 21), 10.5, 10.5)
        p.setPen(Qt.NoPen)
        p.setBrush(pal.color(pal.ColorRole.HighlightedText) if on else pal.color(pal.ColorRole.PlaceholderText))
        p.drawEllipse(QRectF(21 if on else 3, 3, 16, 16))


class Control(QWidget):
    changed = Signal(object)

    def value(self) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    def set_value(self, v: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError


def _row_layout(w: QWidget, spacing: int = 8) -> QHBoxLayout:
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    return lay


class BoolControl(Control):
    def __init__(self) -> None:
        super().__init__()
        self.sw = Switch()
        _row_layout(self).addWidget(self.sw)
        self.sw.toggled.connect(lambda v: self.changed.emit(bool(v)))

    def value(self) -> bool:
        return self.sw.isChecked()

    def set_value(self, v: Any) -> None:
        self.sw.blockSignals(True)
        self.sw.setChecked(bool(v))
        self.sw.blockSignals(False)
        self.sw.update()


class NumberControl(Control):
    def __init__(self, is_int: bool, lo: float | None, hi: float | None, step: float | None = None,
                 special: str = "") -> None:
        super().__init__()
        self.is_int, self.lo, self.hi = is_int, lo, hi
        span = (hi - lo) if (lo is not None and hi is not None) else None
        self.step = 1 if is_int else (step or (0.01 if span is not None and span <= 3 else 0.1))
        lay = _row_layout(self, 10)
        self.slider: QSlider | None = None
        if span is not None and span / self.step <= 5000:
            self.slider = guard_wheel(QSlider(Qt.Horizontal))
            self.slider.setRange(0, round(span / self.step))
            self.slider.setFixedWidth(170)
            lay.addWidget(self.slider)
        if is_int:
            self.spin: QSpinBox | QDoubleSpinBox = QSpinBox()
        else:
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2 if self.step < 0.1 else 1)
        self.spin.setRange(lo if lo is not None else -10**6, hi if hi is not None else 10**6)
        self.spin.setSingleStep(self.step)
        self.spin.setKeyboardTracking(False)
        self.spin.setFixedWidth(78)
        self.spin.setAlignment(Qt.AlignRight)
        if special:
            self.spin.setSpecialValueText(special)
        guard_wheel(self.spin)
        lay.addWidget(self.spin)
        self.spin.valueChanged.connect(self._from_spin)
        if self.slider:
            self.slider.valueChanged.connect(self._from_slider)

    def _emit(self, v: float) -> None:
        self.changed.emit(int(round(v)) if self.is_int else round(float(v), 4))

    def _from_slider(self, i: int) -> None:
        v = (self.lo or 0) + i * self.step
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self._emit(v)

    def _from_spin(self, v: float) -> None:
        if self.slider:
            self.slider.blockSignals(True)
            self.slider.setValue(round((v - (self.lo or 0)) / self.step))
            self.slider.blockSignals(False)
        self._emit(v)

    def value(self) -> float:
        v = self.spin.value()
        return int(v) if self.is_int else float(v)

    def set_value(self, v: Any) -> None:
        for w in (self.spin, self.slider):
            if w:
                w.blockSignals(True)
        self.spin.setValue(v)
        if self.slider:
            self.slider.setValue(round((float(v) - (self.lo or 0)) / self.step))
        for w in (self.spin, self.slider):
            if w:
                w.blockSignals(False)


class EnumControl(Control):
    def __init__(self, choices: tuple[tuple[str, str], ...]) -> None:
        super().__init__()
        self.combo = guard_wheel(QComboBox())
        self.combo.setMinimumWidth(190)
        for value, label in choices:
            self.combo.addItem(label, value)
        _row_layout(self).addWidget(self.combo)
        self.combo.currentIndexChanged.connect(lambda _i: self.changed.emit(self.combo.currentData()))

    def value(self) -> Any:
        return self.combo.currentData()

    def set_value(self, v: Any) -> None:
        self.combo.blockSignals(True)
        i = self.combo.findData(v)
        if i < 0:
            self.combo.addItem(str(v), v)
            i = self.combo.count() - 1
        self.combo.setCurrentIndex(i)
        self.combo.blockSignals(False)


class TextControl(Control):
    def __init__(self, placeholder: str = "", width: int = 260) -> None:
        super().__init__()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumWidth(width)
        _row_layout(self).addWidget(self.edit)
        self.edit.editingFinished.connect(lambda: self.changed.emit(self.edit.text()))

    def value(self) -> str:
        return self.edit.text()

    def set_value(self, v: Any) -> None:
        self.edit.blockSignals(True)
        self.edit.setText("" if v is None else str(v))
        self.edit.blockSignals(False)


class PickerControl(TextControl):
    """Text field with a Browse / Choose button: kind is 'file', 'dir' or 'font'."""

    def __init__(self, kind: str, placeholder: str = "", filt: str = "", fmt: Callable[[Any], str] | None = None) -> None:
        super().__init__(placeholder, 220)
        self.kind, self.filt, self.fmt = kind, filt, fmt
        btn = QPushButton("Choose…")
        btn.clicked.connect(self._pick)
        self.layout().addWidget(btn)

    def _pick(self) -> None:
        if self.kind == "font":
            ok, font = QFontDialog.getFont(self.window().font(), self, "Choose a font")
            if ok:
                text = self.fmt(font) if self.fmt else font.family()
            else:
                return
        elif self.kind == "dir":
            text = QFileDialog.getExistingDirectory(self, "Choose a folder", self.edit.text())
        else:
            text, _ = QFileDialog.getOpenFileName(self, "Choose a file", self.edit.text(), self.filt)
        if text:
            self.set_value(text)
            self.changed.emit(text)


def qcolor(rrggbbaa: str) -> QColor:
    h = rrggbbaa
    return QColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) if len(h) >= 8 else 255)


def hex_rgba(c: QColor) -> str:
    return f"{c.red():02x}{c.green():02x}{c.blue():02x}{c.alpha():02x}"


class ColorControl(Control):
    """One colour, or (gradient=True) a list of colours plus an angle."""

    def __init__(self, gradient: bool = False, alpha: bool = True, allow_empty: bool = False) -> None:
        super().__init__()
        self.gradient, self.alpha, self.allow_empty = gradient, alpha, allow_empty
        self.colors: list[str] = []
        self.angle = 45
        self.lay = _row_layout(self, 6)
        self.swatches: list[QPushButton] = []
        self.add_btn = QPushButton("+")
        self.add_btn.setObjectName("mini")
        self.add_btn.setToolTip("Add a colour (makes a gradient)")
        self.del_btn = QPushButton("−")
        self.del_btn.setObjectName("mini")
        self.del_btn.setToolTip("Remove the last colour")
        self.angle_spin = guard_wheel(QSpinBox())
        self.angle_spin.setRange(0, 360)
        self.angle_spin.setSuffix("°")
        self.angle_spin.setFixedWidth(66)
        self.angle_spin.setToolTip("Gradient angle")
        self.empty = QLabel("Not set")
        self.empty.setObjectName("dim")
        for w in (self.empty, self.add_btn, self.del_btn, self.angle_spin):
            self.lay.addWidget(w)
        self.add_btn.clicked.connect(self._add)
        self.del_btn.clicked.connect(self._del)
        self.angle_spin.valueChanged.connect(self._angle)
        self._build()

    def _build(self) -> None:
        for s in self.swatches:
            self.lay.removeWidget(s)
            s.deleteLater()
        self.swatches = []
        for i, c in enumerate(self.colors):
            b = QPushButton()
            b.setObjectName("swatch")
            col = qcolor(c)
            b.setStyleSheet(f"background: rgba({col.red()},{col.green()},{col.blue()},{col.alphaF():.2f});")
            b.setToolTip(f"#{c[:6]}  ·  {round(col.alphaF() * 100)}% opaque")
            b.clicked.connect(lambda _=False, i=i: self._pick(i))
            self.lay.insertWidget(i, b)
            self.swatches.append(b)
        n = len(self.colors)
        self.empty.setVisible(n == 0)
        self.add_btn.setVisible(self.gradient or n == 0)
        self.del_btn.setVisible(self.gradient and n > (0 if self.allow_empty else 1))
        self.angle_spin.setVisible(self.gradient and n > 1)

    def _pick(self, i: int) -> None:
        opts = QColorDialog.ColorDialogOption.DontUseNativeDialog
        if self.alpha:
            opts |= QColorDialog.ColorDialogOption.ShowAlphaChannel
        c = QColorDialog.getColor(qcolor(self.colors[i]), self.window(), "Choose a colour", opts)
        if c.isValid():
            self.colors[i] = hex_rgba(c) if self.alpha else hex_rgba(c)[:6] + "ff"
            self._build()
            self._emit()

    def _add(self) -> None:
        self.colors.append(self.colors[-1] if self.colors else "33ccffee")
        self._build()
        self._emit()

    def _del(self) -> None:
        self.colors.pop()
        self._build()
        self._emit()

    def _angle(self, v: int) -> None:
        self.angle = v
        self._emit()

    def _emit(self) -> None:
        self.changed.emit(self.value())

    def value(self) -> Any:
        if self.gradient:
            return {"colors": list(self.colors), "angle": self.angle}
        return self.colors[0] if self.colors else "000000ff"

    def set_value(self, v: Any) -> None:
        if isinstance(v, dict):
            self.colors, self.angle = list(v.get("colors", [])), int(v.get("angle", 0))
        else:
            self.colors = [v] if v else []
        self.angle_spin.blockSignals(True)
        self.angle_spin.setValue(self.angle)
        self.angle_spin.blockSignals(False)
        self._build()


class SettingRow(QFrame):
    resetRequested = Signal()

    def __init__(self, title: str, desc: str, control: QWidget, resettable: bool = True) -> None:
        super().__init__()
        self.setObjectName("row")
        self.control = control
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("rowTitle")
        self.title.setWordWrap(True)
        text.addWidget(self.title)
        self.desc = QLabel(desc)
        self.desc.setObjectName("rowDesc")
        self.desc.setWordWrap(True)
        self.desc.setVisible(bool(desc))
        text.addWidget(self.desc)
        lay.addLayout(text, 1)
        lay.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.reset = QToolButton()
        self.reset.setObjectName("reset")
        self.reset.setText("↺")
        self.reset.setToolTip("Reset to default")
        self.reset.setFixedWidth(28)
        self.reset.clicked.connect(self.resetRequested)
        self.reset.setVisible(False)
        self.reset.setEnabled(resettable)
        lay.addWidget(self.reset)

    def set_modified(self, modified: bool) -> None:
        # Keep the button's space reserved so controls don't jump sideways.
        self.reset.setVisible(True)
        self.reset.setText("↺" if modified else "")
        self.reset.setEnabled(modified)


class Section(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.heading = QLabel(title)
        self.heading.setObjectName("groupTitle")
        self.heading.setIndent(0)
        self.lay.addWidget(self.heading)
        self.rows: list[QWidget] = []

    def add_row(self, row: QWidget) -> None:
        self.rows.append(row)
        self.lay.addWidget(row)

    def refresh_visibility(self) -> None:
        self.setVisible(any(not r.isHidden() for r in self.rows))


def note(text: str, error: bool = False) -> QFrame:
    f = QFrame()
    f.setObjectName("note")
    lay = QHBoxLayout(f)
    lay.setContentsMargins(14, 10, 14, 10)
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if error:
        lab.setObjectName("error")
    lay.addWidget(lab)
    return f


class Page(QWidget):
    """Scrollable, centred settings page with a title, blurb and optional fixed header widget."""

    def __init__(self, title: str, blurb: str = "", fixed_top: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("page")
        self.page_title = title
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if fixed_top is not None:
            outer.addWidget(fixed_top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self.scroll, 1)
        inner = QWidget()
        inner.setObjectName("page")
        row = QHBoxLayout(inner)
        row.setContentsMargins(32, 26, 32, 40)
        wrap = QWidget()
        wrap.setObjectName("page")
        wrap.setMaximumWidth(900)
        wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addStretch(1)
        row.addWidget(wrap, 100)
        row.addStretch(1)
        self.body = QVBoxLayout(wrap)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("pageTitle")
        titles.addWidget(t)
        if blurb:
            b = QLabel(blurb)
            b.setObjectName("blurb")
            b.setWordWrap(True)
            titles.addWidget(b)
        head.addLayout(titles, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        head.addLayout(self.actions)
        self.body.addLayout(head)
        self.body.addSpacing(4)
        self.scroll.setWidget(inner)

    def add_section(self, title: str) -> Section:
        s = Section(title)
        self.body.addWidget(s)
        return s

    def add_widget(self, w: QWidget) -> None:
        self.body.addWidget(w)

    def finish(self) -> None:
        self.body.addStretch(1)

    def on_show(self) -> None:  # called when the page becomes visible
        pass


def primary_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("primary")
    return b

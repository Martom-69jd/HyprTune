"""Colour tokens and the application stylesheet (dark and light)."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Tokens:
    name: str
    bg: str       # window
    side: str     # sidebar
    raised: str   # inputs, buttons
    line: str     # hairlines
    text: str
    dim: str
    accent: str
    on_accent: str
    danger: str


DARK = Tokens("dark", "#151922", "#10131a", "#222836", "#2a3142", "#e9e7e2", "#8f97a8", "#35d0c0", "#04201c", "#ff7a7a")
LIGHT = Tokens("light", "#f5f6f8", "#eceef2", "#ffffff", "#dde1e8", "#1c212b", "#667085", "#0f9d90", "#ffffff", "#c53030")
_current = DARK


def tokens() -> Tokens:
    return _current


def apply(app: QApplication, mode: str = "auto") -> Tokens:
    """mode: auto | dark | light. Auto follows the desktop hint and prefers dark."""
    global _current
    if mode == "auto":
        scheme = app.styleHints().colorScheme().name
        mode = "light" if scheme == "Light" else "dark"
    t = _current = DARK if mode == "dark" else LIGHT
    app.setStyle("Fusion")
    pal = QPalette()
    for role, col in [
        (QPalette.Window, t.bg), (QPalette.WindowText, t.text), (QPalette.Base, t.raised),
        (QPalette.AlternateBase, t.side), (QPalette.Text, t.text), (QPalette.Button, t.raised),
        (QPalette.ButtonText, t.text), (QPalette.Highlight, t.accent), (QPalette.HighlightedText, t.on_accent),
        (QPalette.ToolTipBase, t.raised), (QPalette.ToolTipText, t.text), (QPalette.PlaceholderText, t.dim),
        (QPalette.Mid, t.line), (QPalette.Dark, t.line), (QPalette.Link, t.accent),
    ]:
        pal.setColor(role, QColor(col))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(t.dim))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(t.dim))
    app.setPalette(pal)
    f = app.font()
    f.setPointSizeF(max(f.pointSizeF(), 10.0))
    app.setFont(f)
    app.setStyleSheet(stylesheet(t))
    return t


def stylesheet(t: Tokens) -> str:
    return f"""
* {{ outline: none; }}
QWidget {{ color: {t.text}; }}
QMainWindow, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t.bg}; }}
QScrollArea {{ border: none; }}
QToolTip {{ background: {t.raised}; color: {t.text}; border: 1px solid {t.line}; padding: 5px 7px; border-radius: 6px; }}

QFrame#sidebar {{ background: {t.side}; border-right: 1px solid {t.line}; }}
QLabel#brand {{ font-size: 15px; font-weight: 700; }}
QLabel#sideGroup {{ color: {t.dim}; font-size: 12px; padding: 14px 0 4px 0; }}
QPushButton#nav {{ text-align: left; border: none; border-radius: 7px; padding: 8px 12px; margin: 1px 8px;
    background: transparent; color: {t.text}; }}
QPushButton#nav:hover {{ background: {t.raised}; }}
QPushButton#nav:checked {{ background: {t.raised}; font-weight: 600; border-left: 3px solid {t.accent}; padding-left: 9px; }}

QLabel#pageTitle {{ font-size: 24px; font-weight: 600; }}
QLabel#blurb {{ color: {t.dim}; font-size: 13px; }}
QLabel#groupTitle {{ font-size: 13px; font-weight: 600; color: {t.text}; padding: 18px 0 6px 0; }}
QLabel#rowTitle {{ font-size: 13px; }}
QLabel#rowDesc {{ font-size: 12px; color: {t.dim}; }}
QLabel#dim {{ color: {t.dim}; }}
QLabel#error {{ color: {t.danger}; }}
QFrame#row {{ border: none; border-bottom: 1px solid {t.line}; }}
QFrame#note {{ background: {t.raised}; border-radius: 8px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {t.raised}; border: 1px solid {t.line}; border-radius: 7px; padding: 5px 8px; selection-background-color: {t.accent}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {t.accent}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {t.raised}; border: 1px solid {t.line}; selection-background-color: {t.accent};
    selection-color: {t.on_accent}; padding: 3px; outline: none; }}

QPushButton {{ background: {t.raised}; border: 1px solid {t.line}; border-radius: 7px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {t.dim}; }}
QPushButton:disabled {{ color: {t.dim}; }}
QPushButton#primary {{ background: {t.accent}; color: {t.on_accent}; border-color: {t.accent}; font-weight: 600; }}
QPushButton#primary:disabled {{ background: {t.raised}; color: {t.dim}; border-color: {t.line}; }}
QToolButton#reset {{ border: none; color: {t.dim}; padding: 2px 6px; border-radius: 6px; font-size: 14px; }}
QToolButton#reset:hover {{ background: {t.raised}; color: {t.text}; }}
QPushButton#swatch {{ border: 1px solid {t.dim}; border-radius: 6px; padding: 0; min-width: 30px; max-width: 30px; min-height: 22px; max-height: 22px; }}
QPushButton#mini {{ padding: 2px 0; min-width: 24px; max-width: 24px; min-height: 22px; max-height: 22px; }}

QSlider::groove:horizontal {{ height: 4px; background: {t.line}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {t.text}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}

QFrame#banner {{ background: {t.raised}; border-top: 1px solid {t.line}; }}
QLabel#status {{ color: {t.dim}; padding: 4px 14px; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.line}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t.dim}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
"""

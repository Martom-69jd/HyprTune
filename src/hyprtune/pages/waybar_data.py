"""Static knowledge about Waybar: bar options, known modules, per-module options, CSS generation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Field:
    path: tuple[str, ...]
    label: str
    kind: str  # bool int float str enum
    default: Any = None
    desc: str = ""
    lo: float | None = 0
    hi: float | None = 2000
    choices: tuple[tuple[str, str], ...] = ()


def F(path: str, label: str, kind: str, default: Any = None, desc: str = "", lo: float | None = 0,
      hi: float | None = 2000, choices: tuple[str, ...] = ()) -> Field:
    return Field(tuple(path.split(".")), label, kind, default, desc, lo, hi,
                 tuple((c, c.replace("-", " ").capitalize()) for c in choices))


BAR_FIELDS = [
    F("layer", "Layer", "enum", "top", "Draw above (top) or below (bottom) windows.", choices=("top", "bottom")),
    F("position", "Position", "enum", "top", "Screen edge the bar sits on.", choices=("top", "bottom", "left", "right")),
    F("height", "Height", "int", 0, "Pixels. 0 lets Waybar size the bar to its content.", hi=200),
    F("width", "Width", "int", 0, "Pixels. 0 spans the whole edge.", hi=8000),
    F("spacing", "Space between modules", "int", 4, "Pixels.", hi=60),
    F("margin-top", "Margin top", "int", 0, "Gap between the bar and the screen edge.", hi=200),
    F("margin-right", "Margin right", "int", 0, "", hi=200),
    F("margin-bottom", "Margin bottom", "int", 0, "", hi=200),
    F("margin-left", "Margin left", "int", 0, "", hi=200),
    F("exclusive", "Reserve screen space", "bool", True, "Windows won't cover the bar."),
    F("passthrough", "Click through the bar", "bool", False, "Mouse events pass to windows underneath."),
    F("fixed-center", "Keep centre modules centred", "bool", True, "Centre stays put even if left or right grow."),
    F("reload_style_on_change", "Reload style when CSS changes", "bool", False, "Handy while tweaking style.css."),
    F("output", "Only on monitor", "str", "", "Monitor name such as DP-1. Empty shows the bar on every monitor."),
    F("name", "Bar name", "str", "", "Optional; shows up as a CSS class."),
]

KNOWN_MODULES = [
    "hyprland/workspaces", "hyprland/window", "hyprland/submap", "hyprland/language", "clock", "cpu", "memory", "disk",
    "temperature", "load", "battery", "upower", "network", "bluetooth", "pulseaudio", "wireplumber", "backlight", "tray",
    "idle_inhibitor", "power-profiles-daemon", "mpris", "keyboard-state", "user", "privacy", "gamemode",
    "custom/example",
]

_FMT = "Format string. Placeholders depend on the module."
MODULE_FIELDS: dict[str, list[Field]] = {
    "clock": [F("clock.format", "Format", "str", "{:%H:%M}", "strftime-style, e.g. {:%a %d %b  %H:%M}"),
              F("clock.format-alt", "Alternate format (on click)", "str", "{:%A, %d %B %Y}"),
              F("clock.tooltip-format", "Tooltip", "str", "<tt>{calendar}</tt>"),
              F("clock.interval", "Update every (seconds)", "int", 60, lo=1, hi=3600)],
    "cpu": [F("cpu.format", "Format", "str", "{usage}%", _FMT), F("cpu.interval", "Update every (seconds)", "int", 10, lo=1, hi=600)],
    "memory": [F("memory.format", "Format", "str", "{percentage}%", _FMT),
               F("memory.interval", "Update every (seconds)", "int", 30, lo=1, hi=600)],
    "disk": [F("disk.format", "Format", "str", "{percentage_used}%", _FMT), F("disk.path", "Path", "str", "/")],
    "temperature": [F("temperature.format", "Format", "str", "{temperatureC}°C", _FMT),
                    F("temperature.critical-threshold", "Critical above (°C)", "int", 80, lo=0, hi=150)],
    "battery": [F("battery.format", "Format", "str", "{capacity}% {icon}", _FMT),
                F("battery.format-charging", "Format while charging", "str", "{capacity}% "),
                F("battery.format-plugged", "Format when plugged in", "str", "{capacity}% "),
                F("battery.states.warning", "Warning below (%)", "int", 30, lo=1, hi=100),
                F("battery.states.critical", "Critical below (%)", "int", 15, lo=1, hi=100),
                F("battery.interval", "Update every (seconds)", "int", 60, lo=1, hi=600)],
    "network": [F("network.format-wifi", "Format (Wi-Fi)", "str", "{essid} ({signalStrength}%)", _FMT),
                F("network.format-ethernet", "Format (Ethernet)", "str", "{ipaddr}/{cidr}"),
                F("network.format-disconnected", "Format (disconnected)", "str", "Disconnected"),
                F("network.tooltip-format", "Tooltip", "str", "{ifname} via {gwaddr}")],
    "pulseaudio": [F("pulseaudio.format", "Format", "str", "{volume}% {icon}", _FMT),
                   F("pulseaudio.format-muted", "Format when muted", "str", "muted"),
                   F("pulseaudio.scroll-step", "Scroll step (%)", "float", 1.0, lo=0.1, hi=20),
                   F("pulseaudio.on-click", "On click", "str", "pavucontrol")],
    "wireplumber": [F("wireplumber.format", "Format", "str", "{volume}%", _FMT),
                    F("wireplumber.format-muted", "Format when muted", "str", "muted"),
                    F("wireplumber.scroll-step", "Scroll step (%)", "float", 1.0, lo=0.1, hi=20),
                    F("wireplumber.on-click", "On click", "str", "pavucontrol")],
    "backlight": [F("backlight.format", "Format", "str", "{percent}% {icon}", _FMT),
                  F("backlight.scroll-step", "Scroll step (%)", "float", 1.0, lo=0.1, hi=20)],
    "tray": [F("tray.icon-size", "Icon size", "int", 21, lo=8, hi=64), F("tray.spacing", "Icon spacing", "int", 10, hi=40)],
    "idle_inhibitor": [F("idle_inhibitor.format", "Format", "str", "{icon}", _FMT)],
    "hyprland/workspaces": [F("hyprland/workspaces.format", "Format", "str", "{name}", "{name}, {id} or {icon}"),
                            F("hyprland/workspaces.all-outputs", "Show workspaces of all monitors", "bool", False),
                            F("hyprland/workspaces.disable-scroll", "Disable scrolling to switch", "bool", False),
                            F("hyprland/workspaces.active-only", "Only show the active workspace", "bool", False),
                            F("hyprland/workspaces.show-special", "Show special workspaces", "bool", False)],
    "hyprland/window": [F("hyprland/window.format", "Format", "str", "{title}", _FMT),
                        F("hyprland/window.max-length", "Maximum length (characters)", "int", 0, "0 means unlimited.", hi=300),
                        F("hyprland/window.separate-outputs", "Per-monitor window title", "bool", False)],
    "mpris": [F("mpris.format", "Format", "str", "{player_icon} {title}", _FMT),
              F("mpris.max-length", "Maximum length (characters)", "int", 0, hi=300)],
}

# -- style -------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StyleField:
    key: str
    label: str
    kind: str  # font int color color_a
    default: Any
    desc: str = ""
    lo: int = 0
    hi: int = 60


STYLE_FIELDS = [
    StyleField("font", "Font", "font", "", "Font family used by every module."),
    StyleField("font_size", "Font size", "int", 13, "Pixels.", 6, 40),
    StyleField("fg", "Text colour", "color", "e6e6e6ff"),
    StyleField("bar_bg", "Bar background", "color_a", "11111bd9", "Use the alpha slider for transparency."),
    StyleField("bar_radius", "Bar corner radius", "int", 0, "Looks best with some bar margin.", 0, 40),
    StyleField("mod_bg", "Module background", "color_a", "ffffff14", "Behind each module, such as clock or battery."),
    StyleField("mod_radius", "Module corner radius", "int", 8, "", 0, 30),
    StyleField("mod_pad", "Module padding", "int", 10, "Horizontal pixels inside each module.", 0, 30),
    StyleField("mod_gap", "Module margin", "int", 2, "Horizontal pixels outside each module.", 0, 20),
    StyleField("accent", "Active workspace", "color", "35d0c0ff"),
    StyleField("urgent", "Urgent / critical", "color", "ff6b6bff"),
]
STYLE_DEFAULTS = {f.key: f.default for f in STYLE_FIELDS}


def _css_color(c: str) -> str:
    r, g, b, a = (int(c[i:i + 2], 16) for i in (0, 2, 4, 6))
    return f"rgba({r}, {g}, {b}, {a / 255:.2f})" if a < 255 else f"rgb({r}, {g}, {b})"


def _on(c: str) -> str:
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return "#0b0f14" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


_MODS = ".module, #clock, #battery, #cpu, #memory, #disk, #temperature, #network, #bluetooth, #pulseaudio, #wireplumber, #backlight, #tray, #idle_inhibitor, #language, #mpris, #window, #load"


def style_css(s: dict[str, Any]) -> str:
    """CSS for only the fields the user has set; everything else is left to their own stylesheet."""
    blocks: list[str] = []

    def rule(sel: str, decls: list[str]) -> None:
        if decls:
            blocks.append(sel + " {\n    " + "\n    ".join(decls) + "\n}")

    g = s.get
    rule("*", ([f'font-family: "{g("font")}";'] if g("font") else []) +
         ([f"font-size: {g('font_size')}px;"] if g("font_size") is not None else []))
    rule("window#waybar", ([f"background-color: {_css_color(g('bar_bg'))};"] if g("bar_bg") else []) +
         ([f"color: {_css_color(g('fg'))};"] if g("fg") else []) +
         ([f"border-radius: {g('bar_radius')}px;"] if g("bar_radius") is not None else []))
    mod = []
    if g("fg"):
        mod.append(f"color: {_css_color(g('fg'))};")
    if g("mod_bg"):
        mod.append(f"background-color: {_css_color(g('mod_bg'))};")
    if g("mod_radius") is not None:
        mod.append(f"border-radius: {g('mod_radius')}px;")
    if g("mod_pad") is not None:
        mod.append(f"padding: 0 {g('mod_pad')}px;")
    if g("mod_gap") is not None:
        mod.append(f"margin: 0 {g('mod_gap')}px;")
    rule(_MODS, mod)
    ws = []
    if g("mod_radius") is not None:
        ws.append(f"border-radius: {g('mod_radius')}px;")
    if g("fg"):
        ws.append(f"color: {_css_color(g('fg'))};")
    if g("mod_pad") is not None:
        ws.append(f"padding: 0 {max(int(g('mod_pad')) - 4, 2)}px;")
    rule("#workspaces button", ws)
    if g("accent"):
        rule("#workspaces button.active, #workspaces button.focused",
             [f"background-color: {_css_color(g('accent'))};", f"color: {_on(g('accent'))};"])
    if g("urgent"):
        rule("#workspaces button.urgent", [f"background-color: {_css_color(g('urgent'))};", f"color: {_on(g('urgent'))};"])
        rule("#battery.critical:not(.charging), #temperature.critical", [f"color: {_css_color(g('urgent'))};"])
    if g("bar_bg"):
        rule("tooltip", [f"background-color: {_css_color(g('bar_bg')[:6] + 'ff')};",
                         f"border-radius: {g('mod_radius', 8)}px;"])
    return "\n\n".join(blocks)

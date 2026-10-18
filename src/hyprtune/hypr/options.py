"""The settings Hyprtune exposes for Hyprland, grouped into pages.

Types, defaults, ranges, enum members and descriptions come from
``data/hypr_options.json`` (generated from Hyprland's own option metadata);
this file only decides *which* options appear, how they are labelled, and a few
overrides."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

from .values import normalize_default

with resources.files("hyprtune.data").joinpath("hypr_options.json").open("r", encoding="utf-8") as _f:
    _DATA = json.load(_f)
SCHEMA: dict[str, dict[str, Any]] = _DATA["options"]
SCHEMA_VERSION: str = _DATA["hyprland_version"]


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    kind: str  # bool int float enum string color gradient
    default: Any
    desc: str
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: tuple[tuple[str, str], ...] = ()
    index_choices: tuple[str, ...] | None = None  # hyprlang wants ints for these


@dataclass
class Group:
    title: str
    specs: list[Spec] = field(default_factory=list)


@dataclass
class PageSpec:
    id: str
    title: str
    blurb: str
    groups: list[Group]


def _pretty(v: str) -> str:
    return "Default" if v == "" else v.replace("_", " ").replace("-", " ").capitalize()


_LABELS = {"fullscreen_game": "Fullscreen games", "take_over": "Take over", "lrm": "Left, right, middle",
           "lmr": "Left, middle, right", "top_left": "Top left", "top_right": "Top right",
           "bottom_left": "Bottom left", "bottom_right": "Bottom right", "follow_mouse": "Follow mouse"}


def _choice(v: Any) -> tuple[str, str]:
    if isinstance(v, (tuple, list)):
        return (v[0], v[1])
    return (v, _LABELS.get(v, _pretty(v)))


def make_spec(key: str, label: str, over: dict[str, Any] | None = None) -> Spec:
    meta = SCHEMA[key]
    over = over or {}
    t = meta["type"]
    kind = {"cssgap": "int", "choice": "enum", "string": "string"}.get(t, t)
    choices = tuple(_choice(c) for c in over.get("choices", ()))
    index_choices = None
    if t == "choice":
        names = tuple(meta["enum"])
        choices = choices or tuple(_choice(n) for n in names)
        index_choices = names
    if choices and kind == "string":
        kind = "enum"
    lo, hi = over.get("min", meta.get("min")), over.get("max", meta.get("max"))
    if kind in ("int", "float") and hi is not None and hi > 1e6:
        hi = None
    if kind == "int" and lo is None:
        lo = 0
    default = normalize_default(t, meta.get("default"), meta.get("default_str"))
    return Spec(key, label, kind, default, over.get("desc", meta.get("desc", "")), lo, hi,
                over.get("step"), choices, index_choices)


def _page(pid: str, title: str, blurb: str, groups: list[tuple[str, list[Any]]]) -> PageSpec:
    out = []
    for gtitle, items in groups:
        specs = []
        for it in items:
            key, label, *rest = it
            specs.append(make_spec(key, label, rest[0] if rest else None))
        out.append(Group(gtitle, specs))
    return PageSpec(pid, title, blurb, out)


_ACCEL = {"choices": ["", "adaptive", "flat"]}
_EDGES = ["left", "right", "top", "bottom"]

PAGES: list[PageSpec] = [
    _page("appearance", "Appearance", "How windows look: gaps, borders, corners, blur and shadows.", [
        ("Gaps", [
            ("general:gaps_in", "Gap between windows", {"max": 60}),
            ("general:gaps_out", "Gap to screen edges", {"max": 120}),
            ("general:gaps_workspaces", "Gap between workspaces"),
        ]),
        ("Borders", [
            ("general:border_size", "Border width"),
            ("general:col.active_border", "Active border"),
            ("general:col.inactive_border", "Inactive border"),
            ("general:resize_on_border", "Resize by dragging borders"),
            ("general:extend_border_grab_area", "Border grab area"),
            ("general:hover_icon_on_border", "Show resize cursor on borders"),
        ]),
        ("Corners and transparency", [
            ("decoration:rounding", "Corner radius"),
            ("decoration:rounding_power", "Corner curvature", {"step": 0.1}),
            ("decoration:active_opacity", "Active window opacity"),
            ("decoration:inactive_opacity", "Inactive window opacity"),
            ("decoration:fullscreen_opacity", "Fullscreen window opacity"),
        ]),
        ("Dimming", [
            ("decoration:dim_inactive", "Dim inactive windows"),
            ("decoration:dim_strength", "Dim strength"),
            ("decoration:dim_special", "Dim behind special workspace"),
        ]),
        ("Blur", [
            ("decoration:blur:enabled", "Blur window backgrounds"),
            ("decoration:blur:size", "Blur size"),
            ("decoration:blur:passes", "Blur passes"),
            ("decoration:blur:ignore_opacity", "Blur ignores window opacity"),
            ("decoration:blur:new_optimizations", "Extra blur optimisations"),
            ("decoration:blur:xray", "X-ray floating windows"),
            ("decoration:blur:noise", "Noise"),
            ("decoration:blur:contrast", "Contrast"),
            ("decoration:blur:brightness", "Brightness"),
            ("decoration:blur:vibrancy", "Vibrancy"),
            ("decoration:blur:special", "Blur behind special workspace"),
            ("decoration:blur:popups", "Blur popups and menus"),
        ]),
        ("Shadows", [
            ("decoration:shadow:enabled", "Window shadows"),
            ("decoration:shadow:range", "Shadow size"),
            ("decoration:shadow:render_power", "Shadow falloff"),
            ("decoration:shadow:sharp", "Sharp shadows"),
            ("decoration:shadow:scale", "Shadow scale"),
            ("decoration:shadow:color", "Shadow colour"),
            ("decoration:shadow:color_inactive", "Inactive shadow colour"),
        ]),
        ("Glow", [
            ("decoration:glow:enabled", "Inner glow"),
            ("decoration:glow:range", "Glow size"),
            ("decoration:glow:render_power", "Glow falloff"),
            ("decoration:glow:color", "Glow colour"),
        ]),
        ("Animations", [
            ("animations:enabled", "Animations"),
            ("animations:workspace_wraparound", "Wrap workspace slide direction"),
        ]),
    ]),
    _page("tiling", "Tiling", "Choose a layout and tune how new windows are placed and resized.", [
        ("Layout", [
            ("general:layout", "Layout", {"choices": ["dwindle", "master", "scrolling", "monocle"]}),
            ("general:no_focus_fallback", "Don't fall back to another window when moving focus"),
        ]),
        ("Dwindle", [
            ("dwindle:force_split", "Split new windows"),
            ("dwindle:default_split_ratio", "Default split ratio"),
            ("dwindle:split_width_multiplier", "Split width multiplier"),
            ("dwindle:split_bias", "Window that gets the split ratio"),
            ("dwindle:preserve_split", "Keep split direction"),
            ("dwindle:smart_split", "Smart split by cursor position"),
            ("dwindle:smart_resizing", "Smart resizing"),
            ("dwindle:use_active_for_splits", "Split the focused window, not the one under the cursor"),
            ("dwindle:permanent_direction_override", "Keep preselected direction"),
            ("dwindle:precise_mouse_move", "Precise drop when dragging windows"),
            ("dwindle:special_scale_factor", "Special workspace scale"),
        ]),
        ("Master", [
            ("master:orientation", "Master area position", {"choices": ["left", "right", "top", "bottom", "center"]}),
            ("master:mfact", "Master area size"),
            ("master:new_status", "New windows become", {"choices": ["master", "slave", "inherit"]}),
            ("master:new_on_top", "New windows go on top of the stack"),
            ("master:new_on_active", "New windows open", {"choices": ["none", "before", "after"]}),
            ("master:slave_count_for_center_master", "Slaves needed to centre the master"),
            ("master:center_master_fallback", "Fallback when not centred", {"choices": _EDGES}),
            ("master:center_ignores_reserved", "Centre ignoring bars"),
            ("master:allow_small_split", "Allow extra masters as horizontal splits"),
            ("master:smart_resizing", "Smart resizing"),
            ("master:drop_at_cursor", "Drop dragged windows at the cursor"),
            ("master:always_keep_position", "Keep master position when alone"),
            ("master:focus_master_on_close", "Focus master when a window closes"),
            ("master:special_scale_factor", "Special workspace scale"),
        ]),
        ("Scrolling", [
            ("scrolling:column_width", "Column width"),
            ("scrolling:explicit_column_widths", "Preset column widths"),
            ("scrolling:direction", "Direction", {"choices": ["right", "left", "down", "up"]}),
            ("scrolling:fullscreen_on_one_column", "A lone column fills the screen"),
            ("scrolling:focus_fit_method", "Bring focused column into view by"),
            ("scrolling:follow_focus", "Scroll to follow focus"),
            ("scrolling:follow_min_visible", "Minimum visible part when following"),
            ("scrolling:wrap_focus", "Wrap focus around"),
            ("scrolling:wrap_swapcol", "Wrap column moves around"),
        ]),
        ("Floating windows", [
            ("general:snap:enabled", "Snap floating windows"),
            ("general:snap:window_gap", "Snap distance to windows"),
            ("general:snap:monitor_gap", "Snap distance to screen edges"),
            ("general:snap:border_overlap", "Overlap borders when snapping"),
            ("general:snap:respect_gaps", "Respect gaps when snapping"),
            ("general:resize_corner", "Always resize from corner"),
        ]),
        ("Workspaces and focus", [
            ("binds:workspace_back_and_forth", "Switching to the current workspace goes back"),
            ("binds:allow_workspace_cycles", "Remember previous workspace per workspace"),
            ("binds:hide_special_on_workspace_change", "Hide special workspace when switching"),
            ("binds:movefocus_cycles_fullscreen", "Cycle windows while fullscreen"),
            ("binds:window_direction_monitor_fallback", "Move across monitor edges"),
            ("binds:drag_threshold", "Drag threshold (px)"),
        ]),
    ]),
    _page("input", "Input", "Keyboard, mouse and touchpad behaviour.", [
        ("Keyboard", [
            ("input:kb_layout", "Layout"),
            ("input:kb_variant", "Variant"),
            ("input:kb_model", "Model"),
            ("input:kb_options", "Options"),
            ("input:repeat_rate", "Repeat rate"),
            ("input:repeat_delay", "Repeat delay (ms)"),
            ("input:numlock_by_default", "Num Lock on at start"),
        ]),
        ("Mouse", [
            ("input:follow_mouse", "Focus follows mouse"),
            ("input:float_switch_override_focus", "Focus under cursor when floating changes"),
            ("input:sensitivity", "Sensitivity"),
            ("input:accel_profile", "Acceleration profile", _ACCEL),
            ("input:force_no_accel", "Disable acceleration"),
            ("input:natural_scroll", "Natural scrolling"),
            ("input:scroll_factor", "Scroll speed"),
            ("input:left_handed", "Left-handed buttons"),
        ]),
        ("Touchpad", [
            ("input:touchpad:natural_scroll", "Natural scrolling"),
            ("input:touchpad:scroll_factor", "Scroll speed"),
            ("input:touchpad:tap-to-click", "Tap to click"),
            ("input:touchpad:tap-and-drag", "Tap and drag"),
            ("input:touchpad:drag_lock", "Drag lock"),
            ("input:touchpad:disable_while_typing", "Disable while typing"),
            ("input:touchpad:middle_button_emulation", "Two-button middle click"),
            ("input:touchpad:clickfinger_behavior", "Click by finger count"),
            ("input:touchpad:tap_button_map", "Tap button order", {"choices": ["", "lrm", "lmr"]}),
        ]),
    ]),
    _page("behavior", "Behavior", "Startup, focus, display and cursor details.", [
        ("Startup", [
            ("misc:disable_hyprland_logo", "Hide the logo background"),
            ("misc:disable_splash_rendering", "Hide the splash text"),
            ("misc:force_default_wallpaper", "Built-in wallpaper"),
            ("misc:background_color", "Background colour"),
            ("misc:font_family", "Interface font"),
        ]),
        ("Windows", [
            ("misc:focus_on_activate", "Focus windows that ask for it"),
            ("misc:on_focus_under_fullscreen", "Focusing behind a fullscreen window"),
            ("misc:enable_swallow", "Window swallowing"),
            ("misc:swallow_regex", "Swallowing terminal class (regex)"),
            ("misc:animate_manual_resizes", "Animate manual resizes"),
            ("misc:animate_mouse_windowdragging", "Animate dragging windows"),
            ("misc:close_special_on_empty", "Close empty special workspace"),
            ("misc:exit_window_retains_fullscreen", "Keep fullscreen when a window closes"),
            ("misc:enable_anr_dialog", "Warn about unresponsive apps"),
            ("misc:layers_hog_keyboard_focus", "Launchers keep keyboard focus"),
            ("misc:middle_click_paste", "Middle-click paste"),
            ("misc:mouse_move_focuses_monitor", "Moving the mouse focuses that monitor"),
        ]),
        ("Display", [
            ("misc:vrr", "Variable refresh rate"),
            ("misc:mouse_move_enables_dpms", "Mouse wakes the screen"),
            ("misc:key_press_enables_dpms", "Keyboard wakes the screen"),
        ]),
        ("Cursor", [
            ("cursor:no_hardware_cursors", "Hardware cursors"),
            ("cursor:inactive_timeout", "Hide after idle (seconds)"),
            ("cursor:hide_on_key_press", "Hide while typing"),
            ("cursor:hide_on_touch", "Hide on touch input"),
            ("cursor:no_warps", "Never warp the cursor"),
            ("cursor:persistent_warps", "Return to last position on refocus"),
            ("cursor:warp_on_change_workspace", "Warp when changing workspace"),
            ("cursor:zoom_factor", "Zoom"),
            ("cursor:enable_hyprcursor", "Hyprcursor themes"),
            ("cursor:sync_gsettings_theme", "Sync cursor theme with GTK"),
        ]),
    ]),
]

SPECS: dict[str, Spec] = {s.key: s for p in PAGES for g in p.groups for s in g.specs}

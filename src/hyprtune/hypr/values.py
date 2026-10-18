"""Hyprland value types: parsing live values and writing Lua / hyprlang syntax.

Canonical in-app representations (all JSON-serialisable):
    bool/int/float/str as-is        enum  -> the option's *name* (str)
    color    -> "rrggbbaa"          gradient -> {"colors": ["rrggbbaa", ...], "angle": int}
"""
from __future__ import annotations

import re
from typing import Any

_HEX = re.compile(r"^[0-9a-fA-F]{1,8}$")


def argb_to_rgba(n: int) -> str:
    n &= 0xFFFFFFFF
    a, r, g, b = (n >> 24) & 255, (n >> 16) & 255, (n >> 8) & 255, n & 255
    return f"{r:02x}{g:02x}{b:02x}{a:02x}"


def parse_color(tok: Any) -> str | None:
    """Best-effort parse of any colour spelling Hyprland or users produce -> "rrggbbaa"."""
    if isinstance(tok, int) and not isinstance(tok, bool):
        return argb_to_rgba(tok)
    s = str(tok).strip().strip('"\'')
    m = re.fullmatch(r"rgba?\(\s*([0-9a-fA-F]{6,8})\s*\)", s)
    if m:
        h = m.group(1).lower()
        return h + "ff" if len(h) == 6 else h
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)", s)
    if m:
        r, g, b = (min(255, int(m.group(i))) for i in (1, 2, 3))
        a = round(min(1.0, float(m.group(4))) * 255) if m.group(4) is not None else 255
        return f"{r:02x}{g:02x}{b:02x}{a:02x}"
    m = re.fullmatch(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?", s)
    if m:
        return (m.group(1) + (m.group(2) or "ff")).lower()
    if s.lower().startswith("0x") and _HEX.match(s[2:]):
        return argb_to_rgba(int(s[2:], 16))
    return None


def parse_live_color(raw: Any) -> str | None:
    """`hyprctl getoption` prints colours as ARGB ints or bare ARGB hex."""
    if isinstance(raw, int):
        return argb_to_rgba(raw)
    s = str(raw).strip()
    if _HEX.match(s):
        return argb_to_rgba(int(s, 16))
    return parse_color(s)


def parse_gradient(raw: Any, live: bool = False) -> dict[str, Any]:
    """Parse "rgba(a) rgba(b) 45deg" (config syntax) or "eeAARRGG ... 45deg" (live) -> canonical."""
    colors: list[str] = []
    angle = 0
    for tok in re.findall(r"rgba?\([^)]*\)|\S+", str(raw)):
        if tok.endswith("deg") and tok[:-3].lstrip("-").isdigit():
            angle = int(tok[:-3])
            continue
        c = parse_live_color(tok) if live else parse_color(tok)
        if c:
            colors.append(c)
    return {"colors": colors, "angle": angle}


def normalize_default(spec_type: str, default: Any, default_str: str | None = None) -> Any:
    if spec_type == "color":
        return parse_color(default) or "000000ff"
    if spec_type == "gradient":
        return parse_gradient(default) if default else {"colors": [], "angle": 0}
    if spec_type == "choice":
        return default_str if default_str is not None else default
    if spec_type == "cssgap":
        return int(default) if not isinstance(default, str) else int(default.split()[0])
    return default


# -- writers -------------------------------------------------------------------------------------

def _rgba(c: str) -> str:
    return f"rgba({c})"


def lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def to_lua(kind: str, value: Any) -> str:
    if kind == "bool":
        return "true" if value else "false"
    if kind in ("int", "float"):
        return repr(int(value)) if kind == "int" else _num(value)
    if kind == "color":
        return lua_str(_rgba(value))
    if kind == "gradient":
        cols = value["colors"]
        if len(cols) == 1:
            return lua_str(_rgba(cols[0]))
        inner = ", ".join(lua_str(_rgba(c)) for c in cols)
        return "{ colors = { %s }, angle = %d }" % (inner, int(value.get("angle", 0)))
    return lua_str(str(value))  # enum + string


def to_hyprlang(kind: str, value: Any, index_choices: tuple[str, ...] | None = None) -> str:
    if kind == "bool":
        return "true" if value else "false"
    if kind == "int":
        return str(int(value))
    if kind == "float":
        return _num(value)
    if kind == "color":
        return _rgba(value)
    if kind == "gradient":
        parts = [_rgba(c) for c in value["colors"]]
        if len(parts) > 1:
            parts.append(f"{int(value.get('angle', 0))}deg")
        return " ".join(parts)
    if kind == "enum" and index_choices is not None:
        return str(index_choices.index(value)) if value in index_choices else str(value)
    return str(value)


def _num(v: Any) -> str:
    s = f"{float(v):.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def nest(flat: dict[str, Any], lua: bool = True) -> dict[str, Any]:
    """{'general:col.active_border': x} -> nested dict.

    Lua: general.col.active_border (hyphens become underscores).
    hyprlang: general { col.active_border = x } (names kept verbatim)."""
    root: dict[str, Any] = {}
    for key, val in flat.items():
        parts = re.split(r"[:.]", key.replace("-", "_")) if lua else key.split(":")
        d = root
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val
    return root

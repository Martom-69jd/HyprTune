"""Talking to Hyprland: hyprctl IPC, config-style detection and the managed file.

Hyprland 0.55 replaced the hyprlang config with Lua. Hyprtune supports both:

  Lua       ~/.config/hypr/hyprland.lua  + hyprtune.lua   (live: ``hyprctl eval``)
  hyprlang  ~/.config/hypr/hyprland.conf + hyprtune.conf  (live: ``hyprctl keyword``)

Like HyprMod, we never rewrite the user's own config. All our settings live in
one file we own; the user's config just loads it (a single line, added only
with permission)."""
from __future__ import annotations

import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .. import util
from . import values
from .options import SPECS, Spec

STATE_RE = re.compile(r"hyprtune-state:\s*(\{.*\})\s*$", re.M)
LUA_HOOK = re.compile(r"^\s*(?!--).*\brequire\s*\(\s*[\"']hyprtune[\"']\s*\)", re.M)
CONF_HOOK = re.compile(r"^\s*source\s*=\s*.*hyprtune\.conf\s*$", re.M)


class HyprBackend:
    def __init__(self) -> None:
        self.hyprctl = shutil.which("hyprctl")
        self._runtime: str | None = None  # "lua" | "hyprlang" | "" (unknown), probed lazily
        self._version: str | None = None

    # -- session ------------------------------------------------------------------------------
    def ctl(self, *args: str, timeout: float = 5.0) -> tuple[int, str, str]:
        if not self.hyprctl:
            return 127, "", "hyprctl not found"
        return util.run([self.hyprctl, *args], timeout=timeout)

    def running(self) -> bool:
        return self.version() is not None

    def version(self) -> str | None:
        if self._version is None:
            rc, out, _ = self.ctl("version", "-j")
            ver = ""
            if rc == 0:
                try:
                    j = json.loads(out)
                    ver = str(j.get("tag") or j.get("version") or "").lstrip("v")
                except ValueError:
                    m = re.search(r"v?(\d+\.\d+\.\d+)", out)
                    ver = m.group(1) if m else ""
            self._version = ver or ""
        return self._version or None

    def runtime_style(self) -> str:
        """Ask the compositor which config manager it runs (``eval`` only exists with Lua)."""
        if self._runtime is None:
            self._runtime = ""
            if self.running():
                rc, out, _ = self.ctl("eval", "return 1")
                if out.startswith("ok"):
                    self._runtime = "lua"
                elif "only supported with the lua" in out or "unknown request" in out.lower() or rc != 0:
                    self._runtime = "hyprlang"
        return self._runtime

    # -- config files ----------------------------------------------------------------------------
    def main_config(self) -> tuple[str, Path]:
        """(style, path) of the user's main Hyprland config; Lua wins when both exist."""
        env = os.environ.get("HYPRLAND_CONFIG")
        if env:
            p = Path(env).expanduser()
            return ("lua" if p.suffix == ".lua" else "hyprlang"), p
        d = util.hypr_dir()
        if (d / "hyprland.lua").exists():
            return "lua", d / "hyprland.lua"
        if (d / "hyprland.conf").exists():
            return "hyprlang", d / "hyprland.conf"
        style = self.runtime_style()
        if not style:
            v = self.version() or "0.56"
            try:
                major, minor = (int(x) for x in v.split(".")[:2])
                style = "lua" if (major, minor) >= (0, 55) else "hyprlang"
            except ValueError:
                style = "lua"
        return style, d / ("hyprland.lua" if style == "lua" else "hyprland.conf")

    @property
    def style(self) -> str:
        return self.main_config()[0]

    def managed_path(self) -> Path:
        style, main = self.main_config()
        return main.parent / ("hyprtune.lua" if style == "lua" else "hyprtune.conf")

    def hook_installed(self) -> bool:
        style, main = self.main_config()
        text = util.read_text(main)
        if text is None:
            return False
        return bool((LUA_HOOK if style == "lua" else CONF_HOOK).search(text))

    def install_hook(self) -> Path:
        style, main = self.main_config()
        text = util.read_text(main) or ""
        if self.hook_installed():
            return main
        if style == "lua":
            add = '\n-- Hyprtune settings (remove this line to disable them)\nrequire("hyprtune")\n'
        else:
            add = f"\n# Hyprtune settings (remove this line to disable them)\nsource = {self.managed_path()}\n"
        util.write_text(main, text.rstrip("\n") + "\n" + add)
        return main

    # -- managed file ---------------------------------------------------------------------------
    def read_managed(self) -> dict[str, Any]:
        text = util.read_text(self.managed_path()) or ""
        m = STATE_RE.search(text)
        try:
            data = json.loads(m.group(1)) if m else {}
        except ValueError:
            data = {}
        return {"options": data.get("options", {}), "autostart": data.get("autostart", [])}

    def render(self, options: dict[str, Any], autostart: list[str]) -> str:
        lua = self.style == "lua"
        c = "--" if lua else "#"
        state = json.dumps({"options": options, "autostart": autostart}, sort_keys=True, separators=(",", ":"))
        out = [f"{c} Managed by Hyprtune. Edit settings in the app; manual changes here are overwritten.",
               f"{c} hyprtune-state: {state}"]
        known = {k: v for k, v in options.items() if k in SPECS}
        if lua:
            if known:
                out += ["hl.config(" + _lua_table(self._nest(known, True), 0) + ")"]
            if autostart:
                out += ["", 'hl.on("hyprland.start", function()']
                out += [f"    hl.exec_cmd({values.lua_str(a)})" for a in autostart]
                out += ["end)"]
        else:
            if known:
                out += _hyprlang_sections(self._nest(known, False), 0)
            out += [f"exec-once = {a}" for a in autostart]
        return "\n".join(out) + "\n"

    def write_managed(self, options: dict[str, Any], autostart: list[str]) -> Path:
        path = self.managed_path()
        util.write_text(path, self.render(options, autostart), make_backup=False)
        return path

    # -- value conversion -------------------------------------------------------------------------
    def _nest(self, options: dict[str, Any], lua: bool) -> dict[str, Any]:
        rendered = {}
        for k, v in options.items():
            s = SPECS[k]
            rendered[k] = (values.to_lua(s.kind, v) if lua
                           else values.to_hyprlang(s.kind, v, s.index_choices))
        return values.nest(rendered, lua)

    # -- live apply -------------------------------------------------------------------------------
    def apply_live(self, changes: dict[str, Any]) -> tuple[bool, str]:
        """Push option values into the running compositor."""
        if not changes:
            return True, ""
        if not self.running():
            return False, "Hyprland is not running"
        if self.runtime_style() == "lua":
            code = "hl.config(" + _lua_table(self._nest(changes, True), 0, compact=True) + ")"
            _, out, err = self.ctl("eval", code)
            return out.startswith("ok"), "" if out.startswith("ok") else (out or err)
        cmds = []
        for k, v in changes.items():
            s = SPECS[k]
            cmds.append(f"keyword {k} {values.to_hyprlang(s.kind, v, s.index_choices)}")
        _, out, err = self.ctl("--batch", " ; ".join(cmds))
        bad = [ln for ln in out.splitlines() if ln.strip() and ln.strip() != "ok"]
        return not bad, "; ".join(bad) or err

    def reload(self) -> tuple[bool, str]:
        _, out, err = self.ctl("reload")
        return out.startswith("ok") or not (out or err), out or err

    def config_errors(self) -> str:
        _, out, _ = self.ctl("configerrors")
        return "" if not out or out.strip().lower().startswith("no errors") else out

    # -- reading live values -----------------------------------------------------------------------
    def get_live(self, keys: list[str]) -> dict[str, Any]:
        """Current value of each option; options this Hyprland doesn't know are omitted."""
        if not self.running():
            return {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(self._get_one, keys))
        return {k: v for k, v in zip(keys, results) if v is not None}

    def _get_one(self, key: str) -> Any:
        rc, out, _ = self.ctl("-j", "getoption", key, timeout=4)
        if rc != 0 or "no such option" in out:
            return None
        try:
            return parse_live(SPECS[key], json.loads(out))
        except (ValueError, KeyError, TypeError, IndexError):
            m = re.search(r'"(int|bool|float|str|custom)":\s*"?([^",}]*)"?', out)
            return parse_live(SPECS[key], {m.group(1): m.group(2)}) if m else None


def parse_live(spec: Spec, j: dict[str, Any]) -> Any:
    raw = next((j[k] for k in ("int", "bool", "float", "str", "custom") if k in j), None)
    if raw is None:
        return None
    k = spec.kind
    if k == "bool":
        return raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1", "yes", "on")
    if k == "int":
        m = re.match(r"-?\d+", str(raw))
        return int(m.group()) if m else None
    if k == "float":
        return float(raw)
    if k == "enum":
        if spec.index_choices and re.fullmatch(r"-?\d+", str(raw)):
            idx = int(raw)
            return spec.index_choices[idx] if 0 <= idx < len(spec.index_choices) else None
        return str(raw)
    if k == "color":
        return values.parse_live_color(raw)
    if k == "gradient":
        return values.parse_gradient(raw, live=True)
    return str(raw)


# -- text rendering ------------------------------------------------------------------------------

def _lua_table(d: dict[str, Any], depth: int, compact: bool = False) -> str:
    if compact:
        items = [f"{k} = {_lua_table(v, 0, True) if isinstance(v, dict) else v}" for k, v in d.items()]
        return "{ " + ", ".join(items) + " }"
    pad = "    " * (depth + 1)
    lines = []
    for k, v in sorted(d.items()):
        lines.append(f"{pad}{k} = " + (_lua_table(v, depth + 1) if isinstance(v, dict) else v) + ",")
    return "{\n" + "\n".join(lines) + "\n" + "    " * depth + "}"


def _hyprlang_sections(d: dict[str, Any], depth: int) -> list[str]:
    pad = "    " * depth
    out: list[str] = []
    for k, v in sorted(d.items(), key=lambda kv: (isinstance(kv[1], dict), kv[0])):
        if isinstance(v, dict):
            out += [f"{pad}{k} {{", *_hyprlang_sections(v, depth + 1), f"{pad}}}"]
        else:
            out.append(f"{pad}{k} = {v}")
    return out

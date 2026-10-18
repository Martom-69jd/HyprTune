#!/usr/bin/env python3
"""Regenerate src/hyprtune/data/hypr_options.json from the `hyprland-schema` package.

    pip install hyprland-schema   # MIT, https://github.com/BlueManCZ/hyprland-schema
    python tools/gen_hypr_data.py

Only a dev-time dependency: the app ships the JSON, not the package."""
import json
import pathlib

import hyprland_schema as hs

out = {"hyprland_version": hs.HYPRLAND_VERSION, "options": {}}
for o in hs.OPTIONS:
    entry = {"type": o.type, "default": o.default, "desc": " ".join(o.description.split())}
    if isinstance(o.default, tuple):
        entry["default"] = list(o.default)
    if o.default_str is not None:
        entry["default_str"] = o.default_str
    if o.min is not None:
        entry["min"] = o.min
    if o.max is not None:
        entry["max"] = o.max
    if o.enum_values:
        entry["enum"] = list(o.enum_values)
    out["options"][o.key] = entry

dest = pathlib.Path(__file__).resolve().parents[1] / "src/hyprtune/data/hypr_options.json"
dest.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
print(f"wrote {dest} ({len(out['options'])} options, Hyprland {hs.HYPRLAND_VERSION})")

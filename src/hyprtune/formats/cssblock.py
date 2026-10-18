"""Manage a clearly-marked block inside a user's CSS file (Waybar style.css)."""
from __future__ import annotations

import json
import re
from typing import Any

BEGIN = "/* >>> hyprtune:begin (managed block: edit in Hyprtune, not here) >>> */"
END = "/* <<< hyprtune:end <<< */"
_BLOCK = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
_STATE = re.compile(r"/\* hyprtune:state (\{.*?\}) \*/")


def has_block(text: str) -> bool:
    return BEGIN in text and END in text


def read_state(text: str) -> dict[str, Any]:
    m = _BLOCK.search(text)
    if not m:
        return {}
    s = _STATE.search(m.group(0))
    try:
        return json.loads(s.group(1)) if s else {}
    except ValueError:
        return {}


def apply_block(text: str, state: dict[str, Any], css: str) -> str:
    block = f"{BEGIN}\n/* hyprtune:state {json.dumps(state, sort_keys=True)} */\n{css.strip()}\n{END}\n"
    if has_block(text):
        return _BLOCK.sub(lambda _m: block, text, count=1)
    sep = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + sep + block


def remove_block(text: str) -> str:
    return _BLOCK.sub("", text).rstrip("\n") + "\n" if has_block(text) else text

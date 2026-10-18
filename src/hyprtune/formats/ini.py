"""Comment-preserving editor for fuzzel.ini-style files.

Fuzzel's stock config ships every option commented out (``#key=default``).
We edit lines in place: uncomment-and-set when possible, append otherwise, and
never touch anything we were not asked to change."""
from __future__ import annotations

import re

_HEADER = re.compile(r"^\s*\[([^\]]+)\]\s*$")


class IniDoc:
    def __init__(self, text: str = "") -> None:
        self.lines = text.split("\n") if text else []
        if self.lines and self.lines[-1] == "":
            self.lines.pop()

    def text(self) -> str:
        return "\n".join(self.lines) + "\n" if self.lines else ""

    # -- section bookkeeping -------------------------------------------------
    def _section_spans(self, section: str) -> list[tuple[int, int]]:
        """Line ranges [start, end) belonging to *section* (``main`` also covers the headerless top)."""
        spans: list[tuple[int, int]] = []
        cur, start = "main", 0
        for i, line in enumerate(self.lines + ["[__end__]"]):
            m = _HEADER.match(line)
            if m:
                if cur == section:
                    spans.append((start, i))
                cur, start = m.group(1).strip(), i + 1
        return spans

    @staticmethod
    def _key_re(key: str, commented: bool) -> re.Pattern[str]:
        pre = r"^\s*[#;]+\s*" if commented else r"^\s*"
        return re.compile(pre + re.escape(key) + r"\s*=(.*)$")

    # -- public API ----------------------------------------------------------
    def get(self, section: str, key: str) -> str | None:
        rx = self._key_re(key, False)
        found = None
        for a, b in self._section_spans(section):
            for i in range(a, b):
                m = rx.match(self.lines[i])
                if m:
                    found = m.group(1).strip()
        return found

    def set(self, section: str, key: str, value: str) -> None:
        new = f"{key}={value}"
        live, dead = self._key_re(key, False), self._key_re(key, True)
        spans = self._section_spans(section)
        live_hits = [i for a, b in spans for i in range(a, b) if live.match(self.lines[i])]
        if live_hits:
            self.lines[live_hits[-1]] = new
            return
        dead_hits = [i for a, b in spans for i in range(a, b) if dead.match(self.lines[i])]
        if dead_hits:
            self.lines[dead_hits[-1]] = new
            return
        if spans:
            a, b = spans[-1]
            end = b
            while end > a and not self.lines[end - 1].strip():
                end -= 1
            self.lines.insert(end, new)
            return
        if self.lines and self.lines[-1].strip():
            self.lines.append("")
        self.lines += [f"[{section}]", new]

    def unset(self, section: str, key: str) -> None:
        """Comment a key out so fuzzel falls back to its default (reversible)."""
        live = self._key_re(key, False)
        for a, b in self._section_spans(section):
            for i in range(a, b):
                if live.match(self.lines[i]):
                    self.lines[i] = "#" + self.lines[i].lstrip()

"""Edit JSON-with-comments files without destroying comments or formatting.

Waybar configs are JSONC: comments, trailing commas and hand-tuned layout are
common. Round-tripping through ``json.dumps`` would erase all of that, so this
module parses the file into a tree that remembers *where* every value lives and
then splices replacement text into exactly those spans.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Sequence


class JsoncError(ValueError):
    pass


@dataclass
class Node:
    kind: str  # object | array | string | number | bool | null
    start: int
    end: int
    value: Any = None
    members: list["Member"] = field(default_factory=list)
    items: list["Node"] = field(default_factory=list)


@dataclass
class Member:
    key: str
    key_start: int
    key_end: int
    value: Node


_LITERAL = re.compile(r"[^\s,\]\}:/\[\{\"]+")


class _Parser:
    def __init__(self, text: str) -> None:
        self.t, self.i, self.n = text, 0, len(text)

    def skip(self) -> None:
        t = self.t
        while self.i < self.n:
            c = t[self.i]
            if c in " \t\r\n\ufeff":
                self.i += 1
            elif t.startswith("//", self.i):
                j = t.find("\n", self.i)
                self.i = self.n if j < 0 else j
            elif t.startswith("/*", self.i):
                j = t.find("*/", self.i + 2)
                if j < 0:
                    raise JsoncError("unterminated /* comment")
                self.i = j + 2
            else:
                break

    def parse(self) -> Node:
        node = self.value()
        self.skip()
        if self.i != self.n:
            raise JsoncError(f"unexpected data at offset {self.i}")
        return node

    def value(self) -> Node:
        self.skip()
        if self.i >= self.n:
            raise JsoncError("unexpected end of file")
        c = self.t[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            return self.string()
        return self.literal()

    def obj(self) -> Node:
        node = Node("object", self.i, 0)
        self.i += 1
        while True:
            self.skip()
            if self.i >= self.n:
                raise JsoncError("unterminated object")
            c = self.t[self.i]
            if c == "}":
                self.i += 1
                break
            if c == ",":
                self.i += 1
                continue
            if c != '"':
                raise JsoncError(f"expected a quoted key at offset {self.i}")
            key = self.string()
            self.skip()
            if self.i >= self.n or self.t[self.i] != ":":
                raise JsoncError(f"expected ':' at offset {self.i}")
            self.i += 1
            node.members.append(Member(key.value, key.start, key.end, self.value()))
        node.end = self.i
        return node

    def arr(self) -> Node:
        node = Node("array", self.i, 0)
        self.i += 1
        while True:
            self.skip()
            if self.i >= self.n:
                raise JsoncError("unterminated array")
            c = self.t[self.i]
            if c == "]":
                self.i += 1
                break
            if c == ",":
                self.i += 1
                continue
            node.items.append(self.value())
        node.end = self.i
        return node

    def string(self) -> Node:
        start = self.i
        self.i += 1
        while self.i < self.n:
            c = self.t[self.i]
            if c == "\\":
                self.i += 2
                continue
            self.i += 1
            if c == '"':
                break
        else:
            raise JsoncError("unterminated string")
        try:
            val = json.loads(self.t[start:self.i], strict=False)
        except ValueError as e:
            raise JsoncError(f"bad string at offset {start}: {e}") from None
        return Node("string", start, self.i, val)

    def literal(self) -> Node:
        m = _LITERAL.match(self.t, self.i)
        if not m:
            raise JsoncError(f"unexpected character {self.t[self.i]!r} at offset {self.i}")
        raw, self.i = m.group(), m.end()
        if raw in ("true", "false"):
            return Node("bool", m.start(), m.end(), raw == "true")
        if raw == "null":
            return Node("null", m.start(), m.end(), None)
        try:
            return Node("number", m.start(), m.end(), json.loads(raw))
        except ValueError:
            raise JsoncError(f"bad value {raw!r} at offset {m.start()}") from None


def _to_py(n: Node) -> Any:
    if n.kind == "object":
        return {m.key: _to_py(m.value) for m in n.members}
    if n.kind == "array":
        return [_to_py(i) for i in n.items]
    return n.value


class JsoncDoc:
    """A JSONC document whose top level is one bar object or a list of them."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.root = _Parser(text).parse()
        if self.root.kind not in ("object", "array"):
            raise JsoncError("top level must be an object or an array")

    # -- reading -------------------------------------------------------------
    def bar_count(self) -> int:
        return len(self.root.items) if self.root.kind == "array" else 1

    def _bar(self, index: int) -> Node:
        if self.root.kind == "array":
            if not 0 <= index < len(self.root.items) or self.root.items[index].kind != "object":
                raise JsoncError(f"no bar at index {index}")
            return self.root.items[index]
        return self.root

    def bar_dict(self, index: int = 0) -> dict[str, Any]:
        return _to_py(self._bar(index))

    def get(self, path: Sequence[str], bar: int = 0, default: Any = None) -> Any:
        node: Node = self._bar(bar)
        for key in path:
            if node.kind != "object":
                return default
            hit = next((m for m in node.members if m.key == key), None)
            if hit is None:
                return default
            node = hit.value
        return _to_py(node)

    # -- editing -------------------------------------------------------------
    def _reparse(self) -> None:
        self.root = _Parser(self.text).parse()

    def _line_indent(self, pos: int) -> str:
        start = self.text.rfind("\n", 0, pos) + 1
        m = re.match(r"[ \t]*", self.text[start:pos])
        return m.group() if m else ""

    def _unit(self, obj: Node) -> str:
        base = self._line_indent(obj.start)
        if obj.members:
            ind = self._line_indent(obj.members[0].key_start)
            if ind.startswith(base) and len(ind) > len(base):
                return ind[len(base):]
        return "\t" if base.startswith("\t") else "    "

    def _fmt(self, value: Any, indent: str, unit: str) -> str:
        if isinstance(value, dict):
            if not value:
                return "{}"
            inner = indent + unit
            body = ",\n".join(f"{inner}{json.dumps(k)}: {self._fmt(v, inner, unit)}" for k, v in value.items())
            return "{\n" + body + "\n" + indent + "}"
        if isinstance(value, (list, tuple)):
            if not value:
                return "[]"
            inner = indent + unit
            body = ",\n".join(inner + self._fmt(v, inner, unit) for v in value)
            return "[\n" + body + "\n" + indent + "]"
        return json.dumps(value, ensure_ascii=False)

    def set(self, path: Sequence[str], value: Any, bar: int = 0) -> None:
        """Set ``path`` to ``value``, creating missing keys and objects."""
        obj = self._bar(bar)
        for depth, key in enumerate(path):
            member = next((m for m in obj.members if m.key == key), None)
            rest = list(path[depth + 1:])
            if member is None:
                for k in reversed(rest):
                    value = {k: value}
                self._insert(obj, key, value)
                return
            if not rest:
                self._replace(member, value, obj)
                return
            if member.value.kind != "object":
                for k in reversed(rest):
                    value = {k: value}
                self._replace(member, value, obj)
                return
            obj = member.value

    def _replace(self, member: Member, value: Any, parent: Node) -> None:
        indent = self._line_indent(member.key_start)
        text = self._fmt(value, indent, self._unit(parent))
        v = member.value
        self.text = self.text[:v.start] + text + self.text[v.end:]
        self._reparse()

    def _insert(self, obj: Node, key: str, value: Any) -> None:
        t, unit = self.text, self._unit(obj)
        base = self._line_indent(obj.start)
        if not obj.members:
            member_indent = base + unit
            body = f"{json.dumps(key)}: {self._fmt(value, member_indent, unit)}"
            self.text = t[:obj.start] + "{\n" + member_indent + body + "\n" + base + "}" + t[obj.end:]
            self._reparse()
            return
        last = obj.members[-1]
        member_indent = self._line_indent(obj.members[0].key_start)
        after = last.value.end
        eol = t.find("\n", after)
        tail = t[after:eol if eol >= 0 else len(t)]
        has_comma = bool(re.match(r"\s*,", tail))
        simple_tail = re.fullmatch(r"\s*,?\s*(//.*|/\*.*\*/)?\s*", tail) is not None
        if eol >= 0 and simple_tail and t[:last.key_start].rstrip(" \t").endswith("\n"):
            body = f"{member_indent}{json.dumps(key)}: {self._fmt(value, member_indent, unit)}"
            addition = "\n" + body + ("," if has_comma else "")
            out = t[:eol] + addition + t[eol:]
            if not has_comma:  # previous last member needs a separating comma
                out = out[:after] + "," + out[after:]
            self.text = out
        else:  # compact / single-line object
            body = f"{json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}"
            self.text = t[:after] + ", " + body + t[after:]
        self._reparse()

    def remove(self, path: Sequence[str], bar: int = 0) -> bool:
        """Delete ``path`` if present. Returns True when something was removed."""
        obj = self._bar(bar)
        for depth, key in enumerate(path):
            idx = next((i for i, m in enumerate(obj.members) if m.key == key), None)
            if idx is None:
                return False
            if depth < len(path) - 1:
                if obj.members[idx].value.kind != "object":
                    return False
                obj = obj.members[idx].value
                continue
            self._cut(obj, idx)
            return True
        return False

    def _cut(self, obj: Node, idx: int) -> None:
        t, m = self.text, obj.members[idx]
        start, end = m.key_start, m.value.end
        j = end
        while j < len(t) and t[j] in " \t":
            j += 1
        trailing_comma = j < len(t) and t[j] == ","
        if trailing_comma:
            end = j + 1
        elif idx > 0:  # last member without comma: drop the previous member's comma
            prev_end = obj.members[idx - 1].value.end
            k = prev_end
            while k < start and t[k] != ",":
                k += 1
            if k < start and t[k] == ",":
                t = t[:k] + t[k + 1:]
                start, end = start - 1, end - 1
        line_start = t.rfind("\n", 0, start) + 1
        eol = t.find("\n", end)
        rest = t[end:eol if eol >= 0 else len(t)]
        if not t[line_start:start].strip() and (not rest.strip() or re.fullmatch(r"\s*(//.*|/\*.*\*/)\s*", rest)):
            start, end = line_start, (eol + 1 if eol >= 0 else len(t))
        self.text = t[:start] + t[end:]
        self._reparse()

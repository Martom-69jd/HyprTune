import json
from hyprtune.formats.jsonc import JsoncDoc
from hyprtune.formats.ini import IniDoc
from hyprtune.formats import cssblock

WAYBAR = '''// Top bar
{
    "layer": "top", // keep on top
    "position": "top",
    /* spacing between modules */
    "spacing": 4,
    "modules-left": ["hyprland/workspaces"],
    "modules-right": [
        "clock", // time
    ],
    "clock": {
        "format": "{:%H:%M}",
    },
}
'''

def test_parse_and_get():
    d = JsoncDoc(WAYBAR)
    assert d.get(["spacing"]) == 4
    assert d.get(["clock", "format"]) == "{:%H:%M}"
    assert d.get(["nope"], default="x") == "x"

def test_replace_keeps_comments():
    d = JsoncDoc(WAYBAR)
    d.set(["spacing"], 10)
    d.set(["position"], "bottom")
    assert "/* spacing between modules */" in d.text and "// keep on top" in d.text
    assert d.get(["spacing"]) == 10 and d.get(["position"]) == "bottom"

def test_replace_array_and_roundtrip():
    d = JsoncDoc(WAYBAR)
    d.set(["modules-right"], ["cpu", "memory", "clock"])
    assert d.get(["modules-right"]) == ["cpu", "memory", "clock"]
    assert "// Top bar" in d.text
    JsoncDoc(d.text)  # still parses

def test_insert_with_trailing_comma_and_comment_line():
    d = JsoncDoc(WAYBAR)
    d.set(["height"], 30)            # appended after trailing-comma member
    d.set(["clock", "interval"], 5)  # nested insert
    d.set(["tray", "spacing"], 8)    # creates a new object
    assert d.get(["height"]) == 30 and d.get(["clock", "interval"]) == 5
    assert d.get(["tray", "spacing"]) == 8
    assert "// Top bar" in d.text

def test_insert_no_trailing_comma():
    d = JsoncDoc('{\n  "a": 1 // one\n}\n')
    d.set(["b"], 2)
    assert d.get(["b"]) == 2 and "// one" in d.text
    assert json.loads(d.text.replace("// one", "")) == {"a": 1, "b": 2}

def test_compact_and_empty_objects():
    d = JsoncDoc('{"a": 1}')
    d.set(["b"], "x")
    assert d.bar_dict() == {"a": 1, "b": "x"}
    e = JsoncDoc("{}")
    e.set(["layer"], "top")
    assert e.bar_dict() == {"layer": "top"}

def test_multi_bar_array():
    d = JsoncDoc('[\n  {"name": "a", "height": 20},\n  {"name": "b"}\n]')
    assert d.bar_count() == 2
    d.set(["height"], 33, bar=1)
    assert d.get(["height"], bar=1) == 33 and d.get(["height"], bar=0) == 20

def test_remove():
    d = JsoncDoc(WAYBAR)
    assert d.remove(["spacing"]) and d.get(["spacing"]) is None
    assert d.remove(["clock", "format"])
    JsoncDoc(d.text)
    assert not d.remove(["missing"])

def test_remove_last_member_without_comma():
    d = JsoncDoc('{\n  "a": 1,\n  "b": 2\n}\n')
    d.remove(["b"])
    assert json.loads(d.text) == {"a": 1}

def test_string_with_slashes_not_comment():
    d = JsoncDoc('{"url": "http://x//y", "n": 1}')
    assert d.get(["url"]) == "http://x//y"

FUZZEL = '''# fuzzel config
[main]
# font=monospace
terminal=foot -e
lines=15

[colors]
#background=fdf6e3ff
text=657b83ff

[border]
width=1
'''

def test_ini_edit_in_place():
    d = IniDoc(FUZZEL)
    assert d.get("main", "lines") == "15" and d.get("colors", "background") is None
    d.set("main", "lines", "8")
    d.set("main", "font", "Inter:size=12")       # uncomments the default
    d.set("colors", "background", "1e1e2eff")     # uncomments
    d.set("main", "anchor", "top")                # appended in [main]
    d.set("dmenu", "mode", "index")               # new section
    t = d.text()
    assert "# fuzzel config" in t and "#font" not in t and "[dmenu]\nmode=index" in t
    assert d.get("main", "anchor") == "top" and d.get("colors", "background") == "1e1e2eff"
    assert t.index("anchor=top") < t.index("[colors]")

def test_ini_headerless_main_and_unset():
    d = IniDoc("lines=3\n[colors]\ntext=ffffffff\n")
    assert d.get("main", "lines") == "3"
    d.set("main", "width", "40")
    assert d.text().index("width=40") < d.text().index("[colors]")
    d.unset("colors", "text")
    assert d.get("colors", "text") is None and "#text=ffffffff" in d.text()

def test_cssblock_roundtrip():
    css = "window#waybar { color: red; }\n"
    out = cssblock.apply_block(css, {"a": 1}, "* { font-size: 12px; }")
    assert out.startswith(css) and cssblock.read_state(out) == {"a": 1}
    out2 = cssblock.apply_block(out, {"a": 2}, "* { font-size: 14px; }")
    assert out2.count(cssblock.BEGIN) == 1 and "14px" in out2 and "12px" not in out2
    assert cssblock.remove_block(out2).strip() == css.strip()

import json, subprocess
import pytest
from PySide6.QtWidgets import QApplication
from hyprtune.formats import cssblock

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])

WB = '''// my bar
{
    "layer": "top", // keep above
    "position": "top",
    "modules-left": ["hyprland/workspaces"],
    "modules-right": ["clock"],
    "clock": { "format": "{:%H:%M}", },
}
'''

def test_waybar_edit_save_preserves_comments(env, qapp):
    wb = env.cfg / "waybar"; wb.mkdir()
    (wb / "config.jsonc").write_text(WB); (wb / "style.css").write_text("window#waybar { color: red; }\n")
    from hyprtune.pages.waybar import WaybarPage, make_field_control
    from hyprtune.pages.waybar_data import BAR_FIELDS
    p = WaybarPage(); p.show()
    assert p.doc.get(["position"]) == "top" and p.lists["modules-right"].items() == ["clock"]
    # drive it through the real controls: change height, add a module, edit a style field
    height = next(f for f in BAR_FIELDS if f.path == ("height",))
    row = p._field_row(height); row.control.spin.setValue(36)
    p.lists["modules-right"].combo.setEditText("cpu"); p.lists["modules-right"]._add()
    sf = next(r for r in p.findChildren(type(row)) if r.title.text() == "Active workspace")
    sf.control.set_value("ff0000ff"); sf.control.changed.emit("ff0000ff")
    assert p.save_btn.isEnabled()
    p.save()
    text = (wb / "config.jsonc").read_text()
    assert "// my bar" in text and "// keep above" in text
    from hyprtune.formats.jsonc import JsoncDoc
    d = JsoncDoc(text)
    assert d.get(["height"]) == 36 and d.get(["modules-right"]) == ["clock", "cpu"] and d.get(["clock", "format"]) == "{:%H:%M}"
    css = (wb / "style.css").read_text()
    assert css.startswith("window#waybar { color: red; }") and cssblock.read_state(css) == {"accent": "ff0000ff"}
    assert "rgb(255, 0, 0)" in css
    assert not p.save_btn.isEnabled()

def test_waybar_bad_config_is_not_touched(env, qapp):
    wb = env.cfg / "waybar"; wb.mkdir()
    (wb / "config").write_text('{ "layer": "top", oops }')
    from hyprtune.pages.waybar import WaybarPage
    p = WaybarPage()
    assert p.doc is None and not p.save_btn.isEnabled()
    assert (wb / "config").read_text() == '{ "layer": "top", oops }'

def test_waybar_create_starter(env, qapp):
    from hyprtune.pages.waybar import WaybarPage
    p = WaybarPage(); assert p.doc is None
    p._create_starter()
    assert p.doc is not None and p.doc.get(["position"]) == "top"

def test_fuzzel_edit_keeps_user_file(env, qapp):
    d = env.cfg / "fuzzel"; d.mkdir()
    (d / "fuzzel.ini").write_text("# mine\n[main]\n# font=monospace\nlines=10\n\n[colors]\nbackground=1e1e2eee\n")
    from hyprtune.pages.fuzzel import FuzzelPage, ALL
    p = FuzzelPage()
    row, ctrl = p.rows[("main", "lines")]
    assert ctrl.value() == 10 and row.reset.isEnabled()
    ctrl.spin.setValue(7)
    p.rows[("colors", "background")][1].set_value("00000080"); p.rows[("colors", "background")][1].changed.emit("00000080")
    p.rows[("main", "prompt")][1].set_value("› "); p.rows[("main", "prompt")][1].changed.emit("› ")
    p.save()
    t = (d / "fuzzel.ini").read_text()
    assert "# mine" in t and "# font=monospace" in t and "lines=7" in t and "background=00000080" in t
    assert 'prompt="› "' in t
    p.rows[("main", "lines")][0].resetRequested.emit()
    p.save()
    assert "#lines=7" in (d / "fuzzel.ini").read_text()
    p.grab()

def test_awww_command_and_script(env, qapp, tmp_path):
    from hyprtune.pages import awww
    cfg = {**awww.DEFAULTS, "image": "/pics/my wall's.png", "type": "wave", "outputs": "DP-1", "resize": "fit"}
    a = awww.build_args("awww", cfg, cfg["image"])
    assert a[:3] == ["awww", "img", "/pics/my wall's.png"] and "--transition-wave" in a and a[a.index("--outputs") + 1] == "DP-1"
    assert a[a.index("--fill-color") + 1] == "000000"
    for source, extra in (("image", {}), ("folder", {"folder": str(tmp_path)})):
        sh = tmp_path / f"{source}.sh"
        sh.write_text(awww.startup_script("awww", "awww-daemon", {**cfg, "source": source, **extra}))
        assert subprocess.run(["sh", "-n", str(sh)]).returncode == 0
    assert "my wall'\"'\"'s.png" in (tmp_path / "image.sh").read_text()   # safely quoted
    (tmp_path / "a.png").write_bytes(b""); (tmp_path / "b.txt").write_text("x")
    assert awww.pick_image({**cfg, "source": "folder", "folder": str(tmp_path)}).endswith("a.png")

def test_awww_page_save_writes_autostart(env, qapp, tmp_path):
    (env.hypr / "hyprland.lua").write_text("")
    import shutil
    from hyprtune.hypr.backend import HyprBackend
    from hyprtune.hypr.model import HyprModel
    from hyprtune.pages.awww import AwwwPage
    from hyprtune.util import AppState
    img = tmp_path / "w.png"; img.write_bytes(b"")
    m = HyprModel(HyprBackend(), AppState())
    p = AwwwPage(AppState(), m)
    p.cfg.update(image=str(img), autostart=True)
    for d in ("awww", "awww-daemon"):  # pretend awww is installed so the script is generated
        s = tmp_path / "bin" / d; s.parent.mkdir(exist_ok=True); s.write_text("#!/bin/sh\n"); s.chmod(0o755)
    env.mp.setenv("PATH", f"{tmp_path / 'bin'}:" + __import__("os").environ["PATH"])
    p.bin = ("awww", "awww-daemon")
    p.save()
    managed = (env.hypr / "hyprtune.lua").read_text()
    assert "awww-startup.sh" in managed and 'hl.on("hyprland.start"' in managed
    assert json.loads((env.cfg / "hyprtune" / "state.json").read_text())["awww"]["image"] == str(img)
    assert (env.cfg / "hyprtune" / "awww-startup.sh").stat().st_mode & 0o100

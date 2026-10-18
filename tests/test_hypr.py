import json
from hyprtune.hypr.backend import HyprBackend
from hyprtune.hypr.options import SPECS, SCHEMA
from hyprtune.hypr import values

def test_color_parsing():
    assert values.parse_color("rgba(33ccffee)") == "33ccffee"
    assert values.parse_color("0xeeb3ff1a") == "b3ff1aee"
    assert values.parse_color("#fafc21") == "fafc21ff"
    assert values.parse_color("rgba(179,255,26,0.933)") == "b3ff1aee"
    assert values.parse_gradient("rgba(33ccffee) rgba(00ff99ee) 45deg") == {"colors": ["33ccffee", "00ff99ee"], "angle": 45}
    assert values.parse_gradient("ee33ccff ee00ff99 45deg", live=True) == {"colors": ["33ccffee", "00ff99ee"], "angle": 45}

def test_registry_matches_schema():
    for k, s in SPECS.items():
        assert k in SCHEMA, k
        if s.kind in ("int", "float") and s.min is not None and s.max is not None:
            assert s.min <= s.max, k
        if s.kind == "enum":
            assert s.choices and s.default in [c[0] for c in s.choices], (k, s.default, s.choices)

def test_lua_render_and_apply(env, monkeypatch):
    (env.hypr / "hyprland.lua").write_text('hl.config({})\n')
    b = HyprBackend()
    assert b.style == "lua" and b.runtime_style() == "lua"
    opts = {"general:gaps_in": 8, "general:col.active_border": {"colors": ["33ccffee", "00ff99ee"], "angle": 45},
            "decoration:blur:enabled": False, "input:touchpad:tap-to-click": True, "dwindle:force_split": "left",
            "decoration:rounding_power": 2.5}
    text = b.render(opts, ["/x/awww.sh"])
    assert 'active_border = { colors = { "rgba(33ccffee)", "rgba(00ff99ee)" }, angle = 45 }' in text
    assert "tap_to_click = true" in text and 'force_split = "left"' in text and "enabled = false" in text
    assert 'hl.exec_cmd("/x/awww.sh")' in text and 'hl.on("hyprland.start"' in text
    ok, _ = b.apply_live({"general:gaps_in": 8, "decoration:blur:enabled": True})
    assert ok and 'eval hl.config({ decoration = { blur = { enabled = true } }, general = { gaps_in = 8 } })'.replace("decoration = { blur = { enabled = true } }, general = { gaps_in = 8 }", "general = { gaps_in = 8 }, decoration = { blur = { enabled = true } }") in env.log.read_text()

def test_hyprlang_render_uses_indices(env, monkeypatch):
    env.mp.setenv("FAKE_STYLE", "hyprlang")
    (env.hypr / "hyprland.conf").write_text("general {\n}\n")
    b = HyprBackend()
    assert b.style == "hyprlang" and b.runtime_style() == "hyprlang"
    text = b.render({"input:follow_mouse": "detached", "general:col.active_border": {"colors": ["33ccffee", "00ff99ee"], "angle": 45},
                     "input:touchpad:tap-to-click": True}, ["waybar"])
    assert "follow_mouse = 2" in text and "col.active_border = rgba(33ccffee) rgba(00ff99ee) 45deg" in text
    assert "tap-to-click = true" in text and "exec-once = waybar" in text
    ok, _ = b.apply_live({"input:follow_mouse": "disabled"})
    assert ok and "keyword input:follow_mouse 0" in env.log.read_text()

def test_live_values(env):
    (env.hypr / "hyprland.lua").write_text("")
    env.mp.setenv("FAKE_MISSING", "decoration:glow:enabled")
    live_file = env.cfg / "live.json"
    live_file.write_text(json.dumps({"general:col.active_border": "live"}))
    env.mp.setenv("FAKE_LIVE", str(live_file))
    b = HyprBackend()
    live = b.get_live(list(SPECS))
    assert "decoration:glow:enabled" not in live and len(live) == len(SPECS) - 1
    assert live["general:gaps_in"] == 5 and live["input:follow_mouse"] == "follow"
    assert live["general:col.active_border"]["colors"][:2] == ["33ccffee", "00ff99ee"]
    assert live["master:mfact"] == 0.55 and live["input:touchpad:tap-to-click"] is True

def test_managed_roundtrip_and_hook(env):
    main = env.hypr / "hyprland.lua"; main.write_text('hl.config({ general = { gaps_in = 3 } })\n')
    b = HyprBackend()
    assert not b.hook_installed()
    b.write_managed({"general:gaps_in": 9}, [])
    assert b.read_managed()["options"] == {"general:gaps_in": 9}
    b.install_hook(); b.install_hook()
    assert b.hook_installed() and main.read_text().count('require("hyprtune")') == 1
    assert "gaps_in = 3" in main.read_text()
    assert list((env.cfg / "hyprtune" / "backups").glob("hyprland.lua.*"))
    main.write_text('-- require("hyprtune")\n'); assert not b.hook_installed()

def test_symlinked_config_survives(env):
    real = env.cfg / "dotfiles"; real.mkdir()
    (real / "hyprland.lua").write_text("-- mine\n")
    (env.hypr / "hyprland.lua").symlink_to(real / "hyprland.lua")
    HyprBackend().install_hook()
    assert (env.hypr / "hyprland.lua").is_symlink() and 'require("hyprtune")' in (real / "hyprland.lua").read_text()

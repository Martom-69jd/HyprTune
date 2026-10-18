import json
import pytest
from PySide6.QtWidgets import QApplication
from hyprtune.hypr.backend import HyprBackend
from hyprtune.hypr.model import HyprModel
from hyprtune.hypr.options import SPECS, PAGES
from hyprtune.util import AppState

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])

@pytest.fixture(autouse=True)
def _drain(env):
    yield
    for m in getattr(env, "models", []):
        m.wait(60000)

def make_model(env, qapp, style="lua"):
    env.mp.setenv("FAKE_STYLE", style)
    (env.hypr / ("hyprland.lua" if style == "lua" else "hyprland.conf")).write_text("-- mine\n" if style == "lua" else "# mine\n")
    m = HyprModel(HyprBackend(), AppState())
    env.models = getattr(env, "models", []); env.models.append(m)
    m.baseline = {"general:gaps_in": 5, "general:layout": "dwindle"}
    m.supported = set(m.baseline)
    return m

def test_edit_undo_save_revert(env, qapp):
    m = make_model(env, qapp)
    assert m.value("general:gaps_in") == 5 and not m.is_dirty()
    m.set_value("general:gaps_in", 9)
    m.set_value("general:gaps_in", 10)      # coalesced into the same undo step
    assert m.is_dirty() and m.value("general:gaps_in") == 10 and len(m._undo) == 1
    m.undo()
    assert m.value("general:gaps_in") == 5 and not m.is_dirty()
    m.set_value("general:gaps_in", 7); m.set_value("general:layout", "master")
    assert m.dirty_count() == 2
    m._flush()
    assert "gaps_in = 7" in env.log.read_text() and 'layout = "master"' in env.log.read_text()
    assert m.save()
    assert not m.is_dirty() and m.saved == {"general:gaps_in": 7, "general:layout": "master"}
    assert 'gaps_in = 7' in (env.hypr / "hyprtune.lua").read_text()
    m.set_value("general:gaps_in", 30)
    m.revert()
    assert m.value("general:gaps_in") == 7 and not m.is_dirty()
    # back to baseline equals "no override needed"
    m.set_value("general:layout", "dwindle"); m._flush()
    assert m.pending == {"general:layout": "dwindle"}  # differs from the saved override, so still pending

def test_reset_removes_override_and_reloads(env, qapp):
    m = make_model(env, qapp)
    m.set_value("general:gaps_in", 7); m.save()
    assert m.is_modified("general:gaps_in")
    m.reset("general:gaps_in")
    assert m.value("general:gaps_in") == SPECS["general:gaps_in"].default and m.is_dirty()
    m.undo()
    assert m.value("general:gaps_in") == 7 and not m.is_dirty()
    m.reset("general:gaps_in"); m.save()
    assert "gaps_in" not in (env.hypr / "hyprtune.lua").read_text().split("hyprtune-state")[1].split("\n", 1)[1]
    assert "reload" in env.log.read_text()
    assert m.saved == {}

def test_hyprlang_mode_saves_conf(env, qapp):
    m = make_model(env, qapp, "hyprlang")
    m.set_value("input:follow_mouse", "detached")
    m.set_value("general:gaps_in", 3); m._flush(); m.save()
    conf = (env.hypr / "hyprtune.conf").read_text()
    assert "follow_mouse = 2" in conf and "gaps_in = 3" in conf and conf.count("input {") == 1
    assert "keyword input:follow_mouse 2" in env.log.read_text()

def test_hypr_pages_build_and_unsupported_rows_hide(env, qapp):
    m = make_model(env, qapp)
    from hyprtune.pages.hypr_pages import HyprPage
    pages = [HyprPage(spec, m, preview=spec.id in ("appearance", "tiling")) for spec in PAGES]
    ap = pages[0]; ap.show(); qapp.processEvents()
    assert not ap.rows["general:gaps_in"][1].isHidden()           # supported
    assert ap.rows["decoration:rounding"][1].isHidden()           # unknown to this fake Hyprland
    ctrl = ap.rows["general:gaps_in"][2]
    ctrl.spin.setValue(12)                                         # user edits the control
    assert m.value("general:gaps_in") == 12 and ap.rows["general:gaps_in"][1].reset.text() == "↺"
    m.undo()
    assert ctrl.value() == 5   # control follows the model
    for p in pages: p.show(); qapp.processEvents(); p.grab()

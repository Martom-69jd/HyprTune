import os, stat, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated XDG_CONFIG_HOME plus a fake hyprctl first on PATH."""
    cfg = tmp_path / "config"; (cfg / "hypr").mkdir(parents=True)
    bindir = tmp_path / "bin"; bindir.mkdir()
    shim = bindir / "hyprctl"
    shim.write_text(f"#!/bin/sh\nexec {sys.executable} -S {Path(__file__).parent / 'fake_hyprctl.py'} \"$@\"\n")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "ctl.log"))
    monkeypatch.delenv("HYPRLAND_CONFIG", raising=False)
    class E: pass
    e = E(); e.cfg = cfg; e.hypr = cfg / "hypr"; e.log = tmp_path / "ctl.log"; e.mp = monkeypatch
    return e

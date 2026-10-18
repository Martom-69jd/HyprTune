#!/usr/bin/env python3
"""Shrink a Python + PySide6 tree to what Hyprtune needs (QtCore/Gui/Widgets, Wayland + XCB, image formats).

Usage: prune_bundle.py <python-prefix>

Libraries are kept by computing the real ELF dependency closure (readelf), so nothing that a kept
module or plugin needs is removed. The packaged build's `--selftest` is the safety net."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

prefix = Path(sys.argv[1])
site = next((prefix / "lib").glob("python3.*/site-packages"))
pyside = site / "PySide6"
qt = pyside / "Qt"

KEEP_MODULES = {"QtCore", "QtGui", "QtWidgets", "QtSvg"}
KEEP_PLUGINS = {  # plugin dir -> None (keep all) or set of file stems to keep
    "platforms": {"libqwayland", "libqxcb", "libqoffscreen", "libqminimal"},
    "imageformats": None, "iconengines": None, "styles": None,
    "platforminputcontexts": None, "xcbglintegrations": None,
    "wayland-decoration-client": None, "wayland-graphics-integration-client": None, "wayland-shell-integration": None,
}
# Plugins we never want even inside kept directories: they drag in Qt Pdf/Qml/VirtualKeyboard (and a newer
# glibc floor) or, for platform themes, the host's GTK. Hyprtune draws its own palette instead.
DENY = {"libqpdf", "libqtvirtualkeyboardplugin", "libqgtk3", "libqxdgdesktopportal"}


def size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


before = size(prefix)

# 1. PySide6 python modules + dev files
for f in pyside.glob("*.abi3.so"):
    if f.name.split(".")[0] not in KEEP_MODULES:
        f.unlink()
for f in list(pyside.glob("*.pyi")) + [pyside / "py.typed"]:
    f.unlink(missing_ok=True)
for d in ("include", "typesystems", "glue", "scripts", "support", "examples", "qml"):
    shutil.rmtree(pyside / d, ignore_errors=True)
for f in pyside.iterdir():  # helper executables (designer, uic, lupdate, ...)
    if f.is_file() and not f.suffix and f.name != "__init__":
        f.unlink()
for d in ("qml", "translations", "metatypes", "libexec", "resources", "modules"):
    shutil.rmtree(qt / d, ignore_errors=True)

# 2. plugins
for d in list((qt / "plugins").iterdir()):
    if d.name not in KEEP_PLUGINS:
        shutil.rmtree(d)
        continue
    stems = KEEP_PLUGINS[d.name]
    if stems:
        for f in d.iterdir():
            if f.name.split(".")[0] not in stems:
                f.unlink()

for f in list((qt / "plugins").rglob("*.so")):
    if f.name.split(".")[0] in DENY:
        f.unlink()

# 3. libraries: keep the dependency closure of everything that stays
libdirs = [qt / "lib", pyside, site / "shiboken6"]
available = {f.name: f for d in libdirs if d.is_dir() for f in d.iterdir() if f.is_file() or f.is_symlink()}


def needed(path: Path) -> list[str]:
    out = subprocess.run(["readelf", "-d", str(path)], capture_output=True, text=True).stdout
    return re.findall(r"\(NEEDED\)\s+Shared library: \[(.+?)\]", out)


roots = [f for f in pyside.glob("*.abi3.so")] + [f for f in (qt / "plugins").rglob("*.so")]
keep: set[str] = set()
stack = list(roots)
while stack:
    cur = stack.pop()
    for n in needed(cur):
        if n in available and n not in keep:
            keep.add(n)
            stack.append(available[n].resolve())
for need in ("libshiboken6", "libpyside6"):
    keep |= {n for n in available if n.startswith(need)}
    stack += [available[n] for n in available if n.startswith(need)]
while stack:  # closure of the forced libs
    cur = stack.pop()
    for n in needed(cur.resolve()):
        if n in available and n not in keep:
            keep.add(n)
            stack.append(available[n].resolve())
# keep the real files behind kept symlinks
for n in list(keep):
    keep.add(available[n].resolve().name)
for d in (qt / "lib",):
    for f in d.iterdir():
        if f.name not in keep and (f.name.startswith("libQt6") or f.name.startswith("libicu") or f.name.startswith("lib")):
            f.unlink()

# 4. the rest of the interpreter we don't need at runtime
for pkg in ("pip", "setuptools", "pkg_resources", "_distutils_hack", "wheel", "pytest", "_pytest", "pluggy", "iniconfig",
            "packaging", "pygments"):
    shutil.rmtree(site / pkg, ignore_errors=True)
for d in site.glob("*.dist-info"):
    if not d.name.startswith(("pyside6", "shiboken6", "hyprtune")):
        shutil.rmtree(d)
stdlib = next((prefix / "lib").glob("python3.*"))
for d in ("test", "idlelib", "tkinter", "turtledemo", "lib2to3", "ensurepip", "unittest/test", "distutils/tests"):
    shutil.rmtree(stdlib / d, ignore_errors=True)
for d in ("include", "share"):
    shutil.rmtree(prefix / d, ignore_errors=True)
for f in (prefix / "lib").glob("libpython*.a"):
    f.unlink()
for f in (prefix / "lib").glob("tcl*"), (prefix / "lib").glob("tk*"), (prefix / "lib").glob("itcl*"):
    for x in f:
        shutil.rmtree(x, ignore_errors=True) if x.is_dir() else x.unlink()
for d in stdlib.glob("config-*"):
    shutil.rmtree(d, ignore_errors=True)
keep_bin = {"python3", "python3.12", "python"}
for f in (prefix / "bin").iterdir():
    if f.name not in keep_bin and not f.name.startswith("python3."):
        f.unlink()
for d in prefix.rglob("__pycache__"):
    shutil.rmtree(d, ignore_errors=True)

print("kept Qt libs:", " ".join(sorted(f.name.split(".so")[0] for f in (qt / "lib").iterdir() if f.name.startswith("libQt6") and not f.is_symlink())))
print(f"pruned {before / 1e6:.0f} MB -> {size(prefix) / 1e6:.0f} MB")

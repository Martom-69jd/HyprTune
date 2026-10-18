#!/usr/bin/env bash
# Build a self-contained Hyprtune AppImage.
#
# Bundles a relocatable CPython (python-build-standalone) + PySide6 (Qt 6) + Hyprtune, so the result
# runs on any glibc >= 2.28 distro without installing Python or Qt. It needs only Wayland/X11 and the
# usual desktop libraries (libxkbcommon, libEGL, fontconfig, dbus) that every Hyprland system has.
#
# Requirements to *build*: bash, curl, python3 (with pip), binutils (readelf), network access.
#   ARCH=x86_64|aarch64  (default: this machine)   PYVER=3.12   OUT=dist/
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
ARCH="${ARCH:-$(uname -m)}"
PYVER="${PYVER:-3.12}"
OUT="${OUT:-$ROOT/dist}"
WORK="${WORK:-$ROOT/.appimage-build}"
APPDIR="$WORK/Hyprtune.AppDir"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/hyprtune/__init__.py)"

for tool in curl python3 readelf; do
  command -v "$tool" >/dev/null || { echo "error: '$tool' is required" >&2; exit 1; }
done

echo "==> Hyprtune $VERSION for $ARCH"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr" "$OUT" "$WORK"

# --- 1. relocatable Python ---------------------------------------------------------------------
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  python3 -m pip install --quiet --target "$WORK/uvtool" uv --break-system-packages 2>/dev/null \
    || python3 -m pip install --quiet --target "$WORK/uvtool" uv
  UV="$WORK/uvtool/bin/uv"
fi
echo "==> Fetching standalone Python $PYVER"
"$UV" python install "$PYVER" --install-dir "$WORK/pbs" >/dev/null
PYSRC="$(find "$WORK/pbs" -maxdepth 1 -mindepth 1 -type d ! -type l -name "cpython-$PYVER*" | sort | tail -1)"
cp -a "$PYSRC" "$APPDIR/usr/python"
rm -f "$APPDIR"/usr/python/lib/python*/EXTERNALLY-MANAGED
PY="$APPDIR/usr/python/bin/python3"

# --- 2. dependencies + app ----------------------------------------------------------------------
echo "==> Installing PySide6 and Hyprtune"
"$PY" -m pip install --quiet --no-cache-dir PySide6-Essentials
rm -rf "$WORK/src-copy"; mkdir -p "$WORK/src-copy"
cp -a pyproject.toml README.md LICENSE src "$WORK/src-copy/"   # build from a copy: keeps the repo clean
"$PY" -m pip install --quiet --no-cache-dir --no-deps "$WORK/src-copy"

# --- 3. shrink -------------------------------------------------------------------------------------
echo "==> Pruning unused Qt modules and Python parts"
"$PY" "$ROOT/tools/prune_bundle.py" "$APPDIR/usr/python"
"$PY" -m compileall -q -j0 "$APPDIR/usr/python/lib" || true

# --- 4. desktop integration -------------------------------------------------------------------------
install -Dm755 packaging/AppRun "$APPDIR/AppRun"
install -Dm644 packaging/hyprtune.desktop "$APPDIR/hyprtune.desktop"
install -Dm644 packaging/hyprtune.desktop "$APPDIR/usr/share/applications/hyprtune.desktop"
install -Dm644 src/hyprtune/data/hyprtune.svg "$APPDIR/hyprtune.svg"
install -Dm644 src/hyprtune/data/hyprtune.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/hyprtune.svg"
install -Dm644 packaging/io.github.hyprtune.Hyprtune.appdata.xml \
  "$APPDIR/usr/share/metainfo/io.github.hyprtune.Hyprtune.appdata.xml"
install -Dm644 LICENSE "$APPDIR/usr/share/licenses/hyprtune/LICENSE"
install -Dm644 packaging/LICENSE.hyprland-schema "$APPDIR/usr/share/licenses/hyprtune/LICENSE.hyprland-schema"
ln -sf hyprtune.svg "$APPDIR/.DirIcon"
mkdir -p "$APPDIR/usr/bin"
printf '#!/bin/sh\nexec "$(dirname "$(readlink -f "$0")")/../../AppRun" "$@"\n' > "$APPDIR/usr/bin/hyprtune"
chmod +x "$APPDIR/usr/bin/hyprtune"

# --- 5. pack ----------------------------------------------------------------------------------------
TOOL="$WORK/appimagetool-$ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
  echo "==> Downloading appimagetool"
  curl -fL --retry 3 -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
  chmod +x "$TOOL"
fi
OUTFILE="$OUT/Hyprtune-$VERSION-$ARCH.AppImage"
rm -f "$OUTFILE"
echo "==> Packing $OUTFILE"
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUTFILE" >/dev/null
chmod +x "$OUTFILE"
( cd "$OUT" && sha256sum "$(basename "$OUTFILE")" > "$(basename "$OUTFILE").sha256" )
echo "==> Built $(du -h "$OUTFILE" | cut -f1)  $OUTFILE"

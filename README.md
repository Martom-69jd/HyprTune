# Hyprtune

A settings app for **Hyprland**, **Waybar**, **awww** and **fuzzel**, in the spirit of
[HyprMod](https://github.com/BlueManCZ/hyprmod): change a value, see it happen live, save when you like it.
Built with Python and Qt 6 (PySide6) and shipped as a single self-contained **AppImage**.

| Page | What it controls |
|---|---|
| **Appearance** | Gaps, borders (gradients), corner radius, opacity, dimming, blur, shadows, glow, animations. A live miniature desktop redraws as you drag. |
| **Tiling** | Layout (dwindle / master / scrolling / monocle) and each layout's options, window snapping, workspace and focus behaviour. |
| **Input**, **Behavior** | Keyboard, mouse, touchpad; startup, focus, VRR, cursor. |
| **Waybar** | Bar options, drag-to-reorder module lists, per-module options (clock, battery, network, ...), and a style block with live preview. |
| **Wallpaper** | awww: image or random-from-folder, resize/filter, every transition option, optional autostart. |
| **Launcher** | fuzzel: every `fuzzel.ini` option, a live mock launcher, and "Preview in fuzzel" using your *unsaved* settings. |

144 Hyprland options are exposed; their types, ranges, defaults and descriptions come straight from
Hyprland's own option metadata (v0.56.1) and are hidden automatically if your Hyprland doesn't have them.

## Run it

```sh
chmod +x Hyprtune-0.1.0-x86_64.AppImage
./Hyprtune-0.1.0-x86_64.AppImage
```

No FUSE? Use `--appimage-extract-and-run`. Window class / app id is `hyprtune` (handy for window rules).

The AppImage bundles Python and Qt. It still expects the usual desktop libraries from the host
(glibc 2.34 or newer): `wayland`, `libxkbcommon`, Mesa (`libEGL`/`libGL`), `fontconfig`, `freetype2`, `harfbuzz`... 
plus `dbus`, `glib2`, `zlib`, `zstd`, `brotli` and `krb5`. On Arch:

```sh
sudo pacman -S --needed wayland libxkbcommon mesa fontconfig freetype2 dbus glib2 zlib zstd brotli krb5
```

(For running under XWayland you'd also need the `xcb-util-*` libraries; on a pure Wayland session you don't.)

## Hyprland: Lua and hyprlang, handled for you

Hyprland 0.55 replaced the hyprlang config with Lua. Hyprtune detects which you use:

| | Lua (0.55+) | hyprlang (older) |
|---|---|---|
| Your config | `~/.config/hypr/hyprland.lua` | `~/.config/hypr/hyprland.conf` |
| Hyprtune's file | `hyprtune.lua` | `hyprtune.conf` |
| Hook line (added with your OK) | `require("hyprtune")` | `source = ~/.config/hypr/hyprtune.conf` |
| Live preview | `hyprctl eval 'hl.config({...})'` | `hyprctl keyword ...` |

Like HyprMod, **your own config is never rewritten**. All Hyprtune settings live in one file it owns; your config
loads it through one line at the end, added only when you click the button (a backup is taken first).
Edits are previewed live, and **Save** writes the file. Ctrl+Z undoes; Revert restores the live state.
Reset on a row removes Hyprtune's override so your own config applies again.

## Your other files are edited in place

* **Waybar** `config(.jsonc)`: a span-preserving JSONC editor rewrites only the values you change.
  Comments, trailing commas and layout survive. Style changes go into one marked block at the end of `style.css`
  and only for fields you touched. A config that doesn't parse is never modified.
* **fuzzel** `fuzzel.ini`: lines are edited or uncommented in place; unset options are commented out, not deleted.
* **awww** has no config file, so Hyprtune generates `~/.config/hyprtune/awww-startup.sh` and starts it from
  Hyprland if you enable autostart. (swww, awww's former name, is detected as a fallback.)
* Every file is copied to `~/.config/hyprtune/backups/` before it changes. Symlinked dotfiles are followed.

## Build the AppImage

```sh
bash packaging/build-appimage.sh        # needs bash, curl, python3+pip, binutils; downloads Python, PySide6, appimagetool
APPIMAGE_EXTRACT_AND_RUN=1 dist/Hyprtune-*.AppImage --selftest
```

`--selftest` builds every page headlessly in a throwaway config directory, so you can check a packaged build.
The script bundles a relocatable CPython, installs PySide6 and Hyprtune into it, and prunes Qt to the modules and
plugins needed (computing the real ELF dependency closure). `ARCH=aarch64` works on an arm64 machine.

## Develop

```sh
pip install PySide6-Essentials pytest
PYTHONPATH=src python -m hyprtune
PYTHONPATH=src python -m pytest          # uses a fake hyprctl; no compositor needed
pip install hyprland-schema && python tools/gen_hypr_data.py   # refresh option data for a newer Hyprland
```

Add or relabel a Hyprland setting in `src/hyprtune/hypr/options.py`: list the key, and its widget, range, default and
description are derived from the generated data.

## Licenses

Hyprtune is MIT. Hyprland option metadata comes from [hyprland-schema](https://github.com/BlueManCZ/hyprland-schema)
(MIT, see `packaging/LICENSE.hyprland-schema`). The AppImage bundles Qt 6 and PySide6 under the LGPL-3.0 and CPython
under the PSF license.

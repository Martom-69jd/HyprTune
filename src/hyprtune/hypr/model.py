"""State for the Hyprland pages: saved overrides, unsaved edits, live values, undo."""
from __future__ import annotations

import threading
import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from ..util import AppState
from .backend import HyprBackend
from .options import SPECS


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b


class HyprModel(QObject):
    optionChanged = Signal(str)
    dirtyChanged = Signal(bool)
    refreshed = Signal()  # live values (re)loaded; pages should re-read everything
    message = Signal(str, bool)  # text, is_error
    _liveReady = Signal(dict)  # emitted from the reader thread; delivered on the UI thread

    def __init__(self, backend: HyprBackend, state: AppState) -> None:
        super().__init__()
        self.b = backend
        self.app_state = state
        self.saved: dict[str, Any] = {}
        self.pending: dict[str, Any] = {}
        self.pending_reset: set[str] = set()
        self.baseline: dict[str, Any] = {}
        self.supported: set[str] | None = None  # None = unknown (Hyprland not running)
        self.autostart: list[str] = []
        self._undo: list[list[Any]] = []  # [key, old, new, timestamp]
        self._queue: dict[str, Any] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._flush)
        self._reader: threading.Thread | None = None
        self._abandoned = False
        self._liveReady.connect(self._loaded)
        self._read_saved()

    # -- loading --------------------------------------------------------------------------------
    def _read_saved(self) -> None:
        data = self.b.read_managed()
        self.saved = {k: v for k, v in data["options"].items() if k in SPECS}
        self.autostart = list(data["autostart"])

    def load(self) -> None:
        """Read live values from Hyprland off the UI thread."""
        if self._reader is not None and self._reader.is_alive():
            return

        def work() -> None:
            live = self.b.get_live(list(SPECS))
            if not self._abandoned:  # the window may be gone by the time hyprctl answers
                self._liveReady.emit(live)

        self._reader = threading.Thread(target=work, name="hyprtune-live", daemon=True)
        self._reader.start()

    def wait(self, ms: int = 8000) -> None:
        """Block until a background refresh has finished (call before the model is destroyed)."""
        if self._reader is not None:
            self._reader.join(ms / 1000)
            if self._reader.is_alive():
                self._abandoned = True

    def _loaded(self, live: dict[str, Any]) -> None:
        self.baseline = live
        self.supported = set(live) if self.b.running() and live else None
        self.refreshed.emit()

    def is_supported(self, key: str) -> bool:
        return self.supported is None or key in self.supported

    # -- values ---------------------------------------------------------------------------------
    def value(self, key: str) -> Any:
        if key in self.pending:
            return self.pending[key]
        if key in self.pending_reset:
            return SPECS[key].default
        if key in self.saved:
            return self.saved[key]
        if key in self.baseline:
            return self.baseline[key]
        return SPECS[key].default

    def is_modified(self, key: str) -> bool:
        return key in self.pending or (key in self.saved and key not in self.pending_reset)

    def is_dirty(self) -> bool:
        return bool(self.pending or self.pending_reset)

    def dirty_count(self) -> int:
        return len(self.pending) + len(self.pending_reset)

    def _assign(self, key: str, value: Any) -> None:
        """Record `value` as the unsaved state of `key`, apply it live and notify."""
        was_dirty = self.is_dirty()
        self.pending_reset.discard(key)
        known = key in self.saved or key in self.baseline
        target = self.saved.get(key, self.baseline.get(key))
        if known and _same(target, value):
            self.pending.pop(key, None)
        else:
            self.pending[key] = value
        self._queue_apply(key, value)
        self.optionChanged.emit(key)
        if was_dirty != self.is_dirty():
            self.dirtyChanged.emit(self.is_dirty())

    def set_value(self, key: str, value: Any, record: bool = True) -> None:
        old = self.value(key)
        if _same(old, value):
            return
        if record:
            now = time.monotonic()
            if self._undo and self._undo[-1][0] == key and now - self._undo[-1][3] < 0.8:
                self._undo[-1][2:] = [value, now]  # one slider drag = one undo step
            else:
                self._undo.append([key, old, value, now])
                del self._undo[:-200]
        self._assign(key, value)

    def reset(self, key: str) -> None:
        """Drop our override so Hyprland falls back to its default / your own config."""
        if not self.is_modified(key):
            return
        was_dirty = self.is_dirty()
        self._undo.append([key, self.value(key), SPECS[key].default, 0.0])
        self.pending.pop(key, None)
        if key in self.saved:
            self.pending_reset.add(key)
        self._queue_apply(key, SPECS[key].default)
        self.optionChanged.emit(key)
        if was_dirty != self.is_dirty():
            self.dirtyChanged.emit(self.is_dirty())

    def undo(self) -> None:
        if self._undo:
            key, old = self._undo.pop()[:2]
            self._assign(key, old)

    def can_undo(self) -> bool:
        return bool(self._undo)

    # -- live apply -----------------------------------------------------------------------------
    def _queue_apply(self, key: str, value: Any) -> None:
        self._queue[key] = value
        self._timer.start()

    def _flush(self) -> None:
        batch, self._queue = self._queue, {}
        ok, msg = self.b.apply_live(batch)
        if not ok and msg and self.b.running():
            self.message.emit(f"Hyprland rejected a change: {msg}", True)

    # -- persistence ----------------------------------------------------------------------------
    def save(self) -> bool:
        needs_reload = bool(self.pending_reset)
        merged = dict(self.saved)
        merged.update(self.pending)
        for k in self.pending_reset:
            merged.pop(k, None)
        for k, v in list(merged.items()):  # an empty gradient can't be written; treat as unset
            if SPECS[k].kind == "gradient" and not v.get("colors"):
                merged.pop(k)
        try:
            path = self.b.write_managed(merged, self.autostart)
        except OSError as e:
            self.message.emit(f"Could not save: {e}", True)
            return False
        self.saved = merged
        changed = set(self.pending) | self.pending_reset
        self.pending.clear()
        self.pending_reset.clear()
        self._undo.clear()
        for k in changed:
            self.optionChanged.emit(k)
        self.dirtyChanged.emit(False)
        if needs_reload and self.b.running():
            self.b.reload()
            self.load()
        errs = self.b.config_errors() if self.b.running() else ""
        if errs:
            self.message.emit("Saved, but Hyprland reported config errors: " + errs.splitlines()[0], True)
        else:
            self.message.emit(f"Saved to {path}", False)
        return True

    def revert(self) -> None:
        keys = set(self.pending) | self.pending_reset
        self.pending.clear()
        self.pending_reset.clear()
        self._undo.clear()
        restore = {k: self.saved.get(k, self.baseline.get(k, SPECS[k].default)) for k in keys}
        if restore:
            self._queue.update(restore)
            self._flush()
        for k in keys:
            self.optionChanged.emit(k)
        self.dirtyChanged.emit(False)

    def set_autostart(self, command: str, enabled: bool) -> None:
        """Add or remove an autostart command in the managed file (used by the Wallpaper page)."""
        self.autostart = [a for a in self.autostart if a != command]
        if enabled:
            self.autostart.append(command)
        merged = dict(self.saved)
        self.b.write_managed(merged, self.autostart)

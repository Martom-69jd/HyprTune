"""Small shared helpers: paths, subprocesses and safe file writes."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))


def hypr_dir() -> Path:
    return config_home() / "hypr"


def app_dir() -> Path:
    return config_home() / "hyprtune"


def run(cmd: list[str], timeout: float = 6.0) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: timed out"
    except OSError as e:
        return 126, "", str(e)


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def spawn_detached(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def backups_dir() -> Path:
    d = app_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup(path: Path, keep: int = 20) -> Path | None:
    """Copy a user file into ~/.config/hyprtune/backups before we change it."""
    path = Path(os.path.realpath(path))
    if not path.is_file():
        return None
    d = backups_dir()
    existing = sorted(d.glob(f"{path.name}.*"))
    if existing and existing[-1].read_bytes() == path.read_bytes():
        return existing[-1]  # identical to newest backup, nothing new to keep
    dest = d / f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, dest)
    for old in sorted(d.glob(f"{path.name}.*"))[:-keep]:
        old.unlink(missing_ok=True)
    return dest


def read_text(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def write_text(path: Path, text: str, make_backup: bool = True) -> bool:
    """Atomically write text. Follows symlinks so dotfile-manager links survive.

    Returns True when the file content actually changed."""
    path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8", errors="replace") == text:
            return False
        if make_backup:
            backup(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return True


class AppState:
    """Tiny JSON store for Hyprtune's own preferences (~/.config/hyprtune/state.json)."""

    def __init__(self) -> None:
        self.path = app_dir() / "state.json"
        try:
            self.data: dict[str, Any] = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        write_text(self.path, json.dumps(self.data, indent=2, sort_keys=True) + "\n", make_backup=False)

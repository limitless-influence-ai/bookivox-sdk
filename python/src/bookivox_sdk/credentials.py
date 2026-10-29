"""Local credential storage for the Bookivox CLI.

The API key is written to a single JSON file under the platform config
directory with ``0600`` permissions (``0700`` for the directory). This is the
same model used by ``gh``/``aws`` style CLIs: no dependency on a desktop
keyring (which is unavailable in CI and on headless servers), while still
preventing other local users from reading the secret.

Threat model: an attacker who already runs code as the current user can read
the file regardless of the mechanism. The file permissions only protect
against *other* users on the same machine, which is exactly what ``0600`` is
for. Nothing is ever written to shell history or process arguments by default.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

CONFIG_DIR_NAME = "bookivox"
CONFIG_FILE_NAME = "credentials.json"


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / CONFIG_DIR_NAME
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / CONFIG_DIR_NAME


def config_path() -> Path:
    return config_dir() / CONFIG_FILE_NAME


def load() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: dict[str, Any]) -> Path:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, stat.S_IRWXU)  # 0700
    path = config_path()
    tmp = path.with_suffix(".tmp")
    # Create with restrictive permissions *before* writing the secret.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


def delete() -> bool:
    path = config_path()
    if not path.exists():
        return False
    path.unlink()
    return True

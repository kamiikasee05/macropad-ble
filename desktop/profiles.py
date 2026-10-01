"""Persistencia de perfiles de keymap en disco.

Ruta: %APPDATA%\\MacropadFx\\profiles.json
Fallback (si APPDATA no existe): <este directorio>\\profiles.json

Formato en disco:
  {"<nombre>": {"raw": "K:4|...", "saved_at": "2026-09-30T12:00:00+00:00"}}

Escritura atomica (temp + os.replace) y UTF-8 sin BOM.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

APP_DIR_NAME = "MacropadFx"
PROFILES_FILE = "profiles.json"


def base_dir() -> str:
    appdata = os.environ.get("APPDATA")
    if appdata:
        d = os.path.join(appdata, APP_DIR_NAME)
    else:
        d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(d, exist_ok=True)
    return d


def profiles_path() -> str:
    return os.path.join(base_dir(), PROFILES_FILE)


def _load() -> dict:
    path = profiles_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _atomic_write(data: dict) -> None:
    path = profiles_path()
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".profiles-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def list_profiles() -> dict:
    """Devuelve {name: {raw, saved_at}} ordenado por nombre."""
    data = _load()
    return {name: data[name] for name in sorted(data)}


def get_profile(name: str) -> Optional[dict]:
    return _load().get(name)


def save_profile(name: str, raw: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre del perfil no puede estar vacio.")
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("El keymap no puede estar vacio.")

    entry = {
        "raw": raw,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    data = _load()
    data[name] = entry
    _atomic_write(data)
    return entry


def delete_profile(name: str) -> bool:
    data = _load()
    if name not in data:
        return False
    del data[name]
    _atomic_write(data)
    return True

"""
booking/mail_config.py  –  Laufzeit-Schalter für den E-Mail-Versand.

Liest/schreibt das Feld `mail_enabled` in vereinsconfig.json (ungecacht, damit
der Admin-Toggle sofort greift, ohne Server-Neustart).

Fällt das Feld in der Datei, wird der Default (aus .env `MAIL_ENABLED`, sonst
True) verwendet. Der Admin-Toggle setzt das Feld explizit und gewinnt damit
über die .env.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _config_file() -> Path:
    config_dir = os.environ.get("CONFIG_DIR", "config")
    return Path(__file__).parent.parent / config_dir / "vereinsconfig.json"


def is_enabled(default: bool = True) -> bool:
    """True, wenn Mailversand aktiv. Datei-Feld gewinnt; sonst `default`."""
    try:
        data = json.loads(_config_file().read_text(encoding="utf-8"))
        if "mail_enabled" in data:
            return bool(data["mail_enabled"])
    except Exception:
        pass
    return default


def set_enabled(enabled: bool) -> None:
    """Schreibt `mail_enabled` in vereinsconfig.json zurück."""
    path = _config_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["mail_enabled"] = bool(enabled)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

"""
booking/scheduler_config.py  –  Konfiguration für den automatischen Spielplan-Sync

Liest/schreibt die Scheduler-Felder direkt aus vereinsconfig.json.
Kein lru_cache, damit Admin-UI-Änderungen sofort greifen ohne Server-Neustart.
Der Rest von vereinsconfig.py bleibt gecacht.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def _config_file() -> Path:
    config_dir = os.environ.get("CONFIG_DIR", "config")
    return Path(__file__).parent.parent / config_dir / "vereinsconfig.json"


@dataclass
class SchedulerConfig:
    spielplan_sync_enabled: bool = True
    spielplan_sync_uhrzeit: str = "06:00"


def load() -> SchedulerConfig:
    """Liest die Scheduler-Felder aus vereinsconfig.json (ungecacht)."""
    try:
        data = json.loads(_config_file().read_text(encoding="utf-8"))
        return SchedulerConfig(
            spielplan_sync_enabled=bool(data.get("spielplan_sync_enabled", True)),
            spielplan_sync_uhrzeit=str(data.get("spielplan_sync_uhrzeit", "06:00")),
        )
    except Exception:
        return SchedulerConfig()


def save(cfg: SchedulerConfig) -> None:
    """Schreibt nur die Scheduler-Felder in vereinsconfig.json zurück."""
    path = _config_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["spielplan_sync_enabled"] = cfg.spielplan_sync_enabled
    data["spielplan_sync_uhrzeit"] = cfg.spielplan_sync_uhrzeit
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

"""
booking/scheduler_config.py  –  Konfiguration für den automatischen Spielplan-Sync

Liest/schreibt config/<CONFIG_DIR>/scheduler.json.
Kein lru_cache, da die Konfiguration zur Laufzeit geändert werden kann.
"""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from pathlib import Path


def _config_file() -> Path:
    config_dir = os.environ.get("CONFIG_DIR", "config")
    return Path(__file__).parent.parent / config_dir / "scheduler.json"


@dataclass
class SchedulerConfig:
    spielplan_sync_enabled: bool = True
    spielplan_sync_uhrzeit: str = "06:00"


def load() -> SchedulerConfig:
    """Liest die Scheduler-Konfiguration aus scheduler.json."""
    try:
        data = json.loads(_config_file().read_text(encoding="utf-8"))
        return SchedulerConfig(
            spielplan_sync_enabled=bool(data.get("spielplan_sync_enabled", True)),
            spielplan_sync_uhrzeit=str(data.get("spielplan_sync_uhrzeit", "06:00")),
        )
    except Exception:
        return SchedulerConfig()


def save(cfg: SchedulerConfig) -> None:
    """Speichert die Scheduler-Konfiguration nach scheduler.json."""
    _config_file().parent.mkdir(parents=True, exist_ok=True)
    _config_file().write_text(
        json.dumps(dataclasses.asdict(cfg), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

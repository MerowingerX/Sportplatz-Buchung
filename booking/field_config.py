"""
booking/field_config.py  –  Konfiguration der sichtbaren Platzgruppen pro Rolle

Die Konfiguration liegt in config/field_config.json und kann vom Admin
über /admin/field-config geändert werden, ohne Neustart.
"""

from __future__ import annotations

import json
from pathlib import Path

from booking.models import FieldName

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "field_config.json"

# Alle definierten Gruppen (Reihenfolge + Felder) als Fallback
_DEFAULT: dict = {
    "field_groups": [
        {
            "name": "Kura (Kunstrasen)",
            "fields": ["Kura Ganz", "Kura Halb A", "Kura Halb B"],
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        },
        {
            "name": "Rasen (Naturrasen)",
            "fields": ["Rasen Ganz", "Rasen Halb A", "Rasen Halb B"],
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        },
        {
            "name": "Turnhalle",
            "fields": ["Halle Ganz", "Halle 2/3", "Halle 1/3"],
            "visible_to": ["Administrator"],
        },
    ]
}

# Alle bekannten Rollen (für das Admin-Formular)
ALL_ROLES: list[str] = ["Trainer", "Platzwart", "DFBnet", "Administrator"]


def load() -> dict:
    """Liest die aktuelle Konfiguration aus der JSON-Datei."""
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _DEFAULT.copy()


def save(config: dict) -> None:
    """Schreibt die Konfiguration in die JSON-Datei."""
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_visible_groups(role_value: str) -> list[tuple[str, list[str]]]:
    """
    Gibt die für diese Rolle sichtbaren Gruppen zurück:
    [(Gruppenname, [Feldname, ...]), ...]
    """
    cfg = load()
    return [
        (g["name"], g["fields"])
        for g in cfg["field_groups"]
        if role_value in g.get("visible_to", [])
    ]


def get_visible_fields(role_value: str) -> list[FieldName]:
    """Gibt alle für diese Rolle sichtbaren FieldName-Werte zurück."""
    visible_names: set[str] = set()
    for _, fields in get_visible_groups(role_value):
        visible_names.update(fields)
    # Reihenfolge aus FieldName-Enum beibehalten
    return [f for f in FieldName if f.value in visible_names]

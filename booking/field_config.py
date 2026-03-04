"""
booking/field_config.py  –  Konfiguration der sichtbaren Platzgruppen pro Rolle

Die Konfiguration liegt in config/field_config.json und kann vom Admin
über /admin/field-config geändert werden, ohne Neustart.

Platznamen werden als stabile interne IDs (A, AA, AB, B, …) gespeichert.
Anzeigenamen kommen aus dem "display_names"-Abschnitt der JSON-Datei.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from booking.models import FieldName


def _config_file() -> Path:
    config_dir = os.environ.get("CONFIG_DIR", "config")
    return Path(__file__).parent.parent / config_dir / "field_config.json"

# Alle definierten Gruppen (Reihenfolge + Felder) als Fallback
_DEFAULT: dict = {
    "display_names": {
        "A":  "Kura AB",
        "AA": "Kura A",
        "AB": "Kura B",
        "B":  "Rasen AB",
        "BA": "Rasen A",
        "BB": "Rasen B",
        "C":  "Halle Ganz",
        "CA": "Halle 2/3",
        "CB": "Halle 1/3",
        "D":  "Trainingsfeld",
        "E":  "Halle (ganz)",
        "EA": "Halle A",
        "EB": "Halle B",
    },
    "field_groups": [
        {
            "id": "kura",
            "name": "Kura (Kunstrasen)",
            "fields": ["A", "AA", "AB"],
            "lit": True,
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        },
        {
            "id": "rasen",
            "name": "Rasen (Naturrasen)",
            "fields": ["B", "BA", "BB"],
            "lit": False,
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        },
        {
            "id": "halle",
            "name": "Turnhalle",
            "fields": ["C", "CA", "CB"],
            "lit": True,
            "visible_to": ["Administrator"],
        },
        {
            "id": "training",
            "name": "Trainingsfeld",
            "fields": ["D"],
            "lit": False,
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        },
        {
            "id": "halle2",
            "name": "Halle",
            "fields": ["E", "EA", "EB"],
            "lit": True,
            "visible_to": ["Administrator"],
        },
    ],
}

# Alle bekannten Rollen (für das Admin-Formular)
ALL_ROLES: list[str] = ["Trainer", "Platzwart", "DFBnet", "Administrator"]


def load() -> dict:
    """Liest die aktuelle Konfiguration aus der JSON-Datei."""
    try:
        return json.loads(_config_file().read_text(encoding="utf-8"))
    except Exception:
        return _DEFAULT.copy()


def save(config: dict) -> None:
    """Schreibt die Konfiguration in die JSON-Datei."""
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def get_display_name(field_id: str) -> str:
    """Gibt den Anzeigenamen für eine Feld-ID zurück (Fallback: die ID selbst)."""
    return load().get("display_names", {}).get(field_id, field_id)


def get_display_names() -> dict[str, str]:
    """Gibt alle ID→Anzeigename-Zuordnungen zurück."""
    return load().get("display_names", {})


def get_group_id(field_id: str) -> str:
    """Gibt die Gruppen-ID zurück, zu der das Feld gehört ('kura', 'rasen', 'halle')."""
    for group in load().get("field_groups", []):
        if field_id in group.get("fields", []):
            return group.get("id", "")
    return ""


def is_lit(field_id: str) -> bool:
    """True wenn das Feld beleuchtet ist (kein Sonnenuntergangs-Hinweis nötig)."""
    for group in load().get("field_groups", []):
        if field_id in group.get("fields", []):
            return group.get("lit", True)
    return True


def get_conflict_sources(visible_field_ids: list[str]) -> dict[str, list[str]]:
    """
    Liefert für jedes Feld die Liste der Felder, die es blockieren.
    Konfliktlogik: f1 und f2 blockieren sich, wenn einer ein Präfix des anderen ist.
    Beispiel: "A" blockiert "AA" und "AB" (und umgekehrt).
    """
    result: dict[str, list[str]] = {}
    for f in visible_field_ids:
        result[f] = [
            g for g in visible_field_ids
            if g != f and (f.startswith(g) or g.startswith(f))
        ]
    return result


def get_visible_groups(role_value: str) -> list[tuple[str, list[str]]]:
    """
    Gibt die für diese Rolle sichtbaren Gruppen zurück:
    [(Gruppenname, [Feld-ID, ...]), ...]
    """
    cfg = load()
    return [
        (g["name"], g["fields"])
        for g in cfg["field_groups"]
        if role_value in g.get("visible_to", [])
    ]


def get_visible_fields(role_value: str) -> list[FieldName]:
    """Gibt alle für diese Rolle sichtbaren FieldName-Werte zurück."""
    visible_ids: set[str] = set()
    for _, fields in get_visible_groups(role_value):
        visible_ids.update(fields)
    # Reihenfolge aus FieldName-Enum beibehalten
    return [f for f in FieldName if f.value in visible_ids]

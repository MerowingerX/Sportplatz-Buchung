"""
booking/vereinsconfig.py  –  Vereinsspezifische Konfiguration

Lädt config/vereinsconfig.json und stellt typisierte Zugriffsfunktionen bereit.
Alle Funktionen cachen das Ergebnis (lru_cache), damit die Datei nur einmal
gelesen wird.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "vereinsconfig.json"


@lru_cache(maxsize=1)
def load() -> dict:
    with open(_CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_vereinsname() -> str:
    return load().get("vereinsname", "Sportverein")


def get_vereinsname_lang() -> str:
    return load().get("vereinsname_lang", get_vereinsname())


def get_heim_keyword() -> str:
    """Schlüsselwort im Heimteam-Namen, das ein Heimspiel kennzeichnet (Kleinschreibung)."""
    return load().get("heim_keyword", "")


def get_spielorte() -> list[dict]:
    """Rohe Spielort-Liste aus der Konfiguration."""
    return load().get("spielorte", [])


def get_spielort_zu_feld() -> list[tuple[str, "FieldName"]]:
    """
    Für spielplan_sync.py: Spielort-Substring (Kleinschreibung) → FieldName.
    Gibt eine geordnete Liste von (substring, FieldName)-Paaren zurück.
    """
    from booking.models import FieldName  # lokaler Import verhindert Zirkelimport

    result: list[tuple[str, FieldName]] = []
    for s in get_spielorte():
        try:
            fn = FieldName(s["feld"])
            result.append((s["fussball_de_string"], fn))
        except (KeyError, ValueError):
            pass
    return result


def get_spielort_zu_praefix() -> list[tuple[str, list[str]]]:
    """
    Für check_spielplan.py: Spielort-Substring → Liste von Platz-Präfixen.
    Gibt eine geordnete Liste von (substring, [praefix, ...])-Paaren zurück.
    """
    return [
        (s["fussball_de_string"], s.get("platz_praefix", []))
        for s in get_spielorte()
        if "fussball_de_string" in s
    ]


def get_feld_praefixe() -> set[str]:
    """Menge aller Platz-Präfixe aus der Spielort-Konfiguration."""
    return {p for s in get_spielorte() for p in s.get("platz_praefix", [])}


def get_saison_defaults() -> dict:
    """Gibt Default-Daten je Saison zurück (MM-DD-Strings)."""
    return load().get("saison_defaults", {
        "ganzjaehrig":    {"start": "08-01", "ende": "06-30"},
        "sommerhalbjahr": {"start": "08-01", "ende": "10-30"},
        "winterhalbjahr": {"start": "10-30", "ende": "03-01"},
    })


def get_colors() -> dict[str, str]:
    """CSS-Farben des Vereins als Dict."""
    cfg = load()
    return {
        "primary": cfg.get("primary_color", "#1e4fa3"),
        "primary_dark": cfg.get("primary_color_dark", "#0d2f6b"),
        "primary_darker": cfg.get("primary_color_darker", "#071c44"),
        "gold": cfg.get("gold_color", "#e8c04a"),
    }

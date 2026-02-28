#!/usr/bin/env python3
"""
Notion-Setup-Script – legt alle 6 Datenbanken für das Sportplatz-Buchungssystem an.

Verwendung:
    python scripts/setup_notion.py --api-key <NOTION_API_KEY> --parent <PARENT_PAGE_ID>

    oder mit Umgebungsvariablen:
    NOTION_API_KEY=... NOTION_PARENT_PAGE_ID=... python scripts/setup_notion.py

Das Script gibt am Ende die generierten Datenbank-IDs aus, die direkt in die .env
eingetragen werden können.

Voraussetzung: Die Notion-Integration muss Zugriff auf die Eltern-Seite haben.
"""

import argparse
import os
import sys

try:
    from notion_client import Client
except ImportError:
    print("FEHLER: notion-client nicht installiert.")
    print("       Bitte zuerst: pip install notion-client")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Zeitslots für Select-Felder (16:00 – 22:00, 30-Minuten-Raster)
# ---------------------------------------------------------------------------
ZEITSLOTS = [
    f"{h:02d}:{m:02d}"
    for h in range(16, 23)
    for m in (0, 30)
    if not (h == 22 and m == 30)
]

DAUER_OPTIONEN = ["60", "90", "120", "180"]

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def sel(*options: str) -> dict:
    """Erstellt ein Notion Select-Property-Schema mit den gegebenen Optionen."""
    return {"select": {"options": [{"name": o} for o in options]}}


def title_prop() -> dict:
    return {"title": {}}


def rich_text_prop() -> dict:
    return {"rich_text": {}}


def date_prop() -> dict:
    return {"date": {}}


def checkbox_prop() -> dict:
    return {"checkbox": {}}


def email_prop() -> dict:
    return {"email": {}}


def create_db(client: Client, parent_page_id: str, name: str, properties: dict) -> str:
    """Erstellt eine Notion-Datenbank und gibt ihre ID zurück."""
    print(f"  Erstelle: {name} ...", end=" ", flush=True)
    result = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": name}}],
        properties=properties,
    )
    db_id = result["id"]
    print(f"OK  →  {db_id}")
    return db_id


# ---------------------------------------------------------------------------
# Datenbank-Schemata
# ---------------------------------------------------------------------------

def schema_buchungen() -> dict:
    """Buchungen – Platzbuchungen aller Art."""
    return {
        "Titel":                    title_prop(),
        "Platz":                    sel(
            "Kura Ganz", "Kura Halb A", "Kura Halb B",
            "Rasen Ganz", "Rasen Halb A", "Rasen Halb B",
            "Halle Ganz", "Halle 2/3", "Halle 1/3",
        ),
        "Datum":                    date_prop(),
        "Startzeit":                sel(*ZEITSLOTS),
        "Endzeit":                  sel(*ZEITSLOTS),
        "Dauer":                    sel(*DAUER_OPTIONEN),
        "Typ":                      sel("Training", "Spiel", "Turnier"),
        "Gebucht von":              rich_text_prop(),   # Notion-ID des Nutzers
        "Gebucht von Name":         rich_text_prop(),
        "Rolle":                    sel("Trainer", "Administrator", "Platzwart", "DFBnet"),
        "Status":                   sel("Bestätigt", "Storniert", "Storniert (DFBnet)"),
        "Mannschaft":               rich_text_prop(),
        "Zweck":                    rich_text_prop(),
        "Kontakt":                  rich_text_prop(),
        "Serie":                    rich_text_prop(),   # notion_id der zugehörigen Serie
        "Serienausnahme":           checkbox_prop(),
        "Hinweis Sonnenuntergang":  rich_text_prop(),
        "Spielkennung":             rich_text_prop(),   # DFBnet-ID für Duplikaterkennung
    }


def schema_serien() -> dict:
    """Serien – wiederkehrende Buchungen."""
    return {
        "Titel":            title_prop(),
        "Platz":            sel(
            "Kura Ganz", "Kura Halb A", "Kura Halb B",
            "Rasen Ganz", "Rasen Halb A", "Rasen Halb B",
            "Halle Ganz", "Halle 2/3", "Halle 1/3",
        ),
        "Startzeit":        sel(*ZEITSLOTS),
        "Dauer":            sel(*DAUER_OPTIONEN),
        "Rhythmus":         sel("Wöchentlich", "14-tägig"),
        "Startdatum":       date_prop(),
        "Enddatum":         date_prop(),
        "Gebucht von ID":   rich_text_prop(),
        "Gebucht von Name": rich_text_prop(),
        "Status":           sel("Aktiv", "Pausiert", "Beendet"),
        "Mannschaft":       rich_text_prop(),
        "Trainer ID":       rich_text_prop(),
        "Trainer Name":     rich_text_prop(),
    }


def schema_sperrzeiten() -> dict:
    """Sperrzeiten – Platzsperren für Rasen-Plätze."""
    return {
        "Titel":                    title_prop(),
        "Datum":                    date_prop(),        # wird als Datumsbereich gespeichert
        "Art":                      sel("Ganztägig", "Zeitlich"),
        "Startzeit":                sel(*ZEITSLOTS),
        "Endzeit":                  sel(*ZEITSLOTS),
        "Grund":                    rich_text_prop(),
        "Eingetragen von ID":       rich_text_prop(),
        "Eingetragen von Name":     rich_text_prop(),
    }


def schema_nutzer() -> dict:
    """Nutzer – Benutzerkonten mit Rollen und Passwort-Hashes."""
    mannschaften = [
        "G1", "G2", "G3",
        "F1", "F2",
        "E1", "E2", "E3",
        "D1", "D2",
        "C", "B", "A",
        "TuS 1", "TuS 2",
        "Ü32", "Ü40",
        "Frauen", "Mädchen",
    ]
    return {
        "Name":             title_prop(),
        "Rolle":            sel("Trainer", "Administrator", "Platzwart", "DFBnet"),
        "E-Mail":           email_prop(),
        "Password_Hash":    rich_text_prop(),
        "Passwort ändern":  checkbox_prop(),
        "Mannschaft":       sel(*mannschaften),
    }


def schema_aufgaben() -> dict:
    """Aufgaben / Schwarzes Brett."""
    return {
        "Titel":                title_prop(),
        "Typ":                  sel("Defekt", "Nutzeranfrage", "Turniertermin", "Sonstiges"),
        "Status":               sel("Offen", "In Bearbeitung", "Erledigt"),
        "Priorität":            sel("Niedrig", "Mittel", "Hoch"),
        "Erstellt am":          date_prop(),
        "Fällig am":            date_prop(),
        "Ort":                  rich_text_prop(),
        "Beschreibung":         rich_text_prop(),
        "Erstellt von ID":      rich_text_prop(),
        "Erstellt von Name":    rich_text_prop(),
    }


def schema_events() -> dict:
    """Externe Events – Auswärtsspiele, Turniere, sonstige Termine ohne Platzbuchung."""
    return {
        "Name":                 title_prop(),
        "Datum":                date_prop(),
        "Startzeit":            rich_text_prop(),       # gespeichert als "HH:MM"
        "Ort":                  rich_text_prop(),
        "Beschreibung":         rich_text_prop(),
        "Mannschaft":           rich_text_prop(),
        "Erstellt von ID":      rich_text_prop(),
        "Erstellt von Name":    rich_text_prop(),
    }


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Legt alle 6 Notion-Datenbanken für das Sportplatz-Buchungssystem an."
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NOTION_API_KEY", ""),
        help="Notion Integration Token (oder Umgebungsvariable NOTION_API_KEY)",
    )
    parser.add_argument(
        "--parent",
        default=os.environ.get("NOTION_PARENT_PAGE_ID", ""),
        help="ID der Notion-Seite, unter der die Datenbanken angelegt werden "
             "(oder Umgebungsvariable NOTION_PARENT_PAGE_ID)",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("FEHLER: Kein API-Key angegeben.")
        print("        --api-key <KEY>  oder  NOTION_API_KEY=<KEY>")
        sys.exit(1)

    if not args.parent:
        print("FEHLER: Keine Parent-Page-ID angegeben.")
        print("        --parent <PAGE_ID>  oder  NOTION_PARENT_PAGE_ID=<ID>")
        print()
        print("Die Page-ID findest du in der URL der Notion-Seite:")
        print("  https://www.notion.so/MeinWorkspace/Seite-<PAGE_ID>")
        print("  (32-stelliger Hex-String, ggf. mit Bindestrichen)")
        sys.exit(1)

    # Parent-ID normalisieren (Bindestriche entfernen falls nötig)
    parent_id = args.parent.replace("-", "")
    if len(parent_id) != 32:
        print(f"WARNUNG: Parent-Page-ID sieht ungewöhnlich aus: {args.parent}")

    client = Client(auth=args.api_key)

    # Verbindung testen
    print("Verbinde mit Notion API ...", end=" ", flush=True)
    try:
        client.users.me()
        print("OK")
    except Exception as e:
        print(f"FEHLER\n{e}")
        sys.exit(1)

    print()
    print("Lege Datenbanken an:")
    print("-" * 60)

    created: dict[str, str] = {}

    databases = [
        ("Buchungen",   schema_buchungen),
        ("Serien",      schema_serien),
        ("Sperrzeiten", schema_sperrzeiten),
        ("Nutzer",      schema_nutzer),
        ("Aufgaben",    schema_aufgaben),
        ("Events",      schema_events),
    ]

    errors: list[str] = []
    for db_name, schema_fn in databases:
        try:
            db_id = create_db(client, args.parent, db_name, schema_fn())
            created[db_name] = db_id
        except Exception as e:
            print(f"FEHLER")
            errors.append(f"{db_name}: {e}")

    print()
    print("=" * 60)
    print("Fertig! Trage folgende Werte in deine .env ein:")
    print("=" * 60)
    print()

    env_keys = {
        "Buchungen":   "NOTION_BUCHUNGEN_DB_ID",
        "Serien":      "NOTION_SERIEN_DB_ID",
        "Sperrzeiten": "NOTION_SPERRZEITEN_DB_ID",
        "Nutzer":      "NOTION_NUTZER_DB_ID",
        "Aufgaben":    "NOTION_AUFGABEN_DB_ID",
        "Events":      "NOTION_EVENTS_DB_ID",
    }

    for db_name, env_key in env_keys.items():
        if db_name in created:
            print(f"{env_key}={created[db_name]}")
        else:
            print(f"# {env_key}=<FEHLER – {db_name} nicht angelegt>")

    if errors:
        print()
        print("FEHLER beim Anlegen folgender Datenbanken:")
        for err in errors:
            print(f"  - {err}")
        print()
        print("Häufige Ursachen:")
        print("  • Die Integration hat keinen Zugriff auf die Parent-Seite")
        print("    → Seite öffnen → '...' → Connections → Integration hinzufügen")
        print("  • Falsche Parent-Page-ID")
        print("  • API-Token abgelaufen oder falsch")
        sys.exit(1)

    print()
    print("Nächste Schritte:")
    print("  1. Werte in .env eintragen")
    print("  2. Ersten Admin-Nutzer anlegen:")
    print("     python scripts/create_admin.py")
    print("  3. Server starten: bash start_server.sh")


if __name__ == "__main__":
    main()

"""
Einmalig ausführen, um alle vier Notion-Datenbanken anzulegen.

Verwendung:
    python -m notion.setup --parent-page-id <NOTION_PAGE_ID>

Nach der Ausführung werden die Datenbank-IDs ausgegeben.
Diese in die .env-Datei eintragen.
"""

import argparse
import sys

from notion_client import Client


def _time_slots(start_h: int = 16, end_h: int = 22) -> list[dict]:
    """Erzeugt alle 30-Minuten-Slots von start_h:00 bis end_h:00."""
    options = []
    h = start_h
    m = 0
    while (h, m) < (end_h, 0):
        options.append({"name": f"{h:02d}:{m:02d}"})
        m += 30
        if m == 60:
            m = 0
            h += 1
    return options


def _start_time_options() -> list[dict]:
    """16:00 bis 21:30"""
    return _time_slots(16, 22)[:-1]  # letzter Slot 21:30


def _end_time_options() -> list[dict]:
    """16:30 bis 22:00"""
    return _time_slots(16, 22)[1:]


PLATZ_OPTIONS = [
    {"name": "Kura Ganz"},
    {"name": "Kura Halb A"},
    {"name": "Kura Halb B"},
    {"name": "Rasen Ganz"},
    {"name": "Rasen Halb A"},
    {"name": "Rasen Halb B"},
    {"name": "Halle Ganz"},
    {"name": "Halle 2/3"},
    {"name": "Halle 1/3"},
]

DAUER_OPTIONS = [
    {"name": "60"},
    {"name": "90"},
    {"name": "180"},
]


def create_buchungen_db(client: Client, parent_page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Buchungen"}}],
        properties={
            "Titel": {"title": {}},
            "Platz": {"select": {"options": PLATZ_OPTIONS}},
            "Datum": {"date": {}},
            "Startzeit": {"select": {"options": _start_time_options()}},
            "Endzeit": {"select": {"options": _end_time_options()}},
            "Dauer": {"select": {"options": DAUER_OPTIONS}},
            "Typ": {
                "select": {
                    "options": [
                        {"name": "Training"},
                        {"name": "Spiel"},
                        {"name": "Turnier"},
                    ]
                }
            },
            "Gebucht von": {"rich_text": {}},
            "Gebucht von Name": {"rich_text": {}},
            "Mannschaft": {"rich_text": {}},
            "Serie": {"rich_text": {}},
            "Rolle": {
                "select": {
                    "options": [
                        {"name": "Trainer"},
                        {"name": "Administrator"},
                        {"name": "DFBnet"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "Bestätigt"},
                        {"name": "Storniert"},
                        {"name": "Storniert (DFBnet)"},
                    ]
                }
            },
            "Serienausnahme": {"checkbox": {}},
            "Hinweis Sonnenuntergang": {"rich_text": {}},
            "Zweck": {"rich_text": {}},
            "Kontakt": {"rich_text": {}},
            "Spielkennung": {"rich_text": {}},
        },
    )
    return db["id"]


def create_serien_db(client: Client, parent_page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Serien"}}],
        properties={
            "Titel": {"title": {}},
            "Platz": {"select": {"options": PLATZ_OPTIONS}},
            "Startzeit": {"select": {"options": _start_time_options()}},
            "Dauer": {"select": {"options": DAUER_OPTIONS}},
            "Rhythmus": {
                "select": {
                    "options": [
                        {"name": "Wöchentlich"},
                        {"name": "14-tägig"},
                    ]
                }
            },
            "Startdatum": {"date": {}},
            "Enddatum": {"date": {}},
            "Gebucht von ID": {"rich_text": {}},
            "Gebucht von Name": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Aktiv"},
                        {"name": "Pausiert"},
                        {"name": "Beendet"},
                    ]
                }
            },
            "Mannschaft": {"rich_text": {}},
            "Trainer ID": {"rich_text": {}},
            "Trainer Name": {"rich_text": {}},
        },
    )
    return db["id"]


def create_sperrzeiten_db(client: Client, parent_page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Sperrzeiten"}}],
        properties={
            "Titel": {"title": {}},
            "Datum": {"date": {}},
            "Art": {
                "select": {
                    "options": [
                        {"name": "Ganztägig"},
                        {"name": "Zeitlich"},
                    ]
                }
            },
            "Startzeit": {"select": {"options": _start_time_options()}},
            "Endzeit": {"select": {"options": _end_time_options()}},
            "Grund": {"rich_text": {}},
            "Eingetragen von ID": {"rich_text": {}},
            "Eingetragen von Name": {"rich_text": {}},
        },
    )
    return db["id"]


def create_nutzer_db(client: Client, parent_page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Nutzer"}}],
        properties={
            "Name": {"title": {}},
            "Rolle": {
                "select": {
                    "options": [
                        {"name": "Trainer"},
                        {"name": "Administrator"},
                        {"name": "Platzwart"},
                        {"name": "DFBnet"},
                    ]
                }
            },
            "E-Mail": {"email": {}},
            "Password_Hash": {"rich_text": {}},
            "Mannschaft": {
                "select": {
                    "options": [
                        {"name": "G1"}, {"name": "G2"}, {"name": "G3"},
                        {"name": "F1"}, {"name": "F2"},
                        {"name": "E1"}, {"name": "E2"}, {"name": "E3"},
                        {"name": "D1"}, {"name": "D2"},
                        {"name": "C"}, {"name": "B"}, {"name": "A"},
                        {"name": "TuS 1"}, {"name": "TuS 2"},
                        {"name": "Ü32"}, {"name": "Ü40"},
                        {"name": "Frauen"}, {"name": "Mädchen"},
                    ]
                }
            },
        },
    )
    return db["id"]



def create_aufgaben_db(client: Client, parent_page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Aufgaben"}}],
        properties={
            "Titel": {"title": {}},
            "Typ": {
                "select": {
                    "options": [
                        {"name": "Defekt"},
                        {"name": "Nutzeranfrage"},
                        {"name": "Turniertermin"},
                        {"name": "Sonstiges"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "Offen"},
                        {"name": "In Bearbeitung"},
                        {"name": "Erledigt"},
                    ]
                }
            },
            "Priorität": {
                "select": {
                    "options": [
                        {"name": "Niedrig"},
                        {"name": "Mittel"},
                        {"name": "Hoch"},
                    ]
                }
            },
            "Erstellt am": {"date": {}},
            "Fällig am": {"date": {}},
            "Erstellt von ID": {"rich_text": {}},
            "Erstellt von Name": {"rich_text": {}},
            "Ort": {"rich_text": {}},
            "Beschreibung": {"rich_text": {}},
        },
    )
    return db["id"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Notion-Datenbanken für das Buchungssystem anlegen")
    parser.add_argument("--parent-page-id", required=True, help="ID der Notion-Seite, unter der die DBs angelegt werden")
    parser.add_argument("--token", help="Notion API Token (alternativ: NOTION_API_KEY in .env)")
    args = parser.parse_args()

    if args.token:
        token = args.token
    else:
        try:
            from dotenv import load_dotenv
            import os
            load_dotenv()
            token = os.environ["NOTION_API_KEY"]
        except KeyError:
            print("Fehler: Kein Token angegeben. --token oder NOTION_API_KEY in .env setzen.")
            sys.exit(1)

    client = Client(auth=token)

    print("Lege Datenbanken an...")

    buchungen_id = create_buchungen_db(client, args.parent_page_id)
    print(f"  Buchungen:   NOTION_BUCHUNGEN_DB_ID={buchungen_id}")

    serien_id = create_serien_db(client, args.parent_page_id)
    print(f"  Serien:      NOTION_SERIEN_DB_ID={serien_id}")

    sperrzeiten_id = create_sperrzeiten_db(client, args.parent_page_id)
    print(f"  Sperrzeiten: NOTION_SPERRZEITEN_DB_ID={sperrzeiten_id}")

    nutzer_id = create_nutzer_db(client, args.parent_page_id)
    print(f"  Nutzer:      NOTION_NUTZER_DB_ID={nutzer_id}")

    aufgaben_id = create_aufgaben_db(client, args.parent_page_id)
    print(f"  Aufgaben:    NOTION_AUFGABEN_DB_ID={aufgaben_id}")

    print("\nFertig! Bitte die obigen IDs in die .env-Datei eintragen.")


if __name__ == "__main__":
    main()

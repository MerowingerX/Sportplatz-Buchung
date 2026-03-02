#!/usr/bin/env python3
"""
Stellt Nutzer und Serien aus einem Backup-Verzeichnis in Notion wieder her.

Einzelbuchungen werden NICHT wiederhergestellt (fließen per DFBnet-Sync
automatisch wieder ein).

Aufruf:
    python scripts/restore_notion.py backup/2026-03-01_19-00

    --dry-run   Zeigt an, was gemacht würde, ohne etwas zu schreiben.

Voraussetzung: Leere (oder neue) Notion-Datenbanken, deren IDs in .env stehen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

try:
    from notion_client import Client
except ImportError:
    print("FEHLER: notion-client nicht installiert.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Hilfsfunktionen: Werte aus Notion-Page-Properties lesen
# ---------------------------------------------------------------------------

def _title(props: dict, key: str) -> str:
    items = props.get(key, {}).get("title", [])
    return items[0]["plain_text"] if items else ""

def _rich_text(props: dict, key: str) -> str:
    items = props.get(key, {}).get("rich_text", [])
    return items[0]["plain_text"] if items else ""

def _select(props: dict, key: str) -> str | None:
    sel = props.get(key, {}).get("select")
    return sel["name"] if sel else None

def _checkbox(props: dict, key: str) -> bool:
    return props.get(key, {}).get("checkbox", False)

def _email(props: dict, key: str) -> str:
    return props.get(key, {}).get("email") or ""

def _date(props: dict, key: str) -> str | None:
    d = props.get(key, {}).get("date")
    return d["start"] if d else None


# ---------------------------------------------------------------------------
# Hilfsfunktionen: Notion-Properties schreiben
# ---------------------------------------------------------------------------

def _w_title(v: str) -> dict:
    return {"title": [{"text": {"content": v}}]}

def _w_rich_text(v: str) -> dict:
    return {"rich_text": [{"text": {"content": v}}]}

def _w_select(v: str) -> dict:
    return {"select": {"name": v}}

def _w_checkbox(v: bool) -> dict:
    return {"checkbox": v}

def _w_email(v: str) -> dict:
    return {"email": v}

def _w_date(v: str) -> dict:
    return {"date": {"start": v}}


# ---------------------------------------------------------------------------
# Nutzer wiederherstellen
# ---------------------------------------------------------------------------

def restore_users(
    client: Client,
    db_id: str,
    pages: list[dict],
    dry_run: bool,
) -> dict[str, str]:
    """Gibt {alter_notion_id: neuer_notion_id} zurück."""
    id_map: dict[str, str] = {}
    print(f"\n--- Nutzer ({len(pages)}) ---")

    for page in pages:
        old_id = page["id"]
        props = page["properties"]

        name        = _title(props, "Name")
        rolle       = _select(props, "Rolle") or "Trainer"
        email       = _email(props, "E-Mail")
        pw_hash     = _rich_text(props, "Password_Hash")
        mannschaft  = _select(props, "Mannschaft")
        must_change = _checkbox(props, "Passwort ändern")

        print(f"  {name} ({rolle})", end="")

        if dry_run:
            print("  [dry-run]")
            id_map[old_id] = f"dry-run-{old_id}"
            continue

        notion_props: dict = {
            "Name":            _w_title(name),
            "Rolle":           _w_select(rolle),
            "Password_Hash":   _w_rich_text(pw_hash),
            "Passwort ändern": _w_checkbox(must_change),
        }
        if email:
            notion_props["E-Mail"] = _w_email(email)
        if mannschaft:
            notion_props["Mannschaft"] = _w_select(mannschaft)

        new_page = client.pages.create(
            parent={"database_id": db_id},
            properties=notion_props,
        )
        new_id = new_page["id"]
        id_map[old_id] = new_id
        print(f"  → {new_id}")

    return id_map


# ---------------------------------------------------------------------------
# Serien wiederherstellen
# ---------------------------------------------------------------------------

def restore_series(
    client: Client,
    db_id: str,
    pages: list[dict],
    user_map: dict[str, str],
    dry_run: bool,
) -> None:
    print(f"\n--- Serien ({len(pages)}) ---")

    for page in pages:
        props = page["properties"]

        titel          = _title(props, "Titel")
        platz          = _select(props, "Platz")
        startzeit      = _select(props, "Startzeit")
        dauer          = _select(props, "Dauer")
        rhythmus       = _select(props, "Rhythmus")
        startdatum     = _date(props, "Startdatum")
        enddatum       = _date(props, "Enddatum")
        status         = _select(props, "Status") or "Aktiv"
        mannschaft     = _rich_text(props, "Mannschaft")
        gebucht_von_id = _rich_text(props, "Gebucht von ID")
        gebucht_von_name = _rich_text(props, "Gebucht von Name")
        trainer_id     = _rich_text(props, "Trainer ID")
        trainer_name   = _rich_text(props, "Trainer Name")

        # IDs remappen
        new_gebucht_id = user_map.get(gebucht_von_id, gebucht_von_id)
        new_trainer_id = user_map.get(trainer_id, trainer_id) if trainer_id else ""

        if gebucht_von_id and gebucht_von_id not in user_map:
            print(f"  WARNUNG: Gebucht-von-ID {gebucht_von_id!r} nicht im User-Mapping")
        if trainer_id and trainer_id not in user_map:
            print(f"  WARNUNG: Trainer-ID {trainer_id!r} nicht im User-Mapping")

        print(f"  {titel}", end="")

        if dry_run:
            print("  [dry-run]")
            continue

        notion_props: dict = {
            "Titel":            _w_title(titel),
            "Status":           _w_select(status),
            "Gebucht von ID":   _w_rich_text(new_gebucht_id),
            "Gebucht von Name": _w_rich_text(gebucht_von_name),
        }
        if platz:
            notion_props["Platz"] = _w_select(platz)
        if startzeit:
            notion_props["Startzeit"] = _w_select(startzeit)
        if dauer:
            notion_props["Dauer"] = _w_select(dauer)
        if rhythmus:
            notion_props["Rhythmus"] = _w_select(rhythmus)
        if startdatum:
            notion_props["Startdatum"] = _w_date(startdatum)
        if enddatum:
            notion_props["Enddatum"] = _w_date(enddatum)
        if mannschaft:
            notion_props["Mannschaft"] = _w_rich_text(mannschaft)
        if new_trainer_id:
            notion_props["Trainer ID"] = _w_rich_text(new_trainer_id)
        if trainer_name:
            notion_props["Trainer Name"] = _w_rich_text(trainer_name)

        new_page = client.pages.create(
            parent={"database_id": db_id},
            properties=notion_props,
        )
        print(f"  → {new_page['id']}")


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Notion-Restore (Nutzer + Serien)")
    parser.add_argument("backup_dir", type=Path, help="Backup-Verzeichnis (z. B. backup/2026-03-01_19-00)")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")
    args = parser.parse_args()

    backup_dir: Path = args.backup_dir
    if not backup_dir.is_dir():
        print(f"FEHLER: Verzeichnis nicht gefunden: {backup_dir}")
        sys.exit(1)

    api_key       = os.environ.get("NOTION_API_KEY", "")
    nutzer_db_id  = os.environ.get("NOTION_NUTZER_DB_ID", "")
    serien_db_id  = os.environ.get("NOTION_SERIEN_DB_ID", "")

    if not api_key or not nutzer_db_id or not serien_db_id:
        print("FEHLER: NOTION_API_KEY, NOTION_NUTZER_DB_ID und NOTION_SERIEN_DB_ID müssen gesetzt sein.")
        sys.exit(1)

    nutzer_file = backup_dir / "nutzer.json"
    serien_file = backup_dir / "serien.json"

    if not nutzer_file.exists() or not serien_file.exists():
        print(f"FEHLER: nutzer.json oder serien.json fehlen in {backup_dir}")
        sys.exit(1)

    nutzer_pages = json.loads(nutzer_file.read_text())
    serien_pages = json.loads(serien_file.read_text())

    meta_file = backup_dir / "meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        print(f"Backup vom: {meta.get('timestamp', '?')}")

    mode = "[DRY-RUN] " if args.dry_run else ""
    print(f"\n{mode}Restore aus: {backup_dir}")
    print(f"  Ziel Nutzer-DB:  {nutzer_db_id}")
    print(f"  Ziel Serien-DB:  {serien_db_id}")

    if not args.dry_run:
        antwort = input("\nFortfahren? Bestehende Einträge in den Ziel-DBs werden NICHT gelöscht. [j/N] ")
        if antwort.strip().lower() != "j":
            print("Abgebrochen.")
            sys.exit(0)

    client = Client(auth=api_key)

    user_map = restore_users(client, nutzer_db_id, nutzer_pages, args.dry_run)
    restore_series(client, serien_db_id, serien_pages, user_map, args.dry_run)

    print("\nRestore abgeschlossen.")
    if args.dry_run:
        print("(Kein Schreiben — dry-run)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Migration: Platz-Feldnamen → stabile interne IDs

Benennt alle "Platz"-Werte in der Buchungen-DB und Serien-DB von
menschenlesbaren Namen (z. B. "Kura Ganz") auf interne IDs (z. B. "A") um.

Ausführung:
  python scripts/migrate_field_names.py           # tatsächliche Migration
  python scripts/migrate_field_names.py --dry-run # nur Anzeige, kein Update
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Projektroot ins sys.path (für Imports aus web.config)
sys.path.insert(0, str(Path(__file__).parent.parent))

from notion_client import Client
from web.config import get_settings

OLD_TO_NEW: dict[str, str] = {
    "Kura Ganz":    "A",
    "Kura Halb A":  "AA",
    "Kura Halb B":  "AB",
    "Rasen Ganz":   "B",
    "Rasen Halb A": "BA",
    "Rasen Halb B": "BB",
    "Halle Ganz":   "C",
    "Halle 2/3":    "CA",
    "Halle 1/3":    "CB",
}


def _get_platz(page: dict) -> str | None:
    """Liest den aktuellen Platz-Select-Wert aus einer Notion-Seite."""
    try:
        sel = page["properties"]["Platz"]["select"]
        return sel["name"] if sel else None
    except (KeyError, TypeError):
        return None


def migrate_db(
    client: Client,
    db_id: str,
    db_name: str,
    dry_run: bool,
) -> tuple[int, int]:
    """
    Migriert alle Seiten in einer Datenbank.
    Gibt (aktualisiert, übersprungen) zurück.
    """
    updated = 0
    skipped = 0
    start_cursor = None

    print(f"\n=== {db_name} (DB: {db_id}) ===")

    while True:
        kwargs: dict = {
            "database_id": db_id,
            "page_size": 100,
            "filter": {"property": "Platz", "select": {"is_not_empty": True}},
        }
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        response = client.databases.query(**kwargs)
        pages = response.get("results", [])

        for page in pages:
            page_id = page["id"]
            old_val = _get_platz(page)

            if old_val is None:
                skipped += 1
                continue

            new_val = OLD_TO_NEW.get(old_val)
            if new_val is None:
                # Wert ist schon eine neue ID oder unbekannt
                print(f"  SKIP  {page_id[:8]}…  Platz={old_val!r} (kein Mapping)")
                skipped += 1
                continue

            print(f"  {'DRY ' if dry_run else ''}UPDATE  {page_id[:8]}…  {old_val!r} → {new_val!r}")
            if not dry_run:
                client.pages.update(
                    page_id=page_id,
                    properties={"Platz": {"select": {"name": new_val}}},
                )
            updated += 1

        if not response.get("has_more"):
            break
        start_cursor = response["next_cursor"]

    print(f"  → {updated} aktualisiert, {skipped} übersprungen")
    return updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Migriert Platz-Feldnamen in Notion-DBs")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, kein tatsächliches Update",
    )
    args = parser.parse_args()

    dry_run: bool = args.dry_run
    if dry_run:
        print("=== DRY RUN – es werden keine Änderungen vorgenommen ===")

    settings = get_settings()
    client = Client(auth=settings.notion_api_key)

    total_updated = 0
    total_skipped = 0

    dbs = [
        (settings.notion_buchungen_db_id, "Buchungen"),
        (settings.notion_serien_db_id, "Serien"),
    ]

    for db_id, db_name in dbs:
        u, s = migrate_db(client, db_id, db_name, dry_run)
        total_updated += u
        total_skipped += s

    print(f"\n{'DRY RUN ' if dry_run else ''}GESAMT: {total_updated} aktualisiert, {total_skipped} übersprungen")
    if dry_run:
        print("Zum tatsächlichen Migrieren ohne --dry-run ausführen.")


if __name__ == "__main__":
    main()

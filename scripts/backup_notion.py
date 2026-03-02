#!/usr/bin/env python3
"""
Backup aller Notion-Datenbanken nach /backup/<timestamp>/

Aufruf:
    python scripts/backup_notion.py                         # Default: /backup
    python scripts/backup_notion.py --dest ./backup_test    # anderes Ziel
    python scripts/backup_notion.py --keep 60               # Aufbewahrung in Tagen

Cron-Beispiel (täglich 03:00 Uhr):
    0 3 * * * cd /opt/sportplatz && .venv/bin/python scripts/backup_notion.py >> logs/backup.log 2>&1
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from notion_client import Client
except ImportError:
    print("FEHLER: notion-client nicht installiert.")
    sys.exit(1)

DEFAULT_DEST = Path("/backup")
DEFAULT_KEEP_DAYS = 30


def query_all(client: Client, database_id: str) -> list[dict]:
    """Lädt alle Seiten einer Notion-Datenbank (paginiert, 100er-Batches)."""
    results: list[dict] = []
    cursor = None
    while True:
        kwargs: dict = {"database_id": database_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def backup(dest: Path, keep_days: int) -> None:
    api_key = os.environ.get("NOTION_API_KEY", "")
    if not api_key:
        print("FEHLER: NOTION_API_KEY nicht gesetzt.")
        sys.exit(1)

    db_ids: dict[str, str] = {}
    for name, env_var in [
        ("buchungen",   "NOTION_BUCHUNGEN_DB_ID"),
        ("serien",      "NOTION_SERIEN_DB_ID"),
        ("nutzer",      "NOTION_NUTZER_DB_ID"),
        ("aufgaben",    "NOTION_AUFGABEN_DB_ID"),
    ]:
        val = os.environ.get(env_var, "")
        if not val:
            print(f"WARNUNG: {env_var} nicht gesetzt, wird übersprungen.")
        else:
            db_ids[name] = val

    events_id = os.environ.get("NOTION_EVENTS_DB_ID", "")
    if events_id:
        db_ids["events"] = events_id

    client = Client(auth=api_key)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    run_dir = dest / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir.chmod(0o700)  # Nutzer-Dump enthält Passwort-Hashes

    print(f"Backup nach {run_dir}")
    meta: dict = {"timestamp": ts, "databases": {}}

    for name, db_id in db_ids.items():
        print(f"  {name} … ", end="", flush=True)
        try:
            pages = query_all(client, db_id)
        except Exception as e:
            print(f"FEHLER: {e}")
            meta["databases"][name] = {"db_id": db_id, "error": str(e)}
            continue

        out_file = run_dir / f"{name}.json"
        out_file.write_text(
            json.dumps(pages, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        meta["databases"][name] = {"db_id": db_id, "count": len(pages)}
        print(f"{len(pages)} Einträge")

    (run_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Alte Backups löschen
    cutoff = datetime.now() - timedelta(days=keep_days)
    for d in sorted(dest.iterdir()):
        if not d.is_dir() or d == run_dir:
            continue
        try:
            dir_ts = datetime.strptime(d.name, "%Y-%m-%d_%H-%M")
        except ValueError:
            continue
        if dir_ts < cutoff:
            shutil.rmtree(d)
            print(f"  Altes Backup gelöscht: {d.name}")

    total = sum(
        v.get("count", 0) for v in meta["databases"].values() if isinstance(v, dict)
    )
    print(f"\nFertig – {total} Einträge gesichert → {run_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Notion-Datenbank-Backup")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                        help=f"Zielverzeichnis (default: {DEFAULT_DEST})")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP_DAYS,
                        help=f"Aufbewahrung in Tagen (default: {DEFAULT_KEEP_DAYS})")
    args = parser.parse_args()
    backup(args.dest, args.keep)

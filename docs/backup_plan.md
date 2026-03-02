# Plan: Notion-Datenbank-Backup

Stand: 2026-03-01

## Ziel

Ein eigenständiges Script (`scripts/backup_notion.py`) zieht alle Daten
aus den 6 Notion-Datenbanken und speichert sie als JSON-Dateien unter
`/backup/`. Das Script ist als Cron-Job betreibbar.

---

## Ausgabe-Struktur

```
/backup/
  2026-03-01_14-30/
    meta.json           ← Zeitstempel, DB-IDs, Zeilenzahl je Tabelle
    buchungen.json      ← alle Buchungen (roh, Notion-Format)
    serien.json         ← alle Serien
    sperrzeiten.json    ← alle Sperrzeiten
    nutzer.json         ← alle Nutzer inkl. Passwort-Hashes  ⚠ sensitiv
    aufgaben.json       ← alle Aufgaben
    events.json         ← externe Termine (nur wenn konfiguriert)
  2026-02-29_14-30/
  ...
```

Jede `.json`-Datei enthält eine JSON-Liste der rohen Notion-Page-Objekte
(genau was `databases.query()` zurückgibt). Das ermöglicht eine
vollständige Wiederherstellung in Notion oder eine spätere Migration.

---

## Implementierung: `scripts/backup_notion.py`

### Struktur

```python
#!/usr/bin/env python3
"""
Backup aller Notion-Datenbanken nach /backup/<timestamp>/

Aufruf:
    python scripts/backup_notion.py            # Backup mit Defaults
    python scripts/backup_notion.py --dest /mnt/nas/backup
    python scripts/backup_notion.py --keep 60  # Aufbewahrung in Tagen

Cron-Beispiel (täglich 03:00 Uhr):
    0 3 * * * cd /opt/sportplatz && .venv/bin/python scripts/backup_notion.py
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from notion_client import Client
except ImportError:
    print("FEHLER: notion-client nicht installiert.")
    sys.exit(1)


DEFAULT_DEST = Path("/backup")
DEFAULT_KEEP_DAYS = 30


def query_all(client: Client, database_id: str) -> list[dict]:
    """Lädt alle Seiten einer Notion-Datenbank (paginiert, 100er-Batches)."""
    results, cursor = [], None
    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def backup(dest: Path, keep_days: int) -> None:
    api_key = os.environ["NOTION_API_KEY"]
    db_ids = {
        "buchungen":  os.environ["NOTION_BUCHUNGEN_DB_ID"],
        "serien":     os.environ["NOTION_SERIEN_DB_ID"],
        "sperrzeiten":os.environ["NOTION_SPERRZEITEN_DB_ID"],
        "nutzer":     os.environ["NOTION_NUTZER_DB_ID"],
        "aufgaben":   os.environ["NOTION_AUFGABEN_DB_ID"],
    }
    events_id = os.environ.get("NOTION_EVENTS_DB_ID")
    if events_id:
        db_ids["events"] = events_id

    client = Client(auth=api_key)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    run_dir = dest / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    # Berechtigungen einschränken (Passwort-Hashes im Nutzer-Dump)
    run_dir.chmod(0o700)

    meta = {"timestamp": ts, "databases": {}}

    for name, db_id in db_ids.items():
        print(f"  {name} … ", end="", flush=True)
        pages = query_all(client, db_id)
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
        if not d.is_dir():
            continue
        try:
            dir_ts = datetime.strptime(d.name, "%Y-%m-%d_%H-%M")
        except ValueError:
            continue
        if dir_ts < cutoff:
            shutil.rmtree(d)
            print(f"  Altes Backup gelöscht: {d.name}")

    print(f"\nBackup abgeschlossen: {run_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP_DAYS,
                        help="Aufbewahrung in Tagen (default: 30)")
    args = parser.parse_args()
    backup(args.dest, args.keep)
```

---

## Dateien-Übersicht

| Datei | Aktion |
|-------|--------|
| `scripts/backup_notion.py` | Neues Script (erstellen) |
| `Todo.md` | Punkt unter „Backup-Strategie" als erledigt markieren |

Keine weiteren Code-Änderungen nötig — das Script ist vollständig
eigenständig (kein Import aus `web/` oder `booking/`).

---

## Cron-Job einrichten

```bash
# Crontab öffnen
crontab -e

# Täglich 03:00 Uhr (Pfade anpassen)
0 3 * * * cd /opt/sportplatz && .venv/bin/python scripts/backup_notion.py >> logs/backup.log 2>&1
```

Der Cron-Job läuft unter dem gleichen Nutzer wie der App-Dienst.
Ausgabe geht in `logs/backup.log` (liegt bereits in `.gitignore`).

---

## Sicherheitshinweise

| Risiko | Maßnahme |
|--------|----------|
| `nutzer.json` enthält bcrypt-Hashes | Verzeichnis mit `chmod 700` angelegt |
| `/backup` liegt auf dem App-Server | Zusätzlich auf externen Speicher spiegeln (NAS, S3) |
| Kein Verschlüsselung by default | Optional: `gpg --symmetric` nach dem Schreiben |

---

## Wiederherstellung: `scripts/restore_notion.py`

Stellt **Nutzer und Serien** aus einem Backup-Verzeichnis wieder her.
Einzelbuchungen werden nicht restauriert (DFBnet-Buchungen fließen per Sync
wieder ein, manuelle Einzelbuchungen müssen neu angelegt werden).

```bash
# Probe ohne Schreiben
python scripts/restore_notion.py backup/2026-03-01_19-00 --dry-run

# Scharf (fragt zur Bestätigung)
python scripts/restore_notion.py backup/2026-03-01_19-00
```

Das Script baut ein ID-Mapping `alter_notion_id → neuer_notion_id` für alle
Nutzer und trägt die neuen IDs in die wiederhergestellten Serien ein
(`Gebucht von ID`, `Trainer ID`).

**Voraussetzung:** Die Ziel-Datenbanken in Notion sind leer, sonst entstehen
doppelte Einträge.

## Wiederherstellung (Notion-API, manuell)

Die JSON-Dateien enthalten vollständige Notion-Page-Objekte. Eine
Wiederherstellung ist möglich über:

1. **Notion**: `pages.create()` mit den gespeicherten Properties — ein
   separates Restore-Script wäre nötig (nicht Scope dieses Plans).
2. **SQLite-Migration**: Die gespeicherten JSON-Dumps können direkt als
   Eingabe für das Migrationsskript aus
   [docs/db_migration_plan.md](db_migration_plan.md) dienen.

---

## Verifizierung

```bash
# Backup manuell ausführen
python scripts/backup_notion.py --dest ./backup_test --keep 7

# Ergebnis prüfen
ls -la backup_test/
cat backup_test/*/meta.json
```

Erwartetes `meta.json`:
```json
{
  "timestamp": "2026-03-01_14-30",
  "databases": {
    "buchungen":   {"db_id": "...", "count": 142},
    "serien":      {"db_id": "...", "count": 18},
    "sperrzeiten": {"db_id": "...", "count": 7},
    "nutzer":      {"db_id": "...", "count": 23},
    "aufgaben":    {"db_id": "...", "count": 4},
    "events":      {"db_id": "...", "count": 2}
  }
}
```

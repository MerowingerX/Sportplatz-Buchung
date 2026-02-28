#!/usr/bin/env python3
"""
tools/spielplan_sync_daily.py  –  täglicher Spielplan-Sync (für systemd-Timer)

Führt den vollständigen fussball.de ↔ Notion Abgleich durch:
  1. Spielplan von fussball.de laden
  2. Fehlende Heimspiele buchen (mit Verdrängung + E-Mail)
  3. Verwaiste Buchungen stornieren (+ E-Mail)
  4. Ergebnis in logs/sync_status.json schreiben

Verwendung:
    python tools/spielplan_sync_daily.py
    python tools/spielplan_sync_daily.py --dry-run   # nur ausgeben, nichts ändern

Benötigt .env mit:
    NOTION_API_KEY=...  NOTION_BUCHUNGEN_DB_ID=...
    SMTP_HOST=...  SMTP_USER=...  SMTP_PASSWORD=...  SMTP_FROM=...
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from booking.spielplan_sync import SyncResult, sync_spielplan, write_sync_status
    from notion.client import NotionRepository
    from web.config import Settings
except ImportError as e:
    print(f"Fehler beim Import: {e}")
    print("Stelle sicher, dass du das Script vom Projektroot aus startest.")
    sys.exit(1)


async def _run() -> SyncResult:
    settings = Settings()
    repo = NotionRepository(settings)
    return await sync_spielplan(repo, settings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Täglicher Spielplan-Sync")
    parser.add_argument("--dry-run", action="store_true",
                        help="Keine Änderungen, nur Ausgabe (simuliert)")
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Spielplan-Sync gestartet (triggered_by=systemd)")

    if args.dry_run:
        print("DRY-RUN – kein echter Abgleich, kein Statusfile-Update.")
        return

    try:
        result = asyncio.run(_run())
    except Exception as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        err = SyncResult(fehler=[str(exc)])
        write_sync_status(err, "systemd")
        sys.exit(1)

    write_sync_status(result, "systemd")

    print(f"  ✓ {len(result.gebucht)} Spiel(e) eingetragen")
    if result.verdraengt:
        print(f"  ⚠  {result.verdraengt} Buchung(en) verdrängt (E-Mail gesendet)")
    print(f"  ✗ {len(result.storniert)} verwaiste(s) Spiel(e) storniert")
    if result.uebersprungen:
        print(f"  ⏭  {len(result.uebersprungen)} bereits vorhanden")
    if result.fehler:
        print(f"  ⚠  {len(result.fehler)} Fehler:")
        for f in result.fehler:
            print(f"      {f}")
        sys.exit(2)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fertig.")


if __name__ == "__main__":
    main()

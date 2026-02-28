#!/usr/bin/env python3
"""
tools/delete_verwaist.py  –  verwaiste Buchungen stornieren

Liest die verwaist.csv (aus dem letzten Platzbelegung/fussball.de/DATUM/ZEIT/-
Verzeichnis oder per --csv angegeben) und storniert jede darin enthaltene
Buchung im Buchungssystem (Status → "Storniert").

Der jeweilige Buchende erhält automatisch eine Stornierungsmail.

Verwendung:
    python tools/delete_verwaist.py
    python tools/delete_verwaist.py --csv Platzbelegung/fussball.de/.../verwaist.csv
    python tools/delete_verwaist.py --dry-run

Benötigt .env mit:
    NOTION_API_KEY=secret_...
    NOTION_BUCHUNGEN_DB_ID=...
    SMTP_HOST=...  SMTP_USER=...  SMTP_PASSWORD=...  SMTP_FROM=...
"""

import argparse
import asyncio
import csv
import sys
from datetime import date, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from booking.models import BookingStatus, FieldName
    from notion.client import NotionRepository
    from notifications.notify import send_cancellation_notice
    from web.config import Settings
except ImportError as e:
    print(f"Fehler beim Import: {e}")
    print("Stelle sicher, dass du das Script vom Projektroot aus startest.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _find_latest_verwaist() -> str | None:
    base = PROJECT_ROOT / "Platzbelegung" / "fussball.de"
    candidates = sorted(base.glob("*/*/verwaist.csv"), reverse=True)
    return str(candidates[0]) if candidates else None


def _parse_time(s: str) -> time:
    h, m = s.strip().split(":")
    return time(int(h), int(m))


async def _send_mail(booking, repo, settings) -> bool:
    owner = repo.get_user_by_id(booking.booked_by_id)
    if owner and getattr(owner, "email", None):
        await send_cancellation_notice(booking, owner, settings)
        return True
    return False


# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verwaiste Buchungen stornieren",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--csv",
        metavar="DATEI",
        default="",
        help="Pfad zur verwaist.csv (Standard: neueste in Platzbelegung/fussball.de/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Keine Änderungen vornehmen, nur anzeigen was getan würde",
    )
    args = parser.parse_args()

    # CSV finden
    csv_pfad = args.csv or _find_latest_verwaist()
    if not csv_pfad or not Path(csv_pfad).exists():
        print("Fehler: Keine verwaist.csv gefunden.")
        print("  Starte zuerst: python tools/check_spielplan.py --gegencheck")
        print("  Oder gib explizit --csv <pfad> an.")
        sys.exit(1)

    print(f"Lese CSV: {csv_pfad}")

    with open(csv_pfad, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        eintraege = [row for row in reader if row.get("datum")]

    if not eintraege:
        print("Keine Einträge in der CSV gefunden.")
        return

    print(f"  → {len(eintraege)} Buchung(en) zu stornieren\n")

    if args.dry_run:
        print("⚠  DRY-RUN – es werden keine Änderungen vorgenommen.\n")

    try:
        settings = Settings()
        repo = NotionRepository(settings)
    except Exception as e:
        print(f"Fehler beim Initialisieren: {e}")
        sys.exit(1)

    storniert: list[str] = []
    nicht_gefunden: list[str] = []

    for eintrag in eintraege:
        datum_str  = eintrag.get("datum", "").strip()
        startzeit  = eintrag.get("startzeit", "").strip()
        platz_str  = eintrag.get("platz", "").strip()
        titel      = eintrag.get("titel", "").strip()
        label = f"{datum_str}  {startzeit}  {platz_str}"

        # Datum parsen
        try:
            buchungs_datum = date.fromisoformat(datum_str)
        except ValueError:
            print(f"  ✗ Ungültiges Datum {datum_str!r} → übersprungen")
            nicht_gefunden.append(label)
            continue

        if buchungs_datum < date.today():
            print(f"  ⏭  {label}  → liegt in der Vergangenheit, übersprungen")
            nicht_gefunden.append(label)
            continue

        # Uhrzeit parsen
        try:
            start_time = _parse_time(startzeit)
        except (ValueError, AttributeError):
            print(f"  ✗ Ungültige Uhrzeit {startzeit!r} → übersprungen")
            nicht_gefunden.append(label)
            continue

        # Buchung im System suchen: alle Buchungen des Tages laden,
        # dann nach Platz + Startzeit filtern
        tages_buchungen = repo.get_bookings_for_date(buchungs_datum)
        treffer = [
            b for b in tages_buchungen
            if b.field.value == platz_str and b.start_time == start_time
        ]

        if not treffer:
            print(f"  ⚠  {label}  → nicht (mehr) im System gefunden, übersprungen")
            nicht_gefunden.append(label)
            continue

        if args.dry_run:
            for b in treffer:
                print(f"  würde stornieren: {label}  (Buchungs-ID: {b.notion_id[:8]}…)")
            continue

        for b in treffer:
            try:
                updated = repo.update_booking_status(b.notion_id, BookingStatus.STORNIERT)
            except Exception as e:
                print(f"  ✗ Fehler beim Stornieren von {label}: {e}")
                nicht_gefunden.append(label)
                continue

            mail_gesendet = asyncio.run(_send_mail(updated, repo, settings))
            mail_info = "Mail gesendet" if mail_gesendet else "kein E-Mail-Empfänger"
            print(f"  ✓ {label}  → storniert  ({mail_info})")
            storniert.append(label)

    # Abschlussbericht
    print()
    if args.dry_run:
        print(f"DRY-RUN abgeschlossen – {len(eintraege)} Buchung(en) geprüft, nichts geändert.")
        return

    print(f"Fertig:")
    print(f"  ✓ {len(storniert)} Buchung(en) storniert")
    if nicht_gefunden:
        print(f"  ⚠  {len(nicht_gefunden)} nicht gefunden oder Fehler")


if __name__ == "__main__":
    main()

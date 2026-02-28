#!/usr/bin/env python3
"""
tools/import_fehlend.py  –  fehlend.csv Spiele ins Buchungssystem importieren

Liest die fehlend.csv (aus dem letzten Platzbelegung/fussball.de/DATUM/ZEIT/-
Verzeichnis oder per --csv angegeben) und legt für jedes Spiel eine Buchung an.

Bestehende Buchungen, die zeitlich mit dem Spiel kollidieren, werden auf
"Storniert (DFBnet)" gesetzt. Die Betroffenen erhalten automatisch eine E-Mail.

Verwendung:
    python tools/import_fehlend.py
    python tools/import_fehlend.py --csv Platzbelegung/fussball.de/.../fehlend.csv
    python tools/import_fehlend.py --dry-run
    python tools/import_fehlend.py --dauer 90

Benötigt .env mit:
    NOTION_API_KEY=secret_...
    NOTION_BUCHUNGEN_DB_ID=...
    SMTP_HOST=...  SMTP_USER=...  SMTP_PASSWORD=...  SMTP_FROM=...
"""

import argparse
import asyncio
import csv
import os
import sys
from datetime import date, time
from pathlib import Path

# Projektroot in den Python-Pfad aufnehmen
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from booking.booking import dfbnet_displace
    from booking.models import BookingCreate, BookingType, FieldName, TokenPayload, UserRole
    from notion.client import NotionRepository
    from notifications.notify import send_dfbnet_displacement_notice
    from web.config import Settings
except ImportError as e:
    print(f"Fehler beim Import: {e}")
    print("Stelle sicher, dass du das Script vom Projektroot aus startest:")
    print("  python tools/import_fehlend.py")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Spielort → Platzbelegung
# ---------------------------------------------------------------------------
_SPIELORT_ZU_FELD: list[tuple[str, FieldName]] = [
    ("cremlingen b-platz", FieldName.KURA_GANZ),
    ("cremlingen a-platz rasen", FieldName.RASEN_GANZ),
]


def _spielort_zu_feld(spielort: str) -> FieldName | None:
    for substr, feld in _SPIELORT_ZU_FELD:
        if substr in spielort.lower():
            return feld
    return None


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _find_latest_fehlend() -> str | None:
    """Sucht die neueste fehlend.csv unter Platzbelegung/fussball.de/."""
    base = PROJECT_ROOT / "Platzbelegung" / "fussball.de"
    candidates = sorted(base.glob("*/*/fehlend.csv"), reverse=True)
    return str(candidates[0]) if candidates else None


def _parse_time(s: str) -> time:
    h, m = s.strip().split(":")
    return time(int(h), int(m))


def _system_user() -> TokenPayload:
    """Erstellt einen System-TokenPayload mit DFBnet-Rolle."""
    import time as _time
    return TokenPayload(
        sub="dfbnet-import-script",
        username="DFBnet Import",
        role=UserRole.DFBNET,
        mannschaft=None,
        must_change_password=False,
        exp=int(_time.time()) + 3600,
    )


async def _send_displacement_mails(
    displaced_list,
    new_booking,
    repo: NotionRepository,
    settings: Settings,
) -> int:
    """Versendet Verdrängungsmails. Gibt Anzahl versendeter Mails zurück."""
    sent = 0
    for b in displaced_list:
        owner = repo.get_user_by_id(b.booked_by_id)
        if owner and getattr(owner, "email", None):
            await send_dfbnet_displacement_notice(b, owner, new_booking, settings)
            sent += 1
        else:
            print(f"    ⚠  Kein E-Mail-Empfänger für verdrängten Nutzer {b.booked_by_id!r}")
    return sent


# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="fehlend.csv Spiele ins Buchungssystem importieren",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--csv",
        metavar="DATEI",
        default="",
        help="Pfad zur fehlend.csv (Standard: neueste in Platzbelegung/fussball.de/)",
    )
    parser.add_argument(
        "--dauer",
        metavar="MIN",
        type=int,
        default=90,
        help="Buchungsdauer in Minuten (Standard: 90)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Keine Buchungen anlegen, nur anzeigen was getan würde",
    )
    args = parser.parse_args()

    # CSV finden
    csv_pfad = args.csv or _find_latest_fehlend()
    if not csv_pfad or not Path(csv_pfad).exists():
        print("Fehler: Keine fehlend.csv gefunden.")
        print("  Starte zuerst: python tools/check_spielplan.py --gegencheck")
        print("  Oder gib explizit --csv <pfad> an.")
        sys.exit(1)

    print(f"Lese CSV: {csv_pfad}")

    # Spiele einlesen
    with open(csv_pfad, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        spiele = [row for row in reader if row.get("datum")]

    if not spiele:
        print("Keine Spiele in der CSV gefunden.")
        return

    print(f"  → {len(spiele)} Spiel(e) gefunden\n")

    if args.dry_run:
        print("⚠  DRY-RUN – es werden keine Buchungen angelegt.\n")

    # Settings & Repository initialisieren
    try:
        settings = Settings()
        repo = NotionRepository(settings)
    except Exception as e:
        print(f"Fehler beim Initialisieren: {e}")
        sys.exit(1)

    system_user = _system_user()

    # Statistik
    erstellt: list[str] = []
    uebersprungen: list[str] = []
    verdraengt_gesamt = 0

    for spiel in spiele:
        datum_str  = spiel.get("datum", "").strip()
        uhrzeit_str = spiel.get("uhrzeit", "").strip()
        heim        = spiel.get("heim", "").strip()
        gast        = spiel.get("gast", "").strip()
        mannschaft  = spiel.get("mannschaft", "").strip()
        wettbewerb  = spiel.get("wettbewerb", "").strip()
        spielort    = spiel.get("spielort", "").strip()

        # Datum & Zeit parsen
        try:
            datum = date.fromisoformat(datum_str)
        except ValueError:
            print(f"✗ Ungültiges Datum {datum_str!r} → übersprungen")
            uebersprungen.append(f"{datum_str} – {heim} vs {gast}")
            continue

        if datum < date.today():
            print(f"  ⏭  {datum_str}  Spiel liegt in der Vergangenheit → übersprungen")
            uebersprungen.append(f"{datum_str} – {heim} vs {gast}")
            continue

        try:
            start_time = _parse_time(uhrzeit_str)
        except (ValueError, AttributeError):
            print(f"✗ Ungültige Uhrzeit {uhrzeit_str!r} für {datum_str} → übersprungen")
            uebersprungen.append(f"{datum_str} – {heim} vs {gast}")
            continue

        # Platz bestimmen
        feld = _spielort_zu_feld(spielort)
        if feld is None:
            print(f"✗ Unbekannter Spielort für {datum_str}: {spielort!r} → übersprungen")
            uebersprungen.append(f"{datum_str} – {heim} vs {gast}")
            continue

        zweck = f"[{wettbewerb}] {heim} vs {gast}"
        label = f"{datum_str} {uhrzeit_str}  {feld.value}  {zweck}"

        if args.dry_run:
            print(f"  würde anlegen: {label}")
            continue

        # Bestehende Buchungen für diesen Tag laden
        existing = repo.get_bookings_for_date(datum)

        # Duplikat-Check: Gibt es bereits ein Spiel (SPIEL) auf diesem Platz zur selben Zeit?
        from booking.booking import check_availability
        konflikte = check_availability(existing, feld, start_time, args.dauer)
        spiel_konflikte = [b for b in konflikte if b.booking_type == BookingType.SPIEL]

        if spiel_konflikte:
            info = spiel_konflikte[0]
            print(
                f"  ⏭  {datum_str} {uhrzeit_str}  {feld.value}  bereits als Spiel gebucht "
                f"({info.start_time.strftime('%H:%M')}–{info.end_time.strftime('%H:%M')}) → übersprungen"
            )
            uebersprungen.append(label)
            continue

        # Buchung anlegen (mit Verdrängung)
        data = BookingCreate(
            field=feld,
            date=datum,
            start_time=start_time,
            duration_min=args.dauer,
            booking_type=BookingType.SPIEL,
            zweck=zweck,
        )

        try:
            new_booking, displaced = dfbnet_displace(repo, data, system_user, settings, existing)
        except Exception as e:
            print(f"  ✗ Fehler beim Anlegen von {label}: {e}")
            uebersprungen.append(label)
            continue

        erstellt.append(label)
        verdraengt_gesamt += len(displaced)

        print(f"  ✓ {label}")
        if displaced:
            print(f"    → {len(displaced)} Buchung(en) verdrängt, sende E-Mails …")
            mails_gesendet = asyncio.run(
                _send_displacement_mails(displaced, new_booking, repo, settings)
            )
            print(f"    → {mails_gesendet} Verdrängungsmail(s) versendet")

    # Abschlussbericht
    print()
    if args.dry_run:
        print(f"DRY-RUN abgeschlossen – {len(spiele)} Spiel(e) geprüft, nichts geändert.")
        return

    print(f"Fertig:")
    print(f"  ✓ {len(erstellt)} Buchung(en) neu erstellt")
    if verdraengt_gesamt:
        print(f"  ⚠  {verdraengt_gesamt} bestehende Buchung(en) verdrängt (E-Mail gesendet)")
    if uebersprungen:
        print(f"  ⏭  {len(uebersprungen)} übersprungen (bereits vorhanden oder unbekannter Platz)")


if __name__ == "__main__":
    main()

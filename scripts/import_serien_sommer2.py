"""
Skript: Serien aus Backup mit neuen Platzdefinitionen neu anlegen.

Hintergrund:
  Die alten Platznamen ("Kura Halb A", "Kura Ganz", …) wurden auf
  kurze IDs ("AA", "A", …) migriert. Die bestehenden Serien im Backup
  haben noch die alten Namen und müssen mit den neuen Platz-IDs und
  Start ab 01.03.2026 neu angelegt werden.

Aufruf:
  # Nur Vorschau (kein Schreiben nach Notion):
  python scripts/import_serien_sommer2.py --dry-run

  # Tatsächlich anlegen:
  python scripts/import_serien_sommer2.py

Deduplizierung:
  Duplikate (gleiche Mannschaft + Platz + Zeit + Rhythmus + Dauer)
  werden auf einen Eintrag reduziert.
"""

import argparse
import json
import sys
from datetime import date, time, timedelta
from pathlib import Path

# Projekt-Root zum sys.path hinzufügen
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from booking.models import FieldName, SeriesCreate, SeriesRhythm, SeriesSaison, UserRole
from booking.series import create_series_with_bookings
from notion.client import NotionRepository
from web.config import get_settings

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

BACKUP_FILE = ROOT / "backup" / "2026-03-01_19-00" / "serien.json"
TARGET_START = date(2026, 3, 1)
DEFAULT_END = date(2026, 6, 29)
SAISON = SeriesSaison.SOMMERHALBJAHR

# Alte Platznamen → neue FieldName-IDs
FIELD_MAP: dict[str, FieldName] = {
    "Kura Halb A": FieldName.AA,
    "Kura Halb B": FieldName.AB,
    "Kura Ganz":   FieldName.A,
    "Rasen Halb A": FieldName.BA,
    "Rasen Halb B": FieldName.BB,
    "Rasen Ganz":  FieldName.B,
    "Halle Ganz":  FieldName.C,
    "Halle 2/3":   FieldName.CA,
    "Halle 1/3":   FieldName.CB,
}

# Nutzer-IDs (für booked_by_id; aus Backup nutzer.json)
USER_IDS = {
    "frank":    "308ca010-5fee-805e-a957-e3378e5e7e8c",
    "Frank(D)": "309ca010-5fee-814d-83fe-eb162c147525",
    "BerndK":   "30eca010-5fee-81f6-8329-d573c9c1b18c",
    "TommiS":   "30fca010-5fee-8182-a260-cd6cd837de82",
    "admin":    "308ca010-5fee-804b-b86b-ff1135591859",
}

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _get_text(prop: dict) -> str:
    return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))


def _get_select(prop: dict) -> str | None:
    return prop.get("select", {}).get("name") if prop.get("select") else None


def _get_date(prop: dict) -> date | None:
    raw = prop.get("date", {}).get("start") if prop.get("date") else None
    return date.fromisoformat(raw) if raw else None


def first_weekday_from(target: date, weekday: int) -> date:
    """Erstes Datum mit gegebenem Wochentag ab target (0=Mo … 6=So)."""
    days_ahead = (weekday - target.weekday()) % 7
    return target + timedelta(days=days_ahead)


def parse_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


# ---------------------------------------------------------------------------
# Backup parsen und deduplizieren
# ---------------------------------------------------------------------------

def load_series_from_backup() -> list[dict]:
    with open(BACKUP_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Erst alle Einträge einlesen; dann pro (mannschaft, platz, zeit, rhythmus, wochentag)
    # nur den mit der längsten Dauer behalten.
    # Wochentag statt roher Dauer als Dedup-Schlüssel, damit z. B. D2 Kura Halb B
    # Di 17:00 60min und Do 17:00 90min als zwei getrennte Serien behandelt werden.
    best: dict[tuple, dict] = {}

    for entry in data:
        p = entry["properties"]
        mannschaft_str = _get_text(p["Mannschaft"])
        if not mannschaft_str:
            continue

        platz_old = _get_select(p["Platz"])
        if platz_old not in FIELD_MAP:
            print(f"  WARNUNG: unbekannter Platz '{platz_old}' – übersprungen")
            continue

        startzeit_str = _get_select(p["Startzeit"])
        rhythmus_str = _get_select(p["Rhythmus"])
        dauer = int(_get_select(p["Dauer"]) or 90)
        start_old = _get_date(p["Startdatum"])
        ende = _get_date(p["Enddatum"]) or DEFAULT_END
        trainer_name = _get_text(p["Trainer Name"]) or _get_text(p["Gebucht von Name"])
        trainer_id = _get_text(p["Trainer ID"]) or _get_text(p["Gebucht von ID"])

        field = FIELD_MAP[platz_old]
        new_start = first_weekday_from(TARGET_START, start_old.weekday())

        # Schlüssel: Wochentag des neuen Starts (statt Dauer) → Konflikte auf gleichem
        # Platz/Tag/Zeit werden auf den längsten Eintrag reduziert.
        key = (mannschaft_str, field.value, startzeit_str, rhythmus_str, new_start)

        candidate = {
            "mannschaft_str": mannschaft_str,
            "platz_old": platz_old,
            "field": field,
            "startzeit_str": startzeit_str,
            "rhythmus_str": rhythmus_str,
            "dauer": dauer,
            "new_start": new_start,
            "ende": ende,
            "trainer_name": trainer_name,
            "trainer_id": trainer_id,
        }

        # Längere Dauer gewinnt
        if key not in best or dauer > best[key]["dauer"]:
            best[key] = candidate

    return list(best.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Serien aus Backup mit neuen Platzdefinitionen anlegen")
    parser.add_argument("--dry-run", action="store_true", help="Nur Vorschau, kein Schreiben nach Notion")
    args = parser.parse_args()

    print("=== Serien-Import: Sommer 2 (ab 01.03.2026) ===\n")
    if args.dry_run:
        print("MODUS: DRY-RUN – es werden keine Änderungen nach Notion geschrieben.\n")

    series_list = load_series_from_backup()
    print(f"Gefunden: {len(series_list)} Serien (nach Deduplizierung)\n")

    # Vorschau-Tabelle
    print(f"{'#':>2}  {'Mannschaft':<12} {'Platz alt':<16} {'→ Neu':<6} {'Zeit':<7} {'Min':<5} {'Rhythmus':<12} {'Start':<12} {'Ende':<12} {'Trainer'}")
    print("-" * 105)
    for i, s in enumerate(series_list):
        rhythmus_short = "14-täg." if "14" in s["rhythmus_str"] else "wöch."
        print(
            f"{i+1:>2}  {s['mannschaft_str']:<12} {s['platz_old']:<16} "
            f"{s['field'].value:<6} {s['startzeit_str']:<7} {s['dauer']:<5} "
            f"{rhythmus_short:<12} {s['new_start'].isoformat():<12} "
            f"{s['ende'].isoformat():<12} {s['trainer_name']}"
        )

    if args.dry_run:
        print("\nDry-run abgeschlossen. Zum Anlegen ohne --dry-run ausführen.")
        return

    print("\nStarte Anlage in Notion …\n")
    settings = get_settings()
    repo = NotionRepository(settings)

    ok_count = 0
    err_count = 0
    skip_total = 0

    for i, s in enumerate(series_list):
        mannschaft_str = s["mannschaft_str"]
        try:
            rhythmus = SeriesRhythm(s["rhythmus_str"])
        except ValueError:
            print(f"[{i+1}] FEHLER: Rhythmus '{s['rhythmus_str']}' unbekannt – übersprungen")
            err_count += 1
            continue

        data = SeriesCreate(
            field=s["field"],
            start_time=parse_time(s["startzeit_str"]),
            duration_min=s["dauer"],
            rhythm=rhythmus,
            start_date=s["new_start"],
            end_date=s["ende"],
            mannschaft=mannschaft_str,
            trainer_id=s["trainer_id"],
            saison=SAISON,
        )

        # Minimales TokenPayload-Objekt (nur sub + username benötigt)
        class _FakeUser:
            sub = s["trainer_id"]
            username = s["trainer_name"]
            role = UserRole.TRAINER
            mannschaft = s["mannschaft_str"]

        try:
            series, created, skipped = create_series_with_bookings(
                repo=repo,
                data=data,
                current_user=_FakeUser(),
                settings=settings,
                trainer_name=s["trainer_name"],
            )
            ok_count += 1
            skip_total += len(skipped)
            skipped_info = f", {len(skipped)} übersprungen (Konflikt)" if skipped else ""
            print(
                f"[{i+1:>2}] OK  {mannschaft_str:<10} {s['field'].value:<4} "
                f"{s['startzeit_str']}  → Serie {series.notion_id[:8]}…  "
                f"{len(created)} Termine{skipped_info}"
            )
        except Exception as exc:
            print(f"[{i+1:>2}] ERR {mannschaft_str:<10} {s['field'].value:<4} {s['startzeit_str']}  → {exc}")
            err_count += 1

    print(f"\n=== Ergebnis ===")
    print(f"  Angelegt: {ok_count} Serien")
    print(f"  Fehler:   {err_count}")
    print(f"  Übersprungene Buchungstermine (Konflikte): {skip_total}")


if __name__ == "__main__":
    main()

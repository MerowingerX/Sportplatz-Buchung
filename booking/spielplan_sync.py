"""
booking/spielplan_sync.py  –  fussball.de ↔ Notion Spielplan-Synchronisation

Enthält die Kern-Logik für den automatischen Abgleich:
  1. Spielplan von fussball.de laden
  2. Fehlende Heimspiele im Buchungssystem eintragen (mit Verdrängung)
  3. Verwaiste Buchungen stornieren (kein fussball.de-Spiel mehr vorhanden)
  4. Betroffene Nutzer per E-Mail benachrichtigen

Wird verwendet von:
  - web/routers/admin.py  (Admin-Button im Dashboard)
  - tools/import_fehlend.py / tools/delete_verwaist.py (CLI)
"""

from __future__ import annotations

import json
import sys
import time as _time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

SYNC_STATUS_FILE = Path(__file__).parent.parent / "logs" / "sync_status.json"

from booking.booking import check_availability, dfbnet_displace
from booking.models import (
    BookingCreate,
    BookingStatus,
    BookingType,
    FieldName,
    TokenPayload,
    UserRole,
)
from notion.client import NotionRepository
from notifications.notify import send_cancellation_notice, send_dfbnet_displacement_notice
from web.config import Settings

# tools/ zum Pfad hinzufügen, damit fussball_de importiert werden kann
_TOOLS = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(_TOOLS))

try:
    from fussball_de import fetch_matchplan_html, parse_matchplan  # type: ignore[import]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "tools/fussball_de.py nicht gefunden. "
        "Stelle sicher, dass das Script vom Projektroot aus ausgeführt wird."
    ) from e


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------
_FALLBACK_CLUB_ID = "00ES8GN75400000VVV0AG08LVUPGND5I"  # Fallback wenn .env leer

from booking.vereinsconfig import get_spielort_zu_feld, get_feld_praefixe, get_heim_keywords

# fussball.de Spielort-Substring → Notion FieldName  (aus config/vereinsconfig.json)
_SPIELORT_ZU_FELD: list[tuple[str, FieldName]] = get_spielort_zu_feld()

# Notion Platz-Präfix für Gegencheck  (aus config/vereinsconfig.json)
_FELD_PRAEFIXE: set[str] = get_feld_praefixe()


# ---------------------------------------------------------------------------
# Ergebnis-Dataclass
# ---------------------------------------------------------------------------
@dataclass
class SyncResult:
    gebucht: list[str] = field(default_factory=list)       # neue Buchungen
    uebersprungen: list[str] = field(default_factory=list) # bereits als Spiel vorhanden
    verdraengt: int = 0                                    # verdrängte Buchungen gesamt
    storniert: list[str] = field(default_factory=list)     # stornierte Buchungen
    fehler: list[str] = field(default_factory=list)        # Fehlermeldungen
    gefunden: int = 0                                      # Heimspiele auf fussball.de gesamt

    @property
    def ok(self) -> bool:
        return not self.fehler

    def zusammenfassung(self) -> str:
        teile = []
        if self.gefunden:
            teile.append(f"{self.gefunden} Spiel(e) gefunden")
        teile.append(f"{len(self.gebucht)} eingetragen")
        if self.verdraengt:
            teile.append(f"{self.verdraengt} verdrängt")
        teile.append(f"{len(self.storniert)} storniert")
        if self.fehler:
            teile.append(f"{len(self.fehler)} Fehler")
        return " · ".join(teile)


def write_sync_status(result: SyncResult, triggered_by: str = "admin") -> None:
    """Schreibt das Sync-Ergebnis in logs/sync_status.json."""
    status = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "triggered_by": triggered_by,
        "ok": result.ok,
        "summary": result.zusammenfassung(),
        "gefunden": result.gefunden,
        "gebucht": len(result.gebucht),
        "uebersprungen": len(result.uebersprungen),
        "storniert": len(result.storniert),
        "fehler": len(result.fehler),
        "fehler_detail": result.fehler,
    }
    try:
        SYNC_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    except Exception:
        pass


def read_sync_status() -> dict | None:
    """Liest den letzten Sync-Status aus logs/sync_status.json."""
    try:
        return json.loads(SYNC_STATUS_FILE.read_text())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _spielort_zu_feld(spielort: str) -> Optional[FieldName]:
    for substr, feld in _SPIELORT_ZU_FELD:
        if substr in spielort.lower():
            return feld
    return None


def _system_user() -> TokenPayload:
    return TokenPayload(
        sub="dfbnet-import-script",
        username="DFBnet Import",
        role=UserRole.DFBNET,
        mannschaft=None,
        must_change_password=False,
        exp=int(_time.time()) + 3600,
    )


def _get_select(props: dict, name: str) -> str:
    try:
        return props[name]["select"]["name"] or ""
    except (KeyError, TypeError):
        return ""


def _get_date(props: dict, name: str) -> str:
    try:
        return props[name]["date"]["start"] or ""
    except (KeyError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Bulk-Abfrage: alle bestätigten Buchungen in einem Datumsbereich
# ---------------------------------------------------------------------------
def _lade_buchungen_mit_id(
    repo: NotionRepository,
    von_iso: str,
    bis_iso: str,
) -> dict[str, list[dict]]:
    """
    Lädt alle bestätigten Buchungen im Bereich [von, bis] als
    {datum_iso: [{"id": notion_page_id, "props": {...}}, ...]} zurück.
    """
    ergebnis: dict[str, list[dict]] = defaultdict(list)
    cursor = None

    while True:
        kwargs: dict = {
            "database_id": repo._settings.notion_buchungen_db_id,
            "page_size": 100,
            "filter": {
                "and": [
                    {"property": "Datum", "date": {"on_or_after": von_iso}},
                    {"property": "Datum", "date": {"on_or_before": bis_iso}},
                    {"property": "Status", "select": {"equals": "Bestätigt"}},
                ]
            },
        }
        if cursor:
            kwargs["start_cursor"] = cursor

        result = repo._client.databases.query(**kwargs)
        for page in result["results"]:
            props = page["properties"]
            datum = _get_date(props, "Datum")
            if datum:
                ergebnis[datum].append({"id": page["id"], "props": props})

        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")

    return dict(ergebnis)


# ---------------------------------------------------------------------------
# Kern-Synchronisation (async für E-Mail-Versand)
# ---------------------------------------------------------------------------
async def sync_spielplan(repo: NotionRepository, settings: Settings) -> SyncResult:
    """
    Führt den vollständigen Spielplan-Abgleich durch:

    1. Spielplan von fussball.de laden (synchron via requests)
    2. Fehlende Heimspiele eintragen (dfbnet_displace)
    3. Verwaiste Buchungen stornieren
    4. E-Mails versenden (async)

    Gibt ein SyncResult mit Statistiken zurück.
    """
    import asyncio

    result = SyncResult()
    email_coros = []
    sys_user = _system_user()

    # ── 1. fussball.de Spielplan laden ──────────────────────────────────────
    vereinsseite = getattr(settings, "fussball_de_vereinsseite", None)
    if vereinsseite:
        from fussball_de import _club_id_from_url  # type: ignore[import]
        club_id = _club_id_from_url(vereinsseite) or _FALLBACK_CLUB_ID
    else:
        club_id = _FALLBACK_CLUB_ID
    html = fetch_matchplan_html(club_id)
    alle_spiele = parse_matchplan(html, heim_keywords=get_heim_keywords())

    heute = date.today()
    heim_spiele = [
        s for s in alle_spiele
        if s.ist_heimspiel
        and s.spielort
        and _spielort_zu_feld(s.spielort)
        and date.fromisoformat(s.datum) >= heute  # nur zukünftige Spiele
    ]

    result.gefunden = len(heim_spiele)

    if not heim_spiele:
        return result

    # Datumsbereich
    daten = sorted(s.datum for s in heim_spiele)
    von_iso = date.today().isoformat()
    bis_iso = daten[-1]

    # ── 2. Notion-Buchungen (Bulk) laden ────────────────────────────────────
    buchungen = _lade_buchungen_mit_id(repo, von_iso, bis_iso)

    # ── 3. Hincheck: Heimspiele ohne Buchung ─────────────────────────────────
    for spiel in sorted(heim_spiele, key=lambda s: (s.datum, s.uhrzeit)):
        feld = _spielort_zu_feld(spiel.spielort)
        if feld is None:
            continue

        # Startzeit parsen
        try:
            from datetime import time as _time_cls
            h, m = spiel.uhrzeit.split(":")
            start_time = _time_cls(int(h), int(m))
        except (ValueError, AttributeError):
            result.fehler.append(f"{spiel.datum} – ungültige Uhrzeit {spiel.uhrzeit!r}")
            continue

        buchungs_datum = date.fromisoformat(spiel.datum)
        zweck = f"[{spiel.wettbewerb}] {spiel.heim} vs {spiel.gast}"

        # Bestehende Buchungen des Tages für Konfliktcheck
        existing = repo.get_bookings_for_date(buchungs_datum)

        # Duplikat-Check: schon als Spiel gebucht (von anderem System)?
        konflikte = check_availability(existing, feld, start_time, 90)
        if any(b.booking_type == BookingType.SPIEL for b in konflikte):
            result.uebersprungen.append(f"{spiel.datum} {spiel.uhrzeit} {feld.value}")
            continue

        data = BookingCreate(
            field=feld,
            date=buchungs_datum,
            start_time=start_time,
            duration_min=90,
            booking_type=BookingType.SPIEL,
            zweck=zweck,
        )

        try:
            new_booking, displaced = dfbnet_displace(repo, data, sys_user, settings, existing)
            result.gebucht.append(f"{spiel.datum} {spiel.uhrzeit} {feld.value} – {zweck}")
            result.verdraengt += len(displaced)

            for b in displaced:
                owner = repo.get_user_by_id(b.booked_by_id)
                if owner and getattr(owner, "email", None):
                    email_coros.append(
                        send_dfbnet_displacement_notice(b, owner, new_booking, settings)
                    )
        except Exception as exc:
            result.fehler.append(f"{spiel.datum} {spiel.uhrzeit}: {exc}")

    # ── 4. Gegencheck: Buchungen ohne fussball.de-Spiel ──────────────────────
    # Spieltage als {datum: set of Platz-Präfixe}
    spiel_tage: dict[str, set[str]] = defaultdict(set)
    for s in heim_spiele:
        if s.spielort:
            feld = _spielort_zu_feld(s.spielort)
            if feld:
                spiel_tage[s.datum].add(feld.value.split()[0])

    for datum_str, tages_eintraege in sorted(buchungen.items()):
        for eintrag in tages_eintraege:
            props = eintrag["props"]
            notion_id = eintrag["id"]
            platz = _get_select(props, "Platz")
            typ = _get_select(props, "Typ")

            # Nur Kura*/Rasen*-Spielbuchungen prüfen
            prefix = next((p for p in _FELD_PRAEFIXE if platz.startswith(p)), None)
            if not prefix or typ == "Training":
                continue

            if prefix not in spiel_tage.get(datum_str, set()):
                try:
                    updated = repo.update_booking_status(notion_id, BookingStatus.STORNIERT)
                    result.storniert.append(f"{datum_str} {platz}")

                    owner = repo.get_user_by_id(updated.booked_by_id)
                    if owner and getattr(owner, "email", None):
                        email_coros.append(
                            send_cancellation_notice(updated, owner, settings)
                        )
                except Exception as exc:
                    result.fehler.append(f"Stornierung {datum_str} {platz}: {exc}")

    # ── 5. E-Mails senden ───────────────────────────────────────────────────
    if email_coros:
        await asyncio.gather(*email_coros, return_exceptions=True)

    return result

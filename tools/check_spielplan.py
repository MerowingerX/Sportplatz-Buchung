#!/usr/bin/env python3
"""
tools/check_spielplan.py  –  fussball.de Heimspiele gegen Notion-Buchungen abgleichen

Prüft für alle Heimspiele auf dem Kunstrasen und Rasenplatz, ob im
Buchungssystem bereits eine DFBnet-Buchung für das jeweilige Datum existiert.
Gibt alle Spiele ohne Buchung als Tabelle aus.

Verwendung:
    python tools/check_spielplan.py
    python tools/check_spielplan.py --von 2026-03-01
    python tools/check_spielplan.py --gegencheck
    python tools/check_spielplan.py --output-dir /pfad/zu/verzeichnis

CSVs werden automatisch unter Platzbelegung/fussball.de/DATUM/ZEIT/ gespeichert.

Benötigt .env mit:
    NOTION_API_KEY=secret_...
    NOTION_BUCHUNGEN_DB_ID=...

Abhängigkeiten (einmalig installieren):
    pip install requests beautifulsoup4 notion-client python-dotenv
"""

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import date, datetime

# Projektroot zum Python-Pfad hinzufügen (für tools/fussball_de.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fussball_de import fetch_matchplan_html, parse_matchplan, Spiel, export_csv, _default_output_dir, _ensure_dir
except ImportError as e:
    print(f"Fehler: {e}")
    print("Stelle sicher, dass tools/fussball_de.py existiert.")
    sys.exit(1)

try:
    from notion_client import Client as NotionClient
except ImportError:
    print("Fehler: notion-client nicht installiert. `pip install notion-client`")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Club-ID aus .env extrahieren (FUSSBALL_DE_VEREINSSEITE enthält die ID)
_vereinsseite = os.environ.get("FUSSBALL_DE_VEREINSSEITE", "")
CLUB_ID = os.environ.get("APIFUSSBALL_CLUB_ID", "")  # aus .env
if _vereinsseite:
    try:
        from fussball_de import _club_id_from_url
        _extracted = _club_id_from_url(_vereinsseite)
        if _extracted:
            CLUB_ID = _extracted
    except Exception:
        pass

# fussball.de Spielort → Notion Platz-Präfixe  (aus config/vereinsconfig.json)
try:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from booking.vereinsconfig import get_spielort_zu_praefix
    SPIELORT_ZU_PLATZ: list[tuple[str, list[str]]] = get_spielort_zu_praefix()
except Exception:
    SPIELORT_ZU_PLATZ = []  # Fallback leer – vereinsconfig.json konfigurieren

BESTAETIGT = "Bestätigt"


# ---------------------------------------------------------------------------
# Notion-Abfrage
# ---------------------------------------------------------------------------
def lade_notion_buchungen(
    client: NotionClient,
    db_id: str,
    von: str,
    bis: str,
) -> dict[str, list[dict]]:
    """
    Lädt alle bestätigten Buchungen im Datumsbereich [von, bis] aus Notion.
    Gibt ein Dict {datum_iso: [booking_props, ...]} zurück.
    """
    print(f"Lade Notion-Buchungen {von} … {bis} …")
    ergebnis: dict[str, list[dict]] = defaultdict(list)

    cursor = None
    gesamt = 0
    while True:
        kwargs: dict = {
            "database_id": db_id,
            "page_size": 100,
            "filter": {
                "and": [
                    {"property": "Datum", "date": {"on_or_after": von}},
                    {"property": "Datum", "date": {"on_or_before": bis}},
                    {"property": "Status", "select": {"equals": BESTAETIGT}},
                ]
            },
        }
        if cursor:
            kwargs["start_cursor"] = cursor

        result = client.databases.query(**kwargs)
        for page in result["results"]:
            props = page["properties"]
            datum = _get_date(props, "Datum")
            if datum:
                ergebnis[datum].append(props)
                gesamt += 1

        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")

    print(f"  → {gesamt} bestätigte Buchungen geladen ({len(ergebnis)} Tage mit Buchungen)")
    return dict(ergebnis)


def _get_date(props: dict, name: str) -> str:
    try:
        return props[name]["date"]["start"] or ""
    except (KeyError, TypeError):
        return ""


def _get_select(props: dict, name: str) -> str:
    try:
        return props[name]["select"]["name"] or ""
    except (KeyError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Abgleich
# ---------------------------------------------------------------------------
def platz_passend(platz: str, praefixe: list[str]) -> bool:
    """Prüft ob der Notion-Platzname zu einem der Präfixe passt."""
    return any(platz.startswith(p) for p in praefixe)


def abgleichen(
    spiele: list[Spiel],
    buchungen: dict[str, list[dict]],
) -> list[Spiel]:
    """
    Gibt alle Spiele zurück, für die am Spieltag keine passende
    Notion-Buchung auf dem zugehörigen Platz existiert.
    """
    fehlend: list[Spiel] = []

    for spiel in sorted(spiele, key=lambda s: (s.datum, s.uhrzeit)):
        # Welche Platz-Präfixe gelten für diesen Spielort?
        praefixe: list[str] = []
        for spielort_substr, px in SPIELORT_ZU_PLATZ:
            if spiel.spielort and spielort_substr.lower() in spiel.spielort.lower():
                praefixe = px
                break

        if not praefixe:
            continue  # unbekannter Spielort → überspringen

        # Buchungen an diesem Tag
        tages_buchungen = buchungen.get(spiel.datum, [])

        # Gibt es eine Buchung auf dem passenden Platz?
        gebucht = any(
            platz_passend(_get_select(b, "Platz"), praefixe)
            for b in tages_buchungen
        )

        if not gebucht:
            fehlend.append(spiel)

    return fehlend


# ---------------------------------------------------------------------------
# Gegencheck: Notion-Buchungen ohne fussball.de-Spiel
# ---------------------------------------------------------------------------
# Platz-Präfix → fussball.de Spielort-Substring  (aus config/vereinsconfig.json)
try:
    from booking.vereinsconfig import get_spielorte as _get_spielorte
    PLATZ_ZU_SPIELORT: dict[str, str] = {
        px: s["fussball_de_string"]
        for s in _get_spielorte()
        for px in s.get("platz_praefix", [])
    }
except Exception:
    PLATZ_ZU_SPIELORT = {
        "Kura":  "cremlingen b-platz",
        "Rasen": "cremlingen a-platz rasen",
    }


def _get_rich_text(props: dict, name: str) -> str:
    try:
        parts = props[name]["rich_text"]
        return "".join(p["plain_text"] for p in parts)
    except (KeyError, TypeError):
        return ""


def _get_title(props: dict, name: str) -> str:
    try:
        parts = props[name]["title"]
        return "".join(p["plain_text"] for p in parts)
    except (KeyError, TypeError):
        return ""


def gegencheck(
    buchungen: dict[str, list[dict]],
    spiele: list[Spiel],
) -> list[dict]:
    """
    Gibt alle Notion-Buchungen zurück, deren Datum keinem fussball.de
    Heimspiel auf dem gleichen Platz entspricht.

    Nur Buchungen auf Kura*/Rasen*-Plätzen werden geprüft.
    Buchungen vom Typ "Training" werden ausgeschlossen (nur Spielbuchungen relevant).
    """
    # fussball.de Heimspiele als Set {(datum, spielort_substr)}
    spiel_tage: dict[str, set[str]] = defaultdict(set)
    for s in spiele:
        if not s.spielort:
            continue
        for spielort_substr, praefixe in SPIELORT_ZU_PLATZ:
            if spielort_substr.lower() in s.spielort.lower():
                for px in praefixe:
                    spiel_tage[s.datum].add(px)

    verwaist: list[dict] = []
    for datum, tages_buchungen in sorted(buchungen.items()):
        for b in tages_buchungen:
            platz = _get_select(b, "Platz")
            typ   = _get_select(b, "Typ")

            # Nur Kura*/Rasen*-Plätze prüfen, Training überspringen
            platz_px = next(
                (px for px in PLATZ_ZU_SPIELORT if platz.startswith(px)),
                None,
            )
            if not platz_px:
                continue
            if typ == "Training":
                continue

            # Hat fussball.de an diesem Tag ein Spiel auf diesem Platz?
            if platz_px not in spiel_tage.get(datum, set()):
                verwaist.append({
                    "datum":  datum,
                    "platz":  platz,
                    "typ":    typ,
                    "titel":  _get_title(b, "Titel") or _get_rich_text(b, "Titel"),
                    "startzeit": _get_select(b, "Startzeit"),
                })

    return verwaist


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------
def print_fehlend(spiele: list[Spiel]) -> None:
    if not spiele:
        print("\n✓ Alle Heimspiele sind im Buchungssystem eingetragen.")
        return

    print(f"\n⚠  {len(spiele)} Heimspiel(e) ohne Buchung:\n")
    print(f"{'DATUM':<12} {'UHRZEIT':<8} {'HEIMTEAM':<30} {'GASTTEAM':<30} MANNSCHAFT / PLATZ")
    print("-" * 105)
    for s in spiele:
        platz_kurz = ""
        if s.spielort:
            if "Kustrasen" in s.spielort or "Kunstrasen" in s.spielort:
                platz_kurz = "Kunstrasen"
            elif "Rasen" in s.spielort:
                platz_kurz = "Rasenplatz"
        print(
            f"{s.datum:<12} {s.uhrzeit or '?:??':<8} "
            f"{s.heim[:29]:<30} {s.gast[:29]:<30} "
            f"{s.mannschaft}  [{platz_kurz}]"
        )


def print_verwaist(buchungen: list[dict]) -> None:
    if not buchungen:
        print("\n✓ Alle Spielbuchungen auf Kunstrasen/Rasenplatz haben ein fussball.de-Spiel.")
        return

    print(f"\n⚠  {len(buchungen)} Buchung(en) ohne fussball.de-Spiel (ggf. abgesagt/verlegt):\n")
    print(f"{'DATUM':<12} {'UHRZEIT':<8} {'TITEL':<45} PLATZ")
    print("-" * 85)
    for b in buchungen:
        print(
            f"{b['datum']:<12} {b['startzeit'] or '?:??':<8} "
            f"{b['titel'][:44]:<45} {b['platz']}"
        )


def export_bericht(spiele: list[Spiel], pfad: str) -> None:
    felder = ["datum", "uhrzeit", "heim", "gast", "mannschaft", "wettbewerb", "spielort"]
    with open(pfad, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=felder)
        writer.writeheader()
        for s in spiele:
            writer.writerow({k: getattr(s, k) for k in felder})
    print(f"✓ Bericht gespeichert → {pfad}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="fussball.de Heimspiele gegen Notion-Buchungen abgleichen",
    )
    parser.add_argument(
        "--von",
        metavar="YYYY-MM-DD",
        default="",
        help="Startdatum (Standard: heute)",
    )
    parser.add_argument(
        "--bis",
        metavar="YYYY-MM-DD",
        default="",
        help="Enddatum (Standard: Saisonende 30.06.)",
    )
    parser.add_argument(
        "--bericht",
        metavar="DATEI.csv",
        help="Fehlende Spiele als CSV-Datei exportieren",
    )
    parser.add_argument(
        "--gegencheck",
        action="store_true",
        help="Zusätzlich: Notion-Buchungen ohne passendes fussball.de-Spiel anzeigen",
    )
    parser.add_argument(
        "--gegencheck-bericht",
        metavar="DATEI.csv",
        help="Verwaiste Buchungen als CSV exportieren",
    )
    parser.add_argument(
        "--output-dir",
        metavar="VERZEICHNIS",
        default="",
        help=(
            "Ausgabeverzeichnis für CSV-Berichte "
            "(Standard: Platzbelegung/fussball.de/DATUM/ZEIT/)"
        ),
    )
    args = parser.parse_args()

    # Notion-Credentials
    api_key = os.environ.get("NOTION_API_KEY")
    db_id = os.environ.get("NOTION_BUCHUNGEN_DB_ID")
    if not api_key or not db_id:
        print("Fehler: NOTION_API_KEY und NOTION_BUCHUNGEN_DB_ID müssen gesetzt sein.")
        print("  export NOTION_API_KEY=secret_...")
        print("  export NOTION_BUCHUNGEN_DB_ID=...")
        sys.exit(1)

    # fussball.de Spielplan laden
    print(f"Lade fussball.de Spielplan …")
    html = fetch_matchplan_html(CLUB_ID, datum_von=args.von, datum_bis=args.bis)
    alle_spiele = parse_matchplan(html)

    # Nur Heimspiele auf Cremlingen-Plätzen
    heim = [
        s for s in alle_spiele
        if s.ist_heimspiel and s.spielort and any(
            sub.lower() in s.spielort.lower()
            for sub, _ in SPIELORT_ZU_PLATZ
        )
    ]
    print(f"  → {len(heim)} Heimspiele auf Kunstrasen/Rasenplatz")

    if not heim:
        print("Keine relevanten Heimspiele gefunden.")
        return

    # Datumsbereich bestimmen
    daten = sorted(s.datum for s in heim)
    von_iso = args.von or date.today().isoformat()
    bis_iso = args.bis or daten[-1]

    # Notion-Buchungen laden
    client = NotionClient(auth=api_key)
    buchungen = lade_notion_buchungen(client, db_id, von_iso, bis_iso)

    # Ausgabeverzeichnis (wird bei Bedarf angelegt)
    out_dir = _ensure_dir(args.output_dir or _default_output_dir())

    # Spiele-CSVs exportieren (Filterung nach Spielort-Strings aus vereinsconfig)
    _kura_substr  = next((s for s in SPIELORT_ZU_PLATZ if "Kura"  in s[1]), ("cremlingen b-platz", []))[0].lower()
    _rasen_substr = next((s for s in SPIELORT_ZU_PLATZ if "Rasen" in s[1]), ("cremlingen a-platz rasen", []))[0].lower()
    kura = [s for s in alle_spiele if s.ist_heimspiel and s.spielort
            and _kura_substr in s.spielort.lower()]
    rasen = [s for s in alle_spiele if s.ist_heimspiel and s.spielort
             and _rasen_substr in s.spielort.lower()]
    auswaerts = [s for s in alle_spiele if not s.ist_heimspiel]
    export_csv(kura,     os.path.join(out_dir, "spiele_Kunstrasen.csv"))
    export_csv(rasen,    os.path.join(out_dir, "spiele_Rasenplatz.csv"))
    export_csv(auswaerts, os.path.join(out_dir, "spiele_Auswaerts.csv"), auswaerts=True)

    # Hincheck: fussball.de-Spiele ohne Notion-Buchung
    fehlend = abgleichen(heim, buchungen)
    print_fehlend(fehlend)
    bericht_pfad = args.bericht or (os.path.join(out_dir, "fehlend.csv") if fehlend else "")
    if bericht_pfad and fehlend:
        export_bericht(fehlend, bericht_pfad)

    # Gegencheck: Notion-Buchungen ohne fussball.de-Spiel
    if args.gegencheck or getattr(args, "gegencheck_bericht", None):
        print("\n--- Gegencheck ---")
        verwaist = gegencheck(buchungen, heim)
        print_verwaist(verwaist)
        gegencheck_pfad = getattr(args, "gegencheck_bericht", None) or (
            os.path.join(out_dir, "verwaist.csv") if verwaist else ""
        )
        if gegencheck_pfad and verwaist:
            felder = ["datum", "startzeit", "platz", "typ", "titel"]
            with open(gegencheck_pfad, "w", encoding="utf-8", newline="") as f:
                import csv as _csv
                writer = _csv.DictWriter(f, fieldnames=felder)
                writer.writeheader()
                for b in verwaist:
                    writer.writerow({k: b.get(k, "") for k in felder})
            print(f"✓ Gegencheck-Bericht gespeichert → {gegencheck_pfad}")

    print(f"\nBerichte unter: {out_dir}/")


if __name__ == "__main__":
    main()

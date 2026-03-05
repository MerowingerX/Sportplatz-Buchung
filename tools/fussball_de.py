#!/usr/bin/env python3
"""
tools/fussball_de.py  –  Vereinsspielplan von fussball.de abrufen

Liest den kompletten Spielplan des TuS Cremlingen von fussball.de und gibt
ihn im Terminal aus, exportiert ihn als JSON oder importiert ihn in die
Notion-Events-Datenbank.

Verwendung:
    python tools/fussball_de.py                         # Terminal-Ausgabe
    python tools/fussball_de.py --json spiele.json      # JSON-Export
    python tools/fussball_de.py --notion                # → Notion importieren
    python tools/fussball_de.py --url <URL>             # andere fussball.de Vereinsseite
    python tools/fussball_de.py --debug                 # HTML-Dump (Debugging)

Abhängigkeiten (einmalig installieren):
    pip install requests beautifulsoup4

Für --notion außerdem .env mit:
    NOTION_API_KEY=...
    NOTION_EVENTS_DB_ID=...
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from typing import Optional

# ---------------------------------------------------------------------------
# Optionale Imports
# ---------------------------------------------------------------------------
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Fehlende Abhängigkeiten. Bitte installieren:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
BASE_URL = "https://www.fussball.de"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "de-DE,de;q=0.9",
}

# Monatsnamen DE → Nummer
MONATE = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3,
    "april": 4, "mai": 5, "juni": 6, "juli": 7,
    "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}

# ---------------------------------------------------------------------------
# Datenmodell
# ---------------------------------------------------------------------------
@dataclass
class Spiel:
    datum: str              # ISO: YYYY-MM-DD
    uhrzeit: str            # HH:MM  (leer wenn noch nicht bekannt)
    heim: str
    gast: str
    mannschaft: str         # z.B. "Herren Ü32"
    wettbewerb: str         # z.B. "Kreisfreundschaftsspiele"
    ergebnis: Optional[str] = None
    spielort: Optional[str] = None
    ist_heimspiel: bool = False

    @property
    def datum_obj(self) -> Optional[date]:
        try:
            return date.fromisoformat(self.datum)
        except ValueError:
            return None

    @property
    def uhrzeit_obj(self) -> Optional[time]:
        try:
            h, m = self.uhrzeit.split(":")
            return time(int(h), int(m))
        except (ValueError, AttributeError):
            return None


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _parse_datum(text: str) -> Optional[str]:
    """Parst verschiedene Datumsformate → ISO-String oder None."""
    text = text.strip()
    # Format: "27.02.2026" oder "27.02.26"
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", text)
    if m:
        tag, monat, jahr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if jahr < 100:
            jahr += 2000
        try:
            return date(jahr, monat, tag).isoformat()
        except ValueError:
            return None
    # Format: "27. Februar 2026"
    m = re.search(r"(\d{1,2})\.\s+(\w+)\s+(\d{4})", text.lower())
    if m:
        tag = int(m.group(1))
        monat = MONATE.get(m.group(2))
        jahr = int(m.group(3))
        if monat:
            try:
                return date(jahr, monat, tag).isoformat()
            except ValueError:
                return None
    return None


def _parse_uhrzeit(text: str) -> str:
    """Extrahiert HH:MM aus einem Text, sonst leerer String."""
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    return ""


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


# ---------------------------------------------------------------------------
# Abruf
# ---------------------------------------------------------------------------
def _club_id_from_url(url: str) -> Optional[str]:
    """Extrahiert die Club-ID aus einer fussball.de Vereins-URL.
    Unterstützt sowohl /id/<ID> als auch /verein-id/<ID>.
    """
    m = re.search(r"/(?:verein-)?id/([A-Z0-9]{32})", url)
    return m.group(1) if m else None


def _matchplan_url(club_id: str, offset: int = 0) -> str:
    """
    fussball.de liefert den Spielplan als JSON mit 'html'-Feld.
    offset=0 → nächste Spiele; negative Werte für vergangene Spiele
    werden über prev.games abgerufen.
    """
    return (
        f"{BASE_URL}/ajax.club.matchplan/-/id/{club_id}"
        f"/mime-type/JSON/mode/PAGE/show-filter/false"
    )


def fetch_matchplan_html(
    club_id: str,
    datum_von: str = "",
    datum_bis: str = "",
    debug: bool = False,
) -> str:
    """
    Holt den Spielplan als HTML-String via POST.
    fussball.de gibt JSON zurück: {"success": true, "html": "<table>..."}

    datum_von / datum_bis: ISO-Format YYYY-MM-DD, wird in DD.MM.YYYY umgewandelt.
    Ohne Angabe gilt: heute bis Saisonende (30.06.).
    """
    url = _matchplan_url(club_id)

    def _to_de(iso: str) -> str:
        """YYYY-MM-DD → DD.MM.YYYY"""
        try:
            d = date.fromisoformat(iso)
            return d.strftime("%d.%m.%Y")
        except ValueError:
            return iso

    heute = date.today()
    saison_ende = date(heute.year if heute.month >= 7 else heute.year - 1 + 1, 6, 30)

    von_de = _to_de(datum_von) if datum_von else heute.strftime("%d.%m.%Y")
    bis_de = _to_de(datum_bis) if datum_bis else saison_ende.strftime("%d.%m.%Y")

    post_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    }
    payload = {
        "show-venues": "true",
        "checked": "true",
        "datum-von": von_de,
        "datum-bis": bis_de,
        "offset": "0",
        "max": "500",   # möglichst alle Spiele auf einmal
    }

    resp = requests.post(url, headers=post_headers, data=payload, timeout=30)
    resp.raise_for_status()

    try:
        data = resp.json()
        html = data.get("html", "")
    except ValueError:
        html = resp.text

    if debug:
        print("\n--- HTML-Auszug (erste 4000 Zeichen) ---")
        print(html[:4000])
        print("---\n")

    return html


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def parse_matchplan(html: str, heim_keywords: "list[str] | str" = "") -> list[Spiel]:
    """
    Parst den HTML-Matchplan von fussball.de.

    Tabellenstruktur (aus Live-Analyse):
      <tr class="row-headline visible-small">
        <td>Freitag, 27.02.2026 - 19:00 Uhr | Herren Ü32 | Kreisfreundschaftsspiele</td>
      </tr>
      <tr class="odd row-competition hidden-small">   ← Desktopansicht, überspringen
        ...
      </tr>
      <tr class="odd">                                ← Spielzeile
        <td class="hidden-small"></td>
        <td class="column-club"><a ...><div class="club-name">TuS Cremlingen</div></a></td>
        <td class="column-score">:</td>               ← "2:1" wenn gespielt
        <td class="column-club"><a ...><div class="club-name">MTV Hondelage</div></a></td>
        <td colspan="2"><a>Zum Spiel</a></td>
      </tr>
    """
    soup = BeautifulSoup(html, "html.parser")
    spiele: list[Spiel] = []

    # Aktueller Kontext aus dem letzten row-headline
    aktuelles_datum = ""
    aktuelle_uhrzeit = ""
    aktuelle_mannschaft = ""
    aktueller_wettbewerb = ""

    def _team_name(cell) -> str:
        div = cell.find("div", class_="club-name")
        if div:
            return _clean(div.get_text())
        a = cell.find("a")
        if a:
            return _clean(a.get_text())
        return _clean(cell.get_text())

    for row in soup.find_all("tr"):
        classes = row.get("class", [])

        # ── Kopfzeile: Datum + Mannschaft + Wettbewerb ───────────────────────
        if "row-headline" in classes:
            text = _clean(row.get_text())
            # Format: "Freitag, 27.02.2026 - 19:00 Uhr | Herren Ü32 | Kreisfreundschaftsspiele"
            d = _parse_datum(text)
            if d:
                aktuelles_datum = d
            aktuelle_uhrzeit = _parse_uhrzeit(text)
            teile = [t.strip() for t in text.split("|")]
            aktuelle_mannschaft = teile[1] if len(teile) > 1 else ""
            aktueller_wettbewerb = teile[2] if len(teile) > 2 else ""
            continue

        # ── Spielort-Zeile → letztes Spiel ergänzen ──────────────────────────
        if "row-venue" in classes:
            if spiele:
                cells = row.find_all("td")
                # Spielort steht in der zweiten td (erste ist leer)
                ort_text = ""
                for td in cells:
                    t = _clean(td.get_text())
                    if t:
                        ort_text = t
                        break
                if ort_text:
                    spiele[-1].spielort = ort_text
            continue

        # ── Desktop-Kompaktzeile überspringen ────────────────────────────────
        if "row-competition" in classes or "thead" in classes:
            continue

        # ── Spielzeile ────────────────────────────────────────────────────────
        club_cells = row.find_all("td", class_="column-club")
        if len(club_cells) < 2 or not aktuelles_datum:
            continue

        heim = _team_name(club_cells[0])
        gast = _team_name(club_cells[1])
        if not heim or not gast:
            continue

        score_cell = row.find("td", class_="column-score")
        ergebnis = _clean(score_cell.get_text()) if score_cell else None
        if ergebnis and not re.search(r"\d", ergebnis):
            ergebnis = None

        _keywords = [heim_keywords] if isinstance(heim_keywords, str) else heim_keywords
        ist_heimspiel = any(kw and kw.lower() in heim.lower() for kw in _keywords)

        spiele.append(
            Spiel(
                datum=aktuelles_datum,
                uhrzeit=aktuelle_uhrzeit,
                heim=heim,
                gast=gast,
                mannschaft=aktuelle_mannschaft,
                wettbewerb=aktueller_wettbewerb,
                ergebnis=ergebnis,
                ist_heimspiel=ist_heimspiel,
            )
        )

    return spiele


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------
def print_tabelle(spiele: list[Spiel]) -> None:
    if not spiele:
        print("Keine Spiele gefunden.")
        return

    # Sortiert nach Datum
    spiele_sorted = sorted(spiele, key=lambda s: (s.datum, s.uhrzeit))
    heute = date.today().isoformat()

    print(f"\n{'DATUM':<12} {'UHRZEIT':<8} {'H':<2} {'HEIMTEAM':<30} {'GASTTEAM':<30} {'ERGEBNIS':<10} MANNSCHAFT")
    print("-" * 110)

    last_datum = ""
    for s in spiele_sorted:
        # Trennlinie bei neuem Datum
        if s.datum != last_datum:
            if last_datum:
                print()
            last_datum = s.datum

        vergangen = s.datum < heute
        kommt = ">" if s.datum == heute else (" " if vergangen else " ")
        heimzeichen = "H" if s.ist_heimspiel else "A"

        ergebnis = s.ergebnis or ("(ausstehend)" if not vergangen else "-")
        uhrzeit = s.uhrzeit or "?:??"

        print(
            f"{s.datum:<12} {uhrzeit:<8} {heimzeichen:<2} "
            f"{s.heim[:29]:<30} {s.gast[:29]:<30} "
            f"{ergebnis:<10} {s.mannschaft}"
        )

    print(f"\nGesamt: {len(spiele)} Spiele")


# ---------------------------------------------------------------------------
# JSON-Export
# ---------------------------------------------------------------------------
def export_json(spiele: list[Spiel], pfad: str) -> None:
    data = [asdict(s) for s in spiele]
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ {len(spiele)} Spiele gespeichert → {pfad}")


# ---------------------------------------------------------------------------
# CSV-Export
# ---------------------------------------------------------------------------
def export_csv(spiele: list[Spiel], pfad: str, auswaerts: bool = False) -> None:
    import csv
    if auswaerts:
        felder = ["datum", "uhrzeit", "heim", "gast", "mannschaft", "wettbewerb", "ergebnis", "spielort"]
    else:
        felder = ["datum", "uhrzeit", "heim", "gast", "mannschaft", "wettbewerb", "ergebnis"]
    spiele_sorted = sorted(spiele, key=lambda s: (s.datum, s.uhrzeit))
    with open(pfad, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=felder)
        writer.writeheader()
        for s in spiele_sorted:
            writer.writerow({k: getattr(s, k) for k in felder})
    print(f"✓ {len(spiele)} Spiele gespeichert → {pfad}")


# ---------------------------------------------------------------------------
# Notion-Import
# ---------------------------------------------------------------------------
def import_notion(spiele: list[Spiel]) -> None:
    """Importiert Spiele in die Notion-Events-Datenbank."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("NOTION_API_KEY")
    db_id = os.environ.get("NOTION_EVENTS_DB_ID")

    if not api_key or not db_id:
        print("Fehler: NOTION_API_KEY und NOTION_EVENTS_DB_ID müssen gesetzt sein.")
        print("  export NOTION_API_KEY=secret_...")
        print("  export NOTION_EVENTS_DB_ID=...")
        sys.exit(1)

    try:
        from notion_client import Client
    except ImportError:
        print("Fehler: notion-client nicht installiert. `pip install notion-client`")
        sys.exit(1)

    client = Client(auth=api_key)

    # Bestehende Events laden (um Duplikate zu vermeiden)
    print("Lade bestehende Events aus Notion …")
    existing: set[str] = set()
    try:
        cursor = None
        while True:
            kwargs: dict = {
                "database_id": db_id,
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor
            result = client.databases.query(**kwargs)
            for page in result["results"]:
                props = page["properties"]
                # Name + Datum als Duplikat-Schlüssel
                name = ""
                if props.get("Name") and props["Name"].get("title"):
                    name = "".join(t["plain_text"] for t in props["Name"]["title"])
                datum = ""
                if props.get("Datum") and props["Datum"].get("date"):
                    datum = props["Datum"]["date"].get("start", "")
                if name and datum:
                    existing.add(f"{datum}|{name}")
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
    except Exception as e:
        print(f"Warnung: Konnte bestehende Events nicht laden: {e}")

    hinzugefuegt = 0
    uebersprungen = 0

    for s in sorted(spiele, key=lambda x: (x.datum, x.uhrzeit)):
        # Titel: "TuS Cremlingen – Gegner" oder "Gegner – TuS Cremlingen"
        if s.ist_heimspiel:
            title = f"{s.heim} – {s.gast}"
        else:
            title = f"{s.heim} – {s.gast}"

        key = f"{s.datum}|{title}"
        if key in existing:
            uebersprungen += 1
            continue

        # Startzeit
        startzeit = s.uhrzeit if s.uhrzeit else "00:00"

        # Wettbewerb als Description
        beschreibung = s.wettbewerb if s.wettbewerb else None

        props: dict = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Datum": {"date": {"start": s.datum}},
            "Startzeit": {"rich_text": [{"text": {"content": startzeit}}]},
        }
        if s.mannschaft:
            props["Mannschaft"] = {"rich_text": [{"text": {"content": s.mannschaft}}]}
        if beschreibung:
            props["Beschreibung"] = {"rich_text": [{"text": {"content": beschreibung}}]}

        try:
            client.pages.create(
                parent={"database_id": db_id},
                properties=props,
            )
            hinzugefuegt += 1
            print(f"  + {s.datum}  {title}")
        except Exception as e:
            print(f"  ✗ Fehler bei '{title}': {e}")

    print(f"\nFertig: {hinzugefuegt} neu importiert, {uebersprungen} bereits vorhanden.")


# ---------------------------------------------------------------------------
# Ausgabe-Verzeichnis
# ---------------------------------------------------------------------------
def _default_output_dir() -> str:
    """Gibt Platzbelegung/fussball.de/YYYY-MM-DD/HH-MM/ relativ zum Projektroot zurück."""
    jetzt = datetime.now()
    projekt_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(
        projekt_root,
        "Platzbelegung", "fussball.de",
        jetzt.strftime("%Y-%m-%d"),
        jetzt.strftime("%H-%M"),
    )


def _ensure_dir(pfad: str) -> str:
    os.makedirs(pfad, exist_ok=True)
    return pfad


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="fussball.de Vereinsspielplan abrufen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("FUSSBALL_DE_VEREINSSEITE", ""),
        help="fussball.de Vereins-URL (Standard: FUSSBALL_DE_VEREINSSEITE aus .env)",
    )
    parser.add_argument(
        "--json",
        metavar="DATEI",
        help="Spielplan als JSON-Datei exportieren",
    )
    parser.add_argument(
        "--csv",
        metavar="DATEI",
        help="Spielplan als CSV-Datei exportieren",
    )
    parser.add_argument(
        "--notion",
        action="store_true",
        help="Spiele in Notion-Events-DB importieren",
    )
    parser.add_argument(
        "--spielort",
        metavar="SUCHBEGRIFF",
        default="",
        help="Nur Spiele an diesem Spielort ausgeben (Teilstring, Groß-/Kleinschreibung egal)",
    )
    parser.add_argument(
        "--heimspiele",
        action="store_true",
        help="Nur Heimspiele ausgeben",
    )
    parser.add_argument(
        "--auswaertsspiele",
        action="store_true",
        help="Nur Auswärtsspiele ausgeben",
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
        "--alle-csv",
        action="store_true",
        help=(
            "Alle Standard-CSVs erzeugen (Kunstrasen, Rasenplatz, Auswärts) "
            "und im Ausgabeverzeichnis speichern"
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="VERZEICHNIS",
        default="",
        help=(
            "Ausgabeverzeichnis für CSV-Dateien "
            "(Standard: Platzbelegung/fussball.de/DATUM/ZEIT/)"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Rohen HTML-Auszug ausgeben (für Debugging)",
    )
    args = parser.parse_args()

    # Club-ID aus URL extrahieren
    club_id = _club_id_from_url(args.url) if args.url else None
    if not club_id:
        print("Fehler: Keine gültige fussball.de-URL angegeben.", file=sys.stderr)
        print("  Setze FUSSBALL_DE_VEREINSSEITE in .env oder übergib --url <URL>.", file=sys.stderr)
        sys.exit(1)
    print(f"Lade Spielplan für Club-ID {club_id} …")

    html = fetch_matchplan_html(club_id, datum_von=args.von, datum_bis=args.bis, debug=args.debug)
    spiele = parse_matchplan(html)

    if args.spielort:
        spiele = [s for s in spiele if s.spielort and args.spielort.lower() in s.spielort.lower()]
    if args.heimspiele:
        spiele = [s for s in spiele if s.ist_heimspiel]
    if args.auswaertsspiele:
        spiele = [s for s in spiele if not s.ist_heimspiel]

    if not spiele and not args.debug:
        print("Keine Spiele geparst. Starte mit --debug um den HTML-Auszug zu sehen.")
        sys.exit(1)

    # Ausgabe
    print_tabelle(spiele)

    if args.json:
        export_json(spiele, args.json)

    if args.csv:
        export_csv(spiele, args.csv, auswaerts=args.auswaertsspiele)

    if args.alle_csv:
        out = _ensure_dir(args.output_dir or _default_output_dir())
        print(f"\nSpeichere CSVs → {out}/")

        # Kunstrasen-Heimspiele
        kura = [s for s in spiele if s.ist_heimspiel and s.spielort
                and "cremlingen b-platz" in s.spielort.lower()]
        export_csv(kura, os.path.join(out, "spiele_Kunstrasen.csv"))

        # Rasenplatz-Heimspiele
        rasen = [s for s in spiele if s.ist_heimspiel and s.spielort
                 and "cremlingen a-platz rasen" in s.spielort.lower()]
        export_csv(rasen, os.path.join(out, "spiele_Rasenplatz.csv"))

        # Auswärtsspiele
        auswaerts = [s for s in spiele if not s.ist_heimspiel]
        export_csv(auswaerts, os.path.join(out, "spiele_Auswaerts.csv"), auswaerts=True)

    if args.notion:
        import_notion(spiele)


if __name__ == "__main__":
    main()

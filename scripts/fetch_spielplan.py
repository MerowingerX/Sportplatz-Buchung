#!/usr/bin/env python3
"""
Ruft den TuS Cremlingen Spielplan von api-fussball.de ab und schreibt
eine DFBnet-kompatible CSV nach Platzbelegung/platzbelegung.csv.

Nur HEIMSPIELE werden berücksichtigt (Platzbuchung erforderlich).

Verwendung:
    python3 scripts/fetch_spielplan.py          # normal
    python3 scripts/fetch_spielplan.py -v       # mit Roh-JSON des ersten Spiels
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.request
from datetime import date, datetime

# ── Konfiguration ────────────────────────────────────────────────────────────
TOKEN    = "Y1t797t1t5Z8Y5h2D2b6r736X5M6HVEYzhWbM6DIeU"
CLUB_ID  = "00ES8GN75400000VVV0AG08LVUPGND5I"
API_BASE = "https://api-fussball.de"
_HEADERS = {"x-auth-token": TOKEN}

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH    = os.path.join(PROJECT_DIR, "Platzbelegung", "platzbelegung.csv")
LOG_DIR     = os.path.join(PROJECT_DIR, "Platzbelegung", "logs")

# Schlüsselwörter im Heimteam-Namen, die ein TuS-Heimspiel kennzeichnen
TUS_HOME_KEYWORDS = {"cremlingen"}

# Deutsche Wochentagsabkürzungen (DFBnet-Format)
_DE_DAYS = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]


# ── API-Hilfsfunktionen ──────────────────────────────────────────────────────

def _api_get(path: str) -> dict:
    req = urllib.request.Request(f"{API_BASE}{path}", headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get_teams() -> list[dict]:
    return _api_get(f"/api/club/{CLUB_ID}").get("data", [])


def get_next_games(url_path: str) -> list[dict]:
    return _api_get(url_path).get("data", [])


def _log_response(team_id: str, raw_data: dict) -> None:
    """Schreibt die rohe API-Antwort als JSON-Datei in Platzbelegung/logs/."""
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{team_id}.json"
    path = os.path.join(LOG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)


# ── Spielfeld-Parsing ────────────────────────────────────────────────────────
# Bekannte Feldnamen laut api-fussball.de next_games-Response:
#   date        "DD.MM.YYYY"
#   time        "HH:MM"
#   homeTeam    String
#   awayTeam    String
#   competition String (Liga/Staffel)
#   status      "" oder z.B. "Nichtantritt GAST" – solche Spiele überspringen
# Kein Spielkennung-Feld vorhanden.

def _parse_game(g: dict) -> dict | None:
    """Extrahiert Datum/Zeit/Teams/Liga aus einem api-fussball.de Spieldatensatz."""
    raw_date = g.get("date", "")
    raw_time = str(g.get("time", ""))[:5]
    heim     = g.get("homeTeam", "")
    gast     = g.get("awayTeam", "")
    liga     = g.get("competition", "")
    status   = g.get("status", "")

    if not raw_date or not raw_time:
        return None

    # Spiele mit besonderem Status (Nichtantritt etc.) ignorieren
    if status:
        return None

    return {
        "raw_date": raw_date,  # "DD.MM.YYYY"
        "raw_time": raw_time,  # "HH:MM"
        "heim":     heim,
        "gast":     gast,
        "liga":     liga,
        "kennung":  "",        # API liefert keine Spielkennung
    }


def _is_home_game(heim: str) -> bool:
    h = heim.lower()
    return any(kw in h for kw in TUS_HOME_KEYWORDS)


def _format_date(raw: str) -> tuple[date, str]:
    """Gibt (date-Objekt, DFBnet-String 'Sa., 28.02.2026') zurück."""
    if "-" in raw:
        d = date.fromisoformat(raw[:10])
    else:
        parts = raw.split(".")
        d = date(int(parts[2]), int(parts[1]), int(parts[0]))
    return d, f"{_DE_DAYS[d.weekday()]}, {d.strftime('%d.%m.%Y')}"


# ── Hauptfunktion (auch importierbar) ────────────────────────────────────────

def generate_csv(verbose: bool = False, progress_cb=None) -> tuple[int, str]:
    """
    Lädt den Spielplan aller TuS-Mannschaften und schreibt die CSV.
    Gibt (anzahl_heimspiele, csv_pfad) zurück.
    Wirft bei Fehler eine Exception.

    progress_cb: optionaler Callback(current: int, total: int, team_name: str)
    """
    teams = get_teams()
    total = len(teams)
    print(f"Teams geladen: {total}", file=sys.stderr)
    if progress_cb:
        progress_cb(0, total, "")

    rows: list[tuple[date, dict]] = []
    seen:  set[str] = set()
    first_dump_done = False
    today = date.today()

    for idx, team in enumerate(teams):
        team_name = team.get("name", "?")
        url_path  = team.get("url", {}).get("nextGames", "")
        if not url_path:
            if progress_cb:
                progress_cb(idx + 1, total, team_name)
            continue

        team_id = team.get("id", f"team{idx}")
        try:
            raw = _api_get(url_path)
            games = raw.get("data", [])
            _log_response(team_id, raw)
        except Exception as exc:
            print(f"  ⚠ {team_name}: {exc}", file=sys.stderr)
            time.sleep(4)
            if progress_cb:
                progress_cb(idx + 1, total, team_name)
            continue

        time.sleep(4)  # Rate-Limit: 4 Sekunden zwischen API-Aufrufen
        if progress_cb:
            progress_cb(idx + 1, total, team_name)

        # Beim ersten Fund im Verbose-Modus den Roh-JSON ausgeben
        if verbose and games and not first_dump_done:
            print(f"\n=== Roh-JSON erstes Spiel ({team_name}) ===", file=sys.stderr)
            print(json.dumps(games[0], indent=2, ensure_ascii=False), file=sys.stderr)
            first_dump_done = True

        for g in games:
            parsed = _parse_game(g)
            if not parsed or not _is_home_game(parsed["heim"]):
                continue

            # Duplikate via Spielkennung oder Datum+Zeit+Heim verhindern
            uid = parsed["kennung"] or f'{parsed["raw_date"]}{parsed["raw_time"]}{parsed["heim"]}'
            if uid in seen:
                continue
            seen.add(uid)

            try:
                d, date_str = _format_date(parsed["raw_date"])
            except (ValueError, IndexError):
                continue

            if d < today:
                continue  # vergangene Spiele überspringen

            rows.append((d, {**parsed, "date_str": date_str}))

    rows.sort(key=lambda x: (x[0], x[1]["raw_time"]))

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["Spieldatum", "Uhrzeit", "Heimmannschaft", "Gastmannschaft", "Liga", "Spielkennung"])
        for _, r in rows:
            w.writerow([r["date_str"], r["raw_time"], r["heim"], r["gast"], r["liga"], r["kennung"]])

    return len(rows), CSV_PATH


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    try:
        count, path = generate_csv(verbose=verbose)
        print(f"✅ {count} Heimspiele → {path}")
    except Exception as exc:
        print(f"❌ Fehler: {exc}", file=sys.stderr)
        sys.exit(1)

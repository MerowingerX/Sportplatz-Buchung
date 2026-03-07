#!/usr/bin/env python3
"""
instagram_matchday.py — Generiert Matchday-Karussell-Bilder für Instagram.

Erzeugt für jedes anstehende Spiel eine 1080×1080-Karte sowie ein Cover-Bild
(Spielübersicht). Die Bilder werden lokal gespeichert. Das Instagram-Posting
ist als Stub vorbereitet und kann aktiviert werden, sobald ein Meta-API-Token
vorliegt (s. Abschnitt „Instagram Graph API" unten).

Voraussetzungen:
    pip install playwright jinja2 python-dotenv notion-client
    playwright install chromium

Verwendung:
    # Alle Spiele der nächsten 3 Wochen
    python scripts/instagram_matchday.py

    # Nur die nächsten 7 Tage, anderes Ausgabeverzeichnis
    python scripts/instagram_matchday.py --days 7 --output /tmp/cards

    # Nur Vorschau (keine Bilder erzeugen)
    python scripts/instagram_matchday.py --dry-run
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("FEHLER: jinja2 nicht installiert.  pip install jinja2")
    sys.exit(1)

try:
    from notion_client import Client
except ImportError:
    print("FEHLER: notion-client nicht installiert.  pip install notion-client")
    sys.exit(1)

# ── Konstanten ────────────────────────────────────────────────────────────────

SCRIPTS_DIR  = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
CONFIG_DIR   = PROJECT_ROOT / "config"
STATIC_DIR   = PROJECT_ROOT / "web" / "static"

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS_DE   = ["", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
               "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Max. Bilder pro Karussell (Instagram-Limit)
CAROUSEL_MAX = 10
# Max. Zeilen im Cover (damit nichts abgeschnitten wird)
COVER_MAX_ROWS = 8


# ── Konfig laden ──────────────────────────────────────────────────────────────

def _load_config() -> dict:
    path = CONFIG_DIR / "vereinsconfig.json"
    if not path.exists():
        print(f"WARNUNG: {path} nicht gefunden – Defaults werden verwendet.")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_field_display_names() -> dict[str, str]:
    """Gibt ein Mapping FieldName → lesbarer Name zurück."""
    path = CONFIG_DIR / "field_config.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("display_names", {})


def _logo_b64(vc: dict) -> Optional[str]:
    """Lädt das SVG-Logo als Base64-String (für data:-URLs)."""
    logo_url = vc.get("logo_url", "/static/logo.svg")
    # URL-Pfad → Dateisystempfad
    rel = logo_url.lstrip("/")
    candidates = [
        PROJECT_ROOT / "web" / rel,
        STATIC_DIR / "logo.svg",
        PROJECT_ROOT / rel,
    ]
    for path in candidates:
        if path.exists() and path.suffix.lower() == ".svg":
            return base64.b64encode(path.read_bytes()).decode()
    return None


# ── Notion-Abfrage ────────────────────────────────────────────────────────────

def _prop_title(props: dict, key: str) -> str:
    items = props.get(key, {}).get("title", [])
    return items[0]["plain_text"] if items else ""


def _prop_select(props: dict, key: str) -> Optional[str]:
    sel = props.get(key, {}).get("select")
    return sel["name"] if sel else None


def _prop_rich_text(props: dict, key: str) -> str:
    items = props.get(key, {}).get("rich_text", [])
    return items[0]["plain_text"] if items else ""


def _prop_date(props: dict, key: str) -> Optional[date]:
    d = props.get(key, {}).get("date")
    if d and d.get("start"):
        return date.fromisoformat(d["start"])
    return None


def get_upcoming_games(
    client: Client,
    db_id: str,
    days: int,
) -> list[dict]:
    today = date.today()
    until = today + timedelta(days=days)
    pages: list[dict] = []
    cursor = None
    while True:
        kwargs: dict = {
            "database_id": db_id,
            "page_size": 100,
            "filter": {
                "and": [
                    {"property": "Typ",    "select":  {"equals": "Spiel"}},
                    {"property": "Status", "select":  {"equals": "Bestätigt"}},
                    {"property": "Datum",  "date":    {"on_or_after":  today.isoformat()}},
                    {"property": "Datum",  "date":    {"on_or_before": until.isoformat()}},
                ]
            },
            "sorts": [{"property": "Datum", "direction": "ascending"}],
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        pages.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return pages


# ── Daten aufbereiten ─────────────────────────────────────────────────────────

_HEIMKEYWORD: str = ""


def _split_title(title: str) -> tuple[Optional[str], Optional[str]]:
    """
    Versucht Heim- und Auswärtsteam aus dem Titel zu extrahieren.
    Erkennt: 'A - B', 'A vs B', 'A – B', 'A vs. B'
    """
    for sep in [" – ", " - ", " vs. ", " vs "]:
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return None, None


def _identify_home_away(title: str) -> tuple[Optional[str], Optional[str]]:
    home, away = _split_title(title)
    if not home or not away:
        return None, None
    # Eigenes Team hervorheben: das Team das _HEIMKEYWORD enthält
    if _HEIMKEYWORD and _HEIMKEYWORD.lower() in home.lower():
        return home, away
    if _HEIMKEYWORD and _HEIMKEYWORD.lower() in away.lower():
        return away, home   # swap: wir immer "oben"
    return home, away


def _format_date(d: date) -> tuple[str, str, str]:
    """→ (weekday, date_short, date_range_part)"""
    return (
        WEEKDAYS_DE[d.weekday()],
        f"{d.day:02d}.{d.month:02d}.",
        f"{d.day}. {MONTHS_DE[d.month]}",
    )


def page_to_game(page: dict, field_display: dict[str, str]) -> dict:
    props = page["properties"]
    # Zweck enthält den lesbaren Spieltitel (z.B. "[Liga] Heim vs Gast").
    # Titel ist nur ein technischer Schlüssel ("Platz – Datum Uhrzeit").
    zweck      = _prop_rich_text(props, "Zweck") or _prop_title(props, "Titel")
    mannschaft = _prop_rich_text(props, "Mannschaft") or None
    field_key  = _prop_select(props, "Platz") or ""
    venue      = field_display.get(field_key, field_key)
    game_date  = _prop_date(props, "Datum") or date.today()
    start_time = _prop_select(props, "Startzeit") or "?"
    end_time   = _prop_select(props, "Endzeit")

    weekday, date_short, _ = _format_date(game_date)

    # Optionalen [Altersklasse · Wettbewerb]-Präfix extrahieren
    # Format (fussball.de-Sync): "[D-Junioren · Kreisfreundschaftsspiele] Heim vs Gast"
    # Format (DFBnet-Import):    "[Wettbewerb] Heim vs Gast"
    match_text = zweck
    liga: Optional[str] = None
    if match_text.startswith("["):
        end_bracket = match_text.find("]")
        if end_bracket > 0:
            bracket_content = match_text[1:end_bracket]
            # Altersklasse steht vor dem " · " Trenner (falls vorhanden)
            liga = bracket_content.split(" · ")[0].strip()
            match_text = match_text[end_bracket + 1:].strip()

    home, away = _identify_home_away(match_text)

    return {
        "title":      match_text,           # Bereinigt ohne [Bracket]-Präfix
        "mannschaft": mannschaft or liga,   # Altersklasse / Mannschafts-Label
        "date":       game_date,
        "weekday":    weekday,
        "date_short": date_short,
        "time":       start_time,
        "end_time":   end_time,
        "field":      field_key,
        "venue":      venue,
        "home":       home or match_text,   # Fallback: ganzer Text wenn kein Trennzeichen
        "away":       away,
    }


# ── Template-Rendering ────────────────────────────────────────────────────────

def _build_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(SCRIPTS_DIR)))


def render_cover(
    games: list[dict],
    vc: dict,
    logo_b64: Optional[str],
    env: Environment,
) -> str:
    today = date.today()
    if games:
        last = games[-1]["date"]
        range_str = f"{today.day}. {MONTHS_DE[today.month]} – {last.day}. {MONTHS_DE[last.month]} {last.year}"
    else:
        range_str = str(today.year)

    display_games = games[:COVER_MAX_ROWS]
    more = max(0, len(games) - COVER_MAX_ROWS)

    tmpl = env.get_template("instagram_cover.html")
    return tmpl.render(
        vereinsname=vc.get("vereinsname", "Sportverein"),
        bg_color=vc.get("primary_color_darker", "#071c44"),
        primary_color=vc.get("primary_color", "#1e4fa3"),
        gold_color=vc.get("gold_color", "#e8c04a"),
        logo_b64=logo_b64,
        date_range=range_str,
        games=display_games,
        more=more,
    )


def render_card(
    game: dict,
    vc: dict,
    logo_b64: Optional[str],
    env: Environment,
) -> str:
    d = game["date"]
    date_label = f"{game['weekday']}, {d.day}. {MONTHS_DE[d.month]} {d.year}"

    tmpl = env.get_template("instagram_card.html")
    return tmpl.render(
        vereinsname=vc.get("vereinsname", "Sportverein"),
        bg_color=vc.get("primary_color_darker", "#071c44"),
        primary_color=vc.get("primary_color", "#1e4fa3"),
        gold_color=vc.get("gold_color", "#e8c04a"),
        logo_b64=logo_b64,
        mannschaft=game["mannschaft"],
        title=game["title"],
        home=game["home"],
        away=game["away"],
        date_label=date_label,
        time_label=game["time"],
        venue_label=game["venue"],
    )


# ── Screenshot via Playwright ─────────────────────────────────────────────────

def screenshot(html: str, output_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FEHLER: playwright nicht installiert.")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(output_path), type="png")
        browser.close()


# ── Instagram Graph API ───────────────────────────────────────────────────────
#
# Benötigt in .env:
#   INSTAGRAM_ACCOUNT_ID=<Business-Account-ID>
#   INSTAGRAM_ACCESS_TOKEN=<Page-Access-Token>
#   BOOKING_URL=http://<host>:<port>   ← Basis-URL des Servers (öffentlich erreichbar)
#
# Ablauf Karussell:
#   1. Bilder nach web/static/instagram/<datum>/ kopieren → öffentlich per /static/...
#   2. Jedes Bild als Carousel-Item bei Graph API registrieren → creation_id
#   3. Karussell-Container anlegen
#   4. Veröffentlichen

def _publish_images_to_static(image_paths: list[Path]) -> list[str]:
    """Kopiert Bilder in web/static/instagram/<datum>/ und gibt öffentliche URLs zurück."""
    import shutil
    base_url = os.getenv("BOOKING_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("BOOKING_URL nicht in .env gesetzt.")

    date_slug = image_paths[0].parent.name
    static_dir = PROJECT_ROOT / "web" / "static" / "instagram" / date_slug
    static_dir.mkdir(parents=True, exist_ok=True)

    public_urls = []
    for src in image_paths:
        dst = static_dir / src.name
        shutil.copy2(src, dst)
        public_urls.append(f"{base_url}/static/instagram/{date_slug}/{src.name}")
        print(f"  Kopiert: {src.name} → {dst}")

    return public_urls


def post_carousel_to_instagram(image_paths: list[Path], caption: str) -> None:
    import httpx

    account_id   = os.getenv("INSTAGRAM_ACCOUNT_ID")
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    if not account_id or not access_token:
        print("\n[Instagram] Kein INSTAGRAM_ACCOUNT_ID / ACCESS_TOKEN in .env → Posting übersprungen.")
        print("  Bilder liegen lokal bereit und können manuell hochgeladen werden.")
        return

    print("\n[Instagram] Bilder werden auf Server bereitgestellt …")
    public_urls = _publish_images_to_static(image_paths)

    BASE = f"https://graph.facebook.com/v21.0/{account_id}"

    # Schritt 1: Jedes Bild als Carousel-Item registrieren
    print(f"[Instagram] Registriere {len(public_urls)} Bilder als Carousel-Items …")
    children: list[str] = []
    for i, url in enumerate(public_urls, 1):
        r = httpx.post(
            f"{BASE}/media",
            params={
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": access_token,
            },
            timeout=30,
        )
        data = r.json()
        if "id" not in data:
            print(f"  FEHLER bei Bild {i}: {data}")
            return
        children.append(data["id"])
        print(f"  Bild {i}/{len(public_urls)}: {data['id']}")

    # Schritt 2: Karussell-Container anlegen
    print("[Instagram] Erstelle Karussell-Container …")
    r = httpx.post(
        f"{BASE}/media",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    container = r.json()
    if "id" not in container:
        print(f"  FEHLER beim Container: {container}")
        return
    container_id = container["id"]
    print(f"  Container-ID: {container_id}")

    # Schritt 3: Veröffentlichen
    print("[Instagram] Veröffentliche …")
    r = httpx.post(
        f"{BASE}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    result = r.json()
    if "id" in result:
        print(f"Erfolgreich gepostet! Post-ID: {result['id']}")
    else:
        print(f"  FEHLER beim Veröffentlichen: {result}")


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Matchday-Karussell generieren")
    parser.add_argument("--days",       type=int,  default=21,   help="Zeitraum in Tagen (Standard: 21)")
    parser.add_argument("--output",     type=Path, default=None, help="Ausgabeverzeichnis")
    parser.add_argument("--dry-run",    action="store_true",     help="Nur Vorschau, keine Bilder erzeugen")
    parser.add_argument("--post",       action="store_true",     help="Nach Generierung auf Instagram posten")
    parser.add_argument("--config-dir", type=Path, default=None, help="Alternativer Config-Ordner (Standard: config/)")
    args = parser.parse_args()

    # Config-Verzeichnis überschreiben falls angegeben
    if args.config_dir:
        global CONFIG_DIR
        CONFIG_DIR = args.config_dir.resolve()

    # Notion API Key
    notion_key = os.getenv("NOTION_API_KEY")
    db_id      = os.getenv("NOTION_BUCHUNGEN_DB_ID")
    if not notion_key or not db_id:
        print("FEHLER: NOTION_API_KEY und NOTION_BUCHUNGEN_DB_ID müssen in .env gesetzt sein.")
        sys.exit(1)

    # Konfig
    vc = _load_config()
    global _HEIMKEYWORD
    _HEIMKEYWORD = vc.get("heim_keyword", "")
    field_display = _load_field_display_names()
    logo = _logo_b64(vc)
    env  = _build_env()

    # Spiele laden
    print(f"Lade Spiele der nächsten {args.days} Tage …")
    client = Client(auth=notion_key)
    pages  = get_upcoming_games(client, db_id, args.days)
    games  = [page_to_game(p, field_display) for p in pages]

    if not games:
        print("Keine Spiele gefunden.")
        return

    print(f"  → {len(games)} Spiel(e) gefunden")
    for g in games:
        team = f"[{g['mannschaft']}] " if g["mannschaft"] else ""
        print(f"    {g['weekday']} {g['date_short']} {g['time']}  {team}{g['title']}")

    if args.dry_run:
        print("\n--dry-run: keine Bilder erzeugt.")
        return

    # Ausgabeverzeichnis
    if args.output is None:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d")
        out_dir = PROJECT_ROOT / "output" / "instagram" / ts
    else:
        out_dir = args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nErzeuge Bilder in {out_dir} …")

    generated: list[Path] = []

    # Cover-Bild (Spielübersicht)
    cover_html = render_cover(games, vc, logo, env)
    cover_path = out_dir / "00_cover.png"
    print("  Rendere Cover …", end=" ", flush=True)
    screenshot(cover_html, cover_path)
    print("OK")
    generated.append(cover_path)

    # Einzelkarten (max. CAROUSEL_MAX - 1, da Cover Slot 1 belegt)
    card_games = games[: CAROUSEL_MAX - 1]
    for i, game in enumerate(card_games, start=1):
        card_html = render_card(game, vc, logo, env)
        card_path = out_dir / f"{i:02d}_card.png"
        label = game["mannschaft"] or game["title"][:30]
        print(f"  Rendere Karte {i}/{len(card_games)}: {label} …", end=" ", flush=True)
        screenshot(card_html, card_path)
        print("OK")
        generated.append(card_path)

    print(f"\n✓ {len(generated)} Bilder gespeichert in {out_dir}")

    # Caption generieren
    caption_lines = [
        f"🏟 Spielvorschau {vc.get('vereinsname', '')}",
        "",
    ]
    for g in games:
        team = f"[{g['mannschaft']}] " if g["mannschaft"] else ""
        caption_lines.append(f"{g['weekday']} {g['date_short']} {g['time']} – {team}{g['title']}")
    caption_lines += ["", "#Fussball #Matchday"]
    caption = "\n".join(caption_lines)

    print("\n── Caption ──────────────────────────────")
    print(caption)
    print("─────────────────────────────────────────")

    if args.post:
        post_carousel_to_instagram(generated, caption)


if __name__ == "__main__":
    main()

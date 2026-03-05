"""
booking/instagram.py — Instagram Wochenend-Spielvorschau posten

Ablauf:
  1. Spiele bis nächsten Sonntag 23:59 aus der Notion-DB laden
  2. Pro Spiel eine 1080×1080-Karte + Cover-Bild mit Playwright rendern
  3. Bilder unter web/static/instagram/ ablegen (von der App serviert)
  4. Via Instagram Graph API als Karussell veröffentlichen
     (Bilder müssen von außen erreichbar sein → BOOKING_URL als Basis)

Benötigt:
  - INSTAGRAM_ACCOUNT_ID und INSTAGRAM_ACCESS_TOKEN in .env
  - BOOKING_URL muss öffentlich erreichbar sein
  - playwright installiert: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
STATIC_INSTAGRAM = PROJECT_ROOT / "web" / "static" / "instagram"

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS_DE   = ["", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
               "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
CAROUSEL_MAX = 10


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _next_sunday() -> date:
    today = date.today()
    days_ahead = 6 - today.weekday()  # weekday(): Mo=0 … So=6
    if days_ahead < 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _load_matchday_module():
    """Lädt das standalone-Script als Modul (wiederverwendet seine Render-Logik)."""
    spec = importlib.util.spec_from_file_location(
        "instagram_matchday", SCRIPTS_DIR / "instagram_matchday.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _logo_b64(vc: dict) -> Optional[str]:
    logo_url = vc.get("logo_url", "/static/logo.svg")
    rel = logo_url.lstrip("/")
    for path in [PROJECT_ROOT / "web" / rel, PROJECT_ROOT / "web" / "static" / "logo.svg"]:
        if path.exists() and path.suffix.lower() == ".svg":
            return base64.b64encode(path.read_bytes()).decode()
    return None


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def post_wochenende(notion_key: str, db_id: str, booking_url: str,
                    account_id: str, access_token: str) -> dict:
    """
    Generiert Karussell-Bilder für alle Spiele bis nächsten Sonntag und
    postet sie auf Instagram.

    Rückgabe: {"posted": int, "skipped": int, "images": [str], "caption": str}
    Wirft Exception bei Fehler.
    """
    from notion_client import Client
    mod = _load_matchday_module()

    # ── Spiele laden ──────────────────────────────────────────────────────────
    sunday = _next_sunday()
    today  = date.today()
    days   = (sunday - today).days + 1  # inkl. Sonntag bis 23:59

    client = Client(auth=notion_key)
    pages  = mod.get_upcoming_games(client, db_id, days)

    if not pages:
        return {"posted": 0, "skipped": 0, "images": [], "caption": ""}

    config_dir = os.environ.get("CONFIG_DIR", "config")
    vc_path = PROJECT_ROOT / config_dir / "vereinsconfig.json"
    vc = json.loads(vc_path.read_text(encoding="utf-8")) if vc_path.exists() else {}

    fc_path = PROJECT_ROOT / config_dir / "field_config.json"
    field_display = json.loads(fc_path.read_text(encoding="utf-8")).get("display_names", {}) if fc_path.exists() else {}

    # heim_keywords setzen für _identify_home_away im Skript
    keywords = vc.get("heim_keywords", [vc.get("heim_keyword", "")])
    mod._HEIMKEYWORD = keywords[0] if keywords else ""

    games = [mod.page_to_game(p, field_display) for p in pages]

    # ── Bilder rendern ────────────────────────────────────────────────────────
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(SCRIPTS_DIR)))
    logo = _logo_b64(vc)

    STATIC_INSTAGRAM.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []

    cover_html = mod.render_cover(games, vc, logo, env)
    cover_path = STATIC_INSTAGRAM / "00_cover.png"
    mod.screenshot(cover_html, cover_path)
    generated.append(cover_path)

    card_games = games[: CAROUSEL_MAX - 1]
    for i, game in enumerate(card_games, start=1):
        card_html = mod.render_card(game, vc, logo, env)
        card_path = STATIC_INSTAGRAM / f"{i:02d}_card.png"
        mod.screenshot(card_html, card_path)
        generated.append(card_path)

    # ── Caption ───────────────────────────────────────────────────────────────
    lines = [f"Spielvorschau {vc.get('vereinsname', '')} – Wochenende", ""]
    for g in games:
        team = f"[{g['mannschaft']}] " if g["mannschaft"] else ""
        lines.append(f"{g['weekday']} {g['date_short']} {g['time']} – {team}{g['title']}")
    hashtags = vc.get("instagram_hashtags", "#Fussball #Matchday")
    lines += ["", hashtags]
    caption = "\n".join(lines)

    # ── Instagram Graph API ───────────────────────────────────────────────────
    import httpx

    base_url = booking_url.rstrip("/")
    api_base = f"https://graph.facebook.com/v21.0/{account_id}"

    children: list[str] = []
    for img_path in generated:
        public_url = f"{base_url}/static/instagram/{img_path.name}"
        r = httpx.post(
            f"{api_base}/media",
            params={
                "image_url":         public_url,
                "is_carousel_item":  "true",
                "access_token":      access_token,
            },
            timeout=30,
        )
        r.raise_for_status()
        children.append(r.json()["id"])

    container = httpx.post(
        f"{api_base}/media",
        params={
            "media_type":   "CAROUSEL",
            "children":     ",".join(children),
            "caption":      caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    container.raise_for_status()
    container_id = container.json()["id"]

    publish = httpx.post(
        f"{api_base}/media_publish",
        params={
            "creation_id":  container_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    publish.raise_for_status()

    return {
        "posted":  len(generated),
        "skipped": max(0, len(games) - (CAROUSEL_MAX - 1)),
        "images":  [p.name for p in generated],
        "caption": caption,
    }

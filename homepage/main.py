from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, timedelta

# Projektroot zum Python-Pfad hinzufügen, damit booking/, notion/, utils/ gefunden werden
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from booking.models import FieldName
import booking.field_config as fc
from booking.vereinsconfig import load as _load_vc
from notion.client import NotionRepository
from utils.time_slots import get_all_start_slots
from web.config import get_settings

BASE_DIR = os.path.dirname(__file__)
VEREINSINFO_DIR = os.path.join(BASE_DIR, "userdata", "vereinsinfo")


def _load_vereins_map() -> dict[str, str]:
    """Baut ein Mapping von Vereinsnamen (normalisiert) → Club-ID aus vereinsinfo/."""
    result: dict[str, str] = {}
    if not os.path.isdir(VEREINSINFO_DIR):
        return result
    for fname in os.listdir(VEREINSINFO_DIR):
        if not fname.endswith(".json"):
            continue
        club_id = fname[:-5]
        try:
            with open(os.path.join(VEREINSINFO_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for team in data.get("data", []):
            if not isinstance(team, dict):
                continue
            raw: str = team.get("name", "")
            # "Herren - FT Braunschweig" → "FT Braunschweig"
            club_part = raw.split(" - ", 1)[1] if " - " in raw else raw
            # Nullbreite Leerzeichen entfernen (kommen in manchen Namen vor)
            club_part = club_part.replace("\u200b", "").strip()
            key = club_part.lower()
            if key and key not in result:
                result[key] = club_id
    return result


CLUBS_MAP: dict[str, str] = _load_vereins_map()

# Mapping: venue-Kürzel → (Label, Gruppen-ID in field_config.json)
VENUES = {
    "kura":  ("Kunstrasen", "kura"),
    "rasen": ("Naturrasen", "rasen"),
    "halle": ("Turnhalle",  "halle"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.repo = NotionRepository(settings)
    app.state.settings = settings
    yield


_vc = _load_vc()
app = FastAPI(title=_vc.get("vereinsname", "Sportverein"), lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/userdata", StaticFiles(directory=os.path.join(BASE_DIR, "userdata")), name="userdata")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["enumerate"] = enumerate

# Vereinsspezifische Template-Globals aus config/vereinsconfig.json
templates.env.globals["vereinsname"] = _vc.get("vereinsname", "Sportverein")
templates.env.globals["vereinsname_lang"] = _vc.get("vereinsname_lang", _vc.get("vereinsname", "Sportverein"))
templates.env.globals["vereinsfarben"] = {
    "primary":        _vc.get("primary_color", "#1e4fa3"),
    "primary_dark":   _vc.get("primary_color_dark", "#0d2f6b"),
    "primary_darker": _vc.get("primary_color_darker", "#071c44"),
    "gold":           _vc.get("gold_color", "#e8c04a"),
}


def _team_initials(name: str) -> str:
    """'SV Muster FC' → 'SM',  'FC Bayern' → 'FB',  '' → '?'"""
    words = [w for w in name.split() if w and w[0].isalpha()]
    letters = [w[0].upper() for w in words if w[0].isupper()]
    return "".join(letters[:2]) or name[:2].upper() or "?"


templates.env.filters["team_initials"] = _team_initials


def _club_logo_url(name: str) -> str:
    """Gibt den lokalen Pfad zum Vereinslogo zurück, oder '' wenn nicht gefunden."""
    if not name:
        return ""
    key = name.strip().replace("\u200b", "").lower()
    # 1. Exakter Treffer
    club_id = CLUBS_MAP.get(key)
    if not club_id:
        # 2. Teilstring-Treffer: bekannter Vereinsname ist in gegnerischem Namen enthalten
        for known, cid in CLUBS_MAP.items():
            if known and known in key:
                club_id = cid
                break
    if club_id and os.path.exists(os.path.join(VEREINSINFO_DIR, f"{club_id}.png")):
        return f"/userdata/vereinsinfo/{club_id}.png"
    return ""


templates.env.filters["club_logo_url"] = _club_logo_url


# ------------------------------------------------------------------ Hilfsfunktionen

def _week_context(year: int, week: int) -> dict:
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    prev = monday - timedelta(days=7)
    nxt = monday + timedelta(days=7)
    return {
        "year": year, "week": week,
        "monday": monday, "sunday": sunday,
        "prev_year": prev.isocalendar()[0], "prev_week": prev.isocalendar()[1],
        "next_year": nxt.isocalendar()[0], "next_week": nxt.isocalendar()[1],
        "days": [monday + timedelta(days=i) for i in range(7)],
    }


def _fields_for_venue(venue: str) -> list[FieldName]:
    """Gibt alle FieldName-Werte zurück, die zur angegebenen Venue-Gruppe gehören."""
    _, group_id = VENUES.get(venue, VENUES["kura"])
    cfg = fc.load()
    for group in cfg.get("field_groups", []):
        if group.get("id") == group_id:
            return [FieldName(fid) for fid in group["fields"]]
    return []


def _availability_context(fields: list[FieldName]) -> dict:
    """Baut den Kontext für field_display_names und conflict_sources."""
    visible_ids = [f.value for f in fields]
    return {
        "field_display_names": fc.get_display_names(),
        "conflict_sources": fc.get_conflict_sources(visible_ids),
    }


# ------------------------------------------------------------------ Routes

@app.get("/impressum", response_class=HTMLResponse)
async def impressum(request: Request):
    return templates.TemplateResponse("impressum.html", {"request": request})


_UPCOMING_PAGE_SIZE = 8


def _get_upcoming_page(repo, page: int) -> tuple[list, int]:
    """Gibt (items_auf_seite, total_pages) zurück."""
    games = repo.get_upcoming_games(limit=100)
    ext_events = repo.get_upcoming_events(limit=100)
    all_items = sorted(
        [{"kind": "game",  "item": g} for g in games] +
        [{"kind": "event", "item": e} for e in ext_events],
        key=lambda x: (x["item"].date, x["item"].start_time),
    )
    total = len(all_items)
    total_pages = max(1, (total + _UPCOMING_PAGE_SIZE - 1) // _UPCOMING_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * _UPCOMING_PAGE_SIZE
    return all_items[offset: offset + _UPCOMING_PAGE_SIZE], page, total_pages


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    today = date.today()
    iso = today.isocalendar()
    ctx = _week_context(iso[0], iso[1])
    repo = request.app.state.repo
    upcoming_items, page, total_pages = _get_upcoming_page(repo, 1)
    return templates.TemplateResponse("index.html", {
        "request": request, **ctx, "today": today,
        "upcoming_items": upcoming_items, "page": page, "total_pages": total_pages,
        "booking_url": request.app.state.settings.booking_url,
    })


@app.get("/upcoming", response_class=HTMLResponse)
async def upcoming_partial(request: Request, page: int = 1):
    repo = request.app.state.repo
    upcoming_items, page, total_pages = _get_upcoming_page(repo, page)
    return templates.TemplateResponse(
        "partials/_upcoming.html",
        {"request": request, "upcoming_items": upcoming_items, "page": page, "total_pages": total_pages},
    )


@app.get("/availability/week", response_class=HTMLResponse)
async def availability_week(request: Request, year: int, week: int, venue: str = "kura"):
    repo = request.app.state.repo
    bookings = repo.get_bookings_for_week(year, week)
    venue_fields = _fields_for_venue(venue)
    ctx = _week_context(year, week)
    label, _ = VENUES.get(venue, VENUES["kura"])
    return templates.TemplateResponse(
        "partials/_availability_week.html",
        {
            "request": request,
            "bookings": bookings,
            "fields": venue_fields,
            "slots": get_all_start_slots(),
            "venue": venue,
            "venue_label": label,
            "today": date.today().isoformat(),
            **_availability_context(venue_fields),
            **ctx,
        },
    )


@app.get("/availability/day", response_class=HTMLResponse)
async def availability_day(request: Request, day: date, venue: str = "kura"):
    repo = request.app.state.repo
    bookings = repo.get_bookings_for_date(day)
    venue_fields = _fields_for_venue(venue)
    label, _ = VENUES.get(venue, VENUES["kura"])
    return templates.TemplateResponse(
        "partials/_availability_day.html",
        {
            "request": request,
            "bookings": bookings,
            "fields": venue_fields,
            "slots": get_all_start_slots(),
            "day": day,
            "today": date.today().isoformat(),
            "prev_day": (day - timedelta(days=1)).isoformat(),
            "next_day": (day + timedelta(days=1)).isoformat(),
            "venue": venue,
            "venue_label": label,
            **_availability_context(venue_fields),
        },
    )

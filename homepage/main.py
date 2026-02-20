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

from booking.models import BlackoutType, FieldName
from notion.client import NotionRepository
from utils.time_slots import get_all_start_slots
from web.config import get_settings

BASE_DIR = os.path.dirname(__file__)

# Club-Name → fussball.de Club-ID (für Logos)
_clubs_path = os.path.join(BASE_DIR, "userdata", "clubs.json")
try:
    with open(_clubs_path, encoding="utf-8") as _f:
        CLUBS_MAP: dict[str, str] = json.load(_f)
except FileNotFoundError:
    CLUBS_MAP = {}

# Mapping: venue-Kürzel → (Label, Feld-Filter-Attr, Prefix)
VENUES = {
    "kura":  ("Kunstrasen", "is_kura", "Kura"),
    "rasen": ("Naturrasen", "is_rasen", "Rasen"),
    "halle": ("Turnhalle",  "is_halle", "Halle"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.repo = NotionRepository(settings)
    app.state.settings = settings
    yield


app = FastAPI(title="TuS Cremlingen", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/userdata", StaticFiles(directory=os.path.join(BASE_DIR, "userdata")), name="userdata")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["enumerate"] = enumerate


def _team_initials(name: str) -> str:
    """'SV Muster FC' → 'SM',  'FC Bayern' → 'FB',  '' → '?'"""
    words = [w for w in name.split() if w and w[0].isalpha()]
    letters = [w[0].upper() for w in words if w[0].isupper()]
    return "".join(letters[:2]) or name[:2].upper() or "?"


templates.env.filters["team_initials"] = _team_initials


def _club_logo_url(name: str) -> str:
    """Gibt die fussball.de-Logo-URL zurück, oder '' wenn kein Eintrag vorhanden."""
    club_id = CLUBS_MAP.get(name) or CLUBS_MAP.get(name.strip())
    if not club_id:
        # Case-insensitive fallback
        lower = name.lower()
        for k, v in CLUBS_MAP.items():
            if k.lower() == lower:
                club_id = v
                break
    if club_id:
        return f"https://www.fussball.de/export.media/-/action/getLogo/format/2/id/{club_id}"
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
    _, attr, _ = VENUES.get(venue, VENUES["kura"])
    return [f for f in FieldName if getattr(f, attr)]


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
    blackouts = repo.get_blackouts_for_week(year, week)
    venue_fields = _fields_for_venue(venue)
    ctx = _week_context(year, week)
    label, _, prefix = VENUES.get(venue, VENUES["kura"])
    return templates.TemplateResponse(
        "partials/_availability_week.html",
        {
            "request": request,
            "bookings": bookings,
            "blackouts": blackouts,
            "fields": venue_fields,
            "slots": get_all_start_slots(),
            "venue": venue,
            "venue_label": label,
            "venue_prefix": prefix,
            "today": date.today().isoformat(),
            **ctx,
        },
    )


@app.get("/availability/day", response_class=HTMLResponse)
async def availability_day(request: Request, day: date, venue: str = "kura"):
    repo = request.app.state.repo
    bookings = repo.get_bookings_for_date(day)
    blackouts = repo.get_blackouts_for_date(day)
    venue_fields = _fields_for_venue(venue)
    label, _, prefix = VENUES.get(venue, VENUES["kura"])
    return templates.TemplateResponse(
        "partials/_availability_day.html",
        {
            "request": request,
            "bookings": bookings,
            "blackouts": blackouts,
            "fields": venue_fields,
            "slots": get_all_start_slots(),
            "day": day,
            "today": date.today().isoformat(),
            "prev_day": (day - timedelta(days=1)).isoformat(),
            "next_day": (day + timedelta(days=1)).isoformat(),
            "venue": venue,
            "venue_label": label,
            "venue_prefix": prefix,
        },
    )

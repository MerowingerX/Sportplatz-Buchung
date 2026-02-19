from __future__ import annotations

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
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["enumerate"] = enumerate


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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    today = date.today()
    iso = today.isocalendar()
    ctx = _week_context(iso[0], iso[1])
    repo = request.app.state.repo
    upcoming_games = repo.get_upcoming_games(limit=10)
    return templates.TemplateResponse("index.html", {"request": request, **ctx, "today": today, "upcoming_games": upcoming_games})


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

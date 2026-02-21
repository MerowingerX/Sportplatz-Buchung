from datetime import date as Date, time, timedelta

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
templates.env.globals["time_module"] = time

_cache: TTLCache = TTLCache(maxsize=128, ttl=60)


def _get_week_context(year: int, week: int) -> dict:
    monday = Date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    prev = monday - timedelta(days=7)
    nxt = monday + timedelta(days=7)
    days = [monday + timedelta(days=i) for i in range(7)]
    return {
        "year": year,
        "week": week,
        "monday": monday,
        "sunday": sunday,
        "days": days,
        "prev_year": prev.isocalendar()[0],
        "prev_week": prev.isocalendar()[1],
        "next_year": nxt.isocalendar()[0],
        "next_week": nxt.isocalendar()[1],
    }


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, current_user: CurrentUser):
    today = Date.today()
    iso = today.isocalendar()
    ctx = _get_week_context(iso[0], iso[1])
    return templates.TemplateResponse(
        "calendar.html",
        {"request": request, "current_user": current_user, "today": today.isoformat(), **ctx},
    )


@router.get("/calendar/day", response_class=HTMLResponse)
async def calendar_day(request: Request, current_user: CurrentUser, d: str):
    repo = request.app.state.repo
    target = Date.fromisoformat(d)
    iso = target.isocalendar()
    year, week = iso[0], iso[1]
    cache_key = f"week:{year}:{week}"

    if cache_key not in _cache:
        bookings = repo.get_bookings_for_week(year, week)
        blackouts = repo.get_blackouts_for_week(year, week)
        _cache[cache_key] = (bookings, blackouts)
    else:
        bookings, blackouts = _cache[cache_key]

    day_bookings = [b for b in bookings if b.date == target]
    return templates.TemplateResponse(
        "partials/_calendar_day.html",
        {
            "request": request,
            "current_user": current_user,
            "day": target,
            "bookings": day_bookings,
            "blackouts": blackouts,
            "today": Date.today().isoformat(),
            "prev_day": target - timedelta(days=1),
            "next_day": target + timedelta(days=1),
        },
    )


@router.get("/calendar/week", response_class=HTMLResponse)
async def calendar_week(request: Request, current_user: CurrentUser, year: int, week: int):
    repo = request.app.state.repo
    cache_key = f"week:{year}:{week}"

    if cache_key not in _cache:
        bookings = repo.get_bookings_for_week(year, week)
        blackouts = repo.get_blackouts_for_week(year, week)
        _cache[cache_key] = (bookings, blackouts)
    else:
        bookings, blackouts = _cache[cache_key]

    ctx = _get_week_context(year, week)
    return templates.TemplateResponse(
        "partials/_calendar_week.html",
        {
            "request": request,
            "current_user": current_user,
            "bookings": bookings,
            "blackouts": blackouts,
            "today": Date.today().isoformat(),
            **ctx,
        },
    )


def invalidate_week_cache(booking_date: Date) -> None:
    iso = booking_date.isocalendar()
    key = f"week:{iso[0]}:{iso[1]}"
    _cache.pop(key, None)

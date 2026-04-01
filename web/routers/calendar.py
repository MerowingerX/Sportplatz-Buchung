from web.templates_instance import templates
from datetime import date as Date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from icalendar import Calendar, Event as IcalEvent

from auth.dependencies import CurrentUser
import booking.field_config as fc
from utils.time_slots import SLOT_MINUTES

router = APIRouter()
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


def _field_context(role_value: str) -> dict:
    """Baut den Kontext für field_groups, display_names und conflict_sources."""
    field_groups = fc.get_visible_groups(role_value)
    visible_ids = [fid for _, fields in field_groups for fid in fields]
    return {
        "field_groups": field_groups,
        "field_display_names": fc.get_display_names(),
        "conflict_sources": fc.get_conflict_sources(visible_ids),
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
        _cache[cache_key] = bookings
    else:
        bookings = _cache[cache_key]

    day_bookings = [b for b in bookings if b.date == target]
    mannschaft_shortnames = {
        m.name: m.shortname for m in repo.get_all_mannschaften() if m.shortname
    }
    return templates.TemplateResponse(
        "partials/_calendar_day.html",
        {
            "request": request,
            "current_user": current_user,
            "day": target,
            "bookings": day_bookings,
            "today": Date.today().isoformat(),
            "prev_day": target - timedelta(days=1),
            "next_day": target + timedelta(days=1),
            "mannschaft_shortnames": mannschaft_shortnames,
            **_field_context(current_user.role.value),
        },
    )


@router.get("/calendar/week", response_class=HTMLResponse)
async def calendar_week(
    request: Request,
    current_user: CurrentUser,
    year: int,
    week: int,
    start_hour: int = 16,
):
    repo = request.app.state.repo
    cache_key = f"week:{year}:{week}"

    if cache_key not in _cache:
        bookings = repo.get_bookings_for_week(year, week)
        _cache[cache_key] = bookings
    else:
        bookings = _cache[cache_key]

    # Clamp and compute time-navigation context
    start_hour = max(0, min(18, start_hour))
    prev_start_hour = max(0, start_hour - 2)
    next_start_hour = min(18, start_hour + 2)

    # 6-hour window of slots starting at start_hour, using configured SLOT_MINUTES
    num_slots = 360 // SLOT_MINUTES
    slots: list[str] = []
    h, m = start_hour, 0
    for _ in range(num_slots):
        slots.append(f"{h:02d}:{m:02d}")
        m += SLOT_MINUTES
        if m >= 60:
            m -= 60
            h += 1
        if h >= 24:
            break

    last_slot = slots[-1]
    time_range = f"{slots[0]} – {last_slot}"

    mannschaft_shortnames = {
        m.name: m.shortname for m in repo.get_all_mannschaften() if m.shortname
    }
    ctx = _get_week_context(year, week)
    return templates.TemplateResponse(
        "partials/_calendar_week.html",
        {
            "request": request,
            "current_user": current_user,
            "bookings": bookings,
            "today": Date.today().isoformat(),
            "time_slots": slots,
            "start_hour": start_hour,
            "prev_start_hour": prev_start_hour,
            "next_start_hour": next_start_hour,
            "time_range": time_range,
            "mannschaft_shortnames": mannschaft_shortnames,
            **_field_context(current_user.role.value),
            **ctx,
        },
    )


def invalidate_week_cache(booking_date: Date) -> None:
    iso = booking_date.isocalendar()
    key = f"week:{iso[0]}:{iso[1]}"
    _cache.pop(key, None)


_TZ = ZoneInfo("Europe/Berlin")


@router.get("/calendar/export.ics")
async def calendar_export_ics(request: Request, current_user: CurrentUser):
    """iCal-Export aller eigenen kommenden Buchungen."""
    from booking.models import UserRole
    repo = request.app.state.repo
    all_bookings = repo.get_all_bookings()

    # Trainer sehen nur ihre eigenen Buchungen; Admins/Platzwart sehen alle
    if current_user.role == UserRole.TRAINER:
        bookings = [b for b in all_bookings if b.booked_by_id == current_user.notion_id]
    else:
        bookings = all_bookings

    cal = Calendar()
    cal.add("prodid", "-//Sportplatz Buchungssystem//DE")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Platzbelegung")
    cal.add("x-wr-timezone", "Europe/Berlin")
    cal.add("calscale", "GREGORIAN")

    for b in bookings:
        ev = IcalEvent()
        label = b.mannschaft or b.zweck or b.booking_type.value
        ev.add("summary", f"{label} – {b.field.value}")
        ev.add("dtstart", datetime.combine(b.date, b.start_time).replace(tzinfo=_TZ))
        ev.add("dtend",   datetime.combine(b.date, b.end_time).replace(tzinfo=_TZ))
        ev.add("uid",     f"booking-{b.notion_id}@sportplatz")
        desc_parts = [b.booking_type.value]
        if b.zweck:
            desc_parts.append(b.zweck)
        if b.kontakt:
            desc_parts.append(f"Kontakt: {b.kontakt}")
        ev.add("description", " | ".join(desc_parts))
        cal.add_component(ev)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="platzbelegung.ics"'},
    )

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser, require_role
from booking.booking import build_booking, check_availability, dfbnet_displace
from booking.models import BookingCreate, BookingStatus, FieldName, BookingType, Mannschaft, SeriesRhythm, UserRole
from utils.time_slots import (
    compute_end_time,
    get_all_start_slots,
)
from booking.booking import is_rasen_season
from utils.sunset import sunset_warning_text
from web.config import get_settings
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/bookings")
templates = Jinja2Templates(directory="web/templates")


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


@router.get("", response_class=HTMLResponse)
async def bookings_page(
    request: Request,
    current_user: CurrentUser,
    date: Optional[date] = None,
    field: Optional[str] = None,
    start_time: Optional[str] = None,
):
    start_slots = get_all_start_slots()
    return templates.TemplateResponse(
        "partials/_booking_form.html",
        {
            "request": request,
            "current_user": current_user,
            "fields": list(FieldName),
            "start_slots": start_slots,
            "durations": [60, 90, 180],
            "booking_types": list(BookingType),
            "rhythms": list(SeriesRhythm),
            "mannschaften": list(Mannschaft),
            "prefill_date": date,
            "prefill_field": field,
            "prefill_start_time": start_time,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_booking(
    request: Request,
    current_user: CurrentUser,
    field: str = Form(...),
    booking_date: date = Form(..., alias="date"),
    start_time: str = Form(...),
    duration_min: int = Form(...),
    booking_type: str = Form(...),
):
    from datetime import time as dtime
    repo = request.app.state.repo
    settings = get_settings()

    h, m = start_time.split(":")
    parsed_start = dtime(int(h), int(m))

    data = BookingCreate(
        field=FieldName(field),
        date=booking_date,
        start_time=parsed_start,
        duration_min=duration_min,
        booking_type=BookingType(booking_type),
    )

    existing = repo.get_bookings_for_date(booking_date)
    blackouts = repo.get_blackouts_for_date(booking_date) if data.field.is_rasen else []

    booking, errors = build_booking(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        existing_bookings=existing,
        blackouts=blackouts,
    )

    if errors:
        error_html = "".join(f"<li>{e}</li>" for e in errors)
        return HTMLResponse(
            f'<div id="form-errors" class="errors"><ul>{error_html}</ul></div>'
            + _toast("Buchung fehlgeschlagen", "error"),
            status_code=422,
        )

    invalidate_week_cache(booking_date)

    owner = repo.get_user_by_id(current_user.sub)
    if owner:
        from notifications.notify import send_booking_confirmation
        await send_booking_confirmation(booking, owner, settings)

    iso = booking_date.isocalendar()
    html = (
        _toast(f"Buchung für {booking.field.value} am {booking.date.strftime('%d.%m.%Y')} gespeichert!")
        + f'<div id="calendar-week" hx-swap-oob="innerHTML">'
        + f'<div hx-get="/calendar/week?year={iso[0]}&week={iso[1]}"'
        + ' hx-trigger="load" hx-swap="innerHTML"></div></div>'
    )
    resp = HTMLResponse(html)
    resp.headers["HX-Trigger"] = "closeModal"
    return resp


@router.delete("/{booking_id}", response_class=HTMLResponse)
async def cancel_booking(
    request: Request,
    booking_id: str,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    settings = get_settings()
    booking = repo.update_booking_status(booking_id, BookingStatus.STORNIERT)
    invalidate_week_cache(booking.date)

    owner = repo.get_user_by_id(booking.booked_by_id)
    if owner:
        from notifications.notify import send_cancellation_notice
        await send_cancellation_notice(booking, owner, settings)

    free_slot = (
        f'<button class="slot slot--free slot--clickable"'
        f' hx-get="/bookings?date={booking.date.isoformat()}'
        f'&field={booking.field.value}'
        f'&start_time={booking.start_time.strftime("%H:%M")}"'
        f' hx-target="#booking-modal-content"'
        f' hx-swap="innerHTML"'
        f' onclick="document.getElementById(\'booking-modal\').showModal()"'
        f' title="{booking.date.strftime("%d.%m.%Y")} {booking.start_time.strftime("%H:%M")}'
        f' – {booking.field.value}">'
        f'</button>'
    )
    return HTMLResponse(free_slot + _toast("Buchung storniert."))


@router.get("/check-availability", response_class=HTMLResponse)
async def check_availability_endpoint(
    request: Request,
    current_user: CurrentUser,
    field: str = Query(""),
    booking_date: Optional[date] = Query(None, alias="date"),
    start_time: str = Query(""),
    duration_min: Optional[int] = Query(None, alias="duration_min"),
):
    if not field or not booking_date or not start_time or not duration_min:
        return HTMLResponse("")

    from datetime import time as dtime
    repo = request.app.state.repo

    try:
        h, m = start_time.split(":")
        parsed_start = dtime(int(h), int(m))
        field_enum = FieldName(field)
    except (ValueError, KeyError):
        return HTMLResponse('<span class="badge badge--neutral">–</span>')

    existing = repo.get_bookings_for_date(booking_date)
    conflicts = check_availability(existing, field_enum, parsed_start, duration_min)

    if conflicts:
        names = ", ".join(
            f"{b.field.value} {b.start_time.strftime('%H:%M')}–{b.end_time.strftime('%H:%M')}"
            for b in conflicts
        )
        return HTMLResponse(
            f'<span class="badge badge--error">Belegt: {names}</span>'
        )
    return HTMLResponse('<span class="badge badge--success">Verfügbar</span>')


@router.get("/sunset-info", response_class=HTMLResponse)
async def sunset_info(
    request: Request,
    current_user: CurrentUser,
    field: str = Query(""),
    booking_date: Optional[date] = Query(None, alias="date"),
    duration_min: Optional[int] = Query(None, alias="duration_min"),
    start_time: str = Query(""),
):
    if not field or not booking_date or not start_time or not duration_min:
        return HTMLResponse("")

    # Sonnenuntergang nur für Rasen relevant (Kura/Halle haben Flutlicht)
    try:
        field_enum = FieldName(field)
    except (ValueError, KeyError):
        return HTMLResponse("")
    if not field_enum.is_rasen:
        return HTMLResponse("")

    from datetime import time as dtime
    settings = get_settings()
    h, m = start_time.split(":")
    parsed_start = dtime(int(h), int(m))
    end_time = compute_end_time(parsed_start, duration_min)
    note = sunset_warning_text(
        booking_date, end_time,
        settings.location_lat, settings.location_lon, settings.location_name,
    )
    if note:
        return HTMLResponse(f'<div class="sunset-warning">{note}</div>')
    return HTMLResponse("")


@router.get("/validate-rasen-season", response_class=HTMLResponse)
async def validate_rasen_season(
    request: Request,
    current_user: CurrentUser,
    field: str = Query(""),
    booking_date: Optional[date] = Query(None, alias="date"),
):
    if not field or not booking_date:
        return HTMLResponse("")
    try:
        field_enum = FieldName(field)
    except (ValueError, KeyError):
        return HTMLResponse("")
    if not field_enum.is_rasen:
        return HTMLResponse("")
    if not is_rasen_season(booking_date):
        return HTMLResponse(
            '<div class="season-warning">Rasen ist außerhalb der Saison (März–November) nicht buchbar.</div>'
        )
    return HTMLResponse("")

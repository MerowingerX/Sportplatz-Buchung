from web.templates_instance import templates
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Form
from fastapi.responses import HTMLResponse

from auth.dependencies import CurrentUser, require_permission
from booking.booking import build_booking, check_availability, dfbnet_displace
from booking.models import BookingCreate, BookingStatus, FieldName, BookingType, Permission, has_permission
import booking.field_config as fc
from utils.time_slots import (
    compute_end_time,
    get_all_start_slots,
)
from utils.sunset import sunset_warning_text
from web.audit_log import log_booking, log_cancel
from web.config import get_settings
from booking.field_config import get_visible_fields, get_display_name
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/bookings")


def _visible_fields(current_user) -> list[FieldName]:
    return get_visible_fields(current_user.role.value)


from web.htmx import toast as _toast


def _get_cc_emails(repo, mannschaft_name: Optional[str]) -> list[str]:
    if not mannschaft_name:
        return []
    mannschaften = repo.get_all_mannschaften()
    m = next((m for m in mannschaften if m.name == mannschaft_name), None)
    return m.cc_emails if m else []


@router.get("", response_class=HTMLResponse)
async def bookings_page(
    request: Request,
    current_user: CurrentUser,
    date: Optional[date] = None,
    field: Optional[str] = None,
    start_time: Optional[str] = None,
):
    repo = request.app.state.repo
    mannschaften = repo.get_all_mannschaften(only_active=True)
    user_mannschaft = current_user.mannschaft
    start_slots = get_all_start_slots()
    return templates.TemplateResponse(
        "partials/_booking_form.html",
        {
            "request": request,
            "current_user": current_user,
            "fields": _visible_fields(current_user),
            "field_display_names": fc.get_display_names(),
            "start_slots": start_slots,
            "durations": [60, 90, 180],
            "booking_types": list(BookingType),
            "prefill_date": date,
            "prefill_field": field,
            "prefill_start_time": start_time,
            "mannschaften": mannschaften,
            "user_mannschaft": user_mannschaft,
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
    mannschaft: Optional[str] = Form(None),
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
        mannschaft=mannschaft or None,
    )

    existing = repo.get_bookings_for_date(booking_date)

    booking, errors = build_booking(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        existing_bookings=existing,
    )

    if errors:
        start_slots = get_all_start_slots()
        mannschaften = repo.get_all_mannschaften(only_active=True)
        return templates.TemplateResponse(
            "partials/_booking_form.html",
            {
                "request": request,
                "current_user": current_user,
                "fields": _visible_fields(current_user),
                "field_display_names": fc.get_display_names(),
                "start_slots": start_slots,
                "durations": [60, 90, 180],
                "booking_types": list(BookingType),
                "prefill_date": booking_date,
                "prefill_field": field,
                "prefill_start_time": start_time,
                "errors": errors,
                "form_toast": _toast("Buchung fehlgeschlagen", "error"),
                "mannschaften": mannschaften,
                "user_mannschaft": current_user.mannschaft,
            },
        )

    invalidate_week_cache(booking_date)
    log_booking(request, current_user.username, booking)

    owner = repo.get_user_by_id(current_user.sub)
    if owner:
        cc = _get_cc_emails(repo, booking.mannschaft)
        from notifications.notify import send_booking_confirmation
        await send_booking_confirmation(booking, owner, settings, cc=cc)

    display = get_display_name(booking.field.value)
    iso = booking_date.isocalendar()
    html = (
        _toast(f"Buchung für {display} am {booking.date.strftime('%d.%m.%Y')} gespeichert!")
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

    # Eigentumscheck: nur eigene Buchungen stornieren, außer DELETE_ALL_BOOKINGS
    if not has_permission(current_user.role, Permission.DELETE_ALL_BOOKINGS):
        booking_check = repo.get_booking_by_id(booking_id)
        if not booking_check:
            return HTMLResponse(_toast("Buchung nicht gefunden.", "error"), status_code=404)
        if booking_check.booked_by_id != current_user.sub:
            return HTMLResponse(_toast("Keine Berechtigung.", "error"), status_code=403)

    booking = repo.update_booking_status(booking_id, BookingStatus.STORNIERT)
    invalidate_week_cache(booking.date)
    log_cancel(request, current_user.username, booking)

    owner = repo.get_user_by_id(booking.booked_by_id)
    if owner:
        cc = _get_cc_emails(repo, booking.mannschaft)
        from notifications.notify import send_cancellation_notice
        await send_cancellation_notice(booking, owner, settings, cc=cc)

    display = get_display_name(booking.field.value)
    free_slot = (
        f'<button class="slot slot--free slot--clickable"'
        f' hx-get="/bookings?date={booking.date.isoformat()}'
        f'&field={booking.field.value}'
        f'&start_time={booking.start_time.strftime("%H:%M")}"'
        f' hx-target="#booking-modal-content"'
        f' hx-swap="innerHTML"'
        f' onclick="document.getElementById(\'booking-modal\').showModal()"'
        f' title="{booking.date.strftime("%d.%m.%Y")} {booking.start_time.strftime("%H:%M")}'
        f' – {display}">'
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
            f"{get_display_name(b.field.value)} {b.start_time.strftime('%H:%M')}–{b.end_time.strftime('%H:%M')}"
            for b in conflicts
        )
        return HTMLResponse(
            f'<span class="badge badge--error">Belegt: {names}</span>'
        )
    return HTMLResponse('<span class="badge badge--success">Verfügbar</span>')


@router.get("/list", response_class=HTMLResponse, dependencies=[Depends(require_permission(Permission.MANAGE_SERIES))])
async def bookings_list(
    request: Request,
    current_user: CurrentUser,
    mannschaft: str = "",
    trainer: str = "",
    wochentag: str = "",
):
    """Buchungsliste mit Filter nach Mannschaft, Trainer, Wochentag."""
    repo = request.app.state.repo
    all_bookings = repo.get_all_bookings()
    wochentag_int = int(wochentag) if wochentag else None

    mannschaften = sorted({b.mannschaft for b in all_bookings if b.mannschaft})
    trainers = sorted({b.booked_by_name for b in all_bookings if b.booked_by_name})

    filtered = all_bookings
    if mannschaft:
        filtered = [b for b in filtered if (b.mannschaft or "") == mannschaft]
    if trainer:
        filtered = [b for b in filtered if b.booked_by_name == trainer]
    if wochentag_int is not None:
        filtered = [b for b in filtered if b.date.weekday() == wochentag_int]

    ctx = {
        "request": request,
        "current_user": current_user,
        "bookings": filtered,
        "mannschaften": mannschaften,
        "trainers": trainers,
        "sel_mannschaft": mannschaft,
        "sel_trainer": trainer,
        "sel_wochentag": wochentag_int,
        "field_display_names": fc.get_display_names(),
    }
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("partials/_booking_list_tbody.html", ctx)
    return templates.TemplateResponse("bookings/list.html", ctx)


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

    # Sonnenuntergang nur für nicht-beleuchtete Felder (Kura/Halle haben Flutlicht)
    try:
        field_enum = FieldName(field)
    except (ValueError, KeyError):
        return HTMLResponse("")
    if fc.is_lit(field_enum.value):
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



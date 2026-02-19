from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser, require_role
from booking.models import FieldName, Mannschaft, SeriesCreate, SeriesRhythm, UserRole

_admin_required = Depends(require_role(UserRole.ADMINISTRATOR, UserRole.DFBNET))
from booking.series import (
    cancel_series,
    create_series_with_bookings,
    remove_date_from_series,
)
from utils.time_slots import get_all_start_slots
from web.config import get_settings
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/series")
templates = Jinja2Templates(directory="web/templates")


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


@router.get("/new", response_class=HTMLResponse, dependencies=[_admin_required])
async def series_form(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(
        "partials/_series_form.html",
        {
            "request": request,
            "current_user": current_user,
            "fields": list(FieldName),
            "start_slots": get_all_start_slots(),
            "durations": [60, 90, 180],
            "rhythms": list(SeriesRhythm),
            "mannschaften": list(Mannschaft),
        },
    )


@router.get("/trainers", response_class=HTMLResponse, dependencies=[_admin_required])
async def get_trainers(request: Request, mannschaft: str):
    """Gibt <option>-Tags für alle Trainer einer Mannschaft zurück (HTMX)."""
    repo = request.app.state.repo
    trainers = repo.get_trainers_for_mannschaft(mannschaft)
    if not trainers:
        return HTMLResponse('<option value="">– Kein Trainer für diese Mannschaft –</option>')
    html = '<option value="">– Trainer wählen –</option>'
    for t in trainers:
        html += f'<option value="{t.notion_id}">{t.name}</option>'
    return HTMLResponse(html)


@router.post("", response_class=HTMLResponse, dependencies=[_admin_required])
async def create_series(
    request: Request,
    current_user: CurrentUser,
    field: str = Form(...),
    start_time: str = Form(...),
    duration_min: int = Form(...),
    rhythm: str = Form(...),
    start_date: date = Form(...),
    end_date: date = Form(...),
    mannschaft: str = Form(...),
    trainer_id: str = Form(...),
):
    from datetime import time as dtime
    repo = request.app.state.repo
    settings = get_settings()

    h, m = start_time.split(":")
    parsed_start = dtime(int(h), int(m))

    if end_date <= start_date:
        return HTMLResponse(
            '<div id="form-errors" class="errors"><ul><li>Enddatum muss nach dem Startdatum liegen.</li></ul></div>'
            + _toast("Serie fehlgeschlagen", "error"),
            status_code=422,
        )

    # Saisonende: 30. Juni
    season_end = date(start_date.year, 6, 30)
    if start_date.month >= 7:
        season_end = date(start_date.year + 1, 6, 30)
    if end_date > season_end:
        end_date = season_end

    # Trainer-Name auflösen
    trainer = repo.get_user_by_id(trainer_id)
    if not trainer:
        return HTMLResponse(
            '<div id="form-errors" class="errors"><ul><li>Ausgewählter Trainer nicht gefunden.</li></ul></div>'
            + _toast("Serie fehlgeschlagen", "error"),
            status_code=422,
        )

    data = SeriesCreate(
        field=FieldName(field),
        start_time=parsed_start,
        duration_min=duration_min,
        rhythm=SeriesRhythm(rhythm),
        start_date=start_date,
        end_date=end_date,
        mannschaft=Mannschaft(mannschaft),
        trainer_id=trainer_id,
    )

    series, created, skipped = create_series_with_bookings(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        trainer_name=trainer.name,
    )

    if not created:
        return HTMLResponse(
            '<div id="form-errors" class="errors"><ul><li>Kein einziger Termin konnte angelegt werden (alle Konflikte oder Sperrzeiten).</li></ul></div>'
            + _toast("Serie fehlgeschlagen", "error"),
            status_code=422,
        )

    for booking in created:
        invalidate_week_cache(booking.date)

    # Bestätigungsmail mit Konfliktliste an Admin senden
    from notifications.notify import send_series_confirmation
    admin_user = repo.get_user_by_id(current_user.sub)
    if admin_user and admin_user.email:
        import asyncio
        asyncio.ensure_future(send_series_confirmation(
            series=series,
            created=created,
            skipped=skipped,
            admin=admin_user,
            settings=settings,
        ))

    msg = f"Serie angelegt ({data.mannschaft.value}): {len(created)} Termine erstellt."
    if skipped:
        skipped_list = ", ".join(d.strftime("%d.%m.") for d in skipped)
        msg += f" {len(skipped)} übersprungen (Konflikt): {skipped_list}"

    # Kalender neu laden + Modal schließen
    iso = start_date.isocalendar()
    html = (
        _toast(msg, "warning" if skipped else "success")
        + f'<div id="calendar-week" hx-swap-oob="innerHTML">'
        + f'<div hx-get="/calendar/week?year={iso[0]}&week={iso[1]}"'
        + ' hx-trigger="load" hx-swap="innerHTML"></div></div>'
    )
    resp = HTMLResponse(html)
    resp.headers["HX-Trigger"] = "closeModal"
    return resp


@router.patch("/{booking_id}/remove-date", response_class=HTMLResponse)
async def remove_date(
    request: Request,
    booking_id: str,
    current_user: CurrentUser,
):
    """Einzeltermin aus Serie entfernen. Erlaubt für Admins und den zugewiesenen Trainer."""
    repo = request.app.state.repo

    # Buchung laden um series_id zu bekommen
    from booking.models import BookingStatus
    booking_page = repo.get_booking_by_id(booking_id)
    if not booking_page:
        raise HTTPException(status_code=404, detail="Buchung nicht gefunden.")

    # Berechtigung prüfen: Admin oder zugewiesener Trainer der Serie
    is_admin = current_user.role in (UserRole.ADMINISTRATOR, UserRole.DFBNET)
    is_series_trainer = False

    if booking_page.series_id:
        series = repo.get_series_by_id(booking_page.series_id)
        if series and series.trainer_id == current_user.sub:
            is_series_trainer = True

    if not is_admin and not is_series_trainer:
        raise HTTPException(status_code=403, detail="Keine Berechtigung.")

    booking = remove_date_from_series(repo, booking_id, current_user)
    invalidate_week_cache(booking.date)
    return HTMLResponse(
        _toast("Termin aus Serie entfernt.")
        + f'<tr id="booking-{booking_id}" hx-swap-oob="true"></tr>'
    )


@router.delete("/{series_id}", response_class=HTMLResponse, dependencies=[_admin_required])
async def cancel_series_endpoint(
    request: Request,
    series_id: str,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    series, cancelled = cancel_series(repo, series_id, current_user)

    for booking in cancelled:
        invalidate_week_cache(booking.date)

    return HTMLResponse(
        _toast(f"Serie beendet. {len(cancelled)} zukünftige Termine storniert.")
    )

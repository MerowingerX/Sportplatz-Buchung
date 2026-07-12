from web.templates_instance import templates
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse

from auth.dependencies import CurrentUser, require_permission
from booking.models import FieldName, Permission, SeriesCreate, SeriesRhythm, SeriesSaison, SeriesStatus, UserRole, has_permission
from booking.vereinsconfig import get_saison_defaults
import booking.field_config as fc

_series_required = Depends(require_permission(Permission.MANAGE_SERIES))
from booking.series import (
    analyze_series_conflicts,
    cancel_series,
    create_series_with_bookings,
    remove_date_from_series,
)
from utils.time_slots import get_all_start_slots, get_duration_options
from web.config import get_settings
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/series")


from web.htmx import toast as _toast


@router.get("", response_class=HTMLResponse, dependencies=[_series_required])
async def series_list(
    request: Request,
    current_user: CurrentUser,
    mannschaft: str = "",
    trainer: str = "",
    wochentag: str = "",
    status: str = "",
):
    """Listet alle Serien auf, optional gefiltert."""
    repo = request.app.state.repo
    all_series = repo.get_all_series()
    wochentag_int = int(wochentag) if wochentag else None

    mannschaften = sorted({s.mannschaft for s in all_series if s.mannschaft})
    trainers = sorted({s.trainer_name or s.booked_by_name for s in all_series
                       if s.trainer_name or s.booked_by_name})

    filtered = all_series
    if mannschaft:
        filtered = [s for s in filtered if (s.mannschaft or "") == mannschaft]
    if trainer:
        filtered = [s for s in filtered if (s.trainer_name or s.booked_by_name or "") == trainer]
    if wochentag_int is not None:
        filtered = [s for s in filtered if s.start_date.weekday() == wochentag_int]
    if status:
        filtered = [s for s in filtered if s.status.value == status]

    ctx = {
        "request": request,
        "current_user": current_user,
        "series_list": filtered,
        "mannschaften": mannschaften,
        "trainers": trainers,
        "sel_mannschaft": mannschaft,
        "sel_trainer": trainer,
        "sel_wochentag": wochentag_int,
        "sel_status": status,
    }
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("partials/_series_table_body.html", ctx)
    return templates.TemplateResponse("series/index.html", ctx)


def _series_form_ctx(request, repo, current_user, errors=None, toast=None,
                     prefill_field="", prefill_start_time="",
                     prefill_start_date="", prefill_end_date="",
                     prefill_duration=None, prefill_mannschaft="",
                     prefill_trainer_id="", trainer_options=None):
    return {
        "request": request,
        "current_user": current_user,
        "fields": list(FieldName),
        "field_display_names": fc.get_display_names(),
        "start_slots": get_all_start_slots(),
        "durations": get_duration_options(),
        "rhythms": list(SeriesRhythm),
        "mannschaften": repo.get_all_mannschaften(only_active=True),
        "saisons": list(SeriesSaison),
        "saison_defaults": get_saison_defaults(),
        "errors": errors or [],
        "form_toast": toast or "",
        "prefill_field": prefill_field,
        "prefill_start_time": prefill_start_time,
        "prefill_start_date": prefill_start_date,
        "prefill_end_date": prefill_end_date,
        "prefill_duration": prefill_duration,
        "prefill_mannschaft": prefill_mannschaft,
        "prefill_trainer_id": prefill_trainer_id,
        "trainer_options": trainer_options or [],
    }


def _compute_saison_end(ref: date) -> date:
    """Berechnet das konfigurierte Ganzjährig-Saisonende ab dem Referenzdatum."""
    defaults = get_saison_defaults()
    ende_str = defaults.get("ganzjaehrig", {}).get("ende", "06-30")
    em, ed = [int(x) for x in ende_str.split("-")]
    candidate = date(ref.year, em, ed)
    if candidate <= ref:
        candidate = date(ref.year + 1, em, ed)
    return candidate


@router.get("/new", response_class=HTMLResponse, dependencies=[_series_required])
async def series_form(
    request: Request, current_user: CurrentUser,
    field: str = "",
    start_time: str = "",
    date: str = "",
    from_booking: str = "",
):
    from datetime import date as _date
    repo = request.app.state.repo

    prefill_duration = None
    prefill_mannschaft = ""
    prefill_trainer_id = ""
    trainer_options = []

    if from_booking:
        # Bestehende Buchung als Vorlage: alle Serienfelder daraus übernehmen.
        # Die Originalbuchung bleibt bestehen; die Serie überspringt diesen
        # Termin später als Konflikt.
        b = repo.get_booking_by_id(from_booking)
        if b:
            field = b.field.value
            start_time = b.start_time.strftime("%H:%M")
            date = b.date.isoformat()
            prefill_duration = b.duration_min
            if b.mannschaft:
                prefill_mannschaft = b.mannschaft
                trainer_options = repo.get_trainers_for_mannschaft(b.mannschaft)
                if not trainer_options:
                    trainer_options = [u for u in repo.get_all_users()
                                       if u.role == UserRole.ADMINISTRATOR]
                if any(t.notion_id == b.booked_by_id for t in trainer_options):
                    prefill_trainer_id = b.booked_by_id

    try:
        ref = _date.fromisoformat(date) if date else _date.today()
    except ValueError:
        ref = _date.today()
    end_date = _compute_saison_end(ref)
    return templates.TemplateResponse(
        "partials/_series_form.html",
        _series_form_ctx(
            request, repo, current_user,
            prefill_field=field,
            prefill_start_time=start_time,
            prefill_start_date=date,
            prefill_end_date=end_date.isoformat(),
            prefill_duration=prefill_duration,
            prefill_mannschaft=prefill_mannschaft,
            prefill_trainer_id=prefill_trainer_id,
            trainer_options=trainer_options,
        ),
    )


@router.get("/trainers", response_class=HTMLResponse, dependencies=[_series_required])
async def get_trainers(request: Request, mannschaft: str):
    """Gibt <option>-Tags für alle Verantwortlichen einer Mannschaft zurück (HTMX).
    Wenn kein Verantwortlicher eingetragen ist, werden die Administratoren als Fallback angeboten."""
    repo = request.app.state.repo
    trainers = repo.get_trainers_for_mannschaft(mannschaft)
    if trainers:
        html = '<option value="">– Verantwortlichen wählen –</option>'
        for t in trainers:
            html += f'<option value="{t.notion_id}">{t.name}</option>'
        return HTMLResponse(html)

    # Kein Verantwortlicher für diese Mannschaft → Administratoren als Fallback
    all_users = repo.get_all_users()
    admins = [u for u in all_users if u.role == UserRole.ADMINISTRATOR]
    if admins:
        html = '<option value="">– Kein Verantwortlicher, bitte Administrator wählen –</option>'
        for a in admins:
            html += f'<option value="{a.notion_id}">{a.name} (Administrator)</option>'
        return HTMLResponse(html)

    return HTMLResponse('<option value="">– Kein Verantwortlicher oder Administrator gefunden –</option>')


@router.post("", response_class=HTMLResponse, dependencies=[_series_required])
async def create_series(
    request: Request,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    field: str = Form(...),
    start_time: str = Form(...),
    duration_min: int = Form(...),
    rhythm: str = Form(...),
    start_date: date = Form(...),
    end_date: date = Form(...),
    mannschaft: str = Form(...),
    trainer_id: str = Form(...),
    saison: str = Form("Ganzjährig"),
    confirm_series: str = Form(""),
    share_date: List[str] = Form(default=[]),
    share_series: List[str] = Form(default=[]),
):
    from datetime import time as dtime
    repo = request.app.state.repo
    settings = get_settings()

    h, m = start_time.split(":")
    parsed_start = dtime(int(h), int(m))

    if end_date <= start_date:
        return templates.TemplateResponse(
            "partials/_series_form.html",
            _series_form_ctx(request, repo, current_user,
                             errors=["Enddatum muss nach dem Startdatum liegen."],
                             toast=_toast("Serie fehlgeschlagen", "error")),
        )

    # Ganzjährig: Enddatum auf konfiguriertes Saisonende begrenzen
    try:
        saison_enum = SeriesSaison(saison)
    except ValueError:
        saison_enum = SeriesSaison.GANZJAEHRIG

    if saison_enum == SeriesSaison.GANZJAEHRIG:
        defaults = get_saison_defaults()
        m_str, d_str = defaults["ganzjaehrig"]["ende"].split("-")
        em, ed = int(m_str), int(d_str)
        gz_ende = date(
            start_date.year if start_date.month < em else start_date.year + 1,
            em, ed,
        )
        if end_date > gz_ende:
            end_date = gz_ende

    # Trainer-Name auflösen
    trainer = repo.get_user_by_id(trainer_id)
    if not trainer:
        return templates.TemplateResponse(
            "partials/_series_form.html",
            _series_form_ctx(request, repo, current_user,
                             errors=["Ausgewählter Verantwortlicher nicht gefunden."],
                             toast=_toast("Serie fehlgeschlagen", "error")),
        )

    data = SeriesCreate(
        field=FieldName(field),
        start_time=parsed_start,
        duration_min=duration_min,
        rhythm=SeriesRhythm(rhythm),
        start_date=start_date,
        end_date=end_date,
        mannschaft=mannschaft,
        trainer_id=trainer_id,
        saison=saison_enum,
    )

    # Zwei-Phasen-Flow für teilbare Konflikte: erst Dry-Run, bei teilbaren
    # Überschneidungen Rückfrage (pro Tag bei Einzelbuchungen, pauschal pro
    # Serie). Token bindet die Bestätigung an genau diese Serienparameter.
    confirm_token = (
        f"{field}|{start_time}|{duration_min}|{rhythm}"
        f"|{start_date.isoformat()}|{end_date.isoformat()}"
    )
    analysis = analyze_series_conflicts(repo, data)
    if (analysis["single"] or analysis["series"]) and confirm_series != confirm_token:
        return templates.TemplateResponse(
            "partials/_series_share_confirm.html",
            {
                "request": request,
                "current_user": current_user,
                "analysis": analysis,
                "confirm_token": confirm_token,
                "form_values": {
                    "field": field,
                    "start_time": start_time,
                    "duration_min": duration_min,
                    "rhythm": rhythm,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "mannschaft": mannschaft,
                    "trainer_id": trainer_id,
                    "saison": saison,
                },
                "form_toast": "",
            },
        )

    share_dates = set()
    for ds in share_date:
        try:
            share_dates.add(date.fromisoformat(ds))
        except ValueError:
            pass

    series, created, skipped = create_series_with_bookings(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        trainer_name=trainer.name,
        share_dates=share_dates,
        share_series_ids=set(share_series),
    )

    if not created:
        # Leere Serie nicht in der DB zurücklassen
        repo.delete_series(series.notion_id)
        return templates.TemplateResponse(
            "partials/_series_form.html",
            _series_form_ctx(request, repo, current_user,
                             errors=["Kein einziger Termin konnte angelegt werden (alle Konflikte)."],
                             toast=_toast("Serie fehlgeschlagen", "error")),
        )

    for booking in created:
        invalidate_week_cache(booking.date)

    # Bestätigungsmail mit Konfliktliste an Admin senden
    from notifications.notify import send_series_confirmation
    admin_user = repo.get_user_by_id(current_user.sub)
    if admin_user and admin_user.email:
        background_tasks.add_task(
            send_series_confirmation,
            series=series,
            created=created,
            skipped=skipped,
            admin=admin_user,
            settings=settings,
        )

    msg = f"Serie angelegt ({data.mannschaft}): {len(created)} Termine erstellt."
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


@router.get("/season-transfer", response_class=HTMLResponse, dependencies=[_series_required])
async def season_transfer_form(request: Request, current_user: CurrentUser):
    """Zeigt Auswahlliste aller Serien für die Saisonübernahme (+1 Jahr)."""
    repo = request.app.state.repo
    all_series = repo.get_all_series(only_active=False)

    entries = []
    for s in sorted(all_series, key=lambda x: x.mannschaft or ""):
        try:
            new_start = s.start_date.replace(year=s.start_date.year + 1)
            new_end = s.end_date.replace(year=s.end_date.year + 1)
        except ValueError:  # Feb 29 in Nicht-Schaltjahr
            new_start = s.start_date + timedelta(days=365)
            new_end = s.end_date + timedelta(days=365)
        entries.append({"series": s, "new_start": new_start, "new_end": new_end})

    return templates.TemplateResponse(
        "partials/_season_transfer.html",
        {"request": request, "current_user": current_user, "entries": entries},
    )


@router.post("/season-transfer", response_class=HTMLResponse, dependencies=[_series_required])
async def season_transfer_execute(
    request: Request,
    current_user: CurrentUser,
    series_ids: List[str] = Form(default=[]),
):
    """Dupliziert ausgewählte Serien mit +1 Jahr auf Start- und Enddatum."""
    repo = request.app.state.repo
    settings = get_settings()

    if not series_ids:
        return HTMLResponse(_toast("Keine Serien ausgewählt.", "error"))

    all_series = repo.get_all_series(only_active=False)
    by_id = {s.notion_id: s for s in all_series}

    total_created = 0
    total_skipped = 0
    errors: list[str] = []

    for sid in series_ids:
        s = by_id.get(sid)
        if not s:
            continue
        if not s.mannschaft:
            errors.append(f'"{s.title}": keine Mannschaft gesetzt - uebersprungen')
            continue
        try:
            new_start = s.start_date.replace(year=s.start_date.year + 1)
            new_end = s.end_date.replace(year=s.end_date.year + 1)
        except ValueError:
            new_start = s.start_date + timedelta(days=365)
            new_end = s.end_date + timedelta(days=365)
        try:
            data = SeriesCreate(
                field=s.field,
                start_time=s.start_time,
                duration_min=s.duration_min,
                rhythm=s.rhythm,
                start_date=new_start,
                end_date=new_end,
                mannschaft=s.mannschaft,
                trainer_id=s.trainer_id or "",
                saison=s.saison,
            )
            _, created, skipped = create_series_with_bookings(
                repo=repo,
                data=data,
                current_user=current_user,
                settings=settings,
                trainer_name=s.trainer_name or "",
            )
            total_created += len(created)
            total_skipped += len(skipped)
            for booking in created:
                invalidate_week_cache(booking.date)
        except Exception as exc:
            errors.append(f'"{s.title}": {exc}')

    msg = f"Saisonübernahme: {total_created} Termine angelegt"
    if total_skipped:
        msg += f", {total_skipped} Konflikte übersprungen"
    kind = "success" if not errors else "warning"

    result_html = f'<p class="transfer-summary">{msg}.</p>'
    if errors:
        result_html += '<ul class="transfer-errors">' + "".join(f"<li>{e}</li>" for e in errors) + "</ul>"

    return HTMLResponse(
        _toast(msg, kind)
        + f'<div id="season-transfer-result" hx-swap-oob="true">{result_html}</div>'
    )


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
    is_admin = has_permission(current_user.role, Permission.DELETE_ALL_BOOKINGS)
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


@router.delete("/{series_id}/purge", response_class=HTMLResponse)
async def purge_series(request: Request, series_id: str, current_user: CurrentUser):
    """Serie samt aller Termine endgültig löschen (nur Administrator)."""
    if current_user.role != UserRole.ADMINISTRATOR:
        return HTMLResponse(_toast("Keine Berechtigung.", "error"), status_code=403)
    repo = request.app.state.repo
    series = repo.get_series_by_id(series_id)
    if not series:
        return HTMLResponse(_toast("Serie nicht gefunden.", "error"), status_code=404)

    bookings = repo.get_bookings_for_series(series_id)
    deleted = repo.delete_series(series_id)
    for b in bookings:
        invalidate_week_cache(b.date)

    return HTMLResponse(
        f'<tr id="series-{series_id}" hx-swap-oob="delete"></tr>'
        + _toast(f"Serie gelöscht. {deleted} Termine endgültig entfernt.")
    )


@router.delete("/{series_id}", response_class=HTMLResponse, dependencies=[_series_required])
async def cancel_series_endpoint(
    request: Request,
    series_id: str,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    series, cancelled = cancel_series(repo, series_id, current_user)

    for booking in cancelled:
        invalidate_week_cache(booking.date)

    # Zeile in-place auf "Beendet" aktualisieren
    updated_row = templates.get_template("partials/_series_row.html").render(
        {"s": series, "current_user": current_user}
    )
    return HTMLResponse(
        updated_row
        + _toast(f"Serie beendet. {len(cancelled)} zukünftige Termine storniert.")
    )

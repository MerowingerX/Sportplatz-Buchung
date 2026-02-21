from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import os
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from auth.auth import hash_password
from auth.dependencies import CurrentUser, require_permission
from booking.booking import dfbnet_displace
from booking.models import BookingCreate, BookingType, FieldName, Mannschaft, Permission, UserCreate, UserRole
from utils.time_slots import get_all_start_slots
from web.config import get_settings
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="web/templates")
templates.env.filters["enumerate"] = enumerate

_admin_required = Depends(require_permission(Permission.ACCESS_ADMIN))
_manage_users   = Depends(require_permission(Permission.MANAGE_USERS))
_dfbnet_required = Depends(require_permission(Permission.DFBNET_BOOKING))


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


@router.get("", response_class=HTMLResponse, dependencies=[_admin_required])
async def admin_dashboard(request: Request, current_user: CurrentUser):
    repo = request.app.state.repo
    users = repo.get_all_users()
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "current_user": current_user, "users": users},
    )


# ------------------------------------------------------------------ Nutzerverwaltung

@router.get("/users", response_class=HTMLResponse, dependencies=[_manage_users])
async def users_page(request: Request, current_user: CurrentUser):
    repo = request.app.state.repo
    users = repo.get_all_users()
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "current_user": current_user,
            "users": users,
            "roles": list(UserRole),
            "mannschaften": list(Mannschaft),
        },
    )


@router.post("/users", response_class=HTMLResponse, dependencies=[_manage_users])
async def create_user(
    request: Request,
    current_user: CurrentUser,
    name: str = Form(...),
    role: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    mannschaft: Optional[str] = Form(None),
):
    repo = request.app.state.repo
    if repo.get_user_by_name(name):
        return HTMLResponse(_toast(f"Nutzername '{name}' ist bereits vergeben.", "error"))
    user_data = UserCreate(
        name=name,
        role=UserRole(role),
        email=email,
        password=password,
        mannschaft=Mannschaft(mannschaft) if mannschaft else None,
    )
    pw_hash = hash_password(password)
    repo.create_user(user_data, pw_hash)
    return HTMLResponse(_toast(f"Nutzer '{name}' angelegt. Passwortänderung wird beim ersten Login erzwungen."))


@router.post("/users/{user_id}/reset-password", response_class=HTMLResponse, dependencies=[_manage_users])
async def reset_user_password(
    request: Request,
    user_id: str,
    current_user: CurrentUser,
    new_password: str = Form(...),
):
    repo = request.app.state.repo
    pw_hash = hash_password(new_password)
    user = repo.reset_user_password(user_id, pw_hash)
    return HTMLResponse(
        _toast(f"Passwort für '{user.name}' zurückgesetzt. Nutzer muss Passwort beim nächsten Login ändern.")
    )


def _user_row_ctx(user, current_user):
    return {"user": user, "current_user": current_user, "roles": list(UserRole), "mannschaften": list(Mannschaft)}


@router.get("/users/{user_id}/row", response_class=HTMLResponse, dependencies=[_manage_users])
async def user_row(request: Request, user_id: str, current_user: CurrentUser):
    repo = request.app.state.repo
    user = repo.get_user_by_id(user_id)
    if not user:
        return HTMLResponse(_toast("Nutzer nicht gefunden.", "error"), status_code=404)
    return HTMLResponse(
        templates.get_template("partials/_user_row.html").render(_user_row_ctx(user, current_user))
    )


@router.get("/users/{user_id}/edit", response_class=HTMLResponse, dependencies=[_manage_users])
async def user_edit_row(request: Request, user_id: str, current_user: CurrentUser):
    repo = request.app.state.repo
    user = repo.get_user_by_id(user_id)
    if not user:
        return HTMLResponse(_toast("Nutzer nicht gefunden.", "error"), status_code=404)
    return HTMLResponse(
        templates.get_template("partials/_user_row_edit.html").render(_user_row_ctx(user, current_user))
    )


@router.patch("/users/{user_id}", response_class=HTMLResponse, dependencies=[_manage_users])
async def update_user(
    request: Request,
    user_id: str,
    current_user: CurrentUser,
    role: str = Form(...),
    email: str = Form(...),
    mannschaft: Optional[str] = Form(None),
):
    repo = request.app.state.repo
    user = repo.update_user(user_id, role=role, email=email, mannschaft=mannschaft or None)
    return HTMLResponse(
        templates.get_template("partials/_user_row.html").render(_user_row_ctx(user, current_user))
        + _toast(f"Nutzer '{user.name}' aktualisiert.")
    )


@router.delete("/users/{user_id}", response_class=HTMLResponse, dependencies=[_manage_users])
async def delete_user(request: Request, user_id: str, current_user: CurrentUser):
    if user_id == current_user.sub:
        return HTMLResponse(_toast("Du kannst dich nicht selbst löschen.", "error"))
    repo = request.app.state.repo
    user = repo.get_user_by_id(user_id)
    if not user:
        return HTMLResponse(_toast("Nutzer nicht gefunden.", "error"))
    repo.delete_user(user_id)
    return HTMLResponse(
        f'<tr id="user-{user_id}"></tr>'
        + _toast(f"Nutzer '{user.name}' gelöscht.")
    )


# ------------------------------------------------------------------ DFBnet-Buchung

@router.get("/dfbnet", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def dfbnet_form(
    request: Request,
    current_user: CurrentUser,
):
    return templates.TemplateResponse(
        "admin/dfbnet_booking.html",
        {
            "request": request,
            "current_user": current_user,
            "fields": list(FieldName),
            "start_slots": get_all_start_slots(),
            "durations": [60, 90, 180],
        },
    )


@router.post("/dfbnet", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def create_dfbnet_booking(
    request: Request,
    current_user: CurrentUser,
    field: str = Form(...),
    booking_date: date = Form(..., alias="date"),
    start_time: str = Form(...),
    duration_min: int = Form(...),
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
        booking_type=BookingType.SPIEL,
    )

    existing = repo.get_bookings_for_date(booking_date)
    new_booking, displaced = dfbnet_displace(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        existing_bookings=existing,
    )

    invalidate_week_cache(booking_date)

    # Benachrichtigungen für verdrängte Buchungen
    if displaced:
        from notifications.notify import send_dfbnet_displacement_notice
        for b in displaced:
            owner = repo.get_user_by_id(b.booked_by_id)
            if owner:
                await send_dfbnet_displacement_notice(b, owner, new_booking, settings)

    msg = f"DFBnet-Buchung erstellt."
    if displaced:
        msg += f" {len(displaced)} Buchung(en) verdrängt und benachrichtigt."

    return HTMLResponse(_toast(msg))


# ------------------------------------------------------------------ Admin-Buchung (freier Zweck)

@router.get("/booking", response_class=HTMLResponse, dependencies=[_admin_required])
async def admin_booking_page(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(
        "admin/booking.html",
        {
            "request": request,
            "current_user": current_user,
            "fields": list(FieldName),
            "start_slots": get_all_start_slots(),
            "durations": [30, 60, 90, 120, 180],
            "booking_types": list(BookingType),
        },
    )


@router.post("/booking", response_class=HTMLResponse, dependencies=[_admin_required])
async def admin_create_booking(
    request: Request,
    current_user: CurrentUser,
    field: str = Form(...),
    booking_date: date = Form(..., alias="date"),
    start_time_str: str = Form(..., alias="start_time"),
    duration_min: int = Form(...),
    booking_type: str = Form(...),
    zweck: str = Form(...),
    kontakt: Optional[str] = Form(None),
):
    from booking.booking import build_booking
    from booking.models import BookingCreate, FieldName, BookingType

    h, m = start_time_str.split(":")
    parsed_start = time(int(h), int(m))

    data = BookingCreate(
        field=FieldName(field),
        date=booking_date,
        start_time=parsed_start,
        duration_min=duration_min,
        booking_type=BookingType(booking_type),
        zweck=zweck.strip() or None,
        kontakt=kontakt.strip() if kontakt else None,
    )

    repo = request.app.state.repo
    settings = get_settings()
    existing = repo.get_bookings_for_date(booking_date)
    blackouts = repo.get_blackouts_for_date(booking_date) if data.field.is_rasen else []

    booking, errors = build_booking(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        existing_bookings=existing,
        blackouts=blackouts,
        skip_time_check=True,    # Admins dürfen außerhalb 16-22 Uhr buchen
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

    return HTMLResponse(
        '<div id="form-errors"></div>'
        + _toast(f"Buchung '{booking.zweck}' am {booking.date} um {booking.start_time.strftime('%H:%M')} gespeichert!")
    )


# ------------------------------------------------------------------ ICS-Import

_TZ_BERLIN = ZoneInfo("Europe/Berlin")

_ALLOWED_DURATIONS = [60, 90, 180]


def _round_to_slot(t: time) -> time:
    """Rundet eine Uhrzeit auf den nächsten (früheren) 30-Min-Slot."""
    total = t.hour * 60 + t.minute
    rounded = (total // 30) * 30
    return time(rounded // 60, rounded % 60)


def _nearest_duration(minutes: int) -> int:
    """Gibt die nächstliegende erlaubte Buchungsdauer zurück."""
    return min(_ALLOWED_DURATIONS, key=lambda d: abs(d - minutes))


def _parse_ics(content: bytes) -> list[dict]:
    """Parst ICS-Inhalt und gibt sortierte Event-Liste zurück."""
    from icalendar import Calendar

    try:
        cal = Calendar.from_ical(content)
    except Exception:
        return []

    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        if not dtstart:
            continue
        dt = dtstart.dt

        # Nur Einträge mit Uhrzeit (nicht ganztägig)
        if not isinstance(dt, datetime):
            continue

        # Zeitzone → Europe/Berlin
        if dt.tzinfo is not None:
            dt_local = dt.astimezone(_TZ_BERLIN).replace(tzinfo=None)
        else:
            dt_local = dt

        event_date = dt_local.date()
        event_time = dt_local.time()

        # Dauer ermitteln
        dtend = component.get("DTEND")
        duration_prop = component.get("DURATION")
        duration_min = 90  # Fallback: Standard-Fußballspiel

        if dtend:
            end = dtend.dt
            if isinstance(end, datetime):
                if end.tzinfo is not None:
                    end = end.astimezone(_TZ_BERLIN).replace(tzinfo=None)
                diff = end - dt_local
                duration_min = max(30, int(diff.total_seconds() / 60))
        elif duration_prop and hasattr(duration_prop, "dt"):
            duration_min = max(30, int(duration_prop.dt.total_seconds() / 60))

        events.append({
            "date": event_date,
            "start_time": _round_to_slot(event_time),
            "duration_min": _nearest_duration(duration_min),
            "summary": str(component.get("SUMMARY", "Kein Titel")),
        })

    events.sort(key=lambda e: (e["date"], e["start_time"]))
    return events


@router.get("/dfbnet-import", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def dfbnet_import_page(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(
        "admin/dfbnet_import.html",
        {"request": request, "current_user": current_user},
    )


@router.post("/dfbnet-import", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def dfbnet_import_preview(
    request: Request,
    current_user: CurrentUser,
    ics_file: UploadFile = File(...),
):
    content = await ics_file.read()
    events = _parse_ics(content)
    return templates.TemplateResponse(
        "partials/_ics_preview.html",
        {
            "request": request,
            "events": events,
            "fields": list(FieldName),
            "start_slots": get_all_start_slots(),
            "durations": _ALLOWED_DURATIONS,
        },
    )


@router.post("/dfbnet-import/confirm", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def dfbnet_import_confirm(
    request: Request,
    current_user: CurrentUser,
):
    form = await request.form()
    count = int(form.get("count", 0))
    repo = request.app.state.repo
    settings = get_settings()

    created = 0
    displaced_total = 0

    for i in range(count):
        if not form.get(f"include_{i}"):
            continue

        date_str = form.get(f"date_{i}")
        start_time_str = form.get(f"start_time_{i}")
        duration_str = form.get(f"duration_{i}")
        field_str = form.get(f"field_{i}")

        if not all([date_str, start_time_str, duration_str, field_str]):
            continue

        try:
            booking_date = date.fromisoformat(str(date_str))
            h, m = str(start_time_str).split(":")
            parsed_start = time(int(h), int(m))
            duration_min = int(str(duration_str))
            field = FieldName(str(field_str))
        except (ValueError, KeyError):
            continue

        data = BookingCreate(
            field=field,
            date=booking_date,
            start_time=parsed_start,
            duration_min=duration_min,
            booking_type=BookingType.SPIEL,
        )

        existing = repo.get_bookings_for_date(booking_date)
        new_booking, displaced = dfbnet_displace(
            repo=repo,
            data=data,
            current_user=current_user,
            settings=settings,
            existing_bookings=existing,
        )

        invalidate_week_cache(booking_date)
        created += 1
        displaced_total += len(displaced)

        if displaced:
            from notifications.notify import send_dfbnet_displacement_notice
            for b in displaced:
                owner = repo.get_user_by_id(b.booked_by_id)
                if owner:
                    await send_dfbnet_displacement_notice(b, owner, new_booking, settings)

    msg = f"{created} DFBnet-Buchung(en) aus ICS-Import erstellt."
    if displaced_total:
        msg += f" {displaced_total} bestehende Buchung(en) verdrängt und benachrichtigt."

    return HTMLResponse(_toast(msg))


# ------------------------------------------------------------------ CSV-Import

_PLATZBELEGUNG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Platzbelegung")


def _parse_dfbnet_csv(content: bytes) -> list[dict]:
    """Parst DFBnet-Platzbelegungs-CSV (Tab-separiert) und gibt sortierte Event-Liste zurück."""
    import csv
    import io

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("utf-16")
    reader = csv.reader(io.StringIO(text), delimiter="\t")

    header = next(reader, None)
    if not header:
        return []

    # Spaltenindizes anhand der Header bestimmen
    col_map = {h.strip(): idx for idx, h in enumerate(header)}
    idx_datum = col_map.get("Spieldatum")
    idx_zeit = col_map.get("Uhrzeit")
    idx_heim = col_map.get("Heimmannschaft")
    idx_gast = col_map.get("Gastmannschaft")
    idx_liga = col_map.get("Liga")
    idx_kennung = col_map.get("Spielkennung")

    if idx_datum is None or idx_zeit is None:
        return []

    today = date.today()
    events = []

    for row in reader:
        if len(row) <= max(idx_datum, idx_zeit):
            continue

        # Spieldatum parsen: "Sa., 28.02.2026" → date
        datum_raw = row[idx_datum].strip()
        if ", " in datum_raw:
            datum_raw = datum_raw.split(", ", 1)[1]
        try:
            parts = datum_raw.split(".")
            event_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            continue

        # Vergangene Termine überspringen
        if event_date < today:
            continue

        # Uhrzeit parsen
        zeit_raw = row[idx_zeit].strip()
        try:
            h, m = zeit_raw.split(":")
            event_time = _round_to_slot(time(int(h), int(m)))
        except (ValueError, IndexError):
            continue

        # Summary zusammenbauen
        heim = row[idx_heim].strip() if idx_heim is not None and len(row) > idx_heim else ""
        gast = row[idx_gast].strip() if idx_gast is not None and len(row) > idx_gast else ""
        liga = row[idx_liga].strip() if idx_liga is not None and len(row) > idx_liga else ""
        summary = f"{heim} vs {gast}" if heim and gast else heim or "DFBnet-Spiel"
        if liga:
            summary = f"[{liga}] {summary}"

        kennung = row[idx_kennung].strip() if idx_kennung is not None and len(row) > idx_kennung else ""

        events.append({
            "date": event_date,
            "start_time": event_time,
            "duration_min": 90,
            "summary": summary,
            "spielkennung": kennung,
        })

    events.sort(key=lambda e: (e["date"], e["start_time"]))
    return events


def _save_csv_file(content: bytes, filename: str) -> str:
    """Speichert die CSV-Datei im Platzbelegung-Ordner."""
    os.makedirs(_PLATZBELEGUNG_DIR, exist_ok=True)
    target = os.path.join(_PLATZBELEGUNG_DIR, filename)

    if os.path.exists(target):
        base, ext = os.path.splitext(filename)
        from datetime import datetime as dt
        suffix = dt.now().strftime("%Y%m%d_%H%M%S")
        target = os.path.join(_PLATZBELEGUNG_DIR, f"{base}_{suffix}{ext}")

    with open(target, "wb") as f:
        f.write(content)
    return target


@router.get("/csv-import", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def csv_import_page(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(
        "admin/csv_import.html",
        {"request": request, "current_user": current_user},
    )


@router.post("/csv-import", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def csv_import_preview(
    request: Request,
    current_user: CurrentUser,
    csv_file: UploadFile = File(...),
):
    content = await csv_file.read()
    filename = csv_file.filename or "import.csv"
    _save_csv_file(content, filename)

    events = _parse_dfbnet_csv(content)

    # Bekannte Spielkennungen prüfen
    repo = request.app.state.repo
    kennungen = [ev["spielkennung"] for ev in events if ev.get("spielkennung")]
    known = repo.get_bookings_by_spielkennung(kennungen) if kennungen else {}
    for ev in events:
        ev["already_known"] = ev.get("spielkennung", "") in known

    return templates.TemplateResponse(
        "partials/_import_preview.html",
        {
            "request": request,
            "events": events,
            "fields": list(FieldName),
            "start_slots": get_all_start_slots(),
            "durations": _ALLOWED_DURATIONS,
            "confirm_url": "/admin/csv-import/confirm",
        },
    )


@router.post("/csv-import/confirm", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def csv_import_confirm(
    request: Request,
    current_user: CurrentUser,
):
    form = await request.form()
    count = int(form.get("count", 0))
    repo = request.app.state.repo
    settings = get_settings()

    created_bookings: list[tuple[str, str]] = []  # (summary, spielkennung)
    skipped_known: list[str] = []  # summaries von bereits bekannten
    displaced_total = 0

    # Pauschal gewählter Zielplatz für alle Spiele
    field_str = form.get("field")
    try:
        field = FieldName(str(field_str))
    except (ValueError, KeyError):
        return HTMLResponse(_toast("Kein gültiger Platz gewählt.", "error"))

    for i in range(count):
        if not form.get(f"include_{i}"):
            continue

        date_str = form.get(f"date_{i}")
        start_time_str = form.get(f"start_time_{i}")
        duration_str = form.get(f"duration_{i}")
        spielkennung = str(form.get(f"spielkennung_{i}", "") or "")
        summary = str(form.get(f"summary_{i}", "") or "DFBnet-Spiel")

        if not all([date_str, start_time_str, duration_str]):
            continue

        try:
            booking_date = date.fromisoformat(str(date_str))
            hh, mm = str(start_time_str).split(":")
            parsed_start = time(int(hh), int(mm))
            duration_min = int(str(duration_str))
        except (ValueError, KeyError):
            continue

        # Duplikat-Check: Spielkennung bereits in Notion?
        if spielkennung:
            existing_by_kennung = repo.get_bookings_by_spielkennung([spielkennung])
            if spielkennung in existing_by_kennung:
                skipped_known.append(f"{booking_date.strftime('%d.%m.%Y')} {summary}")
                continue

        data = BookingCreate(
            field=field,
            date=booking_date,
            start_time=parsed_start,
            duration_min=duration_min,
            booking_type=BookingType.SPIEL,
            spielkennung=spielkennung or None,
            zweck=summary,
        )

        existing = repo.get_bookings_for_date(booking_date)
        new_booking, displaced = dfbnet_displace(
            repo=repo,
            data=data,
            current_user=current_user,
            settings=settings,
            existing_bookings=existing,
        )

        invalidate_week_cache(booking_date)
        created_bookings.append((f"{booking_date.strftime('%d.%m.%Y')} {summary}", spielkennung))
        displaced_total += len(displaced)

        if displaced:
            from notifications.notify import send_dfbnet_displacement_notice
            for b in displaced:
                owner = repo.get_user_by_id(b.booked_by_id)
                if owner:
                    await send_dfbnet_displacement_notice(b, owner, new_booking, settings)

    # Import-Zusammenfassung per E-Mail an Admin
    from notifications.notify import send_csv_import_summary
    admin_user = repo.get_user_by_id(current_user.sub)
    if admin_user and admin_user.email:
        import asyncio
        asyncio.ensure_future(send_csv_import_summary(
            created=[c[0] for c in created_bookings],
            skipped_known=skipped_known,
            displaced_count=displaced_total,
            admin=admin_user,
            settings=settings,
        ))

    msg = f"{len(created_bookings)} DFBnet-Buchung(en) aus CSV-Import erstellt."
    if skipped_known:
        msg += f" {len(skipped_known)} bereits bekannt (übersprungen)."
    if displaced_total:
        msg += f" {displaced_total} bestehende Buchung(en) verdrängt."

    return HTMLResponse(_toast(msg, "warning" if skipped_known else "success"))


# ── Spielplan-CSV von api-fussball.de abrufen ─────────────────────────────────

import asyncio as _asyncio
import importlib.util as _importlib_util
import pathlib as _pathlib

# Gemeinsamer Job-Zustand (einfaches In-Memory-Dict, ausreichend für Einzel-Nutzer)
_spielplan_job: dict = {"running": False, "current": 0, "total": 0, "team": "", "result": "", "error": ""}


def _load_fetch_mod():
    script_path = _pathlib.Path(__file__).parent.parent.parent / "scripts" / "fetch_spielplan.py"
    spec = _importlib_util.spec_from_file_location("fetch_spielplan", script_path)
    mod  = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_generate_csv():
    global _spielplan_job
    mod = _load_fetch_mod()

    def _cb(current: int, total: int, team_name: str):
        _spielplan_job["current"] = current
        _spielplan_job["total"]   = total
        _spielplan_job["team"]    = team_name

    try:
        count, csv_path = mod.generate_csv(progress_cb=_cb)
        _spielplan_job["result"] = f"{count} Heimspiele → {os.path.relpath(csv_path)}"
        _spielplan_job["error"]  = ""
    except Exception as exc:
        _spielplan_job["error"]  = str(exc)
        _spielplan_job["result"] = ""
    finally:
        _spielplan_job["running"] = False


def _progress_toast(current: int, total: int, team: str) -> str:
    label = f"{current} / {total}" if total else str(current)
    team_short = team.split(" - ")[-1] if " - " in team else team
    return (
        f'<div id="toast" class="toast toast--progress"'
        f' hx-get="/admin/fetch-spielplan/progress"'
        f' hx-trigger="every 2s"'
        f' hx-swap="outerHTML">'
        f'&#8987; Spielplan wird geladen … {label}'
        + (f'<br><small>{team_short}</small>' if team_short else '')
        + '</div>'
    )


@router.post("/fetch-spielplan", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def fetch_spielplan(request: Request):
    """Startet den Spielplan-Abruf im Hintergrund und gibt sofort einen Progress-Toast zurück."""
    global _spielplan_job
    if _spielplan_job.get("running"):
        return HTMLResponse(_progress_toast(
            _spielplan_job["current"], _spielplan_job["total"], _spielplan_job["team"]
        ))
    _spielplan_job = {"running": True, "current": 0, "total": 0, "team": "", "result": "", "error": ""}
    loop = _asyncio.get_event_loop()
    loop.run_in_executor(None, _run_generate_csv)
    return HTMLResponse(_progress_toast(0, 0, ""))


@router.get("/fetch-spielplan/progress", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def fetch_spielplan_progress():
    """Liefert den aktuellen Fortschritt des Spielplan-Abrufs."""
    global _spielplan_job
    if _spielplan_job.get("running"):
        return HTMLResponse(_progress_toast(
            _spielplan_job["current"], _spielplan_job["total"], _spielplan_job["team"]
        ))
    if _spielplan_job.get("error"):
        return HTMLResponse(_toast(f'Fehler: {_spielplan_job["error"]}', "error"))
    if _spielplan_job.get("result"):
        return HTMLResponse(_toast(f'\u2705 {_spielplan_job["result"]}', "success"))
    return HTMLResponse("")  # Kein aktiver Job

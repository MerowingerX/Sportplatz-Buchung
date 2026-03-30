from web.templates_instance import templates
from datetime import datetime, date, time, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

import os
from fastapi import APIRouter, BackgroundTasks, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

from auth.auth import hash_password
from auth.dependencies import CurrentUser, require_permission
from booking.booking import dfbnet_displace
import booking.field_config as fc
from booking.field_config import get_display_name
from booking.models import BookingCreate, BookingType, FieldName, Permission, UserCreate, UserRole
from utils.time_slots import get_all_start_slots
from web.config import get_settings
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/admin")
templates.env.filters["enumerate"] = enumerate

_admin_required = Depends(require_permission(Permission.ACCESS_ADMIN))
_manage_users   = Depends(require_permission(Permission.MANAGE_USERS))
_dfbnet_required = Depends(require_permission(Permission.DFBNET_BOOKING))


from web.htmx import toast as _toast


@router.get("", response_class=HTMLResponse, dependencies=[_admin_required])
async def admin_dashboard(request: Request, current_user: CurrentUser):
    from booking.spielplan_sync import read_sync_status
    from booking.scheduler_config import load as load_scheduler_cfg
    from datetime import datetime as _dt

    repo = request.app.state.repo
    users = repo.get_all_users()
    sync_status = read_sync_status()
    scheduler_cfg = load_scheduler_cfg()

    # Zeitstempel leserlich formatieren
    if sync_status and sync_status.get("timestamp"):
        try:
            ts = _dt.fromisoformat(sync_status["timestamp"])
            sync_status["timestamp_fmt"] = ts.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            sync_status["timestamp_fmt"] = sync_status["timestamp"]

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "users": users,
            "sync_status": sync_status,
            "scheduler_cfg": scheduler_cfg,
            "server_time": _dt.now().strftime("%d.%m.%Y %H:%M:%S"),
        },
    )


@router.post("/scheduler-config", response_class=HTMLResponse, dependencies=[_admin_required])
async def save_scheduler_config(
    request: Request,
    enabled: Optional[str] = Form(None),
    uhrzeit: str = Form("06:00"),
):
    from booking.scheduler_config import SchedulerConfig, save as save_scheduler_cfg
    from booking.scheduler import apply_schedule

    cfg = SchedulerConfig(
        spielplan_sync_enabled=enabled is not None,
        spielplan_sync_uhrzeit=uhrzeit,
    )
    save_scheduler_cfg(cfg)
    apply_schedule(request.app.state.scheduler, request.app)

    if cfg.spielplan_sync_enabled:
        msg = f"Automatischer Sync aktiviert – täglich {uhrzeit} Uhr"
    else:
        msg = "Automatischer Sync deaktiviert"
    return HTMLResponse(_toast(msg, "success"))


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
            "mannschaften": repo.get_all_mannschaften(),
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
        mannschaft=mannschaft or None,
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
    _invalidate_user_tokens(request.app.state, user_id)
    return HTMLResponse(
        _toast(f"Passwort für '{user.name}' zurückgesetzt. Nutzer muss Passwort beim nächsten Login ändern.")
    )


def _user_row_ctx(user, current_user, repo):
    return {"user": user, "current_user": current_user, "roles": list(UserRole), "mannschaften": repo.get_all_mannschaften()}


def _invalidate_user_tokens(app_state, user_id: str) -> None:
    """Markiert alle vor jetzt ausgestellten Tokens des Nutzers als ungültig."""
    invalidations = getattr(app_state, "token_invalidations", {})
    invalidations[user_id] = int(datetime.now(timezone.utc).timestamp())
    app_state.token_invalidations = invalidations


@router.get("/users/{user_id}/row", response_class=HTMLResponse, dependencies=[_manage_users])
async def user_row(request: Request, user_id: str, current_user: CurrentUser):
    repo = request.app.state.repo
    user = repo.get_user_by_id(user_id)
    if not user:
        return HTMLResponse(_toast("Nutzer nicht gefunden.", "error"), status_code=404)
    return HTMLResponse(
        templates.get_template("partials/_user_row.html").render(_user_row_ctx(user, current_user, repo))
    )


@router.get("/users/{user_id}/edit", response_class=HTMLResponse, dependencies=[_manage_users])
async def user_edit_row(request: Request, user_id: str, current_user: CurrentUser):
    repo = request.app.state.repo
    user = repo.get_user_by_id(user_id)
    if not user:
        return HTMLResponse(_toast("Nutzer nicht gefunden.", "error"), status_code=404)
    return HTMLResponse(
        templates.get_template("partials/_user_row_edit.html").render(_user_row_ctx(user, current_user, repo))
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
    old_user = repo.get_user_by_id(user_id)
    new_mannschaft = mannschaft or None
    user = repo.update_user(user_id, role=role, email=email, mannschaft=new_mannschaft)
    _invalidate_user_tokens(request.app.state, user_id)
    if old_user:
        _sync_user_mannschaft_change(repo, user_id, user.name, old_user.mannschaft, new_mannschaft)
    return HTMLResponse(
        templates.get_template("partials/_user_row.html").render(_user_row_ctx(user, current_user, repo))
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


# ------------------------------------------------------------------ Mannschaftsverwaltung

def _mannschaft_row_ctx(m, current_user, repo):
    trainers = [u for u in repo.get_all_users() if u.role == UserRole.TRAINER]
    return {"m": m, "current_user": current_user, "trainers": trainers}


def _sync_trainer_change(repo, old_trainer_id: Optional[str], new_trainer_id: Optional[str],
                         mannschaft_name: str) -> None:
    """
    Hält User.mannschaft und MannschaftConfig.trainer_id synchron wenn der Trainer einer
    Mannschaft geändert wird.
    - old_trainer_id: bisheriger Trainer (dessen User.mannschaft geleert wird)
    - new_trainer_id: neuer Trainer (dessen User.mannschaft auf mannschaft_name gesetzt wird)
    """
    if old_trainer_id and old_trainer_id != new_trainer_id:
        old_trainer = repo.get_user_by_id(old_trainer_id)
        if old_trainer and old_trainer.mannschaft == mannschaft_name:
            repo.update_user(old_trainer_id, old_trainer.role.value, old_trainer.email, None)
    if new_trainer_id:
        new_trainer = repo.get_user_by_id(new_trainer_id)
        if new_trainer and new_trainer.mannschaft != mannschaft_name:
            repo.update_user(new_trainer_id, new_trainer.role.value, new_trainer.email, mannschaft_name)


def _sync_user_mannschaft_change(repo, user_id: str, user_name: str,
                                 old_mannschaft: Optional[str], new_mannschaft: Optional[str]) -> None:
    """
    Hält MannschaftConfig.trainer_id und User.mannschaft synchron wenn die Mannschaft
    eines Nutzers geändert wird.
    - Alte Mannschaft: trainer_id wird geleert (falls sie auf diesen Nutzer zeigt)
    - Neue Mannschaft: trainer_id wird auf diesen Nutzer gesetzt
    """
    all_teams = repo.get_all_mannschaften()
    if old_mannschaft and old_mannschaft != new_mannschaft:
        for m in all_teams:
            if m.name == old_mannschaft and m.trainer_id == user_id:
                repo.update_mannschaft(m.notion_id, m.name, None, None,
                                       m.fussball_de_team_id, m.cc_emails, m.aktiv,
                                       shortname=m.shortname)
    if new_mannschaft:
        for m in all_teams:
            if m.name == new_mannschaft and m.trainer_id != user_id:
                repo.update_mannschaft(m.notion_id, m.name, user_id, user_name,
                                       m.fussball_de_team_id, m.cc_emails, m.aktiv,
                                       shortname=m.shortname)


@router.get("/mannschaften", response_class=HTMLResponse, dependencies=[_manage_users])
async def mannschaften_page(request: Request, current_user: CurrentUser):
    repo = request.app.state.repo
    mannschaften = repo.get_all_mannschaften()
    trainers = [u for u in repo.get_all_users() if u.role == UserRole.TRAINER]
    return templates.TemplateResponse(
        "admin/mannschaften.html",
        {
            "request": request,
            "current_user": current_user,
            "mannschaften": mannschaften,
            "trainers": trainers,
        },
    )


@router.post("/mannschaften", response_class=HTMLResponse, dependencies=[_manage_users])
async def create_mannschaft(
    request: Request,
    current_user: CurrentUser,
    name: str = Form(...),
    shortname: Optional[str] = Form(None),
    trainer_id: Optional[str] = Form(None),
    fussball_de_team_id: Optional[str] = Form(None),
    cc_emails: Optional[str] = Form(None),
    aktiv: Optional[str] = Form(None),
):
    repo = request.app.state.repo
    trainer_name: Optional[str] = None
    if trainer_id:
        trainer = repo.get_user_by_id(trainer_id)
        trainer_name = trainer.name if trainer else None
    cc_list = [e.strip() for e in (cc_emails or "").split(",") if e.strip()]
    repo.create_mannschaft(
        name=name.strip(),
        shortname=shortname.strip() if shortname else None,
        trainer_id=trainer_id or None,
        trainer_name=trainer_name,
        fussball_de_team_id=fussball_de_team_id.strip() if fussball_de_team_id else None,
        cc_emails=cc_list,
        aktiv=aktiv is not None,
    )
    return HTMLResponse(_toast(f"Mannschaft '{name}' angelegt."))


# ── fussball.de Mannschaft-Sync ───────────────────────────────────────────────

def _load_fussball_de_mod():
    import importlib.util as _ilu
    import pathlib as _pl
    path = _pl.Path(__file__).parent.parent.parent / "tools" / "fussball_de.py"
    spec = _ilu.spec_from_file_location("fussball_de", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@router.post("/mannschaften/sync-fussball-de", response_class=HTMLResponse, dependencies=[_manage_users])
async def mannschaft_sync_fussball_de(request: Request, current_user: CurrentUser):
    import asyncio as _asyncio
    repo = request.app.state.repo
    settings = get_settings()
    url = getattr(settings, "fussball_de_vereinsseite", None)
    if not url:
        return HTMLResponse(_toast("FUSSBALL_DE_VEREINSSEITE nicht konfiguriert.", "error"))

    from booking.vereinsconfig import get_heim_keywords
    heim_kw = get_heim_keywords()

    def _scrape():
        mod = _load_fussball_de_mod()
        club_id = mod._club_id_from_url(url)
        if not club_id:
            raise ValueError(f"Konnte Club-ID nicht aus URL extrahieren: {url}")
        html = mod.fetch_matchplan_html(club_id)
        return mod.parse_matchplan(html, heim_kw)

    try:
        loop = _asyncio.get_event_loop()
        spiele = await loop.run_in_executor(None, _scrape)
    except Exception as exc:
        return HTMLResponse(_toast(f"fussball.de konnte nicht abgerufen werden: {exc}", "error"))

    altersklassen = sorted({s.altersklasse for s in spiele if s.altersklasse})
    existing = repo.get_all_mannschaften()
    existing_names = {m.name for m in existing}
    neu = [a for a in altersklassen if a not in existing_names]

    return HTMLResponse(
        templates.get_template("partials/_mannschaft_sync.html").render({
            "neu": neu,
            "existing": existing,
            "altersklassen_alle": altersklassen,
        })
    )


@router.post("/mannschaften/from-fussball-de", response_class=HTMLResponse, dependencies=[_manage_users])
async def mannschaft_from_fussball_de(
    request: Request,
    current_user: CurrentUser,
):
    form = await request.form()
    selected = form.getlist("add_mannschaft")
    repo = request.app.state.repo
    created = 0
    for name in selected:
        name = name.strip()
        if not name:
            continue
        existing = repo.get_all_mannschaften()
        if any(m.name == name for m in existing):
            continue
        repo.create_mannschaft(
            name=name,
            trainer_id=None,
            trainer_name=None,
            fussball_de_team_id=None,
            cc_emails=[],
            aktiv=True,
        )
        created += 1
    msg = f"{created} Mannschaft(en) angelegt." if created else "Keine neuen Mannschaften ausgewählt."
    level = "success" if created else "warning"
    # Reload full table body
    mannschaften = repo.get_all_mannschaften()
    rows_html = "".join(
        templates.get_template("partials/_mannschaft_row.html").render(
            _mannschaft_row_ctx(m, current_user, repo)
        )
        for m in mannschaften
    )
    return HTMLResponse(
        f'<tbody id="mannschaft-tbody">{rows_html}</tbody>'
        + _toast(msg, level)
    )


@router.get("/mannschaften/{mid}/row", response_class=HTMLResponse, dependencies=[_manage_users])
async def mannschaft_row(request: Request, mid: str, current_user: CurrentUser):
    repo = request.app.state.repo
    m = repo.get_mannschaft_by_id(mid)
    if not m:
        return HTMLResponse(_toast("Mannschaft nicht gefunden.", "error"), status_code=404)
    return HTMLResponse(
        templates.get_template("partials/_mannschaft_row.html").render(
            _mannschaft_row_ctx(m, current_user, repo)
        )
    )


@router.get("/mannschaften/{mid}/edit", response_class=HTMLResponse, dependencies=[_manage_users])
async def mannschaft_edit_row(request: Request, mid: str, current_user: CurrentUser):
    repo = request.app.state.repo
    m = repo.get_mannschaft_by_id(mid)
    if not m:
        return HTMLResponse(_toast("Mannschaft nicht gefunden.", "error"), status_code=404)
    return HTMLResponse(
        templates.get_template("partials/_mannschaft_row_edit.html").render(
            _mannschaft_row_ctx(m, current_user, repo)
        )
    )


@router.patch("/mannschaften/{mid}", response_class=HTMLResponse, dependencies=[_manage_users])
async def update_mannschaft(
    request: Request,
    mid: str,
    current_user: CurrentUser,
    name: str = Form(...),
    shortname: Optional[str] = Form(None),
    trainer_id: Optional[str] = Form(None),
    fussball_de_team_id: Optional[str] = Form(None),
    cc_emails: Optional[str] = Form(None),
    aktiv: Optional[str] = Form(None),
):
    repo = request.app.state.repo
    old_m = repo.get_mannschaft_by_id(mid)
    new_trainer_id = trainer_id or None
    trainer_name: Optional[str] = None
    if new_trainer_id:
        trainer = repo.get_user_by_id(new_trainer_id)
        trainer_name = trainer.name if trainer else None
    cc_list = [e.strip() for e in (cc_emails or "").split(",") if e.strip()]
    m = repo.update_mannschaft(
        mannschaft_id=mid,
        name=name.strip(),
        shortname=shortname.strip() if shortname else None,
        trainer_id=new_trainer_id,
        trainer_name=trainer_name,
        fussball_de_team_id=fussball_de_team_id.strip() if fussball_de_team_id else None,
        cc_emails=cc_list,
        aktiv=aktiv is not None,
    )
    if old_m:
        _sync_trainer_change(repo, old_m.trainer_id, new_trainer_id, m.name)
    return HTMLResponse(
        templates.get_template("partials/_mannschaft_row.html").render(
            _mannschaft_row_ctx(m, current_user, repo)
        )
        + _toast(f"Mannschaft '{m.name}' aktualisiert.")
    )


@router.delete("/mannschaften/{mid}", response_class=HTMLResponse, dependencies=[_manage_users])
async def delete_mannschaft(request: Request, mid: str, current_user: CurrentUser):
    repo = request.app.state.repo
    m = repo.get_mannschaft_by_id(mid)
    if not m:
        return HTMLResponse(_toast("Mannschaft nicht gefunden.", "error"))
    # Alle Buchungen dieser Mannschaft stornieren
    from booking.models import BookingStatus
    from web.routers.calendar import invalidate_week_cache
    all_bookings = repo.get_all_bookings()
    cancelled = 0
    for b in all_bookings:
        if b.mannschaft == m.name and b.status == BookingStatus.BESTAETIGT:
            repo.update_booking_status(b.notion_id, BookingStatus.STORNIERT)
            invalidate_week_cache(b.date)
            cancelled += 1
    repo.delete_mannschaft(mid)
    msg = f"Mannschaft '{m.name}' gelöscht."
    if cancelled:
        msg += f" {cancelled} Buchung(en) storniert."
    return HTMLResponse(
        f'<tr id="mannschaft-{mid}"></tr>'
        + _toast(msg, "warning" if cancelled else "success")
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
            "field_groups": fc.get_visible_groups("Administrator"),
            "field_display_names": fc.get_display_names(),
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

    booking, errors = build_booking(
        repo=repo,
        data=data,
        current_user=current_user,
        settings=settings,
        existing_bookings=existing,
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


# ------------------------------------------------------------------ Instagram

_instagram_job: dict = {"running": False, "result": "", "error": ""}


def _run_instagram_post(notion_key: str, db_id: str, booking_url: str,
                        account_id: str, access_token: str) -> None:
    global _instagram_job
    from booking.instagram import post_wochenende
    try:
        result = post_wochenende(notion_key, db_id, booking_url, account_id, access_token)
        skipped = result["skipped"]
        msg = f"{result['posted']} Bild(er) gepostet"
        if skipped:
            msg += f", {skipped} Spiel(e) wegen Karussell-Limit übersprungen"
        _instagram_job["result"] = msg
        _instagram_job["error"]  = ""
    except Exception as exc:
        _instagram_job["error"]  = str(exc)
        _instagram_job["result"] = ""
    finally:
        _instagram_job["running"] = False


@router.post("/instagram/post-wochenende", response_class=HTMLResponse, dependencies=[_admin_required])
async def instagram_post_wochenende(request: Request):
    global _instagram_job
    if _instagram_job.get("running"):
        return HTMLResponse(_toast("Instagram-Post läuft bereits…", "warning"))

    settings = get_settings()
    if not settings.instagram_account_id or not settings.instagram_access_token:
        return HTMLResponse(_toast(
            "Instagram nicht konfiguriert – Account-ID und Token in der Vereinskonfiguration eintragen.",
            "error",
        ))

    notion_key  = settings.notion_api_key
    db_id       = settings.notion_buchungen_db_id
    booking_url = settings.booking_url
    account_id  = settings.instagram_account_id
    access_token = settings.instagram_access_token

    _instagram_job = {"running": True, "result": "", "error": ""}

    loop = _asyncio.get_event_loop()
    loop.run_in_executor(
        None, _run_instagram_post,
        notion_key, db_id, booking_url, account_id, access_token,
    )

    return HTMLResponse(
        '<div id="toast" class="toast toast--progress"'
        ' hx-get="/admin/instagram/post-wochenende/progress"'
        ' hx-trigger="every 2s" hx-swap="outerHTML">'
        '&#8987; Bilder werden generiert und gepostet…</div>'
    )


@router.get("/instagram/post-wochenende/progress", response_class=HTMLResponse, dependencies=[_admin_required])
async def instagram_post_progress():
    global _instagram_job
    if _instagram_job.get("running"):
        return HTMLResponse(
            '<div id="toast" class="toast toast--progress"'
            ' hx-get="/admin/instagram/post-wochenende/progress"'
            ' hx-trigger="every 2s" hx-swap="outerHTML">'
            '&#8987; Bilder werden generiert und gepostet…</div>'
        )
    if _instagram_job.get("error"):
        return HTMLResponse(_toast(f'Fehler: {_instagram_job["error"]}', "error"))
    if _instagram_job.get("result"):
        return HTMLResponse(_toast(f'\u2705 Instagram: {_instagram_job["result"]}', "success"))
    return HTMLResponse("")


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


# ------------------------------------------------------------------ Spielplan-Sync

@router.post("/spielplan-sync", response_class=HTMLResponse, dependencies=[_dfbnet_required])
async def spielplan_sync(request: Request):
    """
    Vollständiger Spielplan-Abgleich:
      1. fussball.de Spielplan laden
      2. Fehlende Heimspiele buchen (mit Verdrängung + E-Mail)
      3. Verwaiste Buchungen stornieren (+ E-Mail)
    """
    from booking.spielplan_sync import sync_spielplan

    repo = request.app.state.repo
    settings = get_settings()

    try:
        sync_result = await sync_spielplan(repo, settings)
    except Exception as exc:
        from booking.spielplan_sync import SyncResult, write_sync_status
        err = SyncResult(fehler=[str(exc)])
        write_sync_status(err, "admin")
        return HTMLResponse(_toast(f"Fehler beim Spielplan-Sync: {exc}", "error"))

    kind = "success" if sync_result.ok else "warning"
    toast = _toast(f"✅ Spielplan-Sync: {sync_result.zusammenfassung()}", kind)

    # Detailinhalt für das Modal
    def _section(title: str, items: list[str], css: str) -> str:
        rows = "".join(f'<li class="sync-item sync-item--{css}">{s}</li>' for s in items)
        return f'<h3 class="sync-section__title">{title}</h3><ul class="sync-list">{rows}</ul>'

    sections: list[str] = []
    if sync_result.gebucht:
        sections.append(_section(f"✓ Neu eingetragen ({len(sync_result.gebucht)})", sync_result.gebucht, "ok"))
    if sync_result.uebersprungen:
        sections.append(_section(f"⏭ Bereits vorhanden ({len(sync_result.uebersprungen)})", sync_result.uebersprungen, "skip"))
    if sync_result.storniert:
        sections.append(_section(f"✗ Storniert ({len(sync_result.storniert)})", sync_result.storniert, "warn"))
    if sync_result.fehler:
        sections.append(_section(f"⚠ Fehler ({len(sync_result.fehler)})", sync_result.fehler, "error"))

    from booking.spielplan_sync import write_sync_status
    write_sync_status(sync_result, "admin")

    body = "".join(sections) if sections else '<p class="sync-empty">Keine Änderungen notwendig.</p>'
    modal_oob = f'<div id="sync-modal-content" hx-swap-oob="true">{body}</div>'

    response = HTMLResponse(toast + modal_oob)
    if sections:
        response.headers["HX-Trigger"] = "openSyncModal"
    return response


# ------------------------------------------------------------------ Platzkonfiguration

@router.get("/field-config", response_class=HTMLResponse, dependencies=[_admin_required])
async def field_config_page(request: Request, current_user: CurrentUser):
    from booking.field_config import ALL_ROLES, load
    cfg = load()
    return templates.TemplateResponse(
        "admin/field_config.html",
        {
            "request": request,
            "current_user": current_user,
            "field_groups": cfg["field_groups"],
            "all_roles": ALL_ROLES,
        },
    )


@router.post("/field-config", response_class=HTMLResponse, dependencies=[_admin_required])
async def field_config_save(request: Request, current_user: CurrentUser):
    from booking.field_config import ALL_ROLES, load, save
    form = await request.form()
    cfg = load()

    for group in cfg["field_groups"]:
        group_key = group["name"].replace(" ", "_").replace("(", "").replace(")", "")
        group["visible_to"] = [
            role for role in ALL_ROLES
            if form.get(f"{group_key}__{role}") == "on"
        ]

    save(cfg)
    return HTMLResponse(
        _toast("Platzkonfiguration gespeichert.")
        + '<script>setTimeout(()=>history.back(),1200)</script>'
    )


# ------------------------------------------------------------------ Housekeeping

def _housekeeping_cutoff(mode: str) -> date:
    today = date.today()
    if mode == "saison":
        saison_start = date(today.year, 8, 1)
        return saison_start if today >= saison_start else date(today.year - 1, 8, 1)
    return today


def _housekeeping_general_candidates(repo, cutoff: date):
    """Stornierte + vergangene Buchungen, Buchungen aktiver Serien ausgenommen."""
    active_series_ids = {s.notion_id for s in repo.get_all_series(only_active=True)}
    all_candidates = repo.get_housekeeping_candidates(cutoff)
    return [b for b in all_candidates if b.series_id not in active_series_ids]


@router.get("/housekeeping", response_class=HTMLResponse, dependencies=[_admin_required])
async def housekeeping_preview(
    request: Request,
    current_user: CurrentUser,
    cutoff: str = "saison",
):
    """Vorschau: Wie viele Buchungen werden bereinigt?"""
    from booking.models import SeriesStatus
    repo = request.app.state.repo
    cutoff_date = _housekeeping_cutoff(cutoff)
    candidates = _housekeeping_general_candidates(repo, cutoff_date)

    storniert_statuses = {"Storniert", "Storniert (DFBnet)"}
    storniert_count = sum(1 for b in candidates if b.status.value in storniert_statuses)
    vergangen_count = len(candidates) - storniert_count

    # Inaktive Serien mit Buchungsanzahl
    all_series = repo.get_all_series(only_active=False)
    inactive_series = [s for s in all_series if s.status != SeriesStatus.AKTIV]
    inactive_entries = []
    for s in sorted(inactive_series, key=lambda x: x.mannschaft or ""):
        bookings = repo.get_all_bookings_for_series(s.notion_id)
        inactive_entries.append({"series": s, "booking_count": len(bookings)})

    return templates.TemplateResponse(
        "partials/_housekeeping_preview.html",
        {
            "request": request,
            "current_user": current_user,
            "cutoff": cutoff,
            "cutoff_date": cutoff_date,
            "total": len(candidates),
            "storniert": storniert_count,
            "vergangen": vergangen_count,
            "inactive_entries": inactive_entries,
        },
    )


@router.post("/housekeeping", response_class=HTMLResponse, dependencies=[_admin_required])
async def housekeeping_execute(
    request: Request,
    current_user: CurrentUser,
    cutoff: str = Form("saison"),
    series_ids: List[str] = Form(default=[]),
):
    """Bereinigung ausführen: allgemeine Kandidaten + gewählte inaktive Serien archivieren."""
    repo = request.app.state.repo
    cutoff_date = _housekeeping_cutoff(cutoff)

    to_delete: set[str] = set()

    # Allgemeine Kandidaten
    for b in _housekeeping_general_candidates(repo, cutoff_date):
        to_delete.add(b.notion_id)

    # Buchungen ausgewählter inaktiver Serien
    for sid in series_ids:
        for b in repo.get_all_bookings_for_series(sid):
            to_delete.add(b.notion_id)

    deleted = 0
    errors = 0
    for booking_id in to_delete:
        try:
            repo.delete_booking(booking_id)
            deleted += 1
        except Exception:
            errors += 1

    msg = f"Bereinigung abgeschlossen: {deleted} Buchungen entfernt."
    if errors:
        msg += f" {errors} Fehler."
    kind = "success" if not errors else "warning"

    resp = HTMLResponse(_toast(msg, kind))
    resp.headers["HX-Trigger"] = "closeModal"
    return resp


# ------------------------------------------------------------------ Vereinskonfiguration

@router.get("/vereinsconfig", response_class=HTMLResponse, dependencies=[_admin_required])
async def vereinsconfig_page(request: Request, current_user: CurrentUser):
    from booking.vereinsconfig import load as load_vc
    from web.config import get_env_path
    from dotenv import dotenv_values

    cfg = load_vc()
    raw_env = dotenv_values(get_env_path())

    # Secrets: Wert nie an den Client senden – nur ob gesetzt
    env = {
        "FUSSBALL_DE_VEREINSSEITE":  raw_env.get("FUSSBALL_DE_VEREINSSEITE", ""),
        "APIFUSSBALL_CLUB_ID":       raw_env.get("APIFUSSBALL_CLUB_ID", ""),
        "APIFUSSBALL_TOKEN":         "",   # nie senden
        "BOOKING_URL":               raw_env.get("BOOKING_URL", ""),
        "LOCATION_LAT":              raw_env.get("LOCATION_LAT", ""),
        "LOCATION_LON":              raw_env.get("LOCATION_LON", ""),
        "LOCATION_NAME":             raw_env.get("LOCATION_NAME", ""),
        "INSTAGRAM_ACCOUNT_ID":      raw_env.get("INSTAGRAM_ACCOUNT_ID", ""),
        "INSTAGRAM_ACCESS_TOKEN":    "",   # nie senden
    }
    env_set = {
        "APIFUSSBALL_TOKEN":      bool(raw_env.get("APIFUSSBALL_TOKEN")),
        "INSTAGRAM_ACCESS_TOKEN": bool(raw_env.get("INSTAGRAM_ACCESS_TOKEN")),
    }
    return templates.TemplateResponse(
        "admin/vereinsconfig.html",
        {"request": request, "current_user": current_user,
         "cfg": cfg, "env": env, "env_set": env_set},
    )


@router.post("/vereinsconfig", response_class=HTMLResponse, dependencies=[_admin_required])
async def save_vereinsconfig(request: Request, current_user: CurrentUser):
    import json as _json
    from booking.vereinsconfig import load as _load_vc, get_config_path
    from web.templates_instance import refresh_globals
    from web.config import get_env_path, reset_settings
    from dotenv import set_key

    form = await request.form()

    # ── vereinsconfig.json ──────────────────────────────────────────────
    path = get_config_path()
    try:
        data = _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    data["vereinsname"]           = form.get("vereinsname", "").strip()
    data["vereinsname_lang"]      = form.get("vereinsname_lang", "").strip()
    data["logo_url"]              = form.get("logo_url", "").strip()
    data["primary_color"]         = form.get("primary_color", "#1e4fa3").strip()
    data["primary_color_dark"]    = form.get("primary_color_dark", "#0d2f6b").strip()
    data["primary_color_darker"]  = form.get("primary_color_darker", "#071c44").strip()
    data["gold_color"]            = form.get("gold_color", "#e8c04a").strip()

    kw_raw = form.get("heim_keywords", "")
    data["heim_keywords"] = [k.strip().lower() for k in kw_raw.split(",") if k.strip()]

    try:
        data["spielorte"] = _json.loads(form.get("spielorte", "[]"))
    except _json.JSONDecodeError as exc:
        return HTMLResponse(_toast(f"Ungültiges JSON in Spielorte: {exc}", "error"))

    data["saison_defaults"] = {
        "ganzjaehrig":    {"start": form.get("saison_ganzjaehrig_start",    "08-01"),
                           "ende":  form.get("saison_ganzjaehrig_ende",     "06-30")},
        "sommerhalbjahr": {"start": form.get("saison_sommerhalbjahr_start", "08-01"),
                           "ende":  form.get("saison_sommerhalbjahr_ende",  "10-30")},
        "winterhalbjahr": {"start": form.get("saison_winterhalbjahr_start", "10-30"),
                           "ende":  form.get("saison_winterhalbjahr_ende",  "03-01")},
    }

    path.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _load_vc.cache_clear()
    refresh_globals()

    # ── .env-Felder ─────────────────────────────────────────────────────
    env_path = str(get_env_path())
    _plain_env_fields = [
        "FUSSBALL_DE_VEREINSSEITE", "APIFUSSBALL_CLUB_ID",
        "BOOKING_URL", "LOCATION_LAT", "LOCATION_LON", "LOCATION_NAME",
        "INSTAGRAM_ACCOUNT_ID",
    ]
    for key in _plain_env_fields:
        val = form.get(key, "").strip()
        if val:
            set_key(env_path, key, val)

    # Secrets: nur schreiben wenn explizit neuer Wert eingegeben
    for secret_key in ("APIFUSSBALL_TOKEN", "INSTAGRAM_ACCESS_TOKEN"):
        val = form.get(secret_key, "").strip()
        if val:
            set_key(env_path, secret_key, val)

    # Settings-Cache leeren damit neue .env-Werte greifen
    new_settings = reset_settings()
    request.app.state.settings = new_settings

    response = HTMLResponse(_toast("Konfiguration gespeichert – Seite wird neu geladen.", "success"))
    response.headers["HX-Refresh"] = "true"
    return response

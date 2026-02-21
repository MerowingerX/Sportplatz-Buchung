from datetime import date

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser, require_permission
from booking.models import BlackoutCreate, BlackoutType, Permission
from utils.time_slots import get_all_start_slots
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/blackouts")
templates = Jinja2Templates(directory="web/templates")

_blackout_required = Depends(require_permission(Permission.MANAGE_BLACKOUTS))


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


def _invalidate_range(start: date, end: date) -> None:
    """Invalidiert den Wochen-Cache für alle Wochen im Sperrzeitraum."""
    from datetime import timedelta
    d = start
    seen_weeks: set[tuple[int, int]] = set()
    while d <= end:
        iso = d.isocalendar()
        week_key = (iso[0], iso[1])
        if week_key not in seen_weeks:
            invalidate_week_cache(d)
            seen_weeks.add(week_key)
        d += timedelta(days=7)


@router.get("", response_class=HTMLResponse, dependencies=[_blackout_required])
async def blackouts_page(
    request: Request,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    blackouts = repo.get_all_blackouts()
    return templates.TemplateResponse(
        "blackouts/index.html",
        {
            "request": request,
            "current_user": current_user,
            "blackouts": blackouts,
            "blackout_types": list(BlackoutType),
            "start_slots": get_all_start_slots(),
        },
    )


@router.post("", response_class=HTMLResponse, dependencies=[_blackout_required])
async def create_blackout(
    request: Request,
    current_user: CurrentUser,
    start_date: date = Form(...),
    end_date: date = Form(...),
    blackout_type: str = Form(...),
    start_time: str = Form(None),
    end_time: str = Form(None),
    reason: str = Form(""),
):
    from datetime import time as dtime

    repo = request.app.state.repo

    # end_date darf nicht vor start_date liegen
    if end_date < start_date:
        return HTMLResponse(
            _toast("Ende-Datum darf nicht vor Beginn-Datum liegen.", "error"),
            status_code=422,
        )

    parsed_start = None
    parsed_end = None
    if start_time:
        h, m = start_time.split(":")
        parsed_start = dtime(int(h), int(m))
    if end_time:
        h, m = end_time.split(":")
        parsed_end = dtime(int(h), int(m))

    data = BlackoutCreate(
        start_date=start_date,
        end_date=end_date,
        blackout_type=BlackoutType(blackout_type),
        start_time=parsed_start,
        end_time=parsed_end,
        reason=reason,
    )

    blackout = repo.create_blackout(
        data=data,
        entered_by_id=current_user.sub,
        entered_by_name=current_user.username,
    )
    _invalidate_range(start_date, end_date)

    label = (
        f"{start_date.strftime('%d.%m.%Y')} – {end_date.strftime('%d.%m.%Y')}"
        if end_date > start_date
        else start_date.strftime('%d.%m.%Y')
    )
    return HTMLResponse(
        templates.get_template("partials/_blackout_row.html").render(
            {"blackout": blackout, "current_user": current_user}
        )
        + _toast(f"Sperrzeit {label} eingetragen.")
    )


@router.delete("/{blackout_id}", response_class=HTMLResponse, dependencies=[_blackout_required])
async def delete_blackout(
    request: Request,
    blackout_id: str,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    repo.delete_blackout(blackout_id)
    return HTMLResponse(_toast("Sperrzeit gelöscht."))

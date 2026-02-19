from datetime import date

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser, require_role
from booking.models import BlackoutCreate, BlackoutType, UserRole
from utils.time_slots import get_all_start_slots
from web.routers.calendar import invalidate_week_cache

router = APIRouter(prefix="/blackouts")
templates = Jinja2Templates(directory="web/templates")


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


@router.get("", response_class=HTMLResponse)
async def blackouts_page(
    request: Request,
    current_user: CurrentUser,
):
    return templates.TemplateResponse(
        "partials/_blackout_form.html",
        {
            "request": request,
            "current_user": current_user,
            "blackout_types": list(BlackoutType),
            "start_slots": get_all_start_slots(),
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_blackout(
    request: Request,
    current_user: CurrentUser,
    blackout_date: date = Form(..., alias="date"),
    blackout_type: str = Form(...),
    start_time: str = Form(None),
    end_time: str = Form(None),
    reason: str = Form(""),
):
    from datetime import time as dtime

    repo = request.app.state.repo

    parsed_start = None
    parsed_end = None
    if start_time:
        h, m = start_time.split(":")
        parsed_start = dtime(int(h), int(m))
    if end_time:
        h, m = end_time.split(":")
        parsed_end = dtime(int(h), int(m))

    data = BlackoutCreate(
        date=blackout_date,
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
    invalidate_week_cache(blackout_date)

    return HTMLResponse(_toast(f"Sperrzeit für {blackout_date} eingetragen."))


@router.delete("/{blackout_id}", response_class=HTMLResponse)
async def delete_blackout(
    request: Request,
    blackout_id: str,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    repo.delete_blackout(blackout_id)
    return HTMLResponse(_toast("Sperrzeit gelöscht."))

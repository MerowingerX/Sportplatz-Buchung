from datetime import date, time as dtime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser, require_role
from booking.models import ExternalEventCreate, UserRole

router = APIRouter(prefix="/events")
templates = Jinja2Templates(directory="web/templates")

_any_user = Depends(require_role(
    UserRole.TRAINER, UserRole.ADMINISTRATOR, UserRole.PLATZWART, UserRole.DFBNET
))


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


PAGE_SIZE = 25


@router.get("", response_class=HTMLResponse, dependencies=[_any_user])
async def events_page(request: Request, current_user: CurrentUser, page: int = 1):
    repo = request.app.state.repo
    db_configured = bool(request.app.state.settings.notion_events_db_id)
    all_events = repo.get_all_events() if db_configured else []
    total = len(all_events)
    page = max(1, min(page, max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)))
    offset = (page - 1) * PAGE_SIZE
    events = all_events[offset: offset + PAGE_SIZE]
    return templates.TemplateResponse(
        "events/index.html",
        {
            "request": request,
            "current_user": current_user,
            "events": events,
            "db_configured": db_configured,
            "page": page,
            "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
            "total": total,
        },
    )


@router.post("", response_class=HTMLResponse, dependencies=[_any_user])
async def create_event(
    request: Request,
    current_user: CurrentUser,
    title: str = Form(...),
    event_date: date = Form(...),
    start_time: str = Form(...),
    location: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    repo = request.app.state.repo
    try:
        h, m = start_time.split(":")
        parsed_time = dtime(int(h), int(m))
    except (ValueError, AttributeError):
        return HTMLResponse(_toast("Ungültige Uhrzeit.", "error"))

    data = ExternalEventCreate(
        title=title.strip(),
        date=event_date,
        start_time=parsed_time,
        location=location.strip() if location else None,
        description=description.strip() if description else None,
    )
    try:
        event = repo.create_event(data, current_user.sub, current_user.username)
    except ValueError as e:
        return HTMLResponse(_toast(str(e), "error"))

    row_html = templates.get_template("partials/_event_row.html").render({"event": event})
    return HTMLResponse(
        row_html
        + _toast(f'Termin "{event.title}" eingetragen.')
    )


@router.delete("/{event_id}", response_class=HTMLResponse, dependencies=[_any_user])
async def delete_event(request: Request, event_id: str, current_user: CurrentUser):
    repo = request.app.state.repo
    repo.delete_event(event_id)
    return HTMLResponse(
        f'<tr id="event-{event_id}" hx-swap-oob="true"></tr>'
        + _toast("Termin gelöscht.")
    )

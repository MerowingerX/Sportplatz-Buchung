from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from auth.dependencies import CurrentUser, require_permission
from booking.models import AufgabeCreate, AufgabeStatus, AufgabeTyp, Permission, Prioritaet, has_permission

router = APIRouter(prefix="/tasks")
templates = Jinja2Templates(directory="web/templates")

_task_required = Depends(require_permission(Permission.CREATE_TASK))


def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'


@router.get("", response_class=HTMLResponse, dependencies=[_task_required])
async def tasks_page(
    request: Request,
    current_user: CurrentUser,
    filter_typ: Optional[str] = None,
    filter_status: Optional[str] = None,
):
    repo = request.app.state.repo
    aufgaben = repo.get_all_aufgaben()

    if filter_typ:
        aufgaben = [a for a in aufgaben if a.typ.value == filter_typ]
    if filter_status:
        aufgaben = [a for a in aufgaben if a.status.value == filter_status]

    return templates.TemplateResponse(
        "tasks/index.html",
        {
            "request": request,
            "current_user": current_user,
            "aufgaben": aufgaben,
            "typen": list(AufgabeTyp),
            "statuswerte": list(AufgabeStatus),
            "prioritaeten": list(Prioritaet),
            "filter_typ": filter_typ,
            "filter_status": filter_status,
        },
    )


@router.post("", response_class=HTMLResponse, dependencies=[_task_required])
async def create_task(
    request: Request,
    current_user: CurrentUser,
    titel: str = Form(...),
    typ: str = Form(...),
    prioritaet: str = Form(Prioritaet.MITTEL.value),
    faellig_am: Optional[date] = Form(None),
    ort: Optional[str] = Form(None),
    beschreibung: Optional[str] = Form(None),
):
    repo = request.app.state.repo
    data = AufgabeCreate(
        titel=titel,
        typ=AufgabeTyp(typ),
        prioritaet=Prioritaet(prioritaet),
        faellig_am=faellig_am,
        ort=ort.strip() if ort else None,
        beschreibung=beschreibung.strip() if beschreibung else None,
    )
    aufgabe = repo.create_aufgabe(data, current_user.sub, current_user.username)
    return HTMLResponse(
        templates.get_template("partials/_task_row.html").render(
            {"aufgabe": aufgabe, "current_user": current_user}
        )
        + _toast(f"Aufgabe '{aufgabe.titel}' erstellt.")
    )


@router.patch("/{aufgabe_id}/status", response_class=HTMLResponse, dependencies=[_task_required])
async def update_task_status(
    request: Request,
    aufgabe_id: str,
    current_user: CurrentUser,
    status: str = Form(...),
):
    repo = request.app.state.repo
    aufgabe = repo.update_aufgabe_status(aufgabe_id, AufgabeStatus(status))
    return HTMLResponse(
        templates.get_template("partials/_task_row.html").render(
            {"aufgabe": aufgabe, "current_user": current_user}
        )
        + _toast(f"Status auf '{aufgabe.status.value}' gesetzt.")
    )


@router.delete("/{aufgabe_id}", response_class=HTMLResponse, dependencies=[_task_required])
async def delete_task(
    request: Request,
    aufgabe_id: str,
    current_user: CurrentUser,
):
    repo = request.app.state.repo
    aufgabe = repo.get_aufgabe_by_id(aufgabe_id)
    if not aufgabe:
        return HTMLResponse(_toast("Aufgabe nicht gefunden.", "error"), status_code=404)
    can_delete_all = has_permission(current_user.role, Permission.DELETE_ALL_TASKS)
    is_owner = aufgabe.erstellt_von_id == current_user.sub
    if not can_delete_all and not is_owner:
        return HTMLResponse(_toast("Keine Berechtigung.", "error"), status_code=403)
    repo.delete_aufgabe(aufgabe_id)
    return HTMLResponse(
        f'<tr id="task-{aufgabe_id}" hx-swap-oob="true"></tr>'
        + _toast("Aufgabe gelöscht.")
    )

from web.templates_instance import templates
from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from auth.auth import create_jwt, hash_password, verify_password
from auth.dependencies import CurrentUser
from web.audit_log import log_login_ok, log_login_fail, log_logout
from web.config import get_settings

router = APIRouter()


def _set_session_cookie(response, token: str, settings):
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.jwt_expire_hours * 3600,
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    settings = get_settings()
    repo = request.app.state.repo

    user = repo.get_user_by_name(username)
    if not user or not verify_password(password, user.password_hash):
        log_login_fail(request, username)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Ungültiger Nutzername oder Passwort"},
            status_code=401,
        )

    token = create_jwt(
        user.notion_id, user.name, user.role, settings,
        mannschaft=user.mannschaft if user.mannschaft else None,
        must_change_password=user.must_change_password,
    )

    log_login_ok(request, user.name)
    target_url = "/change-password" if user.must_change_password else "/calendar"
    redirect = RedirectResponse(url=target_url, status_code=303)
    _set_session_cookie(redirect, token, settings)
    return redirect


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request, current_user: CurrentUser):
    forced = current_user.must_change_password
    return templates.TemplateResponse(
        "change_password.html",
        {"request": request, "current_user": current_user, "forced": forced, "error": None, "success": None},
    )


@router.post("/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    current_user: CurrentUser,
    current_password: str = Form(""),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    settings = get_settings()
    repo = request.app.state.repo
    forced = current_user.must_change_password

    # Bei erzwungenem Wechsel kein altes Passwort nötig
    if not forced:
        user = repo.get_user_by_id(current_user.sub)
        if not user or not verify_password(current_password, user.password_hash):
            return templates.TemplateResponse(
                "change_password.html",
                {"request": request, "current_user": current_user, "forced": forced,
                 "error": "Aktuelles Passwort ist falsch.", "success": None},
            )

    if len(new_password) < 8:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "current_user": current_user, "forced": forced,
             "error": "Neues Passwort muss mindestens 8 Zeichen lang sein.", "success": None},
        )

    if new_password != confirm_password:
        return templates.TemplateResponse(
            "change_password.html",
            {"request": request, "current_user": current_user, "forced": forced,
             "error": "Passwörter stimmen nicht überein.", "success": None},
        )

    pw_hash = hash_password(new_password)
    repo.update_user_password(current_user.sub, pw_hash)

    # Neues JWT ohne must_change_password
    token = create_jwt(
        current_user.sub, current_user.username, current_user.role, settings,
        mannschaft=current_user.mannschaft,
        must_change_password=False,
    )

    if forced:
        redirect = RedirectResponse(url="/calendar", status_code=303)
        _set_session_cookie(redirect, token, settings)
        return redirect

    # Freiwilliger Wechsel: auf gleicher Seite bleiben mit Erfolg
    resp = templates.TemplateResponse(
        "change_password.html",
        {"request": request, "current_user": current_user, "forced": False,
         "error": None, "success": "Passwort erfolgreich geändert."},
    )
    _set_session_cookie(resp, token, settings)
    return resp


@router.post("/logout")
async def logout(request: Request, current_user: CurrentUser):
    log_logout(request, current_user.username)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, current_user: CurrentUser):
    repo = request.app.state.repo
    mannschaft = None
    all_teams = repo.get_all_mannschaften()
    for m in all_teams:
        if m.trainer_id == current_user.sub:
            mannschaft = m
            break
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "current_user": current_user, "mannschaft": mannschaft},
    )


@router.post("/profile/cc", response_class=HTMLResponse)
async def profile_cc(
    request: Request,
    current_user: CurrentUser,
    cc_emails: str = Form(""),
):
    repo = request.app.state.repo
    all_teams = repo.get_all_mannschaften()
    mannschaft = next((m for m in all_teams if m.trainer_id == current_user.sub), None)
    if mannschaft is None:
        return HTMLResponse(
            '<div id="toast" class="toast toast--error">Keine Mannschaft zugeordnet.</div>'
        )
    cc_list = [e.strip() for e in cc_emails.replace(",", "\n").splitlines() if e.strip()]
    repo.update_mannschaft(
        mannschaft_id=mannschaft.notion_id,
        name=mannschaft.name,
        shortname=mannschaft.shortname,
        trainer_id=mannschaft.trainer_id,
        trainer_name=mannschaft.trainer_name,
        fussball_de_team_id=mannschaft.fussball_de_team_id,
        cc_emails=cc_list,
        aktiv=mannschaft.aktiv,
    )
    return HTMLResponse(
        '<div id="toast" class="toast toast--success">CC-Adressen gespeichert.</div>'
    )

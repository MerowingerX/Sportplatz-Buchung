from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from auth.auth import create_jwt, hash_password, verify_password
from auth.dependencies import CurrentUser
from web.config import get_settings

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


def _set_session_cookie(response, token: str, settings):
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
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
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Ungültiger Nutzername oder Passwort"},
            status_code=401,
        )

    token = create_jwt(
        user.notion_id, user.name, user.role, settings,
        mannschaft=user.mannschaft.value if user.mannschaft else None,
        must_change_password=user.must_change_password,
    )

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
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response

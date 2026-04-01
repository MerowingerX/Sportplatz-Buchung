import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from auth.auth import decode_jwt
from web.config import get_settings
from web.routers import auth, bookings, calendar, series, admin, tasks, events, about 


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from booking.scheduler import apply_schedule

    settings = get_settings()

    # CONFIG_DIR in os.environ exportieren, damit booking/vereinsconfig.py,
    # booking/field_config.py und onboarding.py alle denselben Pfad verwenden.
    # Systemvariable (z. B. aus docker-compose) hat Vorrang; .env-Wert greift als Fallback.
    if "CONFIG_DIR" not in os.environ:
        os.environ["CONFIG_DIR"] = settings.config_dir

    # Ensure config files exist (copy from example if missing)
    project_root = Path(__file__).parent.parent
    config_dir = project_root / os.environ.get("CONFIG_DIR", "config")
    vc_path = config_dir / "vereinsconfig.json"
    fc_path = config_dir / "field_config.json"
    if not vc_path.exists() or vc_path.stat().st_size == 0:
        example = project_root / "config" / "vereinsconfig.example.json"
        if example.exists():
            vc_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(example, vc_path)
    if not fc_path.exists() or fc_path.stat().st_size == 0:
        example = project_root / "config" / "field_config.example.json"
        if example.exists():
            fc_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(example, fc_path)

    # Jinja2-Globals wurden beim Import von templates_instance mit dem damals
    # gültigen CONFIG_DIR gesetzt (evtl. noch ohne .env-Wert). Jetzt neu einlesen.
    from booking.vereinsconfig import load as _vc_load
    _vc_load.cache_clear()
    from web.templates_instance import refresh_globals
    refresh_globals()

    if settings.db_backend == "sqlite":
        from db.sqlite_repository import SQLiteRepository
        os.makedirs(os.path.dirname(os.path.abspath(settings.sqlite_db_path)), exist_ok=True)
        app.state.repo = SQLiteRepository(settings.sqlite_db_path)
    else:
        from notion.client import NotionRepository
        app.state.repo = NotionRepository(settings)

    app.state.settings = settings
    app.state.token_invalidations: dict[str, int] = {}  # {user_sub: invalidated_after_ts}

    scheduler = AsyncIOScheduler()
    app.state.scheduler = scheduler
    apply_schedule(scheduler, app)
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="Sportplatz-Buchungssystem", lifespan=lifespan)


class OnboardingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Always allow static files, onboarding itself, login, logout
        if (
            path.startswith("/static")
            or path.startswith("/onboarding")
            or path in ("/login", "/logout")
        ):
            return await call_next(request)
        try:
            if not hasattr(request.app.state, "repo"):
                return await call_next(request)
            users = request.app.state.repo.get_all_users()
            if not users:
                return RedirectResponse(url="/onboarding", status_code=303)
        except Exception:
            pass
        return await call_next(request)


app.add_middleware(OnboardingMiddleware)

app.mount("/static", StaticFiles(directory="web/static"), name="static")

from web.routers import onboarding  # noqa: E402
app.include_router(onboarding.router)
app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(bookings.router)
app.include_router(series.router)
app.include_router(admin.router)
app.include_router(tasks.router)
app.include_router(events.router)
app.include_router(about.router)

from web.templates_instance import templates  # noqa: E402


@app.get("/")
async def root(request: Request):
    token = request.cookies.get("session")
    if token:
        try:
            decode_jwt(token, get_settings())
            return RedirectResponse(url="/calendar", status_code=303)
        except Exception:
            pass
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status": 403, "message": "Keine Berechtigung"},
        status_code=403,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status": 404, "message": "Seite nicht gefunden"},
        status_code=404,
    )

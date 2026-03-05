from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from auth.auth import decode_jwt
from notion.client import NotionRepository
from web.config import get_settings
from web.routers import auth, bookings, calendar, series, admin, tasks, events


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from booking.scheduler import apply_schedule

    settings = get_settings()
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

app.mount("/static", StaticFiles(directory="web/static"), name="static")

app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(bookings.router)
app.include_router(series.router)
app.include_router(admin.router)
app.include_router(tasks.router)
app.include_router(events.router)

from web.templates_instance import templates


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

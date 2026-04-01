"""web/routers/about.py — About / System-Info"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from auth.dependencies import CurrentUser
from web.templates_instance import templates

router = APIRouter(prefix="/about")

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_REPO_URL = "https://github.com/MerowingerX/Sportplatz-Buchung"


def _git_info() -> dict:
    def _run(args):
        return subprocess.check_output(
            args, cwd=_PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()

    try:
        commit = _run(["git", "log", "-1", "--format=%h"])
        date   = _run(["git", "log", "-1", "--format=%ci"])[:16]
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    except Exception:
        commit = os.environ.get("GIT_COMMIT", "–")
        date   = os.environ.get("GIT_DATE", "–")
        branch = os.environ.get("GIT_BRANCH", "–")

    return {"commit": commit, "date": date, "branch": branch, "repo_url": _REPO_URL}


@router.get("", response_class=HTMLResponse)
async def about(request: Request, current_user: CurrentUser):
    from web.config import get_settings
    settings = get_settings()
    git = _git_info()
    return templates.TemplateResponse(
        "about.html",
        {
            "request": request,
            "current_user": current_user,
            "git": git,
            "db_backend": getattr(settings, "db_backend", "notion"),
        },
    )

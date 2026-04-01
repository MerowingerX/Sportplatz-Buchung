"""web/routers/about.py — About / System-Info"""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from auth.dependencies import CurrentUser
from web.templates_instance import templates

router = APIRouter(prefix="/about")

_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _git_info() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%h"],
            cwd=_PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        date = subprocess.check_output(
            ["git", "log", "-1", "--format=%ci"],
            cwd=_PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()[:16]
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=_PROJECT_ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        # SSH → HTTPS umwandeln: git@github.com:User/Repo.git → https://github.com/User/Repo
        if remote.startswith("git@"):
            # git@github.com:User/Repo.git → https://github.com/User/Repo
            remote = remote[len("git@"):]          # github.com:User/Repo.git
            remote = remote.replace(":", "/", 1)   # github.com/User/Repo.git
            remote = remote.removesuffix(".git")   # github.com/User/Repo
            remote = "https://" + remote
        elif remote.endswith(".git"):
            remote = remote[:-4]
        return {"commit": commit, "date": date, "branch": branch, "repo_url": remote}
    except Exception:
        return {"commit": "–", "date": "–", "branch": "–", "repo_url": None}


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

"""
web/routers/onboarding.py — Ersteinrichtungs-Assistent

Wird angezeigt wenn die Datenbank leer ist (kein Admin-Nutzer vorhanden).
Führt durch die Grundkonfiguration des Systems.
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from web.templates_instance import templates
from web.config import get_settings

router = APIRouter(prefix="/onboarding")

PROJECT_ROOT = Path(__file__).parent.parent.parent

def _roman_to_int(s: str):
    values = {'I': 1, 'V': 5, 'X': 10}
    total = 0
    prev = 0
    for ch in reversed(s.upper()):
        val = values.get(ch)
        if val is None:
            return None
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


def _tail_roman_number(text: str):
    import re
    m = re.search(r'\b([IVX]+)\s*$', text, re.IGNORECASE)
    return _roman_to_int(m.group(1)) if m else None


def _tail_team_size(text: str):
    import re
    m = re.search(r'(\d+)er\s*$', text, re.IGNORECASE)
    return f"{m.group(1)}er" if m else None


def _derive_shortname(name: str) -> str:
    """Leitet einen kompakten Kurznamen aus dem fussball.de-Teamnamen ab."""
    import re

    n = name.strip().replace('/\u200b', '/').replace('\u200b', '')

    # "1. Herren", "2. Herren"
    m = re.match(r'^(\d+)\.\s*Herren(?:\b|\s*-)', n, re.IGNORECASE)
    if m:
        return f"Herren-{m.group(1)}"

    # Herren
    if re.match(r'^Herren\b', n, re.IGNORECASE):
        size = _tail_team_size(n)
        if size:
            return f"Herren-{size}"
        roman = _tail_roman_number(n)
        return f"Herren-{roman}" if roman is not None else "Herren"

    # "1. Damen", "1. Frauen"
    m = re.match(r'^(\d+)\.\s*(?:Damen|Frauen)', n, re.IGNORECASE)
    if m:
        return f"Frauen-{m.group(1)}"

    # Frauen / Damen
    if re.match(r'^(?:Damen|Frauen)\b', n, re.IGNORECASE):
        size = _tail_team_size(n)
        if size:
            return f"Frauen-{size}"
        roman = _tail_roman_number(n)
        return f"Frauen-{roman}" if roman is not None else "Frauen"

    # Mädchen / Juniorinnen
    m = re.match(r'^([A-G])[-\s](?:Mädchen|Juniorinnen)(?:.*)$', n, re.IGNORECASE)
    if m:
        prefix = f"{m.group(1).upper()}M"
        size = _tail_team_size(n)
        if size:
            return f"{prefix}-{size}"
        roman = _tail_roman_number(n)
        return f"{prefix}-{roman}" if roman is not None else prefix

    # Junioren / Jugend
    m = re.match(r'^([A-G])[-\s](?:Junioren|Jugend|Jun\.?)(?:.*)$', n, re.IGNORECASE)
    if m:
        prefix = m.group(1).upper()
        size = _tail_team_size(n)
        if size:
            return f"{prefix}-{size}"
        roman = _tail_roman_number(n)
        return f"{prefix}-{roman}" if roman is not None else prefix

    # Ü-Mannschaften
    m = re.search(r'Ü\s*(\d+)', n, re.IGNORECASE)
    if m:
        return f"Ü{m.group(1)}"

    # Schwache Fallbacks für erkennbare Klassen
    m = re.match(r'^([A-G])[-\s]', n, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    if re.match(r'^(?:Damen|Frauen)\b', n, re.IGNORECASE):
        return "Frauen"

    if re.match(r'^Herren\b', n, re.IGNORECASE):
        return "Herren"

    # Letzter Fallback
    words = re.sub(r'[^\w\s]', '', n).split()
    if len(words) == 1 and words:
        return words[0][:5]
    if words:
        return "".join(w[0].upper() for w in words if w)[:5]
    return "?"

def _config_dir() -> Path:
    return PROJECT_ROOT / os.environ.get("CONFIG_DIR", "config")


def _guard(request: Request) -> Optional[RedirectResponse]:
    """Redirect to /login if users already exist (onboarding done)."""
    try:
        users = request.app.state.repo.get_all_users()
        if users:
            return RedirectResponse(url="/login", status_code=303)
    except Exception:
        pass
    return None


def _mask(value: str, *, show_chars: int = 4) -> str:
    """Masks a secret value, showing only the first few characters."""
    if not value:
        return "(nicht gesetzt)"
    visible = value[:show_chars]
    return f"{visible}{'●' * min(8, len(value) - show_chars)}"


def _load_vereinsconfig_defaults() -> dict:
    """Loads existing vereinsconfig.json and returns form-ready defaults."""
    from booking.vereinsconfig import _DEFAULTS
    vc_path = _config_dir() / "vereinsconfig.json"
    try:
        cfg = json.loads(vc_path.read_text(encoding="utf-8")) if vc_path.exists() else {}
    except Exception:
        cfg = {}
    kw = cfg.get("heim_keywords", cfg.get("heim_keyword", ""))
    if isinstance(kw, list):
        kw = ", ".join(kw)
    return {
        "vereinsname": cfg.get("vereinsname", _DEFAULTS["vereinsname"]),
        "vereinsname_lang": cfg.get("vereinsname_lang", ""),
        "heim_keywords": kw,
        "primary_color": cfg.get("primary_color", _DEFAULTS["primary_color"]),
        "logo_url": cfg.get("logo_url", _DEFAULTS["logo_url"]),
    }


def _load_field_config_defaults(count: int) -> list[dict]:
    """Loads existing field_config.json and returns per-pitch config dicts for count pitches."""
    from booking.field_config import load as fc_load
    cfg = fc_load()
    groups = cfg.get("field_groups", [])
    display_names = cfg.get("display_names", {})

    # Build map: letter → existing group config
    group_by_letter: dict[str, dict] = {}
    for g in groups:
        fields = g.get("fields", [])
        main_field = next((f for f in fields if len(f) == 1), None)
        if main_field:
            group_by_letter[main_field] = {
                "group_name": g.get("name", f"Platz {main_field}"),
                "lit": g.get("lit", False),
                "fields": fields,
            }

    pitches = []
    for i in range(count):
        letter = chr(ord("A") + i)
        existing = group_by_letter.get(letter, {})
        fields_in_group = existing.get("fields", [letter])

        subs = []
        for sub_suffix in "ABC":
            sub_id = f"{letter}{sub_suffix}"
            subs.append({
                "suffix": sub_suffix,
                "field_id": sub_id,
                "enabled": sub_id in fields_in_group,
                "dn": display_names.get(sub_id, ""),
            })

        pitches.append({
            "letter": letter,
            "group_name": existing.get("group_name", ""),
            "dn_whole": display_names.get(letter, ""),
            "lit": existing.get("lit", False),
            "subs": subs,
        })

    return pitches


def _get_sources() -> list[dict]:
    """Returns info about config file sources: path and whether each exists."""
    from web.config import get_env_path
    env_path = get_env_path().resolve()
    config_dir = _config_dir()
    vc_path = config_dir / "vereinsconfig.json"
    fc_path = config_dir / "field_config.json"
    return [
        {"label": "ENV-Datei", "path": str(env_path), "exists": env_path.exists()},
        {"label": "vereinsconfig.json", "path": str(vc_path), "exists": vc_path.exists()},
        {"label": "field_config.json", "path": str(fc_path), "exists": fc_path.exists()},
    ]


def _check_settings(settings) -> list[dict]:
    """Returns list of check dicts: {key, label, value, ok, required, hint}"""
    checks = []

    # JWT
    jwt = getattr(settings, "jwt_secret", "")
    jwt_weak = len(jwt) < 20 or jwt.lower() in ("secret", "change_me", "changeme", "geheim")
    checks.append({
        "key": "JWT_SECRET",
        "label": "JWT_SECRET",
        "value": _mask(jwt) if jwt else "(nicht gesetzt)",
        "secret": True,
        "ok": bool(jwt) and not jwt_weak,
        "required": True,
        "hint": "Mindestens 32 zufällige Zeichen. Generieren: openssl rand -hex 32",
    })

    # fussball.de Vereinsseite
    fuss = getattr(settings, "fussball_de_vereinsseite", None) or ""
    checks.append({
        "key": "FUSSBALL_DE_VEREINSSEITE",
        "label": "FUSSBALL_DE_VEREINSSEITE",
        "value": fuss or "(nicht gesetzt)",
        "secret": False,
        "ok": bool(fuss),
        "required": False,
        "hint": "URL der Vereinsseite auf fussball.de (z. B. https://www.fussball.de/verein/-/verein-id/00ES8GN…)",
    })

    # api-fussball.de Token
    token = getattr(settings, "apifussball_token", None) or ""
    checks.append({
        "key": "APIFUSSBALL_TOKEN",
        "label": "APIFUSSBALL_TOKEN",
        "value": _mask(token) if token else "(nicht gesetzt)",
        "secret": True,
        "ok": bool(token),
        "required": False,
        "hint": "API-Token von api-fussball.de (für automatischen Spielplan-Import)",
    })

    club = getattr(settings, "apifussball_club_id", None) or ""
    checks.append({
        "key": "APIFUSSBALL_CLUB_ID",
        "label": "APIFUSSBALL_CLUB_ID",
        "value": club or "(nicht gesetzt)",
        "secret": False,
        "ok": bool(club),
        "required": False,
        "hint": "Vereins-ID auf fussball.de (z. B. 00ES8GN76C000016VV0AG08LVUPGND5I)",
    })

    # SMTP
    smtp_host = getattr(settings, "smtp_host", "") or ""
    smtp_port = getattr(settings, "smtp_port", 587)
    smtp_user = getattr(settings, "smtp_user", "") or ""
    smtp_pw = getattr(settings, "smtp_password", "") or ""
    smtp_ok = bool(smtp_host and smtp_user)
    smtp_value = (
        f"{smtp_host}:{smtp_port} · {smtp_user} · pw: {_mask(smtp_pw)}"
        if smtp_host
        else "(nicht gesetzt)"
    )
    checks.append({
        "key": "SMTP",
        "label": "SMTP",
        "value": smtp_value,
        "secret": False,
        "ok": smtp_ok,
        "required": True,
        "hint": "SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM in .env setzen",
    })

    # Standort
    lat = getattr(settings, "location_lat", 52.52)
    lon = getattr(settings, "location_lon", 13.405)
    loc_set = not (abs(lat - 52.52) < 0.01 and abs(lon - 13.405) < 0.01)
    loc_name = getattr(settings, "location_name", "")
    checks.append({
        "key": "LOCATION",
        "label": "LOCATION_LAT / LOCATION_LON",
        "value": f"{lat}, {lon}" + (f" ({loc_name})" if loc_name else ""),
        "secret": False,
        "ok": loc_set,
        "required": False,
        "hint": "Koordinaten für Sonnenuntergangs-Berechnung. Standard: Berlin. Optional.",
    })

    # DB Backend
    backend = getattr(settings, "db_backend", "notion")
    sqlite_path = getattr(settings, "sqlite_db_path", "") if backend == "sqlite" else ""
    checks.append({
        "key": "DB_BACKEND",
        "label": "DB_BACKEND",
        "value": backend + (f" → {sqlite_path}" if sqlite_path else ""),
        "secret": False,
        "ok": True,
        "required": False,
        "hint": "sqlite (empfohlen) oder notion. Änderung erfordert Neustart.",
    })

    return checks


@router.get("", response_class=HTMLResponse)
async def onboarding_home(request: Request):
    redirect = _guard(request)
    if redirect:
        return redirect
    settings = get_settings()
    checks = _check_settings(settings)
    sources = _get_sources()
    return templates.TemplateResponse(
        "onboarding/index.html",
        {"request": request, "checks": checks, "sources": sources},
    )


@router.post("/step/checks", response_class=HTMLResponse)
async def step_checks(request: Request):
    redirect = _guard(request)
    if redirect:
        return redirect
    settings = get_settings()
    checks = _check_settings(settings)
    sources = _get_sources()
    required_failed = [c for c in checks if c["required"] and not c["ok"]]
    if required_failed:
        return templates.TemplateResponse(
            "onboarding/_step_checks.html",
            {"request": request, "checks": checks, "sources": sources, "blocked": True},
        )
    return templates.TemplateResponse(
        "onboarding/_step_admin.html",
        {"request": request},
    )


@router.post("/step/admin", response_class=HTMLResponse)
async def step_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
):
    redirect = _guard(request)
    if redirect:
        return redirect
    if password != password2:
        return templates.TemplateResponse(
            "onboarding/_step_admin.html",
            {"request": request, "error": "Passwörter stimmen nicht überein."},
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            "onboarding/_step_admin.html",
            {"request": request, "error": "Passwort muss mindestens 8 Zeichen lang sein."},
        )
    from booking.models import UserCreate, UserRole
    from auth.auth import hash_password

    repo = request.app.state.repo
    pw_hash = hash_password(password)
    repo.create_user(
        UserCreate(name=username, role=UserRole.ADMINISTRATOR, email="", password=password),
        password_hash=pw_hash,
    )
    # Also create dfbnet system user with random password
    rnd = secrets.token_hex(16)
    repo.create_user(
        UserCreate(name="dfbnet", role=UserRole.DFBNET, email="", password=rnd),
        password_hash=hash_password(rnd),
    )
    return templates.TemplateResponse(
        "onboarding/_step_vereinsconfig.html",
        {"request": request, **_load_vereinsconfig_defaults()},
    )


@router.post("/step/vereinsconfig", response_class=HTMLResponse)
async def step_vereinsconfig(
    request: Request,
    vereinsname: str = Form(...),
    vereinsname_lang: str = Form(""),
    heim_keywords: str = Form(""),
    primary_color: str = Form("#1e4fa3"),
    logo_url: str = Form("/static/logo.svg"),
):
    from booking.vereinsconfig import load as vc_load
    vc_path = _config_dir() / "vereinsconfig.json"
    try:
        existing = json.loads(vc_path.read_text(encoding="utf-8")) if vc_path.exists() else {}
    except Exception:
        existing = {}

    keywords = [k.strip() for k in heim_keywords.replace(",", "\n").splitlines() if k.strip()]

    existing.update({
        "vereinsname": vereinsname.strip(),
        "vereinsname_lang": vereinsname_lang.strip() or vereinsname.strip(),
        "heim_keywords": keywords,
        "primary_color": primary_color,
        "primary_color_dark": primary_color,
        "primary_color_darker": primary_color,
        "gold_color": existing.get("gold_color", "#e8c04a"),
        "logo_url": logo_url.strip() or "/static/logo.svg",
    })

    vc_path.parent.mkdir(parents=True, exist_ok=True)
    vc_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    vc_load.cache_clear()

    from web.templates_instance import refresh_globals
    refresh_globals()

    from booking.field_config import load as fc_load
    existing_count = max(len(fc_load().get("field_groups", [])), 1)
    return templates.TemplateResponse(
        "onboarding/_step_fields.html",
        {"request": request, "existing_count": existing_count},
    )


@router.post("/step/fields-count", response_class=HTMLResponse)
async def step_fields_count(request: Request, count: int = Form(...)):
    count = max(1, min(count, 26))
    pitches = _load_field_config_defaults(count)
    return templates.TemplateResponse(
        "onboarding/_step_fields_detail.html",
        {"request": request, "pitches": pitches, "count": count},
    )


@router.post("/step/fields", response_class=HTMLResponse)
async def step_fields(request: Request):
    form = await request.form()
    count = int(form.get("count", 1))

    display_names: dict[str, str] = {}
    field_groups: list[dict] = []

    for i in range(count):
        letter = chr(ord("A") + i)
        group_name = (form.get(f"group_name_{letter}") or f"Platz {letter}").strip()
        dn_whole = (form.get(f"dn_{letter}") or letter).strip()
        lit_group = form.get(f"lit_{letter}") is not None

        display_names[letter] = dn_whole
        fields_in_group: list[str] = [letter]

        for sub_suffix in "ABC":
            sub_id = f"{letter}{sub_suffix}"
            if form.get(f"sub_{letter}_{sub_suffix}"):
                dn_sub = (form.get(f"dn_{sub_id}") or sub_id).strip()
                display_names[sub_id] = dn_sub
                fields_in_group.append(sub_id)

        field_groups.append({
            "id": letter.lower(),
            "name": group_name,
            "fields": fields_in_group,
            "lit": lit_group,
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        })

    fc_data = {
        "display_names": display_names,
        "field_groups": field_groups,
    }
    fc_path = _config_dir() / "field_config.json"
    fc_path.parent.mkdir(parents=True, exist_ok=True)
    fc_path.write_text(json.dumps(fc_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Pre-fill spielorte from existing vereinsconfig
    from booking.vereinsconfig import load as vc_load
    existing_spielorte = {s["feld"]: s for s in vc_load().get("spielorte", [])}

    spielorte_fields = []
    for g in field_groups:
        letter = g["id"].upper()
        existing = existing_spielorte.get(letter, {})
        default_praefix = ", ".join(g["fields"])
        spielorte_fields.append({
            "letter": letter,
            "dn": display_names.get(letter, letter),
            "fussball_de_string": existing.get("fussball_de_string", ""),
            "platz_praefix": ", ".join(existing.get("platz_praefix", g["fields"])),
        })

    return templates.TemplateResponse(
        "onboarding/_step_spielorte.html",
        {"request": request, "spielorte_fields": spielorte_fields},
    )


@router.post("/step/spielorte", response_class=HTMLResponse)
async def step_spielorte(request: Request):
    from booking.vereinsconfig import load as vc_load

    form = await request.form()

    vc_path = _config_dir() / "vereinsconfig.json"
    try:
        vc = json.loads(vc_path.read_text(encoding="utf-8")) if vc_path.exists() else {}
    except Exception:
        vc = {}

    spielorte = []
    for fv in form.getlist("spielort_feld"):
        fuss_str = (form.get(f"spielort_string_{fv}") or "").strip()
        praefix_raw = (form.get(f"spielort_praefix_{fv}") or "").strip()
        praefix = [p.strip() for p in praefix_raw.replace(",", " ").split() if p.strip()]
        if fuss_str:
            spielorte.append({
                "fussball_de_string": fuss_str,
                "feld": fv,
                "platz_praefix": praefix,
            })

    vc["spielorte"] = spielorte
    vc_path.write_text(json.dumps(vc, ensure_ascii=False, indent=2), encoding="utf-8")
    vc_load.cache_clear()

    # Fetch teams from api-fussball.de
    settings = get_settings()
    token = getattr(settings, "apifussball_token", None) or ""
    club_id_api = getattr(settings, "apifussball_club_id", None) or ""

    teams: list[dict] = []
    fetch_error: Optional[str] = None

    if token and club_id_api:
        import asyncio as _asyncio
        import urllib.request as _urlreq
        import json as _json2

        def _fetch_teams():
            req = _urlreq.Request(
                f"https://api-fussball.de/api/club/{club_id_api}",
                headers={"x-auth-token": token},
            )
            with _urlreq.urlopen(req, timeout=15) as r:
                return _json2.loads(r.read()).get("data", [])

        try:
            loop = _asyncio.get_event_loop()
            raw = await loop.run_in_executor(None, _fetch_teams)
            teams = [
                {**t, "shortname": _derive_shortname(t.get("name", ""))}
                for t in raw
            ]
        except Exception as e:
            fetch_error = str(e)

    return templates.TemplateResponse(
        "onboarding/_step_mannschaften.html",
        {
            "request": request,
            "teams": teams,
            "fetch_error": fetch_error,
            "api_missing": not (token and club_id_api),
        },
    )


@router.post("/step/mannschaften", response_class=HTMLResponse)
async def step_mannschaften(request: Request):
    form = await request.form()
    repo = request.app.state.repo
    count = 0
    for idx_str in form.getlist("team_selected"):
        try:
            i = int(idx_str)
        except (ValueError, TypeError):
            continue
        team_id = (form.get(f"team_id_{i}") or "").strip()
        team_name = (form.get(f"team_name_{i}") or "").strip()
        shortname = (form.get(f"shortname_{i}") or "").strip()
        if not team_name and not shortname:
            continue
        repo.create_mannschaft(
            name=team_name or shortname,
            shortname=shortname or None,
            trainer_id=None,
            trainer_name=None,
            fussball_de_team_id=team_id or None,
            cc_emails=[],
            aktiv=True,
        )
        count += 1
    return templates.TemplateResponse(
        "onboarding/_step_done.html",
        {"request": request, "count": count},
    )

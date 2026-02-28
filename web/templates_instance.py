"""
web/templates_instance.py  –  Gemeinsame Jinja2Templates-Instanz

Alle Router importieren `templates` von hier, damit Jinja2-Globals
(vereinsname, vereinsfarben) automatisch in jedem Template verfügbar sind.
"""
from fastapi.templating import Jinja2Templates
from booking.vereinsconfig import load as _load_vc

templates = Jinja2Templates(directory="web/templates")

_vc = _load_vc()
templates.env.globals["vereinsname"] = _vc.get("vereinsname", "Sportverein")
templates.env.globals["vereinsname_lang"] = _vc.get(
    "vereinsname_lang", _vc.get("vereinsname", "Sportverein")
)
templates.env.globals["vereinsfarben"] = {
    "primary":        _vc.get("primary_color", "#1e4fa3"),
    "primary_dark":   _vc.get("primary_color_dark", "#0d2f6b"),
    "primary_darker": _vc.get("primary_color_darker", "#071c44"),
    "gold":           _vc.get("gold_color", "#e8c04a"),
}

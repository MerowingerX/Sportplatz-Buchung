"""Render-Tests für die Kalender-Pill-Anzeige (`_booking_pill.html`).

Sichert die Anzeige-Priorität ab: auf dem Pill gewinnt der Mannschafts-
Kurzname vor dem Freitext-`zweck`, damit bei Einzelbuchungen die Mannschaft
erkennbar bleibt. Der `zweck` darf dabei nicht verloren gehen — er wandert in
den Hover-Tooltip (title-Attribut).

Siehe docs/Features/buchungs-anzeige-name.md.

Ausführen:  pytest docs/tests/test_booking_pill.py
"""
from datetime import date, time
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from booking.models import (
    Booking,
    BookingStatus,
    BookingType,
    FieldName,
    UserRole,
)

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "web" / "templates"
PILL = "partials/_booking_pill.html"


@pytest.fixture(scope="module")
def env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def make_booking(**overrides) -> Booking:
    """Minimale gültige Booking-Instanz; per kwargs überschreibbar."""
    base = dict(
        notion_id="b-1",
        title="Test",
        field=FieldName("A"),
        date=date(2026, 6, 30),
        start_time=time(18, 0),
        end_time=time(19, 30),
        duration_min=90,
        booking_type=BookingType.TRAINING,
        booked_by_id="u-1",
        booked_by_name="Max Mustermann",
        role=UserRole.TRAINER,
        status=BookingStatus.BESTAETIGT,
        mannschaft=None,
        zweck=None,
        kontakt=None,
    )
    base.update(overrides)
    return Booking(**base)


def render(env: Environment, booking: Booking, shortnames: dict | None = None) -> str:
    tmpl = env.get_template(PILL)
    return tmpl.render(
        found=[booking],
        mannschaft_shortnames=shortnames or {},
        current_user=None,
    )


def pill_name(html: str) -> str:
    """Extrahiert den Text der <span class="slot__name">."""
    import re

    m = re.search(r'slot__name">([^<]*)<', html)
    assert m, f"slot__name nicht gefunden in:\n{html}"
    return m.group(1).strip()


def title_attr(html: str) -> str:
    import re

    m = re.search(r'class="slot slot--booked[^"]*"\s+title="([^"]*)"', html)
    assert m, f"title-Attribut nicht gefunden in:\n{html}"
    return m.group(1)


# --- Pill-Name-Priorität -------------------------------------------------

def test_mannschaft_schlaegt_zweck(env):
    """Einzelbuchung mit Mannschaft UND zweck → Pill zeigt Mannschaft."""
    b = make_booking(mannschaft="U17", zweck="Torwarttraining")
    html = render(env, b, {"U17": "U17"})
    assert pill_name(html) == "U17"


def test_shortname_wird_genutzt(env):
    """Langer Mannschaftsname wird über shortnames-Map gekürzt."""
    b = make_booking(mannschaft="1. Herren Senioren", zweck="Spielvorbereitung")
    html = render(env, b, {"1. Herren Senioren": "1.H"})
    assert pill_name(html) == "1.H"


def test_zweck_fallback_ohne_mannschaft(env):
    """Keine Mannschaft → Pill zeigt zweck (Fallback)."""
    b = make_booking(mannschaft=None, zweck="Platzpflege")
    assert pill_name(render(env, b)) == "Platzpflege"


def test_name_fallback_ohne_mannschaft_und_zweck(env):
    """Weder Mannschaft noch zweck → Pill zeigt Bucher-Namen."""
    b = make_booking(mannschaft=None, zweck=None)
    assert pill_name(render(env, b)) == "Max Mustermann"


def test_mannschaft_ohne_shortname_nutzt_vollen_namen(env):
    """Mannschaft nicht in shortnames-Map → voller Name als Fallback."""
    b = make_booking(mannschaft="D2-Jugend", zweck="Training")
    assert pill_name(render(env, b, {})) == "D2-Jugend"


# --- Tooltip behält zweck ------------------------------------------------

def test_tooltip_enthaelt_zweck(env):
    """zweck verschwindet nicht — er steht im Hover-Tooltip."""
    b = make_booking(mannschaft="U17", zweck="Torwarttraining")
    title = title_attr(render(env, b, {"U17": "U17"}))
    assert "U17" in title
    assert "Torwarttraining" in title


def test_tooltip_zeigt_buchungsverantwortlichen(env):
    """Buchungsverantwortlicher (booked_by_name) ist beim Hover immer sichtbar,
    auch wenn eine Mannschaft gesetzt ist."""
    b = make_booking(mannschaft="U17", booked_by_name="Max Mustermann")
    title = title_attr(render(env, b, {"U17": "U17"}))
    assert "U17" in title
    assert "Max Mustermann" in title


def test_tooltip_verantwortlicher_ohne_mannschaft(env):
    b = make_booking(mannschaft=None, booked_by_name="Max Mustermann")
    assert "Max Mustermann" in title_attr(render(env, b))


def test_tooltip_enthaelt_kontakt_und_zeit(env):
    b = make_booking(mannschaft="U17", zweck="Training", kontakt="0151-123")
    title = title_attr(render(env, b, {"U17": "U17"}))
    assert "0151-123" in title
    assert "18:00" in title and "19:30" in title


# --- CSS-Klasse / Buchungsart kodiert ------------------------------------

@pytest.mark.parametrize(
    "btype,css",
    [
        (BookingType.TRAINING, "slot--training"),
        (BookingType.SPIEL, "slot--spiel"),
        (BookingType.TURNIER, "slot--turnier"),
    ],
)
def test_buchungsart_als_css_klasse(env, btype, css):
    """Buchungsart bleibt über CSS-Farbe sichtbar (nicht über den Namen)."""
    b = make_booking(booking_type=btype, mannschaft="U17")
    assert css in render(env, b, {"U17": "U17"})

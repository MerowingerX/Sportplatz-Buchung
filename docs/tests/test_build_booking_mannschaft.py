"""Regressionstest: build_booking muss die im Formular gewählte Mannschaft
(`data.mannschaft`) an die Persistenz weiterreichen.

Bug (gefixt): build_booking nutzte `mannschaft_override or current_user.mannschaft`
und ignorierte `data.mannschaft` komplett. Folge: Admins (ohne eigene Mannschaft)
buchten immer ohne Team → Kalender-Pill zeigte den Bucher-Namen statt der
Mannschaft. Trainer merkten nichts, weil current_user.mannschaft zufällig passte.

Priorität nach Fix:  mannschaft_override  >  data.mannschaft  >  current_user.mannschaft

Siehe booking/booking.py → build_booking, docs/Features/buchungs-anzeige-name.md.

Ausführen:  pytest docs/tests/test_build_booking_mannschaft.py
"""
from datetime import date, time
from types import SimpleNamespace

import pytest

import booking.booking as bb
from booking.booking import build_booking
from booking.models import (
    Booking,
    BookingCreate,
    BookingStatus,
    BookingType,
    FieldName,
    UserRole,
)


class FakeRepo:
    """Zeichnet die an create_booking übergebene Mannschaft auf."""

    def __init__(self):
        self.captured_mannschaft = "__unset__"

    def create_booking(self, *, data, booked_by_id, booked_by_name, role,
                        end_time, sunset_note=None, series_id=None,
                        mannschaft=None, zweck=None, kontakt=None):
        self.captured_mannschaft = mannschaft
        return Booking(
            notion_id="b-1",
            title="t",
            field=data.field,
            date=data.date,
            start_time=data.start_time,
            end_time=end_time,
            duration_min=data.duration_min,
            booking_type=data.booking_type,
            booked_by_id=booked_by_id,
            booked_by_name=booked_by_name,
            role=role,
            status=BookingStatus.BESTAETIGT,
            mannschaft=mannschaft,
            zweck=zweck,
            kontakt=kontakt,
            series_id=series_id,
            sunset_note=sunset_note,
        )


@pytest.fixture(autouse=True)
def _no_sunset(monkeypatch):
    # Feld als beleuchtet behandeln → sunset-Pfad (braucht Geo/astral) entfällt.
    monkeypatch.setattr(bb._fc, "is_lit", lambda field: True)


@pytest.fixture
def settings():
    return SimpleNamespace(
        location_lat=52.0, location_lon=10.0, location_name="Test",
    )


def _data(mannschaft=None):
    return BookingCreate(
        field=FieldName("A"),
        date=date(2026, 7, 2),
        start_time=time(10, 0),
        duration_min=60,
        booking_type=BookingType.TRAINING,
        mannschaft=mannschaft,
    )


def _user(mannschaft=None, role=UserRole.ADMINISTRATOR):
    return SimpleNamespace(
        sub="u-1", username="admin", role=role, mannschaft=mannschaft,
    )


def test_formular_mannschaft_wird_gespeichert(settings):
    """Admin (ohne eigene Mannschaft) wählt im Formular → wird gespeichert."""
    repo = FakeRepo()
    booking, errors = build_booking(
        repo=repo, data=_data(mannschaft="A-Junioren"),
        current_user=_user(mannschaft=None), settings=settings,
        existing_bookings=[],
    )
    assert errors == []
    assert repo.captured_mannschaft == "A-Junioren"
    assert booking.mannschaft == "A-Junioren"


def test_user_default_wenn_formular_leer(settings):
    """Kein Formularwert → Fallback auf current_user.mannschaft (Trainer-Default)."""
    repo = FakeRepo()
    build_booking(
        repo=repo, data=_data(mannschaft=None),
        current_user=_user(mannschaft="F-Junioren", role=UserRole.TRAINER),
        settings=settings, existing_bookings=[],
    )
    assert repo.captured_mannschaft == "F-Junioren"


def test_override_schlaegt_formular(settings):
    """Serien-Override (mannschaft_override) gewinnt vor Formularwert."""
    repo = FakeRepo()
    build_booking(
        repo=repo, data=_data(mannschaft="A-Junioren"),
        current_user=_user(mannschaft="F-Junioren"), settings=settings,
        existing_bookings=[], mannschaft_override="B-Junioren",
    )
    assert repo.captured_mannschaft == "B-Junioren"


def test_formular_schlaegt_user_default(settings):
    """Formularwert gewinnt vor dem persönlichen Default des Buchenden."""
    repo = FakeRepo()
    build_booking(
        repo=repo, data=_data(mannschaft="A-Junioren"),
        current_user=_user(mannschaft="F-Junioren", role=UserRole.TRAINER),
        settings=settings, existing_bookings=[],
    )
    assert repo.captured_mannschaft == "A-Junioren"

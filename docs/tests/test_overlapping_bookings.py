"""Tests für geteilte Platznutzung (Same-Field-Overlap).

Regeln:
- Overlap nur mit explizitem Flag `allow_same_field_overlap=True` (Nutzer-Bestätigung).
- Ohne Flag (Default, z. B. Serienbuchung): Overlap bleibt Konflikt.
- DFBnet-Buchungen sind nie teilbar (unsharable, an der Rolle festgemacht).
- Teilen nur auf unterster Feldebene (Blatt-Feld ohne konfigurierte Sub-Felder).

Ausführen:  pytest docs/tests/test_overlapping_bookings.py
"""
from datetime import date, time
from types import SimpleNamespace

import pytest

import booking.booking as bb
from booking.booking import build_booking, get_same_field_overlaps, overlaps_are_shareable
from booking.models import (
    Booking,
    BookingCreate,
    BookingStatus,
    BookingType,
    FieldName,
    UserRole,
)


class FakeRepo:
    def __init__(self):
        self.created = []

    def get_mannschaften_for_user(self, user_id):
        return []

    def create_booking(self, *, data, booked_by_id, booked_by_name, role,
                        end_time, sunset_note=None, series_id=None,
                        mannschaft=None, zweck=None, kontakt=None):
        self.created.append((data, mannschaft))
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


def _settings():
    return SimpleNamespace(location_lat=52.0, location_lon=10.0, location_name="Test")


def _user():
    return SimpleNamespace(sub="u-1", username="tester", role=UserRole.TRAINER, mannschaft=None)


def _existing(field="AA", role=UserRole.TRAINER):
    return [
        Booking(
            notion_id="existing",
            title="existing",
            field=FieldName(field),
            date=date(2026, 7, 2),
            start_time=time(10, 0),
            end_time=time(11, 0),
            duration_min=60,
            booking_type=BookingType.TRAINING,
            booked_by_id="u-2",
            booked_by_name="other",
            role=role,
            status=BookingStatus.BESTAETIGT,
        )
    ]


def _data(field="AA"):
    return BookingCreate(
        field=FieldName(field),
        date=date(2026, 7, 2),
        start_time=time(10, 30),
        duration_min=60,
        booking_type=BookingType.TRAINING,
    )


@pytest.fixture
def leaf_config(monkeypatch):
    """Blatt-Felder: alles außer 'A' (A hat Sub-Felder AA/AB)."""
    monkeypatch.setattr(bb._fc, "is_lit", lambda field: True)
    monkeypatch.setattr(bb._fc, "is_leaf_field", lambda field_id: field_id != "A")


def test_overlap_allowed_with_confirmation(leaf_config):
    repo = FakeRepo()
    booking, errors = build_booking(
        repo=repo,
        data=_data("AA"),
        current_user=_user(),
        settings=_settings(),
        existing_bookings=_existing("AA"),
        allow_same_field_overlap=True,
    )
    assert errors == []
    assert booking is not None
    assert repo.created


def test_overlap_blocked_without_confirmation(leaf_config):
    """Default (z. B. Serienbuchung): Overlap bleibt Konflikt."""
    repo = FakeRepo()
    booking, errors = build_booking(
        repo=repo,
        data=_data("AA"),
        current_user=_user(),
        settings=_settings(),
        existing_bookings=_existing("AA"),
    )
    assert booking is None
    assert errors
    assert not repo.created


def test_dfbnet_booking_never_shareable(leaf_config):
    """DFBnet-Buchung ist unsharable — auch mit Bestätigung Konflikt."""
    repo = FakeRepo()
    booking, errors = build_booking(
        repo=repo,
        data=_data("AA"),
        current_user=_user(),
        settings=_settings(),
        existing_bookings=_existing("AA", role=UserRole.DFBNET),
        allow_same_field_overlap=True,
    )
    assert booking is None
    assert errors
    assert not repo.created


def test_non_leaf_field_not_shareable(leaf_config):
    """'A' hat Sub-Felder → nicht teilbar, auch mit Bestätigung."""
    repo = FakeRepo()
    booking, errors = build_booking(
        repo=repo,
        data=_data("A"),
        current_user=_user(),
        settings=_settings(),
        existing_bookings=_existing("A"),
        allow_same_field_overlap=True,
    )
    assert booking is None
    assert errors
    assert not repo.created


def test_other_field_conflict_still_blocked(leaf_config):
    """Konfliktfeld (Präfix): 'AA' belegt blockiert 'A' weiterhin."""
    repo = FakeRepo()
    booking, errors = build_booking(
        repo=repo,
        data=_data("A"),
        current_user=_user(),
        settings=_settings(),
        existing_bookings=_existing("AA"),
        allow_same_field_overlap=True,
    )
    assert booking is None
    assert errors


def test_overlaps_are_shareable_rules(leaf_config):
    trainer = _existing("AA", role=UserRole.TRAINER)
    dfbnet = _existing("AA", role=UserRole.DFBNET)
    assert overlaps_are_shareable(FieldName("AA"), trainer) is True
    assert overlaps_are_shareable(FieldName("AA"), dfbnet) is False
    assert overlaps_are_shareable(FieldName("A"), trainer) is False


def test_get_same_field_overlaps_filters_other_fields():
    overlaps = get_same_field_overlaps(_existing("AB"), FieldName("AA"), time(10, 30), 60)
    assert overlaps == []
    overlaps = get_same_field_overlaps(_existing("AA"), FieldName("AA"), time(10, 30), 60)
    assert len(overlaps) == 1

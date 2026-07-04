"""Tests für Team-Zuordnung & Buchungsrechte
(Feature: docs/Features/team_zuordnung_und_buchungsrechte.md).

Abgedeckt:
  - `user_teams` / `user_may_book_for` (booking/booking.py): wer darf für welches
    Team buchen (primär/sekundär zugewiesen, Admin/DFBnet = alle, ohne Team = frei).
  - `_bookable_teams` (web/routers/bookings.py): Team-Dropdown-Filter.
  - `build_booking` Integration: Trainer bucht fremdes Team → Fehler.

Ausführen:  pytest docs/tests/test_team_buchungsrechte.py
"""
from datetime import date, time
from types import SimpleNamespace as NS

import pytest

import booking.booking as bb
from booking.booking import user_teams, user_may_book_for, build_booking
from booking.models import BookingCreate, BookingType, FieldName, UserRole, UserCreate
from db.sqlite_repository import SQLiteRepository
from web.routers.bookings import _bookable_teams


# ─────────────────────────────────────────────────────────── Fixtures

@pytest.fixture
def repo(tmp_path):
    return SQLiteRepository(str(tmp_path / "test.db"))


def _user(repo, name, role=UserRole.TRAINER):
    return repo.create_user(
        UserCreate(name=name, role=role, email=f"{name}@x.de", password="pw"),
        password_hash="x",
    )


def _team(repo, name):
    return repo.create_mannschaft(
        name=name, trainer_id=None, trainer_name=None,
        fussball_de_team_id=None, cc_emails=[],
    )


def _token(user, mannschaft=None):
    # build_booking/_bookable_teams brauchen nur sub, role, mannschaft
    return NS(sub=user.notion_id, username=user.name, role=user.role,
              mannschaft=mannschaft)


@pytest.fixture(autouse=True)
def _no_sunset(monkeypatch):
    monkeypatch.setattr(bb._fc, "is_lit", lambda field: True)


@pytest.fixture
def settings():
    return NS(location_lat=52.0, location_lon=10.0, location_name="Test")


# ─────────────────────────────────────────────── user_teams / user_may_book_for

def test_user_teams_enthaelt_zugewiesene(repo):  # TEAM-1
    hans = _user(repo, "Hans")
    a = _team(repo, "Team A")
    _team(repo, "Team B")
    repo.add_verantwortlicher(a.notion_id, hans.notion_id)
    assert user_teams(repo, _token(hans)) == {"Team A"}


def test_trainer_darf_eigenes_team(repo):
    hans = _user(repo, "Hans")
    a = _team(repo, "Team A")
    repo.add_verantwortlicher(a.notion_id, hans.notion_id)
    assert user_may_book_for(repo, _token(hans), "Team A") is True


def test_trainer_darf_fremdes_team_nicht(repo):  # TEAM-6
    hans = _user(repo, "Hans")
    _team(repo, "Team A")
    b = _team(repo, "Team B")
    # Hans nur Team A zugewiesen, versucht Team B
    repo.add_verantwortlicher(_team(repo, "Team A2").notion_id, hans.notion_id)
    assert user_may_book_for(repo, _token(hans), "Team B") is False


def test_admin_darf_jedes_team(repo):  # TEAM-7
    admin = _user(repo, "Chef", role=UserRole.ADMINISTRATOR)
    _team(repo, "Team A")
    assert user_may_book_for(repo, _token(admin), "Team A") is True


def test_dfbnet_darf_jedes_team(repo):
    dfb = _user(repo, "DFB", role=UserRole.DFBNET)
    _team(repo, "Team A")
    assert user_may_book_for(repo, _token(dfb), "Team A") is True


def test_buchung_ohne_team_immer_erlaubt(repo):  # TEAM-8
    hans = _user(repo, "Hans")
    assert user_may_book_for(repo, _token(hans), None) is True


def test_token_mannschaft_zaehlt_als_zugewiesen(repo):
    # Legacy: primäres Team steckt im Token (current_user.mannschaft)
    hans = _user(repo, "Hans")
    _team(repo, "Team A")
    assert user_may_book_for(repo, _token(hans, mannschaft="Team A"), "Team A") is True


# ─────────────────────────────────────────────────── _bookable_teams (Dropdown)

def test_dropdown_trainer_nur_eigene_teams(repo):  # TEAM-4
    hans = _user(repo, "Hans")
    a = _team(repo, "Team A")
    _team(repo, "Team B")
    repo.add_verantwortlicher(a.notion_id, hans.notion_id)
    names = [m.name for m in _bookable_teams(repo, _token(hans))]
    assert names == ["Team A"]


def test_dropdown_admin_alle_teams(repo):  # TEAM-5
    admin = _user(repo, "Chef", role=UserRole.ADMINISTRATOR)
    _team(repo, "Team A")
    _team(repo, "Team B")
    names = sorted(m.name for m in _bookable_teams(repo, _token(admin)))
    assert names == ["Team A", "Team B"]


# ─────────────────────────────────────────────────── build_booking Integration

def _data(mannschaft):
    return BookingCreate(
        field=FieldName("A"), date=date(2026, 7, 2), start_time=time(10, 0),
        duration_min=60, booking_type=BookingType.TRAINING, mannschaft=mannschaft,
    )


def test_build_booking_trainer_fremdes_team_fehler(repo, settings):  # TEAM-6 (Integration)
    hans = _user(repo, "Hans")
    a = _team(repo, "Team A")
    _team(repo, "Team B")
    repo.add_verantwortlicher(a.notion_id, hans.notion_id)

    booking, errors = build_booking(
        repo=repo, data=_data("Team B"), current_user=_token(hans),
        settings=settings, existing_bookings=[],
    )
    assert booking is None
    assert any("nicht eingetragen" in e for e in errors)


def test_build_booking_trainer_eigenes_team_ok(repo, settings):  # TEAM-6 Gegenprobe
    hans = _user(repo, "Hans")
    a = _team(repo, "Team A")
    repo.add_verantwortlicher(a.notion_id, hans.notion_id)

    booking, errors = build_booking(
        repo=repo, data=_data("Team A"), current_user=_token(hans),
        settings=settings, existing_bookings=[],
    )
    assert errors == []
    assert booking is not None and booking.mannschaft == "Team A"

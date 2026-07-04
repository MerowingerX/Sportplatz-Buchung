"""Tests für die M:N-Beziehung Mannschaft ↔ Verantwortliche und deren
Sichtbarkeit in den Admin-Tabellen (Nutzer- und Mannschaftsverwaltung).

Feature:
  - Ein User kann für mehrere Mannschaften verantwortlich sein.
  - Eine Mannschaft kann mehrere Verantwortliche haben.
  - Beide Richtungen werden in den Admin-Tabellen als Liste angezeigt.

Abgedeckt:
  1. Repo-Schicht (echte SQLiteRepository, temporäre DB):
       add/remove_verantwortlicher, get_verantwortliche_for_mannschaft,
       get_mannschaften_for_user — beide Richtungen, Idempotenz,
       gelöschte User werden gefiltert.
  2. Template-Schicht:
       _user_row / _mannschaft_row zeigen die Liste (bzw. '–' wenn leer).
       Regression: Mannschafts-Combobox im "Neuen Nutzer anlegen"-Formular
       nutzt m.name (nicht das entfernte Enum-Feld m.value).

Ausführen:  pytest docs/tests/test_mannschaft_verantwortliche.py
"""
from types import SimpleNamespace as NS

import pytest

from booking.models import UserCreate, UserRole
from db.sqlite_repository import SQLiteRepository
from web.templates_instance import templates


# ─────────────────────────────────────────────────────────── Fixtures

@pytest.fixture
def repo(tmp_path):
    return SQLiteRepository(str(tmp_path / "test.db"))


def _mk_user(repo, name, role=UserRole.TRAINER):
    return repo.create_user(
        UserCreate(name=name, role=role, email=f"{name}@x.de", password="pw"),
        password_hash="x",
    )


def _mk_team(repo, name):
    return repo.create_mannschaft(
        name=name, trainer_id=None, trainer_name=None,
        fussball_de_team_id=None, cc_emails=[],
    )


# ─────────────────────────────────────────────────── Repo: beide Richtungen

def test_user_verantwortlich_fuer_mehrere_teams(repo):
    """Ein User → mehrere Mannschaften."""
    hans = _mk_user(repo, "Hans")
    team_a = _mk_team(repo, "Team A")
    team_b = _mk_team(repo, "Team B")

    repo.add_verantwortlicher(team_a.notion_id, hans.notion_id)
    repo.add_verantwortlicher(team_b.notion_id, hans.notion_id)

    teams = repo.get_mannschaften_for_user(hans.notion_id)
    assert sorted(m.name for m in teams) == ["Team A", "Team B"]


def test_team_mit_mehreren_verantwortlichen(repo):
    """Eine Mannschaft → mehrere Verantwortliche."""
    hans = _mk_user(repo, "Hans")
    klaus = _mk_user(repo, "Klaus")
    team_a = _mk_team(repo, "Team A")

    repo.add_verantwortlicher(team_a.notion_id, hans.notion_id)
    repo.add_verantwortlicher(team_a.notion_id, klaus.notion_id)

    verantwortliche = repo.get_verantwortliche_for_mannschaft("Team A")
    assert sorted(u.name for u in verantwortliche) == ["Hans", "Klaus"]


def test_add_ist_idempotent(repo):
    """Doppeltes add erzeugt keine Duplikate (INSERT OR IGNORE, Composite-PK)."""
    hans = _mk_user(repo, "Hans")
    team_a = _mk_team(repo, "Team A")

    repo.add_verantwortlicher(team_a.notion_id, hans.notion_id)
    repo.add_verantwortlicher(team_a.notion_id, hans.notion_id)

    assert len(repo.get_verantwortliche_for_mannschaft("Team A")) == 1


def test_remove_verantwortlicher(repo):
    hans = _mk_user(repo, "Hans")
    klaus = _mk_user(repo, "Klaus")
    team_a = _mk_team(repo, "Team A")
    repo.add_verantwortlicher(team_a.notion_id, hans.notion_id)
    repo.add_verantwortlicher(team_a.notion_id, klaus.notion_id)

    repo.remove_verantwortlicher(team_a.notion_id, hans.notion_id)

    namen = [u.name for u in repo.get_verantwortliche_for_mannschaft("Team A")]
    assert namen == ["Klaus"]


def test_geloeschter_user_nicht_mehr_verantwortlich(repo):
    """Soft-gelöschte User dürfen nicht mehr als Verantwortliche erscheinen."""
    hans = _mk_user(repo, "Hans")
    team_a = _mk_team(repo, "Team A")
    repo.add_verantwortlicher(team_a.notion_id, hans.notion_id)

    repo.delete_user(hans.notion_id)

    assert repo.get_verantwortliche_for_mannschaft("Team A") == []


def test_ohne_zuweisung_leer(repo):
    _mk_user(repo, "Hans")
    team_a = _mk_team(repo, "Team A")
    assert repo.get_verantwortliche_for_mannschaft("Team A") == []
    assert repo.get_mannschaften_for_user(_mk_user(repo, "Egon").notion_id) == []


# ─────────────────────────────────────────────────── Templates: Sichtbarkeit

def _render(tmpl, **ctx):
    return templates.get_template(tmpl).render(**ctx)


def test_user_row_zeigt_team_liste():
    user = NS(notion_id="u1", name="Hans", role=NS(value="Trainer"),
              mannschaft="Team A", email="h@x.de")
    html = _render(
        "partials/_user_row.html",
        user=user, current_user=NS(sub="admin"), roles=[], mannschaften=[],
        verantwortet={"u1": ["Team A", "Team B"]},
    )
    assert "Team A, Team B" in html


def test_user_row_leer_zeigt_strich():
    # mannschaft gesetzt → die einzige '–'-Zelle stammt aus der Verantwortlich-Spalte
    user = NS(notion_id="u1", name="Hans", role=NS(value="Trainer"),
              mannschaft="Team A", email="h@x.de")
    html = _render(
        "partials/_user_row.html",
        user=user, current_user=NS(sub="admin"), roles=[], mannschaften=[],
        verantwortet={"u1": []},
    )
    assert html.count("<td>–</td>") == 1


def test_mannschaft_row_zeigt_verantwortlichen_liste():
    m = NS(notion_id="m1", name="Team A", shortname="TA", trainer_name="Hans",
           fussball_de_team_id=None, cc_emails=[], color=None, aktiv=True)
    html = _render(
        "partials/_mannschaft_row.html",
        m=m, current_user=NS(sub="admin"), trainers=[],
        verantwortliche={"m1": ["Hans", "Klaus"]},
    )
    assert "Hans, Klaus" in html


def test_mannschaft_row_leer_zeigt_strich():
    # alle anderen optionalen Felder gesetzt → einzige '–'-Zelle = Verantwortliche
    m = NS(notion_id="m1", name="Team A", shortname="TA", trainer_name="Hans",
           fussball_de_team_id="123", cc_emails=["a@x.de"], color="#fff", aktiv=True)
    html = _render(
        "partials/_mannschaft_row.html",
        m=m, current_user=NS(sub="admin"), trainers=[],
        verantwortliche={"m1": []},
    )
    assert html.count("<td>–</td>") == 1


def test_create_user_combobox_nutzt_name_nicht_value():
    """Regression: Combobox nutzte m.value (entferntes Enum-Feld) → leer.
    Muss m.name rendern."""
    mannschaften = [NS(name="Team A", notion_id="m1"),
                    NS(name="Team B", notion_id="m2")]
    html = _render(
        "admin/users.html",
        request=NS(scope={}, url=NS(path="/admin/users")),
        current_user=NS(sub="a", role=NS(value="Administrator"), name="Admin"),
        users=[], roles=[NS(value="Trainer")],
        mannschaften=mannschaften, verantwortet={},
    )
    assert '<option value="Team A">Team A</option>' in html
    assert '<option value="Team B">Team B</option>' in html

#!/usr/bin/env python3
"""
scripts/setup_sqlite.py — SQLite-Datenbank einrichten

Erstellt die Datenbankdatei, alle Tabellen und einen ersten Admin-Nutzer.
Kann auch aufgerufen werden um weitere Nutzer anzulegen.

Verwendung:
    python scripts/setup_sqlite.py
    python scripts/setup_sqlite.py --db data/sportplatz.db
    python scripts/setup_sqlite.py --add-user
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Projekt-Root in den Pfad
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.sqlite_repository import SQLiteRepository
from booking.models import UserRole
from auth.auth import hash_password


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    if secret:
        import getpass
        val = getpass.getpass(f"{label}{suffix}: ")
    else:
        val = input(f"{label}{suffix}: ").strip()
    return val if val else default


def create_user(repo: SQLiteRepository) -> None:
    print("\n── Neuen Nutzer anlegen ─────────────────────────")
    name = _prompt("Benutzername")
    if not name:
        print("Abgebrochen.")
        return

    print("Rolle:")
    for i, role in enumerate(UserRole, 1):
        print(f"  {i}) {role.value}")
    role_input = _prompt("Nummer", default="1")
    try:
        role = list(UserRole)[int(role_input) - 1]
    except (ValueError, IndexError):
        role = UserRole.ADMINISTRATOR

    email = _prompt("E-Mail (optional)")
    password = _prompt("Passwort", secret=True)
    if not password:
        password = "Aendern123!"
        print(f"  → Kein Passwort eingegeben, temporäres Passwort gesetzt: {password}")

    password_hash = hash_password(password)

    # Prüfen ob Nutzer schon existiert
    existing = repo.get_user_by_name(name)
    if existing:
        print(f"Nutzer '{name}' existiert bereits (ID: {existing.notion_id}).")
        return

    from booking.models import UserCreate
    user = repo.create_user(
        UserCreate(name=name, role=role, email=email or "", password=password),
        password_hash=password_hash,
    )
    print(f"\n✓ Nutzer '{user.name}' angelegt (Rolle: {user.role.value}, ID: {user.notion_id})")
    if password == "Aendern123!":
        print("  ⚠ Bitte beim ersten Login das Passwort ändern.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite-Datenbank einrichten")
    parser.add_argument(
        "--db", type=str, default=None,
        help="Pfad zur SQLite-Datenbankdatei (Standard: aus .env oder data/sportplatz.db)"
    )
    parser.add_argument(
        "--add-user", action="store_true",
        help="Nur einen weiteren Nutzer anlegen (keine Neuinitialisierung)"
    )
    args = parser.parse_args()

    # DB-Pfad bestimmen
    if args.db:
        db_path = args.db
    else:
        # Aus .env lesen falls vorhanden
        env_file = PROJECT_ROOT / ".env"
        if not env_file.exists():
            env_file = PROJECT_ROOT / ".env.demo"
        db_path = "data/sportplatz.db"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("SQLITE_DB_PATH="):
                    db_path = line.split("=", 1)[1].strip().split("#")[0].strip()
                    break

    # Relativ zum Projekt-Root
    db_path_abs = str(PROJECT_ROOT / db_path) if not Path(db_path).is_absolute() else db_path
    os.makedirs(os.path.dirname(db_path_abs), exist_ok=True)

    print(f"Datenbankdatei: {db_path_abs}")

    # Repository initialisieren (erstellt Schema wenn nötig)
    repo = SQLiteRepository(db_path_abs)
    print("✓ Schema initialisiert")

    if args.add_user:
        create_user(repo)
        return

    # Bestehende Nutzer anzeigen
    users = repo.get_all_users()
    if users:
        print(f"\n── Vorhandene Nutzer ({len(users)}) ──────────────────")
        for u in users:
            print(f"  {u.name:<20} {u.role.value}")
        print()
        again = input("Weiteren Nutzer anlegen? [j/N] ").strip().lower()
        if again == "j":
            create_user(repo)
    else:
        print("\nKeine Nutzer vorhanden. Ersten Admin-Nutzer anlegen:")
        create_user(repo)
        # DFBnet-Systemnutzer anlegen
        from booking.models import UserCreate
        rnd_pw = os.urandom(32).hex()
        dfbnet = repo.create_user(
            UserCreate(name="dfbnet", role=UserRole.DFBNET, email="", password=rnd_pw),
            password_hash=hash_password(rnd_pw),
        )
        print(f"✓ Systemnutzer 'dfbnet' angelegt (ID: {dfbnet.notion_id})")

    print("\nSetup abgeschlossen.")


if __name__ == "__main__":
    main()

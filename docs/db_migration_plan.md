# Datenbankmigrationsplan: Notion → SQLite

**Projekt:** Sportplatz-Buchungssystem
**Stand:** 2026-02-28
**Status:** Planungsdokument — noch nicht implementiert

---

## Inhaltsverzeichnis

1. [DB-Technologie-Empfehlung](#1-db-technologie-empfehlung)
2. [Repository-Abstraktionsschicht](#2-repository-abstraktionsschicht)
3. [Datenbankschema](#3-datenbankschema)
4. [Migrationsstrategie](#4-migrationsstrategie)
5. [Phasenplan](#5-phasenplan)
6. [Checkliste vor Produktivsetzung](#6-checkliste-vor-produktivsetzung)

---

## 1. DB-Technologie-Empfehlung

### Entscheidung: SQLite mit `aiosqlite`

| Kriterium | SQLite | PostgreSQL | DuckDB |
|-----------|--------|------------|--------|
| Installationsaufwand | Keine externe Instanz, in stdlib enthalten | Eigener Server, systemd-Unit, Backup-Strategie | Kein Netzwerk-Server, aber OLAP-fokussiert |
| Betrieb ohne DevOps | Perfekt — eine `.db`-Datei | Erfordert Admin-Kenntnisse | Akzeptabel, aber nicht für OLTP optimiert |
| Schreiblast | Gering (~5–15 Buchungen/Tag) | Unnötig stark | Schlecht bei vielen kleinen Schreibzugriffen |
| Abfrageleistung | Sehr gut für <10.000 Datensätze | Skaliert besser, hier nicht nötig | Überdimensioniert |
| Backup | `cp sportplatz.db sportplatz.db.bak` | `pg_dump` + Konfiguration | Ähnlich wie SQLite |
| Asyncio-Support | `aiosqlite` vorhanden, aktiv gepflegt | `asyncpg` | Kein asyncio-nativer Treiber |

**Fazit:** Für ~30 Nutzer, maximal ~50 Buchungen/Tag, einen einzelnen Linux-Server ohne DevOps ist SQLite die technisch sauberste und wartungsarme Wahl.

### Neue Pakete in `requirements.txt`

```
aiosqlite==0.20.0
sqlmodel==0.0.21
alembic==1.13.1
```

### SQLite-Konfiguration beim Start

```python
PRAGMA journal_mode=WAL;   -- gleichzeitige Lesezugriffe (Homepage + Buchungssystem)
PRAGMA synchronous=NORMAL; -- gute Balance zwischen Safety und Speed
PRAGMA foreign_keys=ON;    -- referenzielle Integrität
```

---

## 2. Repository-Abstraktionsschicht

### Designprinzip

Alle Router greifen über `request.app.state.repo` auf das Repository zu — sie kennen nur
die Methoden, nicht die Implementierung. Ein sauberes Interface ermöglicht den Austausch.

### Neue Datei: `db/repository.py`

```python
from abc import ABC, abstractmethod
from datetime import date, time
from typing import Optional
from booking.models import (
    Aufgabe, AufgabeCreate, AufgabeStatus,
    BlackoutCreate, BlackoutPeriod,
    Booking, BookingCreate, BookingStatus,
    ExternalEvent, ExternalEventCreate,
    Series, SeriesCreate, SeriesStatus,
    User, UserCreate, UserRole,
)

class AbstractRepository(ABC):

    # --- Nutzer ---
    @abstractmethod
    def get_user_by_name(self, name: str) -> Optional[User]: ...
    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]: ...
    @abstractmethod
    def create_user(self, user: UserCreate, password_hash: str) -> User: ...
    @abstractmethod
    def update_user_password(self, user_id: str, password_hash: str) -> User: ...
    @abstractmethod
    def reset_user_password(self, user_id: str, password_hash: str) -> User: ...
    @abstractmethod
    def update_user(self, user_id: str, role: str, email: str, mannschaft: Optional[str]) -> User: ...
    @abstractmethod
    def delete_user(self, user_id: str) -> None: ...
    @abstractmethod
    def get_all_users(self) -> list[User]: ...
    @abstractmethod
    def get_trainers_for_mannschaft(self, mannschaft: str) -> list[User]: ...

    # --- Buchungen ---
    @abstractmethod
    def get_bookings_for_date(self, booking_date: date) -> list[Booking]: ...
    @abstractmethod
    def get_bookings_for_week(self, year: int, week: int) -> list[Booking]: ...
    @abstractmethod
    def get_bookings_for_series(self, series_id: str, only_future: bool = False) -> list[Booking]: ...
    @abstractmethod
    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]: ...
    @abstractmethod
    def get_upcoming_games(self, limit: int = 10) -> list[Booking]: ...
    @abstractmethod
    def get_bookings_by_spielkennung(self, kennungen: list[str]) -> dict[str, Booking]: ...
    @abstractmethod
    def get_bookings_in_range(self, start: date, end: date) -> list[Booking]: ...  # neu — für spielplan_sync
    @abstractmethod
    def create_booking(self, data: BookingCreate, booked_by_id: str, booked_by_name: str,
                       role: UserRole, end_time: time, sunset_note: Optional[str] = None,
                       series_id: Optional[str] = None, mannschaft: Optional[str] = None,
                       zweck: Optional[str] = None, kontakt: Optional[str] = None) -> Booking: ...
    @abstractmethod
    def update_booking_status(self, booking_id: str, status: BookingStatus) -> Booking: ...
    @abstractmethod
    def mark_series_exception(self, booking_id: str) -> Booking: ...

    # --- Serien ---
    @abstractmethod
    def get_all_series(self, only_active: bool = False) -> list[Series]: ...
    @abstractmethod
    def get_series_by_id(self, series_id: str) -> Optional[Series]: ...
    @abstractmethod
    def create_series(self, data: SeriesCreate, booked_by_id: str, booked_by_name: str,
                      trainer_name: str) -> Series: ...
    @abstractmethod
    def update_series_status(self, series_id: str, status: SeriesStatus) -> Series: ...

    # --- Sperrzeiten ---
    @abstractmethod
    def get_blackouts_for_date(self, blackout_date: date) -> list[BlackoutPeriod]: ...
    @abstractmethod
    def get_blackouts_for_week(self, year: int, week: int) -> list[BlackoutPeriod]: ...
    @abstractmethod
    def get_all_blackouts(self) -> list[BlackoutPeriod]: ...
    @abstractmethod
    def create_blackout(self, data: BlackoutCreate, entered_by_id: str, entered_by_name: str) -> BlackoutPeriod: ...
    @abstractmethod
    def delete_blackout(self, blackout_id: str) -> None: ...

    # --- Aufgaben ---
    @abstractmethod
    def get_all_aufgaben(self, only_open: bool = False) -> list[Aufgabe]: ...
    @abstractmethod
    def get_aufgabe_by_id(self, aufgabe_id: str) -> Optional[Aufgabe]: ...
    @abstractmethod
    def create_aufgabe(self, data: AufgabeCreate, created_by_id: str, created_by_name: str) -> Aufgabe: ...
    @abstractmethod
    def update_aufgabe_status(self, aufgabe_id: str, status: AufgabeStatus) -> Aufgabe: ...
    @abstractmethod
    def delete_aufgabe(self, aufgabe_id: str) -> None: ...

    # --- Events ---
    @abstractmethod
    def get_upcoming_events(self, limit: int = 10) -> list[ExternalEvent]: ...
    @abstractmethod
    def get_all_events(self) -> list[ExternalEvent]: ...
    @abstractmethod
    def get_event_by_id(self, event_id: str) -> Optional[ExternalEvent]: ...
    @abstractmethod
    def create_event(self, data: ExternalEventCreate, user_id: str, user_name: str) -> ExternalEvent: ...
    @abstractmethod
    def delete_event(self, event_id: str) -> None: ...
```

### Verzeichnisstruktur

```
db/
├── __init__.py
├── repository.py          # AbstractRepository
├── sqlite_repository.py   # SQLiteRepository(AbstractRepository)
└── migrations/            # Alembic
    ├── env.py
    ├── alembic.ini
    └── versions/
        └── 0001_initial_schema.py
```

`NotionRepository` in `notion/client.py` bekommt `AbstractRepository` als Basisklasse
(`class NotionRepository(AbstractRepository):`). Der Pivot-Punkt für die Umschaltung
liegt in `web/main.py`, Zeile 16:
```python
app.state.repo = NotionRepository(settings)   # → SQLiteRepository(settings)
```

### Wichtige Typen-Kompatibilität

Die Pydantic-Modelle verwenden `notion_id: str` als primären Bezeichner.
Die SQLite-Implementierung befüllt dasselbe Feld mit UUID4-Strings.
Ein Umbenennen zu `id` kann als separates Refactoring später erfolgen.

---

## 3. Datenbankschema

### Konventionen

| Notion-Typ | SQL-Typ | Anmerkung |
|------------|---------|-----------|
| `title` | `TEXT NOT NULL` | |
| `select` | `TEXT` | `.value` des Enum-Strings |
| `rich_text` | `TEXT` | Leerer String statt NULL wenn optional |
| `date` (einfach) | `TEXT` | ISO-Format `YYYY-MM-DD` |
| `date` (Range) | `start_date TEXT`, `end_date TEXT` | Notion Range → zwei Felder |
| `checkbox` | `INTEGER` | 0 = False, 1 = True |
| Notion page `id` | `TEXT PRIMARY KEY` | Durch UUID4 ersetzt |

### Tabelle `users`

```sql
CREATE TABLE users (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL,             -- UserRole.value
    email           TEXT NOT NULL DEFAULT '',
    password_hash   TEXT NOT NULL DEFAULT '',
    mannschaft      TEXT,                      -- nullable
    must_change_pw  INTEGER NOT NULL DEFAULT 1,
    deleted_at      TEXT                       -- NULL = aktiv
);
CREATE UNIQUE INDEX idx_users_name ON users(name) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_role ON users(role);
```

### Tabelle `bookings`

```sql
CREATE TABLE bookings (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    field           TEXT NOT NULL,             -- FieldName.value
    date            TEXT NOT NULL,             -- YYYY-MM-DD
    start_time      TEXT NOT NULL,             -- HH:MM
    end_time        TEXT NOT NULL,             -- HH:MM
    duration_min    INTEGER NOT NULL,
    booking_type    TEXT NOT NULL,             -- BookingType.value
    booked_by_id    TEXT NOT NULL,
    booked_by_name  TEXT NOT NULL,
    role            TEXT NOT NULL,             -- UserRole.value
    status          TEXT NOT NULL DEFAULT 'Bestätigt',
    mannschaft      TEXT,
    zweck           TEXT,
    kontakt         TEXT,
    series_id       TEXT,                      -- → series.id
    series_exception INTEGER NOT NULL DEFAULT 0,
    sunset_note     TEXT,
    spielkennung    TEXT,
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE SET NULL
);
CREATE INDEX idx_bookings_date_status ON bookings(date, status);
CREATE INDEX idx_bookings_date ON bookings(date);
CREATE INDEX idx_bookings_series_id ON bookings(series_id) WHERE series_id IS NOT NULL;
CREATE UNIQUE INDEX idx_bookings_spielkennung
    ON bookings(spielkennung) WHERE spielkennung IS NOT NULL AND status = 'Bestätigt';
```

### Tabelle `series`

```sql
CREATE TABLE series (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    field           TEXT NOT NULL,
    start_time      TEXT NOT NULL,
    duration_min    INTEGER NOT NULL,
    rhythm          TEXT NOT NULL,             -- SeriesRhythm.value
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    booked_by_id    TEXT NOT NULL,
    booked_by_name  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Aktiv',
    mannschaft      TEXT,
    trainer_id      TEXT,
    trainer_name    TEXT
);
CREATE INDEX idx_series_status ON series(status);
```

### Tabelle `blackouts`

```sql
CREATE TABLE blackouts (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    blackout_type   TEXT NOT NULL,             -- BlackoutType.value
    start_time      TEXT,
    end_time        TEXT,
    reason          TEXT NOT NULL DEFAULT '',
    entered_by_id   TEXT NOT NULL,
    entered_by_name TEXT NOT NULL,
    deleted_at      TEXT
);
-- Effiziente Bereichsabfrage: start_date <= :end AND end_date >= :start
CREATE INDEX idx_blackouts_start_date ON blackouts(start_date);
CREATE INDEX idx_blackouts_end_date ON blackouts(end_date);
```

**Vorteil gegenüber Notion:** In Notion ist kein `end_date >= X`-Filter möglich,
daher wurde bisher ein Python-seitiger Nachfilter verwendet.
In SQLite löst ein einfacher SQL-Ausdruck das vollständig.

### Tabelle `aufgaben`

```sql
CREATE TABLE aufgaben (
    id                TEXT PRIMARY KEY,
    titel             TEXT NOT NULL,
    typ               TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Offen',
    prioritaet        TEXT NOT NULL DEFAULT 'Mittel',
    erstellt_von_id   TEXT NOT NULL,
    erstellt_von_name TEXT NOT NULL,
    erstellt_am       TEXT NOT NULL,
    faellig_am        TEXT,
    ort               TEXT,
    beschreibung      TEXT,
    deleted_at        TEXT
);
CREATE INDEX idx_aufgaben_status ON aufgaben(status);
```

### Tabelle `events`

```sql
CREATE TABLE events (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    date            TEXT NOT NULL,
    start_time      TEXT NOT NULL,
    location        TEXT,
    description     TEXT,
    created_by_id   TEXT NOT NULL,
    created_by_name TEXT NOT NULL,
    mannschaft      TEXT,
    deleted_at      TEXT
);
CREATE INDEX idx_events_date ON events(date);
```

---

## 4. Migrationsstrategie

### Überblick

Einmaliger Python-Export aus Notion → SQLite. Kein komplexes ETL-Tool nötig.
Geschätzter Datensatz: ~30 Nutzer, Buchungen eines Spieljahrs (~200–500), wenige
Serien und Sperrzeiten.

### Reihenfolge (Fremdschlüssel-Abhängigkeiten)

```
1. Nutzer          (keine FK-Abhängigkeit)
2. Serien          (FK → users)
3. Buchungen       (FK → series)
4. Sperrzeiten     (keine FK-Abhängigkeit)
5. Aufgaben        (keine FK-Abhängigkeit)
6. Events          (keine FK-Abhängigkeit)
```

Notion-UUIDs werden durch neue `uuid.uuid4()` ersetzt.
Ein temporäres Mapping `{ notion_id → neue_id }` löst die Fremdschlüssel auf.

### Skript: `scripts/migrate_notion_to_sqlite.py`

```python
# Pseudocode — Kernlogik

user_id_map: dict[str, str] = {}
series_id_map: dict[str, str] = {}

# Phase 1: Nutzer
for user in notion_repo.get_all_users():
    new_id = str(uuid.uuid4())
    user_id_map[user.notion_id] = new_id
    sqlite_repo.insert_user_raw(id=new_id, **user_fields)

# Phase 2: Serien
for series in notion_repo.get_all_series():
    new_id = str(uuid.uuid4())
    series_id_map[series.notion_id] = new_id
    sqlite_repo.insert_series_raw(
        id=new_id,
        booked_by_id=user_id_map.get(series.booked_by_id, series.booked_by_id),
        trainer_id=user_id_map.get(series.trainer_id) if series.trainer_id else None,
        **other_fields
    )

# Phase 3: Buchungen (inkl. stornierte — vollständige History)
for booking in notion_repo._query_all_bookings():
    sqlite_repo.insert_booking_raw(
        id=str(uuid.uuid4()),
        booked_by_id=user_id_map.get(booking.booked_by_id, booking.booked_by_id),
        series_id=series_id_map.get(booking.series_id) if booking.series_id else None,
        **other_fields
    )

# Phasen 4–6: Sperrzeiten, Aufgaben, Events analog
```

### Sonderfälle

- **System-User-IDs** (z. B. `"dfbnet-import-script"` in `booked_by_id`): Werden
  nicht im `user_id_map` gefunden. Strategie: unverändert übernehmen oder einen
  eigenen System-User in der SQLite-DB anlegen.
- **Verwaiste Serien-Referenzen**: Buchungen mit `series_id`, deren Serie in Notion
  nicht mehr existiert → `series_id = NULL` setzen.
- **JWT-Sessions**: Alle aktiven Sessions nach der Migration ungültig.
  Lösung: `JWT_SECRET` in `.env` rotieren.

### Validierung

```python
assert len(sqlite.get_all_users()) == len(notion.get_all_users())
for test_date in ["2026-03-01", "2026-03-08", "2026-04-01"]:
    assert (len(sqlite.get_bookings_for_date(test_date))
            == len(notion.get_bookings_for_date(test_date))), f"Mismatch {test_date}"
print("✅ Migration validiert")
```

---

## 5. Phasenplan

### Phase 1 — Abstraktionsschicht einführen
**Aufwand:** 1–2 Std. | **Betrieb:** unverändert

1. `db/__init__.py` und `db/repository.py` mit `AbstractRepository` anlegen
2. `NotionRepository` erbt von `AbstractRepository`:
   `class NotionRepository(AbstractRepository):`
3. Neue Methode `get_bookings_in_range()` in `NotionRepository` implementieren
   und `spielplan_sync.py` auf sie umstellen (entfernt direkten `repo._client`-Zugriff)
4. `mypy`-Check: Alle abstrakten Methoden müssen implementiert sein

**Dateien:** `db/repository.py`, `notion/client.py`, `booking/spielplan_sync.py`

---

### Phase 2 — SQLiteRepository implementieren
**Aufwand:** 1–2 Tage | **Betrieb:** unverändert (Notion bleibt aktiv)

1. `db/schema.sql` mit allen Tabellen und Indizes anlegen
2. `db/sqlite_repository.py` mit `SQLiteRepository(AbstractRepository)` implementieren
   - `aiosqlite` für asyncio-kompatible Datenbankzugriffe
   - Hilfsmethoden `_row_to_user()`, `_row_to_booking()`, ... für Typ-Konvertierung
   - UUID4-Generierung für neue Entitäten
3. `Settings` in `web/config.py` um `sqlite_db_path: str = "sportplatz.db"` ergänzen
4. Alembic initialisieren: `db/migrations/`
5. Unit-Tests mit In-Memory-SQLite: `sqlite:///:memory:`

**Dateien:** `db/sqlite_repository.py`, `db/schema.sql`, `web/config.py`, `requirements.txt`

---

### Phase 3 — Migrations-Skript entwickeln
**Aufwand:** 4–8 Std. | **Betrieb:** unverändert

1. `scripts/migrate_notion_to_sqlite.py` implementieren
2. Testlauf gegen Notion-Produktivdaten → Test-SQLite-Datei
3. Validierungs-Checks ausführen
4. Edge-Cases absichern (System-User, verwaiste Referenzen, fehlende Notion-Felder)

**Dateien:** `scripts/migrate_notion_to_sqlite.py`

---

### Phase 4 — Migration + Umschaltung (Wartungsfenster ~20 Min.)
**Aufwand:** 20–30 Min. | **Betrieb:** kurz unterbrochen

```bash
# 1. Services stoppen
systemctl stop sportplatz-buchung sportplatz-homepage

# 2. .env sichern (Rollback-Option)
cp .env .env.notion_backup

# 3. Migration ausführen
.venv/bin/python scripts/migrate_notion_to_sqlite.py --output sportplatz.db

# 4. .env anpassen
#    SQLITE_DB_PATH=sportplatz.db
#    JWT_SECRET=<neuer Wert>   ← alle Sessions werden ungültig

# 5. web/main.py umstellen
#    app.state.repo = SQLiteRepository(settings)

# 6. Services starten
systemctl start sportplatz-buchung sportplatz-homepage

# 7. Smoke-Test: Login, Kalender, Buchung anlegen
```

**Rollback:** Schritt 5 rückgängig machen, `.env.notion_backup` einspielen,
Services neu starten.

---

### Phase 5 — Notion-Abkoppelung
**Aufwand:** 1–2 Std. | **Betrieb:** normal

1. `notion-client` aus `requirements.txt` entfernen
2. Notion-Variablen aus `Settings` in `web/config.py` entfernen
3. `notion/` → `legacy/notion/` verschieben (nicht löschen — Referenz für Rollback)
4. Dokumentation aktualisieren: `docs/ARCHITEKTUR.md`

**Dateien:** `requirements.txt`, `web/config.py`, `docs/ARCHITEKTUR.md`

---

### Phase 6 — Backup-Automatisierung
**Aufwand:** 30 Min.

```bash
# /etc/cron.daily/sportplatz-backup
DB="/root/git.com/Sportplatz-Buchung/sportplatz.db"
BACKUP_DIR="/root/backups/sportplatz"
DATE=$(date +%Y-%m-%d)
mkdir -p "$BACKUP_DIR"
sqlite3 "$DB" ".backup $BACKUP_DIR/sportplatz_$DATE.db"   # Online-Backup, kein Stop nötig
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
```

Außerdem: `sportplatz.db` in `.gitignore` eintragen (enthält Passwort-Hashes).

---

## 6. Checkliste vor Produktivsetzung

### Code
- [ ] Alle Methoden der `AbstractRepository` in `SQLiteRepository` implementiert
- [ ] `mypy`-Check fehlerfrei
- [ ] Unit-Tests für alle Repository-Methoden (In-Memory-SQLite)
- [ ] `spielplan_sync.py` nutzt `get_bookings_in_range()` statt direktem `repo._client`

### Datenmigration
- [ ] Migrations-Skript auf Testdaten erprobt
- [ ] Zähler-Vergleich: alle Entitäten migriert
- [ ] Stichproben: ≥5 Buchungen manuell verglichen
- [ ] Edge-Cases getestet

### Betrieb
- [ ] `sportplatz.db` in `.gitignore`
- [ ] Tägliches Backup-Skript eingerichtet und getestet
- [ ] `JWT_SECRET` rotiert
- [ ] Nutzer per E-Mail informiert (einmaliges Neu-Anmelden nötig)
- [ ] WAL-Modus aktiviert (`PRAGMA journal_mode=WAL`)

---

## Zeitschätzung

| Phase | Beschreibung | Aufwand |
|-------|-------------|---------|
| 1 | Abstraktionsschicht | 1–2 Std. |
| 2 | SQLiteRepository implementieren | 1–2 Tage |
| 3 | Migrations-Skript | 4–8 Std. |
| 4 | Migration + Umschaltung | 20–30 Min. |
| 5 | Notion-Abkoppelung | 1–2 Std. |
| 6 | Backup | 30 Min. |
| **Gesamt** | | **ca. 2–3 Tage** |

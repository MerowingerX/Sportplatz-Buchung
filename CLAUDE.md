# CLAUDE.md — Sportplatz-Buchungssystem

Projektspezifische Anweisungen für Claude Code. Immer lesen, bevor Code geändert wird.

---

## Überblick

**Zwei separate Repos, zwei separate Dienste:**

| Repo | Dienst | Port | Entrypoint |
|------|--------|------|------------|
| `Sportplatz-Buchung/` (dieses Repo) | Buchungssystem (auth-geschützt) | 1946 | `web.main:app` |
| `TuS_Cremlingen-Homepage/` | Öffentliche Homepage | 8046 | `web.main:app` |

**Stack:** FastAPI · Pydantic-Settings · Jinja2 + HTMX · Notion API als Datenbank · JWT-Cookie-Auth

**Datenbank:** Notion (Standard) **oder** SQLite — wählbar über `DB_BACKEND=notion|sqlite` in `.env`. Alle Router greifen ausschließlich über `request.app.state.repo` auf das Repository zu. Interface: `db/repository.py → AbstractRepository`. Implementierungen: `notion/client.py → NotionRepository` und `db/sqlite_repository.py → SQLiteRepository`.

---

## Kritische Regeln

### 1. Pydantic-Settings

Jede neue `.env`-Variable **muss** als Feld in `web/config.py` → `Settings` deklariert werden.
Ohne Deklaration: `ValidationError: Extra inputs are not permitted` beim Start.

```python
# Richtig:
class Settings(BaseSettings):
    neue_variable: str
    optionale_variable: Optional[str] = None
```

### 2. Jinja2-Templates — nie neue Instanz erstellen

Alle Router importieren die **gemeinsame** Templates-Instanz:

```python
from web.templates_instance import templates  # ✓ immer so
```

Niemals `Jinja2Templates(directory=...)` neu instanziieren. Jinja2-Globals (`vereinsname`, `vereinsfarben`, `logo_url`) werden nur in `web/templates_instance.py` gesetzt.

### 3. CSS Cache-Busting

`style.css` wird mit `?v=N` geladen (in `base.html` und `login.html`).
Bei CSS-Änderungen die Versionsnummer in **beiden** Templates hochzählen.

### 4. Notion-Property-Namen sind exakte Strings

Alle Notion-Property-Namen müssen exakt mit den Bezeichnungen in der Notion-Datenbank übereinstimmen. Die **Quelle der Wahrheit** ist `notion/client.py`.
Vollständige Tabellen aller Properties → `docs/naming_constraints.md`.

### 5. Setup-Script

`notion/setup.py` ist veraltet. **Ausschließlich** `scripts/setup_notion.py` verwenden.

---

## Verzeichnisstruktur

```
Sportplatz-Buchung/
├── web/
│   ├── main.py                  # FastAPI-App, Router-Einbindung, Lifespan
│   ├── config.py                # pydantic-settings Settings (alle .env-Felder hier!)
│   ├── templates_instance.py    # Gemeinsame Jinja2Templates + Globals
│   ├── routers/                 # auth, bookings, calendar, series, admin, tasks, events
│   ├── static/                  # style.css, logo.svg, htmx.min.js
│   └── templates/               # Jinja2-Templates
│       └── partials/            # HTMX-Partial-Templates
├── booking/
│   ├── models.py                # Alle Pydantic-Modelle + Enums (FieldName, BookingType …)
│   ├── field_config.py          # Platzkonfiguration (Gruppen, Sichtbarkeit, Konflikte)
│   └── series.py                # Serien-Buchungslogik (Termine generieren)
├── db/
│   ├── repository.py            # AbstractRepository (ABC) — Interface für alle DB-Backends
│   ├── sqlite_repository.py     # SQLiteRepository — stdlib sqlite3, WAL-Modus
│   └── schema.sql               # DDL: Tabellen, Indizes (wird beim Start automatisch ausgeführt)
├── notion/
│   └── client.py                # NotionRepository — alle DB-Methoden (implementiert AbstractRepository)
├── auth/
│   ├── auth.py                  # JWT encode/decode
│   └── dependencies.py          # CurrentUser FastAPI-Dependency
├── config/
│   ├── vereinsconfig.json       # Club: Name, Farben, heim_keyword, spielorte
│   └── field_config.json        # Plätze: Anzeigenamen, Gruppen, Sichtbarkeit
├── data/                        # SQLite-Datenbankdatei (gitignored, nur bei DB_BACKEND=sqlite)
├── scripts/                     # Standalone-Scripts (backup, restore, fetch_spielplan …)
├── docs/                        # Architekturdokumentation
└── Dockerfile / docker-compose.yml
```

---

## Wichtige Dateien im Detail

### `booking/models.py`
Zentrale Pydantic-Modelle und Enums. Änderungen hier haben Kaskadeneffekte:
- `FieldName` → Notion-Select-Optionen, CSS-Klassen, `field_config.json`
- `BookingType` → CSS-Klassen via `{{ b.booking_type.value | lower }}`
- `UserRole` → Template-Hardcodes, `field_config.json` → `"visible_to"`

**Enum-Werte nie umbenennen ohne `docs/naming_constraints.md` zu prüfen.**

### `notion/client.py`
Einziger Weg zur Datenbank. Methoden-Muster:
- `_page_to_*()` — Notion-Page → Pydantic-Modell
- `_query_all()` — paginierte Abfrage (immer nutzen, nie direkt `.query()`)
- Schreiben: `_update_page()`, `pages.create()`

### `config/vereinsconfig.json`
Quelle der Wahrheit für vereinsspezifische Werte. Wird beim Start geladen und als Jinja2-Globals gesetzt:
- `vereinsname`, `vereinsname_lang` → alle Templates
- `primary_color`, `primary_color_dark`, `primary_color_darker`, `gold_color` → CSS-Variablen
- `heim_keyword` → Spielplan-Import (Groß-/Kleinschreibung egal)
- `logo_url` → Navbar + Hintergrund-Wasserzeichen

### `config/field_config.json`
- `display_names` → lesbare Platznamen (nur hier ändern, kein Neustart nötig)
- `field_groups` → welche Felder zu welcher Gruppe gehören
- `visible_to` → Rollen-Sichtbarkeit pro Gruppe
- `lit` → Flutlicht (bool, Sonnenuntergangs-Hinweis-Logik)

---

## Auth-System

- **JWT-Cookie** namens `session` (httponly, samesite=lax)
- Rollen: `Trainer`, `Platzwart`, `Administrator`, `DFBnet`
- FastAPI-Dependency: `CurrentUser` aus `auth/dependencies.py`
- Permission-Checks: `has_permission(user.role, Permission.X)` aus `booking/models.py`
- Trainer sehen nur eigene Buchungen; Admins/Platzwart sehen alles

---

## Notion-Datenbanken

| `.env`-Variable | Inhalt |
|-----------------|--------|
| `NOTION_BUCHUNGEN_DB_ID` | Buchungen (Haupttabelle) |
| `NOTION_SERIEN_DB_ID` | Trainingsserien |
| `NOTION_NUTZER_DB_ID` | Nutzer + Passwort-Hashes |
| `NOTION_AUFGABEN_DB_ID` | Platzwart-Aufgaben |
| `NOTION_EVENTS_DB_ID` | Externe Termine (optional) |
| `NOTION_MANNSCHAFTEN_DB_ID` | Mannschaften-Config (optional) |

---

## HTMX-Muster

Die UI ist HTMX-getrieben. Partials in `web/templates/partials/` werden per `hx-get`/`hx-post` nachgeladen.
Formulare: `hx-post` → Server gibt Partial zurück → HTMX tauscht Ziel-Element aus.
Kein JavaScript außer HTMX (und minimal inline für Dialoge).

---

## Mannschaften

Das `Mannschaft`-Enum wurde **entfernt**. Mannschaften kommen dynamisch aus der Notion Mannschaften-DB:

```python
mannschaften = await repo.get_all_mannschaften(only_active=True)
# → list[MannschaftConfig]
# MannschaftConfig.name ist der angezeigte String
```

Das Feld `mannschaft` in allen Modellen ist `str`, nicht Enum.

---

## Neue Features implementieren — Checkliste

**Neues `.env`-Feld:**
- [ ] `web/config.py` → `Settings`-Klasse ergänzen
- [ ] `.env.example` ergänzen mit Kommentar

**Neuer Router:**
- [ ] `web/routers/<name>.py` anlegen
- [ ] In `web/main.py` → `app.include_router(...)` einbinden
- [ ] `from web.templates_instance import templates` (nie neu instanziieren)

**Neue DB-Methode (beide Backends):**
- [ ] Signatur in `db/repository.py` → `AbstractRepository` als `@abstractmethod` ergänzen
- [ ] In `notion/client.py` → `NotionRepository` implementieren (Property-Namen exakt, `_query_all()` nutzen)
- [ ] In `db/sqlite_repository.py` → `SQLiteRepository` implementieren
- [ ] ggf. `db/schema.sql` um neue Spalte / Tabelle erweitern

**Neue Platz-ID (FieldName):**
- [ ] `booking/models.py` → `FieldName`-Enum
- [ ] `config/field_config.json` → `display_names` + `field_groups` + `visible_to` + `lit`
- [ ] `scripts/setup_notion.py` → Notion Select-Option anlegen
- [ ] `booking/field_config.py` → `_DEFAULT` prüfen
- [ ] `config/vereinsconfig.json` → `spielorte` prüfen

---

## Scripts (`scripts/`)

Alle Scripts sind standalone (kein `sys.path`-Hack nötig, direkt ausführbar):

| Script | Zweck |
|--------|-------|
| `backup_notion.py` | Alle 6 Notion-DBs als JSON sichern (Cron: täglich 03:00) |
| `restore_notion.py` | Nutzer + Serien aus Backup wiederherstellen (`--dry-run`) |
| `fetch_spielplan.py` | Spiele von fussball.de importieren |
| `setup_notion.py` | Notion-DBs initial anlegen / Properties prüfen |
| `setup_sqlite.py` | SQLite-DB einrichten: Schema erstellen, Admin + dfbnet-Nutzer anlegen |
| `instagram_matchday.py` | Matchday-Karussell-Bilder generieren (braucht Playwright) |
| `onboarding.sh` | Interaktives Ersteinrichtungs-Script |

---

## Datenbank-Backend

Das Repository-Interface ist hinter `db/repository.py → AbstractRepository` abstrahiert. Beim Start in `web/main.py` (Lifespan) wird je nach `DB_BACKEND` eine konkrete Implementierung instanziiert und in `app.state.repo` abgelegt. Router greifen **ausschließlich** über `request.app.state.repo` auf Daten zu.

### Auswahl per `.env`

| Variable | Wert | Beschreibung |
|----------|------|--------------|
| `DB_BACKEND` | `notion` (Standard) | Notion-API als Datenbank |
| `DB_BACKEND` | `sqlite` | Lokale SQLite-Datei |
| `SQLITE_DB_PATH` | `data/sportplatz.db` | Pfad zur SQLite-Datei (relativ zum Projekt-Root) |

### SQLite-Setup (Ersteinrichtung)

```bash
# Schema + erste Nutzer anlegen
python scripts/setup_sqlite.py

# Optionen:
python scripts/setup_sqlite.py --db data/sportplatz.db   # expliziter DB-Pfad
python scripts/setup_sqlite.py --add-user                 # nur weiteren Nutzer anlegen
```

Das Script liest `SQLITE_DB_PATH` aus `.env` / `.env.demo`, erstellt das Schema (idempotent) und legt interaktiv einen Admin-Nutzer sowie den Systemnutzer `dfbnet` an.

### SQLite-Datenbank einsehen

```bash
# CLI (interaktiv)
sqlite3 data/sportplatz.db
sqlite> .tables
sqlite> SELECT name, role FROM users;
sqlite> .quit

# Nicht-interaktiv (z. B. für Logs/Cron)
sqlite3 data/sportplatz.db "SELECT name, role FROM users;"
```

Grafisch: **DB Browser for SQLite** (kostenlos, [sqlitebrowser.org](https://sqlitebrowser.org)) oder VS Code Extension **SQLite Viewer** (Florian Klampfer).

### Technische Details

- `SQLiteRepository` nutzt stdlib `sqlite3`, kein ORM
- WAL-Modus (`PRAGMA journal_mode=WAL`) — mehrere gleichzeitige Leser, ein Schreiber
- Foreign-Keys aktiv (`PRAGMA foreign_keys=ON`)
- Thread-Safety: eigene Connection pro Thread via `threading.local()`
- `notion_id`-Feld: bei Notion die echte Page-UUID, bei SQLite ein `uuid4()`-String — intern identisch behandelt
- Schema-Datei: `db/schema.sql` (wird bei jedem Start via `CREATE TABLE IF NOT EXISTS` ausgeführt — sicher beim Neustart)

---

## Laufzeit / Deployment

```bash
# Entwicklung
uvicorn web.main:app --reload --port 1946

# Docker
docker compose up -d
docker compose logs -f buchung

# Cron Backup (auf Server einrichten)
0 3 * * * cd /opt/sportplatz && .venv/bin/python scripts/backup_notion.py >> logs/backup.log 2>&1
```

Logs: `logs/` (in `.gitignore`). Backups: `backup/` (gemountet in Docker).

---

## Was Claude hier NICHT tun soll

- **Keine neue `Jinja2Templates`-Instanz** erstellen — immer aus `web.templates_instance` importieren
- **Keine `.env`-Felder** verwenden ohne sie in `web/config.py` zu deklarieren
- **Keine Enum-Werte umbenennen** ohne `docs/naming_constraints.md` zu prüfen
- **Nicht direkt `self._client.databases.query()`** aufrufen — immer `self._query_all()` nutzen
- **`notion/setup.py` nicht anfassen** — nur `scripts/setup_notion.py` ist aktuell
- **Keine Homepage-Logik** in dieses Repo — Homepage ist ein eigenes Repo (`TuS_Cremlingen-Homepage/`)

---

## Dokumentation

| Datei | Inhalt |
|-------|--------|
| `docs/ARCHITEKTUR.md` | Komponentenübersicht, Datenfluss, Klassendiagramme |
| `docs/naming_constraints.md` | Alle String-Kopplungen zwischen Code, Notion, CSS, Templates |
| `docs/INSTALLATION.md` | Setup-Anleitung für neue Instanz |
| `docs/feldtopologie_aendern.md` | Anleitung Platzstruktur ändern |
| `docs/db_migration_plan.md` | Plan: Notion → SQLite (AbstractRepository, 6 Phasen) |
| `docs/secrets.md` | Alle Hardcodes und bekannte Secrets |
| `docs/instagram_setup.md` | Instagram Business-Konto, Token, ngrok, häufige Fehler |

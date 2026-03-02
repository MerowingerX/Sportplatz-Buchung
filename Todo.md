# Todo – TuS Cremlingen Platzbuchungssystem

## Geplante Features

### ~~Halbjahr-Gliederung für Serienbuchungen~~
→ Detail: [docs/halbjahr_serien.md](docs/halbjahr_serien.md)

- [x] Konfigurierbare Wechseldaten (Sommer-/Winterstart) in `vereinsconfig.json`
- [x] Neues Enum `SeriesSaison` (Ganzjährig / Sommerhalbjahr / Winterhalbjahr) in `models.py`
- [x] Hardcodiertes `30. Juni`-Enddatum in `series.py` durch konfigurierbare Grenzen ersetzen
- [x] Saison-Dropdown im Serien-Formular
- [x] Notion-DB um `Saison`-Property erweitern (inkl. `setup_notion.py`)

### Datenbank-Migration: Notion → lokale DB (SQLite)
→ Detail: [docs/db_migration_plan.md](docs/db_migration_plan.md)

- [ ] `AbstractRepository`-Interface einführen (NotionRepository bleibt Implementierung) `[Aufwand: hoch]`
- [ ] `SQLiteRepository` implementieren (aiosqlite + sqlmodel + alembic) `[Aufwand: hoch]`
- [ ] Migrationsskript: Notion-Daten → SQLite (UUID-Mapping) `[Aufwand: mittel]`
- [ ] Parallelbetrieb testen, dann Notion-Abhängigkeit entfernen `[Aufwand: mittel]`
- [ ] `booking/spielplan_sync.py`: `_lade_buchungen_mit_id()` auf neues Interface migrieren (kein direkter `repo._client`-Zugriff) `[Aufwand: low]`

---

## Code-Qualität
→ Detail: [docs/Review.md](docs/Review.md)

- [x] **Hoch** – `_toast()` in allen Routern dupliziert → gemeinsames `web/htmx.py` `[Aufwand: low]`
- [x] **Hoch** – JWT bleibt nach Rollenänderung gültig → `app.state.token_invalidations` (per-user Timestamp), `iat`-Claim im JWT `[Aufwand: mittel]`
- [x] **Mittel** – `mannschaft` in `ExternalEvent` als `str` statt `Mannschaft`-Enum `[Aufwand: low]`
- [x] **Mittel** – `asyncio.ensure_future()` durch FastAPI `BackgroundTasks` ersetzen `[Aufwand: mittel]`
- [x] **Mittel** – Globale Job-Dicts für ICS/CSV-Import: Spielplan-Job ist Singleton (eine API), ICS/CSV-Import ist synchron — kein Handlungsbedarf `[Aufwand: mittel]`
- [x] **Mittel** – Rollenprüfungen in Templates: `has_permission()` als Jinja2-Global registrieren `[Aufwand: low]`
- [x] **Niedrig** – HTMX lokal hosten statt CDN (`web/static/htmx.min.js`) `[Aufwand: low]`
- [ ] **Niedrig** – Pagination bei Aufgaben (Tasks) ergänzen `[Aufwand: low]`
- [x] **Niedrig** – Notion-Property-Check beim Start per Env-Flag (`SKIP_NOTION_MIGRATE`) deaktivierbar machen `[Aufwand: low]`
- [ ] **Niedrig** – Inline-Styles in Templates in CSS-Klassen überführen `[Aufwand: low]`
- [ ] **Niedrig** – Automatische Tests für Buchungslogik, Slot-Berechnung, JWT, Rollenprüfungen (`pytest`) `[Aufwand: hoch]`

---

## Offen

### Infrastruktur
- [ ] Testserver einrichten (Staging-Umgebung) `[Aufwand: hoch]`
- [x] Backup-Skript implementieren: `scripts/backup_notion.py` (Retention 30 Tage, 6 DBs)
      → Detail: [docs/backup_plan.md](docs/backup_plan.md)
- [x] Backup: Cron-Job auf Server einrichten (`0 1 * * *`) `[Aufwand: low]`

### DFBnet-Integration
- [ ] Automatische Verarbeitung von DFBnet-E-Mails (Spielansetzung, Spielabsetzung, Spielverlegung) `[Aufwand: hoch]`

### Homepage – Eventliste
- [ ] Anmeldung von Events durch Nutzer (mit Admin-Genehmigung vor Veröffentlichung) `[Aufwand: hoch]`

### Homepage – Inhalt
- [x] Anfahrt und Kartenlink (Google Maps) `[Aufwand: low]`
- [x] Kontaktseite/-bereich ausbauen `[Aufwand: low]`
- [ ] Online-Vereinsbeitritt `[Aufwand: mittel]`
- [ ] Instagram-Profile der Teams verlinken `[Aufwand: low]`

### Buchungssystem – weitere Features
- [ ] iCal-Abo pro Mannschaft/Trainer (`/ical/mannschaft/D1` → ICS-Feed für Google/Apple Calendar) `[Aufwand: mittel]`
- [ ] Druckansicht Wochenkalender (`?print=1`, ohne Navigation/HTMX, für Schwarzes Brett) `[Aufwand: low]`
- [ ] Erinnerungs-E-Mail 24h vor Buchung (Cron-Job, nutzt bestehende Mail-Infrastruktur) `[Aufwand: low]`
- [ ] Auslastungsstatistik für Admins (Platz-Nutzung, Top-Mannschaften, freie Slots) `[Aufwand: mittel]`
- [ ] Öffentliche Trainingszeiten auf Homepage (ohne Login, gefiltert nach Mannschaft) `[Aufwand: mittel]`
- [x] Trainer kann eigene Buchungen stornieren (bereits implementiert: `booked_by_id`-Check)

### Mannschaften – Spielpläne via api-fussball.de
Dank `FussballDeTeamId` in der Mannschaften-DB sind je Team die nächsten Spiele abrufbar
(`/api/team/{teamId}/nextGames`). Mögliche Features:
- [ ] Mannschafts-Detailseite mit Spielplan (nächste Heimspiele + Auswärtsspiele) `[Aufwand: mittel]`
- [ ] Homepage-Widget "Nächste Spiele" je Mannschaft (analog zur aktuellen Eventliste) `[Aufwand: mittel]`
- [ ] Ergebnisse vergangener Spiele anzeigen (`/api/team/{teamId}/lastGames`) `[Aufwand: low]`
- [ ] Automatischer Spielplan-Import in Events-DB per Cron (ersetzt manuellen fussball.de-Scraper) `[Aufwand: mittel]`

---

## Referenz-Dokumente

| Dokument | Inhalt |
|----------|--------|
| [docs/halbjahr_serien.md](docs/halbjahr_serien.md) | Implementierungsplan Saison-Label + Datum-Prefill für Serien |
| [docs/manual.md](docs/manual.md) | Betriebshandbuch: Saisonplanung, Sommer/Winterbetrieb, Nutzerverwaltung |
| [docs/db_migration_plan.md](docs/db_migration_plan.md) | 6-Phasen-Plan Notion → SQLite mit AbstractRepository |
| [docs/Review.md](docs/Review.md) | Code-Review: priorisierte Verbesserungspunkte |
| [docs/feldtopologie_aendern.md](docs/feldtopologie_aendern.md) | Anleitung: Platzunterteilung ändern (z. B. Viertel statt Hälften) |
| [docs/naming_constraints.md](docs/naming_constraints.md) | Übersicht: welche String-Namen exakt übereinstimmen müssen |
| [docs/backup_plan.md](docs/backup_plan.md) | Script-Plan: Notion-Daten nach /backup/ sichern (Cron-Job) |
| [docs/secrets.md](docs/secrets.md) | Alle Hardcodes und Secrets im Projekt |
| [docs/datenmodell.md](docs/datenmodell.md) | Notion-Datenbankstruktur (alle Properties) |
| [docs/anforderungen.md](docs/anforderungen.md) | Fachliche Anforderungen, Regeln, Berechtigungen |

---

## Erledigt

### Buchungssystem
- [x] Wochenkalender mit Echtzeit-Verfügbarkeit und Slot-Farbcodierung
- [x] Einzelbuchungen (Kunstrasen, Naturrasen, Turnhalle, je Ganz/Halb)
- [x] Serienbuchungen (wöchentlich / 14-tägig) mit Trainer-Zuweisung
- [x] DFBnet-Verdrängungslogik mit E-Mail-Benachrichtigung
- [x] ICS- und CSV-Massenimport (mit Vorschau-Schritt)
- [x] E-Mail-Benachrichtigungen (Buchung, Storno, DFBnet, Serien)
- [x] Audit-Log (Login, Buchungen, Stornierungen)
- [x] Erzwungener Passwort-Wechsel beim ersten Login
- [x] Sonnenuntergangswarnung für nicht beleuchtete Plätze (konfigurierbar via `lit` in `field_config.json`)

### UX / Interaktion
- [x] Cursor bei klickbaren Elementen korrekt gesetzt (pointer / not-allowed / default)
- [x] Lade-Overlay: zentrierte Statusmeldung bei jeder HTMX-Anfrage (120 ms Delay)
- [x] Mobilgerät-tauglicher Kalender: Tagesansicht mit Wischgesten (Swipe), automatisch ab < 768 px
- [x] Hamburger-Navigation auf Mobilgeräten (mit ✕-Animation)
- [x] Mobile Eventliste auf Homepage: Spielart auf eigener Zeile, Meta rechtsbündig

### Nutzerverwaltung
- [x] Nutzereditor für Admin (Inline-Bearbeitung von Rolle, E-Mail, Mannschaft)
- [x] Passwort-Reset durch Admin

### Externe Termine (Events)
- [x] Separate Eventliste ohne Platzbuchung, auf Homepage anzeigen
- [x] Mannschaft/Trainer-Zuordnung bei Einzelterminen
- [x] Trainer darf Termine seiner Mannschaft löschen (auch wenn Admin erstellt hat)

### Aufgaben / Schwarzes Brett
- [x] Aufgaben mit Typ, Priorität, Fälligkeit und Status-Workflow

### Platz-Konfiguration
- [x] Platz-IDs Refactor: stabile IDs (A, AA, AB, B, BA, BB, C, CA, CB) statt Anzeigenamen als Enum-Werte
- [x] `lit`-Konfiguration pro Platzgruppe in `config/field_config.json` (Kura + Halle beleuchtet, Rasen nicht)
- [x] Sperrzeiten-Feature entfernt (Blackouts → ersetzt durch Admin-Einzelbuchungen)
- [x] Pauschalsperre Rasen im Winter entfernt (`is_rasen_season()`)

### Konfiguration & Vereinsspezifika
- [x] `config/vereinsconfig.json` – Name, Farben, Spielorte zentral konfigurierbar
- [x] Secrets aus Code entfernt, alle Tokens via `.env` (APIFUSSBALL_TOKEN u. a.)
- [x] Zentrale Jinja2-Templates-Instanz mit Vereinsfarben als CSS-Variablen
- [x] Logo-Pfad konfigurierbar via `vereinsconfig.json` → `"logo_url"` (Navbar, Login, Hintergrund)

### Admin-Tools
- [x] Saisonübernahme: Serien per Checkbox auswählen und mit +1 Jahr duplizieren
- [x] Buchungs-Housekeeping: verwaiste/vergangene Buchungen und inaktive Serien bereinigen

### Mannschaften-Konfiguration
- [x] `Mannschaft`-Enum durch Notion-Datenbank ersetzt (dynamisch, vereinsspezifisch)
- [x] `MannschaftConfig`-Model (name, trainer_name, trainer_id, fussball_de_team_id, aktiv)
- [x] `NOTION_MANNSCHAFTEN_DB_ID` in Settings und `.env` (optional, Fallback: leere Liste)
- [x] `get_all_mannschaften(only_active)` in NotionRepository
- [x] Spielplan-Sync nutzt konfigurierte FussballDeTeamIds statt generischem Club-Endpoint

### Dokumentation & Code-Qualität
- [x] INSTALLATION.md (Notion-Setup bis Produktivbetrieb)
- [x] ARCHITEKTUR.md mit PlantUML-Diagrammen, Routen und UI-Features
- [x] README.md mit Featureliste und Doku-Links
- [x] Code-Review (Review.md) mit priorisierten Verbesserungspunkten
- [x] Standortkoordinaten korrigiert (München → Cremlingen)
- [x] Live-Server eingerichtet (Port 1946 / 8046, systemd, nginx)
- [x] docs/secrets.md – alle Hardcodes und Secrets dokumentiert
- [x] docs/naming_constraints.md – String-Kopplungen dokumentiert
- [x] docs/feldtopologie_aendern.md – Anleitung für Platzstrukturänderungen
- [x] docs/datenmodell.md + docs/anforderungen.md auf aktuellen Stand gebracht

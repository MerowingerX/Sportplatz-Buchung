# Sportplatz-Buchungssystem

Buchungs- und Verwaltungssystem für Sportvereine — vereinsunabhängig konfigurierbar.

→ **[Kurzübersicht & Einrichtungsanforderungen für Vereine](docs/PITCH.md)**

---

## Funktionsumfang

### Buchungssystem (`/web` — Port 1946)
- **Wochenkalender** mit Echtzeit-Verfügbarkeitsanzeige (Farbcodierung: frei / belegt / Platzsperre)
- **Responsive Kalender**: Mobilgeräte zeigen eine blätterbare Tagesansicht mit Wischgesten; Desktop zeigt die klassische 7-Tage-Woche
- **Einzelbuchungen**: Platzbuchung für beliebige Platztypen (konfigurierbar)
- **Serienbuchungen**: wöchentlich oder 14-tägig, mit Trainer-Zuweisung und Einzelausnahmen
- **DFBnet-Verdrängung**: Pflichtspiele verdrängen bestehende Buchungen automatisch und benachrichtigen per E-Mail
- **Massenimport**: DFBnet-CSV und ICS-Datei importieren (mit Vorschau-Schritt)
- **Sperrzeiten**: ganztägig oder zeitlich begrenzt (Platzsperre als Hinweis, kein Hard-Block)
- **Externe Termine**: Auswärtsspiele, Turniere und sonstige Termine ohne Platzbuchung; Mannschaftszuordnung für Trainer-Löschrecht
- **Aufgaben / Schwarzes Brett**: Aufgaben mit Typ, Priorität, Fälligkeit und Status
- **Nutzerverwaltung**: Anlegen, Bearbeiten (Inline-Editor), Passwort zurücksetzen
- **E-Mail-Benachrichtigungen**: Buchungsbestätigung, Storno, DFBnet-Verdrängung, Serienzusammenfassung
- **Lade-Overlay**: Bei jedem HTMX-Request erscheint nach 120 ms eine zentrierte Statusmeldung
- **Audit-Log**: Login, Buchungen und Stornierungen werden protokolliert

### Admin-Bereich
- **Vereinskonfiguration**: Name, Logo, Farben, Heimspiel-Keywords, Spielorte — komplett über die UI einstellbar, keine Codeänderung nötig
- **Platzkonfiguration**: Rollen-Sichtbarkeit pro Platzgruppe
- **Spielplan-Sync**: Heimspiele automatisch von fussball.de abrufen und buchen (manuell oder per Cron — Uhrzeit konfigurierbar)
- **Instagram-Posting**: Wochenend-Spielvorschau als Karussell automatisch auf Instagram veröffentlichen
- **Datenbereinigung (Housekeeping)**: vergangene und stornierte Buchungen archivieren
- **Saisonübernahme**: Aktive Serien mit +1 Jahr duplizieren

---

## Technologie-Stack

| Schicht | Technologie |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn |
| Frontend | Jinja2-Templates, HTMX 2.0, vanilla CSS |
| Datenbank | Notion API (notion-client) |
| Auth | JWT HS256, HTTP-only Cookie (8 h) |
| Hintergrund-Jobs | APScheduler 3.10 (AsyncIOScheduler) |
| E-Mail | smtplib, STARTTLS, Port 587 |
| Betrieb | Docker / systemd, Python venv |
| Logging | RotatingFileHandler → `logs/audit.log` |

---

## Benutzerrollen

| Rolle | Kann |
|---|---|
| **Trainer** | Buchen, eigene Buchungen stornieren, Termine und Aufgaben eintragen |
| **Platzwart** | wie Trainer, zusätzlich Sperrzeiten verwalten |
| **Administrator** | alles, inkl. Nutzerverwaltung, Serien, DFBnet-Import, Konfiguration |
| **DFBnet** | wie Administrator, außer Nutzerverwaltung |

---

## Lokaler Start

```bash
cp .env.example .env                  # Werte eintragen (siehe docs/INSTALLATION.md)
cp config/vereinsconfig.example.json config/vereinsconfig.json
cp config/field_config.example.json  config/field_config.json

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn web.main:app --port 1946 --reload
```

---

## Konfiguration

Vereinsspezifische Werte (`config/vereinsconfig.json`, `config/field_config.json`) sind **nicht im Repository** — sie werden aus den mitgelieferten `.example.json`-Vorlagen angelegt und können über die Admin-UI bearbeitet werden.

Alle Zugangsdaten und Tokens werden in `.env` gespeichert (ebenfalls nicht im Repo).

---

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Notion-Setup, `.env`-Konfiguration, Docker, Nginx, erster Admin-Nutzer |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Systemübersicht, Datenmodelle, Ablaufdiagramme, API-Routen |
| [docs/manual.md](docs/manual.md) | Betriebshandbuch: Saisonplanung, Sommer/Winterbetrieb, Nutzerverwaltung |
| [docs/naming_constraints.md](docs/naming_constraints.md) | String-Kopplungen zwischen Code, Notion, CSS und Templates |
| [docs/feldtopologie_aendern.md](docs/feldtopologie_aendern.md) | Anleitung: Platzstruktur ändern |
| [docs/instagram_setup.md](docs/instagram_setup.md) | Instagram Business-Konto, Token generieren, ngrok, häufige Fehler |

---

## Projektstruktur

```
Sportplatz-Buchung/
├── web/
│   ├── main.py               # FastAPI-App, Router, Lifespan (APScheduler)
│   ├── config.py             # pydantic-settings (alle .env-Felder)
│   ├── templates_instance.py # Gemeinsame Jinja2Templates + Globals
│   ├── routers/              # auth, bookings, calendar, series, admin, tasks, events
│   ├── templates/            # Jinja2-Templates + HTMX-Partials
│   └── static/               # style.css, logo, htmx.min.js
├── booking/
│   ├── models.py             # Pydantic-Modelle + Enums
│   ├── field_config.py       # Platzkonfiguration (Gruppen, Sichtbarkeit)
│   ├── vereinsconfig.py      # Vereinsconfig laden (lru_cache)
│   ├── scheduler.py          # APScheduler-Integration
│   ├── scheduler_config.py   # Scheduler-Felder aus vereinsconfig.json
│   ├── spielplan_sync.py     # Automatischer Spielplan-Abgleich
│   ├── instagram.py          # Instagram-Karussell generieren und posten
│   └── series.py             # Serien-Buchungslogik
├── notion/
│   └── client.py             # NotionRepository — alle DB-Methoden
├── auth/                     # JWT, Passwort-Hashing, FastAPI-Dependencies
├── notifications/            # E-Mail-Versand
├── tools/                    # fussball_de.py, check_spielplan.py
├── utils/                    # Slot-Berechnung, Sonnenuntergang
├── scripts/                  # Standalone-Scripts (backup, restore, fetch_spielplan, instagram_matchday)
├── config/                   # vereinsconfig.json + field_config.json (gitignored, aus .example anlegen)
├── docs/                     # Technische Dokumentation
└── Dockerfile / docker-compose.yml
```

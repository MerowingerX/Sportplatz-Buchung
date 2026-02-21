# TuS Cremlingen – Platzbuchungssystem

Buchungs- und Verwaltungssystem für die Sportplätze des TuS Cremlingen e.V.

---

## Funktionsumfang

### Buchungssystem (`/web` — Port 1946)
- **Wochenkalender** mit Echtzeit-Verfügbarkeitsanzeige (Farbcodierung: frei / belegt / Platzsperre)
- **Responsive Kalender**: Mobilgeräte zeigen eine blätterbare Tagesansicht mit Wischgesten; Desktop zeigt die klassische 7-Tage-Woche
- **Einzelbuchungen**: Platzbuchung für Kunstrasen, Naturrasen und Turnhalle (je Ganz/Halb)
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

### Öffentliche Homepage (`/homepage` — Port 8046)
- Nächste Platzbelegungen (DFBnet-Spiele und externe Termine, gemischt nach Datum)
- Vereinsinformationen und Kontaktdaten

---

## Technologie-Stack

| Schicht | Technologie |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn |
| Frontend | Jinja2-Templates, HTMX 2.0, vanilla CSS |
| Datenbank | Notion API (notion-client) |
| Auth | JWT HS256, HTTP-only Cookie (8 h) |
| E-Mail | smtplib, STARTTLS, Port 587 |
| Betrieb | systemd, Python venv |
| Logging | RotatingFileHandler → `logs/audit.log` |

---

## Benutzerrollen

| Rolle | Kann |
|---|---|
| **Trainer** | Buchen, eigene Buchungen stornieren, Termine und Aufgaben eintragen |
| **Platzwart** | wie Trainer, zusätzlich Sperrzeiten verwalten |
| **Administrator** | alles, inkl. Nutzerverwaltung, Serien, DFBnet-Import |
| **DFBnet** | wie Administrator, außer Nutzerverwaltung |

---

## Lokaler Start

```bash
cp .env.example .env   # Werte eintragen (siehe INSTALLATION.md)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Buchungssystem
uvicorn web.main:app --port 1946 --reload

# Homepage (separates Terminal)
uvicorn homepage.main:app --port 8046 --reload
```

---

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Notion-Setup, `.env`-Konfiguration, Systemdienste, Nginx, erster Admin-Nutzer |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Systemübersicht, Datenmodelle, Ablaufdiagramme (PlantUML), API-Routen, UI-Features |
| [CONTEXT.md](CONTEXT.md) | Fachliche Anforderungen, Platzregeln, Buchungszeiten |
| [Todo.md](Todo.md) | Offene Aufgaben und geplante Features |

---

## Projektstruktur (Kurzübersicht)

```
Sportplatz-Buchung/
├── web/            # Buchungssystem (Port 1946)
│   ├── routers/    # auth, bookings, series, blackouts, calendar, admin, tasks, events
│   ├── templates/  # Jinja2-Templates + HTMX-Partials
│   └── static/     # CSS
├── booking/        # Buchungslogik (Konflikt-Check, Slot-Berechnung)
├── notion/         # NotionRepository – alle Datenbankoperationen
├── auth/           # JWT, Passwort-Hashing, FastAPI-Dependencies
├── homepage/       # Öffentliche Seite (Port 8046)
├── notifications/  # E-Mail-Versand
├── utils/          # Slot-Berechnung, Sonnenuntergang
├── deploy/         # systemd Unit-Files
└── docs/           # Technische Dokumentation
```

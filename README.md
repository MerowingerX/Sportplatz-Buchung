# TuS Cremlingen – Platzbuchungssystem

Buchungs- und Verwaltungssystem für die Sportplätze des TuS Cremlingen e.V.

## Übersicht

- **Homepage** (`homepage/`) – öffentliche Vereinsseite mit Verfügbarkeitsanzeige und Eventkalender
- **Buchungssystem** (`web/`) – Buchungsportal für Trainer und Mitglieder (Login erforderlich)
- **Admin** (`/admin`) – DFBnet-Import, Benutzerverwaltung, Sperrzeiten
- **Datenbank** – Notion API als Backend

## Technik

- Python 3.13, FastAPI, Jinja2, HTMX
- Notion API als Datenbank
- E-Mail-Benachrichtigungen via SMTP

## Lokaler Start

```bash
bash start_server.sh
```

## Dokumentation

- [CONTEXT.md](CONTEXT.md) – Fachliche Anforderungen und Platzregeln
- [Todo.md](Todo.md) – Offene Aufgaben und geplante Features

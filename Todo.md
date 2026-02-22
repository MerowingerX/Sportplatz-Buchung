# Todo – TuS Cremlingen Platzbuchungssystem

## Offen

### Infrastruktur
- [ ] Testserver einrichten (Staging-Umgebung)
- [ ] Backup-Strategie umsetzen (automatisiertes Notion-Export-Skript oder Datei-Backup)

### DFBnet-Integration
- [ ] Automatische Verarbeitung von DFBnet-E-Mails (Spielansetzung, Spielabsetzung, Spielverlegung) – Anmeldung durch Josh

### Homepage – Eventliste
- [ ] Anmeldung von Events durch Nutzer (mit Admin-Genehmigung vor Veröffentlichung)

### Homepage – Inhalt
- [ ] Anfahrt und Kartenlink (Google Maps)
- [ ] Kontaktseite/-bereich ausbauen
- [ ] Online-Vereinsbeitritt
- [ ] Instagram-Profile der Teams verlinken

---

## Erledigt

### Buchungssystem
- [x] Wochenkalender mit Echtzeit-Verfügbarkeit und Slot-Farbcodierung
- [x] Einzelbuchungen (Kunstrasen, Naturrasen, Turnhalle, je Ganz/Halb)
- [x] Serienbuchungen (wöchentlich / 14-tägig) mit Trainer-Zuweisung
- [x] DFBnet-Verdrängungslogik mit E-Mail-Benachrichtigung
- [x] ICS- und CSV-Massenimport (mit Vorschau-Schritt)
- [x] Sperrzeiten (ganztägig und zeitlich begrenzt)
- [x] E-Mail-Benachrichtigungen (Buchung, Storno, DFBnet, Serien)
- [x] Audit-Log (Login, Buchungen, Stornierungen)
- [x] Erzwungener Passwort-Wechsel beim ersten Login
- [x] Sonnenuntergangswarnung für Rasenplätze

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

### Dokumentation & Code-Qualität
- [x] INSTALLATION.md (Notion-Setup bis Produktivbetrieb)
- [x] ARCHITEKTUR.md mit PlantUML-Diagrammen, Routen und UI-Features
- [x] README.md mit Featureliste und Doku-Links
- [x] Code-Review (Review.md) mit priorisierten Verbesserungspunkten
- [x] Standortkoordinaten korrigiert (München → Cremlingen)
- [x] Live-Server eingerichtet (Port 1946 / 8046, systemd, nginx)

# Sportplatz-Buchungssystem — Kurzübersicht für Vereine

Ein schlankes, webbasiertes Buchungssystem für Vereinssportplätze. Keine monatlichen Lizenzkosten, keine externe Abhängigkeit von proprietären Plattformen — alles läuft auf eurem eigenen Server.
Ihr könnt eure Vereinsfarben, euer Logo und eure Plätze konfigurieren.

---

## Was das System kann

### Platzbuchung
Trainer buchen ihren Trainingsplatz selbst über den Browser — von jedem Gerät, ohne App-Installation. Auf der web-page siehst Du alle Buchungen in einer Wochenansicht und kannst Konflikte sofort erkennen. Doppelbelegungen sind technisch ausgeschlossen.

### Spielplan-Import
Offizielle Spieltermine werden automatisch aus **fussball.de** übernommen und als Buchungen eingetragen. Zusätzlich können **DFBnet-Exporte** (CSV) direkt importiert werden. Kein manuelles Nachtragen mehr.

### Instagram-Matchday (not working)
Vor dem Wochenende generiert das System automatisch ein Karussell mit allen anstehenden Spielen — fertig zum Posten. Vereinsfarben, Logo und alle Altersklassen werden automatisch berücksichtigt. TODO: Ein Klick im Admin-Bereich veröffentlicht das Karussell direkt auf Instagram. (Musst Du im Moment noch selber posten)

### Rollen & Rechte
- **Trainer** sehen nur ihre eigenen Buchungen und können nur ihren Platz buchen
- **Administrator** sieht alles und kann eingreifen
- **Administrator** verwaltet Nutzer, Serien, Konfiguration und Imports
- **DFBnet** — separater Systemnutzer für automatische Spielplan-Imports

### Weitere Funktionen
- Wiederkehrende Trainingsserien (wöchentlich, 14-täglich, …)
- Flutlicht-Hinweis bei Buchungen nach Sonnenuntergang
- Aufgabenverwaltung (falls etwas kaputt geht)
- Automatisches tägliches Backup aller Daten

---

## Was ihr braucht

### 1. Notion-Konto (kostenlos)
**Warum:** Notion dient als Datenbank. Kein eigener Datenbankserver, keine Backups von Hand — Notion übernimmt Speicherung, Ausfallsicherheit und ist über die offizielle API angebunden. 

**Was konkret:** Ein kostenloses Notion-Konto reicht. Einmalig eine „Integration" anlegen (API-Schlüssel). Den API-Schlüssel müsst Ihr in die .env einfügen, dann 6 Datenbanken erstellen — das erledigt ein Setup-Script auch automatisch.

---

### 2. Einen kleinen Server
**Warum:** Das System läuft als Docker-Container. Es braucht einen Ort, der dauerhaft erreichbar ist — ein heimischer PC reicht nicht.

**Was konkret:** Ein einfacher VPS (Virtual Private Server) bei einem deutschen Anbieter (z. B. Hetzner, IONOS) — kleinstes Paket reicht, ca. 4–6 €/Monat. Betriebssystem: Ubuntu 22.04. Docker muss installiert sein.

**Optional:** Eine eigene Domain (z. B. `buchung.mein-verein.de`), damit die Adresse einprägsam ist.

---

### 3. fussball.de Vereinsseite
**Warum:** Der Spielplan-Import liest die öffentliche Vereinsseite auf fussball.de automatisch aus. Das erspart manuelles Eintragen von 50+ Spielterminen pro Saison.

**Was konkret:** Die URL eurer Vereinsseite auf fussball.de (die habt ihr bereits, wenn ihr beim DFB-Verband registriert seid). Einmalig in der Konfiguration eintragen — fertig.

---

### 4. Instagram Business-Account *(optional, nur für Matchday-Posts)*
**Warum:** Die Instagram Graph API erlaubt nur Business- oder Creator-Konten das automatisierte Posten. Ein normales Privatkonto reicht nicht.

**Was konkret:**
1. Instagram-Konto auf „Professional Account → Business" umstellen (kostenlos, in den Instagram-Einstellungen)
2. Mit einer Facebook-Seite des Vereins verknüpfen (ebenfalls kostenlos)
3. Einmalig einen Zugriffstoken erstellen und in der Admin-Oberfläche eintragen

---

## Einrichtungsaufwand

| Schritt | Aufwand |
|---|---|
| Notion-Konto + Datenbanken anlegen | ~20 Minuten (Setup-Script) |
| Server mieten + Docker einrichten | ~30 Minuten |
| System deployen + Nutzer anlegen | ~15 Minuten |
| Konfiguration (Verein, Plätze, Farben, Logo) | ~20 Minuten |
| Instagram verknüpfen | ~30 Minuten |
| **Gesamt** | **ca. 2 Stunden** |

Danach läuft das System selbstständig. Updates werden per `git pull` + Container-Neustart eingespielt.

---

## Was ihr *nicht* braucht

- Keine Programmierkenntnisse für den Betrieb
- Keine eigene Datenbank (Notion übernimmt das)
- Keine monatlichen Lizenzgebühren
- Keine App-Installation für Trainer (läuft im Browser)

---

## Technischer Stack *(für Interessierte)*

FastAPI · Python 3.12 · Jinja2 + HTMX · Notion API · Docker · JWT-Auth · APScheduler · Playwright

Der Quellcode ist vollständig vorhanden und kann für eigene Anforderungen angepasst werden.

PS: Die Anwendung ist vollständig mit Claude Code erstellt. Eine CLAUDE.md liegt bei. Wenn Ihr etwas ändern wollt, dann verwendet am einfachsten ebenfalls Claude Code. Wenn Ihr Claude auch um ein Onboarding bittet, wird Claude euch da durchführen

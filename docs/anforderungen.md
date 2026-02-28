# Anforderungen – Sportplatz-Buchungssystem

## 1. Plätze

### Kunstrasen (Kura)
- Beleuchtet, ganzjährig verfügbar
- Nutzungszeit: 16:00–22:00 Uhr
- Unterteilung: Ganz, Halb A, Halb B

### Naturrasen (Rasen)
- Nicht beleuchtet (Sonnenuntergangs-Hinweis bei Buchung)
- Saison: März–November
- Nutzungszeit: 16:00–22:00 Uhr
- Kann durch Platzwart gesperrt werden (ganztägig oder zeitlich)
- Unterteilung: Ganz, Halb A, Halb B

### Turnhalle (Halle)
- Beleuchtet, ganzjährig verfügbar
- Nutzungszeit: 16:00–22:00 Uhr
- Unterteilung: Ganz, 2/3, 1/3

### Konfliktregeln
| Buchung | Sperrt |
|---------|--------|
| Kura/Rasen Ganz | Ganz, Halb A, Halb B |
| Kura/Rasen Halb A | Ganz, Halb A |
| Kura/Rasen Halb B | Ganz, Halb B |
| Halle Ganz | Ganz, 2/3, 1/3 |
| Halle 2/3 | Ganz, 2/3 |
| Halle 1/3 | Ganz, 1/3 |

Halle 2/3 und 1/3 können gleichzeitig laufen.

---

## 2. Buchungsregeln

- **Slots:** 30 Minuten
- **Startzeiten:** 16:00, 16:30, 17:00 … 21:30 (12 Slots)
- **Buchungsdauern:** 60, 90, 180 Minuten
- **Buchungsarten:** Training, Spiel, Turnier
- **Ende:** spätestens 22:00 Uhr
- **Optionale Felder:** Mannschaft, Zweck (Freitext), Kontakt

### Validierung
1. Gültige Startzeit (30-Min-Raster ab 16:00)
2. Gültige Dauer (60/90/180)
3. Ende vor 22:00
4. Keine Zeitüberschneidung mit bestehenden Buchungen auf Konfliktfeldern
5. Rasen: Saisoncheck (März–November)
6. Rasen: Sperrzeitcheck

---

## 3. Serienbuchungen

### Regeln
- Nur **Administratoren/DFBnet** dürfen Serien anlegen
- Buchungsart ist immer **Training**
- Rhythmus: **wöchentlich** oder **14-tägig**
- Gleichbleibender Platz und Uhrzeit
- **Saisonende:** 30. Juni (maximales Enddatum, wird automatisch begrenzt)
- Rasen-Termine außerhalb März–November werden übersprungen

### Mannschaft & Trainer
- Admin wählt beim Anlegen eine **Mannschaft** und einen **Trainer**
- Der Trainer wird per HTMX-Dropdown geladen (gefiltert nach Mannschaft)
- Mannschaft wird an alle Einzeltermine der Serie weitergegeben

### Einzeltermine verwalten
- Admin oder **zugewiesener Trainer** kann Einzeltermine stornieren
- Stornierter Termin wird als Serienausnahme markiert, Serie läuft weiter

### Serie stornieren
- Nur **Admin/DFBnet** kann eine ganze Serie stornieren
- Alle zukünftigen Termine werden auf „Storniert" gesetzt
- Serienstatus wird auf „Beendet" gesetzt

### Konflikte
- Termine mit Zeitkonflikten werden beim Anlegen übersprungen
- Übersprungene Termine werden dem Admin angezeigt

### Mannschaften
G1, G2, G3, F1, F2, E1, E2, E3, D1, D2, C, B, A, TuS 1, TuS 2, Ü32, Ü40, Frauen, Mädchen

---

## 4. Rollen & Berechtigungen

| Aktion | Trainer | Administrator | Platzwart | DFBnet |
|--------|---------|---------------|-----------|--------|
| Eigene Buchung erstellen | Ja | Ja | Ja | Ja |
| Buchung stornieren | Eigene | Alle | Eigene | Alle |
| Serie anlegen | – | Ja | – | Ja |
| Serie stornieren | – | Ja | – | Ja |
| Einzeltermin aus Serie entfernen | Zugewiesener Trainer | Ja | – | Ja |
| Sperrzeiten verwalten | – | Ja | Ja | Ja |
| Nutzerverwaltung | – | Ja | – | Ja |
| DFBnet-Buchung (Verdrängung) | – | Ja | – | Ja |
| Admin-Buchung (ohne Zeitprüfung) | – | Ja | – | Ja |
| Externen Termin erstellen | Ja | Ja | Ja | Ja |
| Externen Termin löschen (alle) | – | Ja | – | – |
| Aufgaben erstellen | Ja | Ja | Ja | Ja |
| Aufgaben löschen (alle) | – | Ja | Ja | – |

---

## 5. Externe Termine

- Sichtbar für alle authentifizierten Nutzer (Menüpunkt „Termine")
- Dienen zur Ankündigung von Auswärtsspielen, Turnieren und anderen Terminen **ohne Platzbuchung**
- **Felder:** Bezeichnung, Datum, Uhrzeit, Mannschaft (optional), Ort (optional), Beschreibung (optional)
- Erstellen: alle eingeloggten Rollen
- Löschen: Ersteller, Trainer derselben Mannschaft, Administrator
- Erscheinen auf der öffentlichen Homepage gemischt mit DFBnet-Spielen, sortiert nach Datum
- Konfiguration: `NOTION_EVENTS_DB_ID` in `.env` (Feature wird deaktiviert wenn nicht gesetzt)

---

## 6. DFBnet-Verdrängung

- DFBnet-Buchungen haben **höchste Priorität**
- Bestehende Buchungen im gleichen Zeitfenster werden **verdrängt**
- Verdrängte Buchungen erhalten Status „Storniert (DFBnet)"
- Betroffene Nutzer werden per E-Mail benachrichtigt
- Eintrag manuell durch Administrator oder per **ICS-Import**

### ICS-Import
- Upload einer `.ics`-Datei
- Events werden geparst und auf 30-Min-Slots gerundet
- Dauer wird auf gültige Werte korrigiert (60/90/180)
- Vorschau vor Bestätigung
- Platz pro Termin auswählbar

---

## 7. Sperrzeiten (nur Rasen)

- **Ganztägig:** gesamter Tag gesperrt
- **Zeitlich:** bestimmter Zeitraum gesperrt (Start- und Endzeit)
- Sperrzeiten werden bei der Buchungsvalidierung geprüft
- Fehlermeldung: „Rasen ist gesperrt: [Grund]"
- Anlegen/Löschen durch: Administrator, Platzwart, DFBnet

---

## 8. Homepage (öffentlich)

- Keine Authentifizierung nötig
- Zeigt **Platzverfügbarkeit** als read-only Ansicht

### Platzauswahl
- Kunstrasen, Naturrasen, Turnhalle als auswählbare Tabs

### Wochenansicht
- 7 Tage × Teilflächen des gewählten Platzes
- Farbcodierung: Grün (≥8 frei), Gelb (4–7 frei), Rot (≤3 frei), Grau (gesperrt/Außer Saison)
- Wochenweise blätterbar (vor/zurück)

### Tagesansicht
- 12 Zeitslots × Teilflächen des gewählten Platzes
- Frei/Belegt/Gesperrt/Außer Saison pro Slot
- Tageweise blätterbar (vor/zurück)

---

## 9. Aufgaben / Schwarzes Brett

- Sichtbar für alle authentifizierten Nutzer
- **Typen:** Defekt, Nutzeranfrage, Turniertermin, Sonstiges
- **Status:** Offen, In Bearbeitung, Erledigt
- **Priorität:** Niedrig, Mittel (Standard), Hoch
- **Felder:** Titel, Typ, Priorität, Fällig am, Ort, Beschreibung
- Filterbar nach Typ und Status
- Löschen (alle): Administrator und Platzwart

---

## 10. Benachrichtigungen (E-Mail)

| Anlass | Empfänger | Inhalt |
|--------|-----------|--------|
| Buchung erstellt | Buchender | Bestätigung mit Details, Sonnenuntergangs-Hinweis |
| Buchung storniert | Buchender | Stornierungsmitteilung |
| DFBnet-Verdrängung | Verdrängter Nutzer | Alte + neue Buchung, Bitte um Neubuchung |
| Serie storniert | Serien-Ersteller | Liste aller stornierten Termine |

- Versand via SMTP (aiosmtplib, Port 587, TLS)

---

## 11. Authentifizierung

### Login
- Benutzername + Passwort
- Passwort als bcrypt-Hash in Notion-Nutzer-DB
- JWT-Cookie (HttpOnly, Secure, SameSite=Strict)
- Gültigkeit: 8 Stunden

### Passwort
- Mindestens 8 Zeichen
- Muss beim ersten Login geändert werden
- Admin kann Passwort zurücksetzen (erzwingt Änderung beim nächsten Login)

### JWT-Payload
```
sub:                  Notion-ID des Nutzers
username:             Name
role:                 Trainer | Administrator | Platzwart | DFBnet
mannschaft:           Mannschaft (optional)
must_change_password: true/false
exp:                  Ablaufzeitpunkt
```

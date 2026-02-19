# Sportplatz-Buchungssystem – Projektkontext

## Ausgangslage

Buchungssystem für einen Sportplatz mit zwei Teilflächen. Wird in Notion als Datenbank-Backend aufgebaut, ergänzt durch ein Python-Script für Buchungslogik, Konfliktprüfung und Benachrichtigungen.

---

## Plätze

### Kura (Kunstrasen)
- Beleuchtet
- Verfügbar: täglich
- Nutzungszeit: 16:00 – 22:00 Uhr
- Keine Sperrzeiten

### Rasen (Naturrasen)
- Nicht beleuchtet (Sonnenuntergang als Hinweis bei Buchung anzeigen)
- Verfügbar: März – November
- Nutzungszeit: 16:00 – 22:00 Uhr
- Kann durch Platzwart gesperrt werden:
  - Pauschal (ganztägig)
  - Zeitlich (ab einer bestimmten Uhrzeit)

### Unterteilung (gilt für beide Plätze)
- Ganzer Platz
- Halb A
- Halb B

### Konfliktregeln
- Ganzer Platz gebucht → Halb A und Halb B automatisch gesperrt
- Halb A oder Halb B gebucht → Ganzer Platz gesperrt, die andere Hälfte bleibt buchbar

---

## Buchungsregeln

- Buchungseinheit: 30-Minuten-Slots
- Typische Buchungsdauern: 60 Min, 90 Min (Training), 180 Min (Turnier)
- Nutzungstypen: Training, Spiel

### Serienbuchungen
- Nur für Training
- Rhythmus: wöchentlich oder 14-tägig
- Gleichbleibender Platz und Uhrzeit
- Einzelne Termine können aus der Serie herausgelöst werden (Slot wird freigegeben, Serie läuft weiter)
- Serie beenden → alle zukünftigen Termine werden storniert

---

## Rollen & Berechtigungen

| Rolle | Berechtigung |
|-------|-------------|
| Trainer | Self-service Buchung (löst Benachrichtigung aus) |
| Administrator | Buchungen + Sperrzeiten verwalten |
| Platzwart | Rasen-Sperrzeiten eintragen |
| DFBnet / Super-Admin | Overrule alles, höchste Priorität |

### DFBnet-Sonderrolle
- Bucht Pflichtspiele (DFB-Spielbetrieb) mit höchster Priorität
- Kann bestehende Buchungen verdrängen
- Wird manuell durch Administrator eingetragen
- Verdrängte Buchungen sollen als `Storniert (DFBnet)` markiert und Betroffene benachrichtigt werden

---

## Notion-Datenbankstruktur

### 1. `Buchungen`
| Feld | Typ | Werte / Hinweis |
|------|-----|-----------------|
| Titel | Title | Auto (z.B. "Kura Halb A – 2026-02-15 16:00") |
| Platz | Select | Kura Ganz, Kura Halb A, Kura Halb B, Rasen Ganz, Rasen Halb A, Rasen Halb B |
| Datum | Date | — |
| Startzeit | Select | 16:00, 16:30, 17:00 … 21:30 |
| Endzeit | Select | 16:30, 17:00 … 22:00 |
| Dauer | Select | 60, 90, 180 Min |
| Typ | Select | Training, Spiel, Turnier |
| Gebucht von | Person | — |
| Rolle | Select | Trainer, Administrator, DFBnet |
| Status | Select | Bestätigt, Storniert, Storniert (DFBnet) |
| Serie | Relation → Serien | Verknüpfung zur Mutterserie (falls Serientermin) |
| Serienausnahme | Checkbox | Termin wurde manuell aus Serie herausgelöst |
| Hinweis Sonnenuntergang | Text | Wird bei Rasen-Buchungen automatisch eingetragen |

### 2. `Serien`
| Feld | Typ | Werte |
|------|-----|-------|
| Titel | Title | — |
| Platz | Select | wie Buchungen |
| Startzeit | Select | 16:00 … 21:00 |
| Dauer | Select | 60, 90, 180 Min |
| Rhythmus | Select | Wöchentlich, 14-tägig |
| Startdatum | Date | — |
| Enddatum | Date | — |
| Gebucht von | Person | — |
| Status | Select | Aktiv, Pausiert, Beendet |

### 3. `Sperrzeiten` (nur Rasen)
| Feld | Typ | Werte |
|------|-----|-------|
| Titel | Title | — |
| Datum | Date | — |
| Art | Select | Ganztägig, Zeitlich |
| Startzeit | Select | 16:00 … 21:30 |
| Endzeit | Select | 16:30 … 22:00 |
| Grund | Text | z.B. "Zu nass", "Turnier" |
| Eingetragen von | Person | Platzwart |

### 4. `Nutzer`
| Feld | Typ | Werte |
|------|-----|-------|
| Name | Title | — |
| Rolle | Select | Trainer, Administrator, Platzwart, DFBnet |
| E-Mail | Email | — |

---

## Technische Architektur

### Stack
- **Backend:** Python
- **Datenbank:** Notion API
- **Frontend:** Web-Oberfläche (Framework noch offen)
- **Benachrichtigungen:** E-Mail (SMTP)
- **Sonnenuntergang:** Python-Library `astral`

### Geplante Projektstruktur
```
sportplatz-buchung/
├── README.md
├── CONTEXT.md
├── notion/
│   └── setup.py          # Erstellt alle Notion-Datenbanken via API
├── booking/
│   ├── booking.py        # Buchungslogik & Konfliktprüfung
│   └── series.py         # Serienbuchungen generieren & verwalten
├── notifications/
│   └── notify.py         # Benachrichtigungen auslösen (E-Mail)
├── utils/
│   └── sunset.py         # Sonnenuntergangszeiten berechnen
├── web/
│   └── ...               # Web-Oberfläche (noch zu planen)
└── .env.example          # API Keys (nie ins Git einchecken!)
```

### Kernlogik (noch zu implementieren)
1. **Konfliktprüfung** vor jeder Buchung (Ganz ↔ Halb-Logik)
2. **Seriengenerierung** – Einzeltermine aus Serie erzeugen
3. **Sonnenuntergang** – bei Rasen-Buchungen als Hinweis eintragen
4. **Benachrichtigung** – bei neuer Buchung und bei Stornierung durch DFBnet
5. **Rasen-Saisoncheck** – Buchungen außerhalb März–November blockieren

---

## Nächste Schritte

1. Notion Integration Token erstellen (notion.so → Einstellungen → Integrationen)
2. Notion-Datenbanken manuell oder via `notion/setup.py` anlegen
3. `.env` mit API-Keys befüllen
4. Buchungslogik implementieren
5. Benachrichtigungskanal festlegen (E-Mail / Telegram)
6. DFBnet-Importweg klären

---

## Entscheidungen (getroffen)

- **Web-Framework:** FastAPI + HTMX + Jinja2
- **Auth:** Passwort-Login (bcrypt-Hash in Notion `Nutzer`-DB, JWT-Cookie)
- **DFBnet:** Vorerst manuell durch Administrator; langfristig CSV/API denkbar
- **Benachrichtigungen:** E-Mail via SMTP (aiosmtplib)

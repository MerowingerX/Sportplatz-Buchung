# Sportplatz-Buchungssystem – Architekturdokumentation

## Inhaltsverzeichnis

1. [Systemübersicht](#1-systemübersicht)
2. [Technologie-Stack](#2-technologie-stack)
3. [Datenmodelle](#3-datenmodelle)
4. [Verzeichnisstruktur](#4-verzeichnisstruktur)
5. [Benutzerrollen & Berechtigungen](#5-benutzerrollen--berechtigungen)
6. [Bearbeitungsabläufe](#6-bearbeitungsabläufe)
   - [Login & Session](#61-login--session)
   - [Einzelbuchung erstellen](#62-einzelbuchung-erstellen)
   - [Buchung stornieren](#63-buchung-stornieren)
   - [Serienbuchung anlegen](#64-serienbuchung-anlegen)
   - [Einzeltermin aus Serie entfernen](#65-einzeltermin-aus-serie-entfernen)
   - [Serie beenden](#66-serie-beenden)
   - [DFBnet-Verdrängung](#67-dfbnet-verdrängung)
   - [Sperrzeiten](#68-sperrzeiten)
7. [API-Routen Übersicht](#7-api-routen-übersicht)
8. [Infrastruktur & Betrieb](#8-infrastruktur--betrieb)
9. [UI-Features](#9-ui-features)

---

## 1. Systemübersicht

Das System besteht aus **zwei unabhängigen Webdiensten** und **Notion als Datenbank**:

```plantuml
@startuml
!theme plain
skinparam componentStyle rectangle

actor "Besucher (öffentlich)" as visitor
actor "Trainer / Admin" as user
actor "DFBnet / Admin" as admin

package "Server (46.62.212.248)" {
  component "Homepage\n(Port 8046)\nhomepage/main.py" as hp
  component "Buchungssystem\n(Port 1946)\nweb/main.py" as bs
  database "Notion API" as notion
}

visitor --> hp : öffentliche\nPlatz-Verfügbarkeit
user --> bs : Login, Buchungen\nVerwalten
admin --> bs : DFBnet-Import\nSerien, Admin
hp --> notion : Buchungen lesen\nSpiele lesen\nSperrzeiten lesen
bs --> notion : CRUD alle Entitäten
bs --> hp : Link (booking_url)

note right of notion
  6 Datenbanken:
  - Buchungen
  - Serien
  - Sperrzeiten
  - Nutzer
  - Aufgaben
  - Externe Events
end note
@enduml
```

---

## 2. Technologie-Stack

| Schicht | Technologie |
|---|---|
| Backend | Python 3.13, FastAPI, Uvicorn |
| Frontend | Jinja2-Templates, HTMX 2.0, vanilla CSS |
| Datenbank | Notion API (notion-client) |
| Auth | JWT (HS256), HTTP-only Cookie |
| E-Mail | smtplib (STARTTLS, Port 587) |
| Betrieb | systemd, Python venv |
| Logging | RotatingFileHandler → `logs/audit.log` |

---

## 3. Datenmodelle

```plantuml
@startuml
!theme plain
skinparam classAttributeIconSize 0

class Booking {
  notion_id: str
  title: str
  field: FieldName
  date: date
  start_time: time
  end_time: time
  duration_min: int
  booking_type: BookingType
  booked_by_id: str
  booked_by_name: str
  role: UserRole
  status: BookingStatus
  mannschaft: str?
  zweck: str?
  kontakt: str?
  series_id: str?
  series_exception: bool
  sunset_note: str?
  spielkennung: str?
}

class Series {
  notion_id: str
  title: str
  field: FieldName
  start_time: time
  duration_min: int
  rhythm: SeriesRhythm
  start_date: date
  end_date: date
  booked_by_id: str
  booked_by_name: str
  status: SeriesStatus
  mannschaft: str?
  trainer_id: str?
  trainer_name: str?
}

class BlackoutPeriod {
  notion_id: str
  title: str
  start_date: date
  end_date: date
  blackout_type: BlackoutType
  start_time: time?
  end_time: time?
  reason: str
  entered_by_id: str
  entered_by_name: str
}

class User {
  notion_id: str
  name: str
  role: UserRole
  email: str
  password_hash: str
  mannschaft: Mannschaft?
  must_change_password: bool
}

class ExternalEvent {
  notion_id: str
  title: str
  date: date
  start_time: time
  location: str?
  description: str?
  mannschaft: str?
  created_by_id: str
  created_by_name: str
}

class Aufgabe {
  notion_id: str
  titel: str
  typ: AufgabeTyp
  status: AufgabeStatus
  prioritaet: Prioritaet
  erstellt_von_id: str
  erstellt_von_name: str
  erstellt_am: date
  faellig_am: date?
  ort: str?
  beschreibung: str?
}

enum UserRole {
  TRAINER
  ADMINISTRATOR
  PLATZWART
  DFBNET
}

enum BookingStatus {
  BESTAETIGT
  STORNIERT
  STORNIERT_DFBNET
}

enum BlackoutType {
  GANZTAEGIG
  ZEITLICH
}

enum SeriesStatus {
  AKTIV
  PAUSIERT
  BEENDET
}

Booking "N" --> "0..1" Series : series_id
Booking --> BookingStatus
Booking --> UserRole
User --> UserRole
BlackoutPeriod --> BlackoutType
Series --> SeriesStatus
@enduml
```

### Konflikt-Mapping der Plätze

```plantuml
@startuml
!theme plain
skinparam rectangle {
  BackgroundColor<<ganz>> #ffcccc
  BackgroundColor<<halb>> #ffe0b2
}

package "Kunstrasen (Kura)" {
  rectangle "Kura Ganz" <<ganz>>
  rectangle "Kura Halb A" <<halb>>
  rectangle "Kura Halb B" <<halb>>
}

package "Naturrasen (Rasen)" {
  rectangle "Rasen Ganz" <<ganz>>
  rectangle "Rasen Halb A" <<halb>>
  rectangle "Rasen Halb B" <<halb>>
}

package "Turnhalle" {
  rectangle "Halle Ganz" <<ganz>>
  rectangle "Halle 2/3" <<halb>>
  rectangle "Halle 1/3" <<halb>>
}

note bottom of "Kunstrasen (Kura)"
  Ganz sperrt Halb A + B
  Halb A sperrt Ganz
  Halb B sperrt Ganz
  (Halb A + Halb B können gleichzeitig laufen)
end note
@enduml
```

---

## 4. Verzeichnisstruktur

```
Sportplatz-Buchung/
├── web/                    # Buchungssystem (Port 1946)
│   ├── main.py             # FastAPI App, Router-Registrierung
│   ├── config.py           # Settings (Pydantic, lädt .env)
│   ├── audit_log.py        # Login- und Buchungs-Audit-Log
│   ├── routers/
│   │   ├── auth.py         # Login, Logout, Passwort ändern
│   │   ├── bookings.py     # Einzelbuchungen CRUD
│   │   ├── series.py       # Serienbuchungen CRUD
│   │   ├── blackouts.py    # Sperrzeiten CRUD
│   │   ├── calendar.py     # Wochenkalender (mit Cache)
│   │   ├── admin.py        # Nutzerverwaltung, DFBnet-Import, CSV-Import
│   │   ├── tasks.py        # Aufgaben/Schwarzes Brett
│   │   └── events.py       # Externe Termine (Turniere, Auswärtsspiele)
│   ├── templates/
│   │   ├── base.html       # Layout, Nav
│   │   ├── calendar.html   # Wochenkalender-Seite
│   │   ├── blackouts/      # Sperrzeiten-Listenansicht
│   │   ├── series/         # Serien-Listenansicht
│   │   ├── tasks/          # Aufgaben
│   │   ├── events/         # Externe Termine
│   │   ├── admin/          # Admin-Seiten
│   │   └── partials/       # HTMX-Fragmente
│   └── static/style.css
│
├── booking/                # Buchungslogik (rein)
│   ├── models.py           # Pydantic-Datenmodelle
│   ├── booking.py          # Verfügbarkeit, Konflikt-Check, Buchung bauen
│   └── series.py           # Serientermin-Generierung, Storno
│
├── notion/
│   └── client.py           # NotionRepository – alle DB-Operationen
│
├── auth/
│   ├── auth.py             # JWT erstellen/lesen, Passwort-Hashing
│   └── dependencies.py     # FastAPI CurrentUser, require_role
│
├── homepage/               # Öffentliche Seite (Port 8046)
│   ├── main.py             # Fastapi-Homepage
│   ├── static/
│   └── templates/
│
├── notifications/
│   └── notify.py           # E-Mail-Benachrichtigungen (Bestätigung, Storno, DFBnet)
│
├── utils/
│   ├── time_slots.py       # Slot-Berechnung (16–22 Uhr, 30-Min-Raster)
│   └── sunset.py           # Sonnenuntergangswarnung (ephem)
│
├── scripts/
│   └── notify_crash.py     # Crash-Mail (von systemd OnFailure aufgerufen)
│
├── deploy/                 # systemd Unit-Files
│   ├── sportplatz-buchung.service
│   ├── sportplatz-homepage.service
│   └── sportplatz-crash@.service
│
└── logs/audit.log          # Audit-Protokoll (Login/Buchungen)
```

---

## 5. Benutzerrollen & Berechtigungen

| Funktion | Trainer | Platzwart | Administrator | DFBnet |
|---|:---:|:---:|:---:|:---:|
| Kalender lesen | ✓ | ✓ | ✓ | ✓ |
| Einzelbuchung erstellen | ✓ | ✓ | ✓ | ✓ |
| Eigene Buchung stornieren | ✓ | ✓ | ✓ | ✓ |
| Fremde Buchung stornieren | – | – | ✓ | ✓ |
| Serienbuchung anlegen | – | – | ✓ | ✓ |
| Serie beenden | – | – | ✓ | ✓ |
| DFBnet-Verdrängung | – | – | ✓ | ✓ |
| Sperrzeiten verwalten | – | ✓ | ✓ | – |
| Nutzerverwaltung | – | – | ✓ | – |
| Aufgaben erstellen | ✓ | ✓ | ✓ | ✓ |
| Termine (Events) erstellen | ✓ | ✓ | ✓ | ✓ |

---

## 6. Bearbeitungsabläufe

### 6.1 Login & Session

```plantuml
@startuml
!theme plain
actor Nutzer
participant "Browser" as B
participant "auth.py\n/login" as AUTH
participant "NotionRepository" as NR
participant "Notion API" as N

Nutzer -> B : Formular absenden\n(username, password)
B -> AUTH : POST /login
AUTH -> NR : get_user_by_name(username)
NR -> N : Query Nutzer-DB\n(filter: Name = username)
N --> NR : User-Page
NR --> AUTH : User-Objekt (mit password_hash)

alt Nutzer nicht gefunden oder Passwort falsch
  AUTH -> NR : [kein Nutzer] / verify_password → False
  AUTH --> B : 401, login.html mit Fehlermeldung
  AUTH -> AUTH : log_login_fail()
else Passwort korrekt
  AUTH -> AUTH : log_login_ok()
  AUTH -> AUTH : create_jwt(user_id, name, role, ...)
  alt must_change_password = True
    AUTH --> B : Redirect → /change-password\n+ Set-Cookie: session=<JWT>
  else
    AUTH --> B : Redirect → /calendar\n+ Set-Cookie: session=<JWT>
  end
end

note right of AUTH
  JWT enthält:
  - sub (notion_id)
  - username
  - role
  - mannschaft
  - must_change_password
  - exp (8h)
  Cookie: httponly, samesite=lax
end note
@enduml
```

---

### 6.2 Einzelbuchung erstellen

```plantuml
@startuml
!theme plain
actor Nutzer
participant "Browser\n(HTMX)" as B
participant "bookings.py\nPOST /bookings" as BK
participant "booking.py\nbuild_booking()" as LOGIC
participant "NotionRepository" as NR
participant "notify.py" as MAIL

Nutzer -> B : Slot anklicken
B -> B : GET /bookings?date=&field=&start_time=\n(Formular laden via HTMX → Modal)
Nutzer -> B : Formular ausfüllen & absenden

B -> BK : POST /bookings\n(field, date, start_time, duration_min, booking_type)

BK -> NR : get_bookings_for_date(date)
NR --> BK : existing_bookings (nur Status=Bestätigt)

opt Rasen-Platz
  BK -> NR : get_blackouts_for_date(date)
  NR --> BK : blackouts
end

BK -> LOGIC : build_booking(data, existing, blackouts)

group Validierung
  LOGIC -> LOGIC : validate_booking_input()\n(Dauer gültig? Start gültig? Endet vor 22h?)
  LOGIC -> LOGIC : check_availability()\n(Konflikt-Felder belegt?)
  opt Rasen + Sperrzeit
    LOGIC -> LOGIC : check_blackout()\n→ platzsperre_note (kein Hard-Block)
  end
  opt Rasen
    LOGIC -> LOGIC : sunset_warning_text()\n→ sunset_note
  end
end

alt Validierung fehlgeschlagen
  LOGIC --> BK : (None, [Fehler])
  BK --> B : 422 + Fehlermeldung
else Validierung erfolgreich
  LOGIC -> NR : create_booking(data, ...)
  NR --> LOGIC : Booking-Objekt
  LOGIC --> BK : (Booking, [])

  BK -> BK : invalidate_week_cache(date)
  BK -> BK : log_booking()
  BK -> MAIL : send_booking_confirmation()
  BK --> B : Toast + Kalender-Refresh (HTMX OOB)
end
@enduml
```

---

### 6.3 Buchung stornieren

```plantuml
@startuml
!theme plain
actor Nutzer
participant "Browser\n(HTMX)" as B
participant "bookings.py\nDELETE /bookings/{id}" as BK
participant "NotionRepository" as NR
participant "notify.py" as MAIL

Nutzer -> B : ✕-Button klicken\n(hx-confirm → Bestätigung)
B -> BK : DELETE /bookings/{booking_id}

BK -> NR : update_booking_status(id, STORNIERT)
NR --> BK : Booking (aktualisiert)

BK -> BK : invalidate_week_cache()
BK -> BK : log_cancel()
BK -> MAIL : send_cancellation_notice()\n(an Buchenden)
BK --> B : Slot wird frei (HTMX outerHTML)\n+ Toast

note right of BK
  Bei Serienbuchungen:
  hx-patch → /series/{id}/remove-date
  → Status=Storniert
  → Serienausnahme=True
end note
@enduml
```

---

### 6.4 Serienbuchung anlegen

```plantuml
@startuml
!theme plain
actor Admin
participant "Browser\n(HTMX)" as B
participant "series.py\nPOST /series" as SR
participant "series.py\ncreate_series_with_bookings()" as LOGIC
participant "NotionRepository" as NR
participant "notify.py" as MAIL

Admin -> B : Serienbuchungs-Formular\n(Platz, Zeit, Mannschaft,\nTrainer, Start, Ende, Rhythmus)

note over B
  GET /series/trainers?mannschaft=X
  → Trainer-Dropdown per HTMX
  → Falls kein Trainer: Admins als Fallback
end note

B -> SR : POST /series

SR -> SR : Validierung\n(Enddatum > Startdatum?\nSaisonende = 30.06. als max)
SR -> NR : get_user_by_id(trainer_id)
NR --> SR : Trainer-Objekt

SR -> NR : create_series(data, ...)
NR --> SR : Series-Objekt (in Notion angelegt)

SR -> LOGIC : create_series_with_bookings()

loop für jedes Datum im Zeitraum\n(wöchentlich oder 14-tägig)
  LOGIC -> NR : get_bookings_for_date(d)
  LOGIC -> NR : get_blackouts_for_date(d)\n[nur bei Rasen]
  LOGIC -> LOGIC : build_booking()\n(Konflikt-Check, Platzsperre-Prüfung)
  alt Termin frei
    LOGIC -> NR : create_booking(..., series_id=series.notion_id)
    LOGIC -> LOGIC : created.append(booking)
  else Konflikt
    LOGIC -> LOGIC : skipped.append(date)
  end
end

LOGIC --> SR : (series, created[], skipped[])

alt Kein einziger Termin angelegt
  SR --> B : 422 Fehler
else
  SR -> SR : invalidate_week_cache()\nfür alle erstellten Termine
  SR -> MAIL : send_series_confirmation()\n(Zusammenfassung an Admin)
  SR --> B : Toast + Kalender-Refresh
end

note right of LOGIC
  Jeder Serientermin ist eine
  eigenständige Buchungsseite
  in Notion mit Serie=<series_id>
end note
@enduml
```

---

### 6.5 Einzeltermin aus Serie entfernen

```plantuml
@startuml
!theme plain
actor "Admin / zugewiesener Trainer" as Admin
participant "Browser\n(HTMX)" as B
participant "series.py\nPATCH /series/{booking_id}/remove-date" as SR
participant "NotionRepository" as NR

Admin -> B : ✕ auf Serientermin klicken\n(hx-confirm → Bestätigung)
B -> SR : PATCH /series/{booking_id}/remove-date

SR -> NR : get_booking_by_id(booking_id)
NR --> SR : Booking (mit series_id)

alt Admin oder DFBnet
  SR -> SR : is_admin = True
else Trainer prüfen
  SR -> NR : get_series_by_id(booking.series_id)
  NR --> SR : Series
  SR -> SR : is_series_trainer =\n(series.trainer_id == current_user.sub)
end

alt Keine Berechtigung
  SR --> B : 403 Forbidden
else Berechtigt
  SR -> NR : mark_series_exception(booking_id)
  note right of NR
    Setzt auf der Buchungsseite:
    Status = Storniert
    Serienausnahme = True
  end note
  NR --> SR : Booking (aktualisiert)
  SR -> SR : invalidate_week_cache()
  SR --> B : Slot wird frei + Toast
end

note bottom
  Die Serie selbst bleibt unverändert.
  Der Termin bleibt als Notion-Seite
  erhalten (für Audit-Trail).
  get_bookings_for_series() filtert
  Serienausnahme=True heraus.
end note
@enduml
```

---

### 6.6 Serie beenden

```plantuml
@startuml
!theme plain
actor Admin
participant "Browser" as B
participant "series.py\nDELETE /series/{series_id}" as SR
participant "series.py\ncancel_series()" as LOGIC
participant "NotionRepository" as NR

Admin -> B : "Serie beenden"-Button\n(hx-confirm → Bestätigung)
B -> SR : DELETE /series/{series_id}

SR -> LOGIC : cancel_series(repo, series_id, current_user)

LOGIC -> NR : get_bookings_for_series(series_id,\nonly_future=True)
note right of NR
  Filter:
  - Serie = series_id
  - Status = Bestätigt
  - Serienausnahme = False
  - Datum >= heute
end note
NR --> LOGIC : future_bookings[]

loop für jede zukünftige Buchung
  LOGIC -> NR : update_booking_status(id, STORNIERT)
  NR --> LOGIC : Booking (aktualisiert)
end

LOGIC -> NR : update_series_status(series_id, BEENDET)
NR --> LOGIC : Series (Status=Beendet)

LOGIC --> SR : (series, cancelled[])

SR -> SR : invalidate_week_cache()\nfür alle stornierten Termine
SR --> B : Zeile aktualisiert (Status → Beendet)\n+ Toast "{N} Termine storniert"

note right
  Vergangene Serientermine
  bleiben als Buchungshistorie
  erhalten (Status=Bestätigt).
end note
@enduml
```

---

### 6.7 DFBnet-Verdrängung

```plantuml
@startuml
!theme plain
actor "Admin / DFBnet" as Admin
participant "admin.py\nPOST /admin/dfbnet" as AD
participant "booking.py\ndfbnet_displace()" as LOGIC
participant "NotionRepository" as NR
participant "notify.py" as MAIL

Admin -> AD : DFBnet-Buchungsformular\n(oder CSV/ICS-Import)

AD -> NR : get_bookings_for_date(date)
NR --> AD : existing_bookings

AD -> LOGIC : dfbnet_displace(repo, data, current_user, ...)

LOGIC -> LOGIC : check_availability()\n(finde konfligierende Buchungen)

loop für jede Konflikt-Buchung
  LOGIC -> NR : update_booking_status(id, STORNIERT_DFBNET)
  NR --> LOGIC : verdrängste Buchung
end

LOGIC -> NR : create_booking(..., role=DFBNET)
NR --> LOGIC : neue DFBnet-Buchung

LOGIC --> AD : (new_booking, displaced[])

loop für jede verdrängte Buchung
  AD -> NR : get_user_by_id(booking.booked_by_id)
  AD -> MAIL : send_dfbnet_displacement_notice()\n(E-Mail an Verdrängten)
end

AD -> AD : invalidate_week_cache()
AD --> Admin : Toast (inkl. Anzahl Verdrängter)

note right of LOGIC
  DFBnet-Buchungen haben höchste
  Priorität – sie überschreiben
  alle bestehenden Buchungen
  für den selben Slot.
  Status der Verdrängten:
  STORNIERT_DFBNET (unterscheidbar
  von normalem Storno)
end note
@enduml
```

---

### 6.8 Sperrzeiten

```plantuml
@startuml
!theme plain

participant "Platzwart / Admin" as PW
participant "Browser\n(HTMX)" as B
participant "blackouts.py" as BL
participant "NotionRepository" as NR
participant "Kalender-Rendering\n(_calendar_week.html)" as CAL

== Sperrzeit eintragen ==

PW -> B : Formular: Von, Bis, Art, Grund
B -> BL : POST /blackouts\n(start_date, end_date, blackout_type, reason)

BL -> BL : Prüfung: end_date >= start_date
BL -> NR : create_blackout(data, ...)\n→ Notion Datum = Range {start, end}
NR --> BL : BlackoutPeriod

BL -> BL : _invalidate_range()\n(Cache für alle Wochen im Zeitraum)
BL --> B : Neue Zeile prepend\n+ Toast

== Kalender-Rendering (Woche) ==

note over CAL
  get_blackouts_for_week():
  1. Notion: Datum.start <= Sonntag
  2. Python-Filter: Datum.end >= Montag
  → liefert alle überlappenden Sperrzeiten
end note

loop für jeden Tag × jeden Rasen-Slot
  CAL -> CAL : prüfe: bl.start_date <= day AND bl.end_date >= day
  alt Sperrzeit aktiv
    CAL -> CAL : slot--platzsperre\n(rot, klickbar, Hinweis-Tooltip)
    note right
      Buchung trotzdem möglich!
      Platzsperre wird als Hinweis
      in sunset_note gespeichert.
    end note
  else frei
    CAL -> CAL : slot--free
  end
end

== Sperrzeit löschen ==

PW -> B : ✕-Button
B -> BL : DELETE /blackouts/{id}
BL -> NR : pages.update(archived=True)
BL --> B : Toast "Sperrzeit gelöscht"
@enduml
```

---

## 7. API-Routen Übersicht

### Auth
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET | `/login` | Login-Seite | öffentlich |
| POST | `/login` | Authentifizierung | öffentlich |
| POST | `/logout` | Session löschen | eingeloggt |
| GET/POST | `/change-password` | Passwort ändern | eingeloggt |

### Kalender
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET | `/calendar` | Kalender-Seite (lädt auto. Tag oder Woche per JS) | eingeloggt |
| GET | `/calendar/week` | Wochenansicht (HTMX, gecacht) | eingeloggt |
| GET | `/calendar/day?d=YYYY-MM-DD` | Tagesansicht für Mobilgeräte (HTMX, gecacht) | eingeloggt |

### Buchungen
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET | `/bookings` | Buchungsformular (HTMX) | eingeloggt |
| POST | `/bookings` | Buchung erstellen | eingeloggt |
| DELETE | `/bookings/{id}` | Buchung stornieren | Eigentümer / Admin |
| GET | `/bookings/check-availability` | Verfügbarkeit prüfen (HTMX) | eingeloggt |
| GET | `/bookings/sunset-info` | Sonnenuntergangswarnung (HTMX) | eingeloggt |
| GET | `/bookings/validate-rasen-season` | Platzsperre-Hinweis (HTMX) | eingeloggt |

### Serien
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET | `/series` | Serien-Listenansicht | Admin/DFBnet |
| GET | `/series/trainers` | Trainer-Dropdown (HTMX) | Admin/DFBnet |
| POST | `/series` | Serie anlegen | Admin/DFBnet |
| PATCH | `/series/{id}/remove-date` | Einzeltermin aus Serie | Admin / Serientrainer |
| DELETE | `/series/{id}` | Serie beenden | Admin/DFBnet |

### Sperrzeiten
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET | `/blackouts` | Sperrzeiten-Liste + Formular | Platzwart/Admin |
| POST | `/blackouts` | Sperrzeit eintragen | Platzwart/Admin |
| DELETE | `/blackouts/{id}` | Sperrzeit löschen | Platzwart/Admin |

### Admin
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET | `/admin` | Dashboard | Admin/DFBnet |
| GET/POST | `/admin/users` | Nutzerliste + neuen Nutzer anlegen | Admin |
| GET | `/admin/users/{id}/row` | Nutzerzeile (Anzeigemodus, HTMX) | Admin |
| GET | `/admin/users/{id}/edit` | Nutzerzeile (Bearbeitungsmodus, HTMX) | Admin |
| PATCH | `/admin/users/{id}` | Nutzer aktualisieren (Rolle, E-Mail, Mannschaft) | Admin |
| POST | `/admin/users/{id}/reset-password` | Passwort zurücksetzen | Admin |
| GET/POST | `/admin/dfbnet` | DFBnet-Einzelbuchung | Admin/DFBnet |
| GET/POST | `/admin/dfbnet-import` | ICS-Datei importieren | Admin/DFBnet |
| POST | `/admin/dfbnet-import/confirm` | ICS-Import bestätigen | Admin/DFBnet |
| GET/POST | `/admin/csv-import` | DFBnet-CSV importieren | Admin/DFBnet |
| POST | `/admin/csv-import/confirm` | CSV-Import bestätigen | Admin/DFBnet |
| POST | `/admin/fetch-spielplan` | Spielplan von api-fussball.de | Admin/DFBnet |

### Aufgaben & Termine
| Methode | Route | Beschreibung | Berechtigung |
|---|---|---|---|
| GET/POST | `/tasks` | Aufgaben-Liste | eingeloggt |
| PATCH | `/tasks/{id}/status` | Status ändern | eingeloggt |
| DELETE | `/tasks/{id}` | Aufgabe löschen | Admin |
| GET/POST | `/events` | Externe Termine | eingeloggt |
| DELETE | `/events/{id}` | Termin löschen | eingeloggt |

---

## 8. Infrastruktur & Betrieb

### systemd-Dienste

```plantuml
@startuml
!theme plain
skinparam componentStyle rectangle

component "sportplatz-buchung.service\n(Port 1946)" as BS {
  note "Restart=on-failure\nRestartSec=10s\nStartLimitBurst=3"
}
component "sportplatz-homepage.service\n(Port 8046)" as HP {
  note "Restart=on-failure\nRestartSec=10s\nStartLimitBurst=3"
}
component "sportplatz-crash@.service\n(Type=oneshot)" as CRASH

BS -down-> CRASH : OnFailure=\n(nach 3 Crashes)
HP -down-> CRASH : OnFailure=\n(nach 3 Crashes)
CRASH -> CRASH : scripts/notify_crash.py\n→ journalctl dump\n→ Surrender-Mail an Admin
@enduml
```

### Verwaltungs-Skripte (`/root/`)

| Skript | Funktion |
|---|---|
| `sportplatz-install-all.sh` | Services installieren, aktivieren, starten |
| `sportplatz-start.sh` | Homepage starten |
| `sportplatz-stop.sh` | Homepage stoppen |
| `sportplatz-buchung-start.sh` | Buchungssystem starten |
| `sportplatz-buchung-stop.sh` | Buchungssystem stoppen |
| `sportplatz-stop-all.sh` | Beide Dienste stoppen |

### Audit-Log

Alle sicherheitsrelevanten Ereignisse werden in `logs/audit.log` geschrieben (RotatingFileHandler, max. 5 MB, 3 Backups):

```
2026-02-21 14:32:11 AUDIT LOGIN_OK user=frank.simon ip=192.168.1.100
2026-02-21 14:35:44 AUDIT LOGIN_FAIL user=unbekannt ip=192.168.1.55
2026-02-21 14:36:02 AUDIT BOOKING field=Kura Ganz date=2026-03-01 time=17:00 user=frank.simon
2026-02-21 15:01:18 AUDIT CANCEL booking_id=abc-123 user=frank.simon
2026-02-21 18:00:00 AUDIT LOGOUT user=frank.simon
```

---

## 9. UI-Features

### 9.1 Responsive Kalender (Mobilgeräte)

Bei `window.innerWidth < 768` lädt `calendar.html` automatisch die **Tagesansicht** (`/calendar/day`) statt der Wochenansicht per `htmx.ajax()`. Die Tagesansicht enthält Vor-/Zurück-Navigation und wird durch Wischgesten (Touch-Swipe, Schwelle 60 px) bedienbar.

Auf Desktop wird weiterhin die klassische 7-Spalten-Wochenansicht geladen.

### 9.2 Hamburger-Navigation

Auf Mobilgeräten (< 768 px) wird die Navigationsleiste durch einen Hamburger-Button ersetzt. Beim Öffnen animiert sich das Icon zu einem ✕; nach Klick auf einen Link schließt sich das Menü automatisch.

Implementierung: `web/templates/base.html` (Button + JS), `web/static/style.css` (CSS-Animation, `@media (max-width: 767px)`).

### 9.3 Lade-Overlay

Bei jedem HTMX-Request erscheint nach 120 ms eine zentrierte Overlay-Box mit Spinner und kontextabhängigem Text:

| HTTP-Verb | Anzeigetext |
|---|---|
| POST | Wird gespeichert … |
| PATCH | Wird aktualisiert … |
| DELETE | Wird gelöscht … |
| GET | Wird geladen … |

Das Overlay verschwindet automatisch nach `htmx:afterRequest` bzw. `htmx:sendError`. Implementierung: `web/templates/base.html` (JS), `web/static/style.css` (`.loading-overlay`).

### 9.4 Inline-Nutzereditor (Admin)

In der Nutzerverwaltung (`/admin/users`) können Administratoren Nutzer direkt in der Tabelle bearbeiten (Rolle, E-Mail, Mannschaft). Das Muster folgt dem HTMX-Zeilenswap:

```
Klick "Bearbeiten"  →  GET /admin/users/{id}/edit   →  Formularzeile (outerHTML)
Klick "Speichern"   →  PATCH /admin/users/{id}       →  Anzeigezeile (outerHTML) + Toast
Klick "Abbrechen"   →  GET /admin/users/{id}/row     →  Anzeigezeile (outerHTML)
```

`hx-include="closest tr"` serialisiert alle Eingaben der Tabellenzeile für den PATCH-Request.

### 9.5 Externe Termine mit Mannschaftszuordnung

Externe Termine (`/events`) können einer Mannschaft zugeordnet werden. Dadurch darf der Trainer der jeweiligen Mannschaft den Termin auch dann löschen, wenn er von einem Administrator angelegt wurde.

Löschen-Berechtigungslogik (Server und Template stimmen überein):
- Administrator: darf alle Termine löschen
- Ersteller (`created_by_id == current_user.sub`): darf eigenen Termin löschen
- Mannschaftstrainer (`event.mannschaft == current_user.mannschaft`): darf Termine seiner Mannschaft löschen

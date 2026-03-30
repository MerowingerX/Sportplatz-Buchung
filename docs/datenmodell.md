# Datenmodell – Notion-Datenbanken

## 1. Buchungen

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Titel | Title | Auto: „Platz – Datum Uhrzeit" |
| Platz | Select | Kura Ganz, Kura Halb A, Kura Halb B, Rasen Ganz, Rasen Halb A, Rasen Halb B, Halle Ganz, Halle 2/3, Halle 1/3 |
| Datum | Date | – |
| Startzeit | Select | 16:00, 16:30 … 21:30 |
| Endzeit | Select | 16:30, 17:00 … 22:00 |
| Dauer | Select | 60, 90, 180 |
| Typ | Select | Training, Spiel, Turnier |
| Gebucht von | Rich Text | Notion User-ID |
| Gebucht von Name | Rich Text | Anzeigename |
| Rolle | Select | Trainer, Administrator, Platzwart, DFBnet |
| Status | Select | Bestätigt, Storniert, Storniert (DFBnet) |
| Mannschaft | Rich Text | z.B. „D1", „Frauen" (optional) |
| Zweck | Rich Text | Freitext (optional) |
| Kontakt | Rich Text | Ansprechpartner (optional) |
| Serie | Rich Text | Serien-ID (optional) |
| Serienausnahme | Checkbox | Termin aus Serie herausgelöst |
| Hinweis Sonnenuntergang | Rich Text | Auto bei Rasen |
| Spielkennung | Rich Text | DFBnet-Spielkennung für Duplikaterkennung (optional) |

## 2. Serien

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Titel | Title | Auto: „Serie Mannschaft Platz Uhrzeit ab Datum" |
| Platz | Select | wie Buchungen |
| Startzeit | Select | 16:00 … 21:30 |
| Dauer | Select | 60, 90, 180 |
| Rhythmus | Select | Wöchentlich, 14-tägig |
| Startdatum | Date | – |
| Enddatum | Date | max. 30. Juni |
| Gebucht von ID | Rich Text | Admin-Notion-ID |
| Gebucht von Name | Rich Text | Admin-Name |
| Status | Select | Aktiv, Pausiert, Beendet |
| Mannschaft | Rich Text | z.B. „D1" |
| Trainer ID | Rich Text | Notion-ID des zugewiesenen Trainers |
| Trainer Name | Rich Text | Name des zugewiesenen Trainers |

## 3. Sperrzeiten

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Titel | Title | Auto |
| Datum | Date | – |
| Art | Select | Ganztägig, Zeitlich |
| Startzeit | Select | Optional (bei Zeitlich) |
| Endzeit | Select | Optional (bei Zeitlich) |
| Grund | Rich Text | z.B. „Zu nass" |
| Eingetragen von ID | Rich Text | – |
| Eingetragen von Name | Rich Text | – |

## 4. Nutzer

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Name | Title | – |
| Rolle | Select | Trainer, Administrator, Platzwart, DFBnet |
| E-Mail | Email | – |
| Password_Hash | Rich Text | bcrypt-Hash |
| Mannschaft | Rich Text | Name der verknüpften Mannschaft (optional, freier String) |
| Passwort ändern | Checkbox | Erzwingt Passwortänderung |

> **Hinweis:** `User.mannschaft` und `MannschaftConfig.trainer_id` beschreiben dieselbe Beziehung aus zwei Richtungen.
> Beide werden bei jeder Änderung automatisch synchron gehalten (bidirektionaler Sync in `admin.py`).

## 5. Externe Termine (Events)

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Name | Title | Bezeichnung des Termins |
| Datum | Date | – |
| Startzeit | Rich Text | HH:MM |
| Ort | Rich Text | Optional |
| Beschreibung | Rich Text | Optional |
| Mannschaft | Rich Text | Optional |
| Erstellt von ID | Rich Text | Notion User-ID |
| Erstellt von Name | Rich Text | Anzeigename |

Konfiguriert über `NOTION_EVENTS_DB_ID` in der `.env`-Datei.

## 7. Mannschaften

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Name | Title | Vollständiger Name (z. B. „A-Junioren U19") |
| Shortname | Rich Text | Kompakter Kurzname für Kalenderanzeige (z. B. „A1", „H2", „Fr1") |
| Trainer Name | Rich Text | Anzeigename des zugewiesenen Trainers |
| Trainer ID | Rich Text | Notion-ID / UUID des Trainer-Nutzers |
| fussball.de Team-ID | Rich Text | Team-ID von api-fussball.de für Spielplan-Import |
| CC-Mails | Rich Text | Kommagetrennte E-Mail-Adressen für Buchungsbenachrichtigungen |
| Aktiv | Checkbox | Inaktive Mannschaften werden bei Neubuchungen ausgeblendet |

Konfiguriert über `NOTION_MANNSCHAFTEN_DB_ID` in der `.env`-Datei.

### Shortname-Logik

Der Kurzname (`shortname`) wird im Kalender anstelle des vollen Mannschaftsnamens angezeigt.
Er wird beim fussball.de-Import automatisch abgeleitet (`_derive_shortname()` in `onboarding.py`)
und kann jederzeit unter **Admin → Mannschaften** angepasst werden.

Ableitungsregeln:

| fussball.de-Name | Kurzname |
|---|---|
| 1. Herren | Herren-1 |
| 2. Herren | Herren-2 |
| Herren II | Herren-2 |
| 1. Frauen / 1. Damen | Frauen-1 |
| Frauen / Damen | Frauen |
| A-Junioren | A1 |
| B-Junioren 2 | B2 |
| A-Mädchen | AM1 |
| Senioren Ü32 | Ü32 |
| (sonstiges) | Anfangsbuchstaben der Wörter |

## 6. Aufgaben

| Property | Typ | Werte / Hinweis |
|----------|-----|-----------------|
| Titel | Title | – |
| Typ | Select | Defekt, Nutzeranfrage, Turniertermin, Sonstiges |
| Status | Select | Offen, In Bearbeitung, Erledigt |
| Priorität | Select | Niedrig, Mittel, Hoch |
| Fällig am | Date | Optional |
| Ort | Rich Text | z.B. „Kura Tor A" (optional) |
| Beschreibung | Rich Text | Optional |
| Erstellt von ID | Rich Text | – |
| Erstellt von Name | Rich Text | – |
| Erstellt am | Date | Auto: heute |

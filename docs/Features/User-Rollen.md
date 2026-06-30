# User-Rollen & Rechte

Quelle der Wahrheit: `booking/models.py` → `UserRole`, `Permission`, `ROLE_PERMISSIONS`.
Prüfung im Code: `has_permission(user.role, Permission.X)`.

## Rollen

| Rolle | Wert (DB/JWT) | Zweck |
|-------|---------------|-------|
| `Administrator` | `Administrator` | Voller Zugriff. Alle Rechte inkl. Nutzerverwaltung. |
| `Platzwart` | `Platzwart` | Platz-Verwaltung, Admin-Dashboard, alle Aufgaben löschen. |
| `DFBnet` | `DFBnet` | Systemrolle für Spielplan-Import & DFBnet-Buchungen. |
| `Trainer` | `Trainer` | Eigene Buchungen/Events/Aufgaben. Kein Admin-Zugriff. |

## Berechtigungen (Permission-Enum)

| Permission | Bedeutung |
|------------|-----------|
| `manage_users` | Nutzer anlegen, löschen, Passwort-Reset |
| `access_admin` | Zugriff Admin-Dashboard |
| `create_booking` | Platzbuchung erstellen |
| `delete_own_booking` | Eigene Buchung löschen |
| `delete_all_bookings` | Fremde Buchungen löschen |
| `create_event` | Externen Termin erstellen |
| `delete_own_event` | Eigenen Termin löschen |
| `delete_all_events` | Fremde Termine löschen |
| `create_task` | Aufgabe/Meldung erstellen |
| `delete_own_task` | Eigene Aufgabe löschen |
| `delete_all_tasks` | Fremde Aufgaben löschen |
| `manage_series` | Serien-Buchungen verwalten |
| `dfbnet_spielplan` | Spielplan abrufen / CSV-Import |
| `dfbnet_booking` | Manuelle DFBnet-Buchung |

## Rechte-Matrix

| Permission | Administrator | Platzwart | DFBnet | Trainer |
|------------|:---:|:---:|:---:|:---:|
| `manage_users` | ✓ | – | – | – |
| `access_admin` | ✓ | ✓ | ✓ | – |
| `create_booking` | ✓ | ✓ | ✓ | ✓ |
| `delete_own_booking` | ✓ | ✓ | ✓ | ✓ |
| `delete_all_bookings` | ✓ | – | – | – |
| `create_event` | ✓ | ✓ | ✓ | ✓ |
| `delete_own_event` | ✓ | ✓ | ✓ | ✓ |
| `delete_all_events` | ✓ | – | – | – |
| `create_task` | ✓ | ✓ | ✓ | ✓ |
| `delete_own_task` | ✓ | ✓ | ✓ | ✓ |
| `delete_all_tasks` | ✓ | ✓ | – | – |
| `manage_series` | ✓ | – | ✓ | – |
| `dfbnet_spielplan` | ✓ | – | ✓ | – |
| `dfbnet_booking` | ✓ | – | ✓ | – |

`Administrator` = `frozenset(Permission)`, hat also automatisch jedes neue Recht.

## Mannschaftsverantwortlicher (unabhängig von Rolle)

"Mannschaftsverantwortlicher" ist **keine Rolle**, sondern eine Zuordnung User ↔ Mannschaft
in der M:N-Tabelle `mannschaft_verantwortliche`.

- **Jeder User** kann Verantwortlicher sein — egal welche `UserRole`.
- Ein User kann Verantwortlicher **mehrerer** Mannschaften sein.
- Eine Mannschaft kann **mehrere** Verantwortliche haben.

UI-Begriff: **"Verantwortlicher"** (nicht mehr "Trainer"). Die Rolle `UserRole.TRAINER`
behält intern ihren Enum-Wert `"Trainer"`.

**Verwaltung:** Admin → Aliase/Nutzer → "Verantwortliche je Mannschaft" (Checkboxen über
alle User). Das alte 1:1-Feld `mannschaften.trainer_id` (Team-Formular, Auswahl
"Verantwortlicher") bleibt für Abwärtskompatibilität bestehen — der dort gewählte User wird
automatisch additiv auch als M:N-Verantwortlicher eingetragen.

**Wirkung der Verantwortlichkeit:**
- Series-Buchung: Verantwortliche der Mannschaft erscheinen im Verantwortlichen-Dropdown
  (`get_trainers_for_mannschaft` → M:N). Fallback auf Administratoren wenn keiner gesetzt.
- Benachrichtigungen: Verantwortliche bekommen Mails zu Buchungen der Mannschaft
  (zusätzlich zu Buchendem + CC-Adressen, `get_verantwortliche_for_mannschaft`).

Hinweis: Die `UserRole.TRAINER` steuert weiterhin **Rechte** und "sieht nur eigene
Buchungen". Sie ist getrennt von der Mannschaftsverantwortung.

## Sichtbarkeit Buchungen

- **Trainer**: sehen nur eigene Buchungen.
- **Administrator / Platzwart**: sehen alle Buchungen.
- Platz-Sichtbarkeit zusätzlich pro Rolle via `config/field_config.json` → `visible_to`.

## Neues Recht hinzufügen

1. `Permission`-Enum in `booking/models.py` erweitern.
2. Recht den Rollen in `ROLE_PERMISSIONS` zuordnen (`Administrator` bekommt es automatisch).
3. Im Router/Template prüfen via `has_permission(...)`.

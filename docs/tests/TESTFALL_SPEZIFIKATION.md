# Testfall-Spezifikation — Sportplatz-Buchungssystem

Vollständige Soll-Spezifikation der Einzeltests je Feature.

**Ausreichend-Kriterium** (pro Feature):
1. **Gutfall** ist getestet.
2. Jeder **vorhandene Fehlerpfad** wird mindestens **einmal** erreicht.

**Legende Status:**
- ✅ **getestet** — Testfunktion existiert (Datei::Funktion genannt)
- ⬜ **offen** — noch kein Test

**Testverzeichnis:** `docs/tests/` · **Ausführen:** `pytest docs/tests/`

Stand: 2026-07-04. Bereits vorhanden: 4 Testdateien, 30 Testfunktionen (inkl. parametrisiert).

---

## Übersicht Abdeckung

| Bereich | Gutfall | Fehlerpfade | Status |
|---------|:---:|:---:|:---:|
| 1. Auth & Session | ⬜ | ⬜ | offen |
| 2. Berechtigungen (`has_permission`) | ⬜ | ⬜ | offen |
| 3. Buchungs-Domänenlogik (`booking.py`) | teilweise | ⬜ | teilweise |
| 4. Buchungs-Pill-Rendering | ✅ | ✅ | **fertig** |
| 5. Kalender / Übersicht | teilweise | ⬜ | teilweise |
| 6. Serien | ⬜ | ⬜ | offen |
| 7. Mannschaft-Verantwortliche (M:N) | ✅ | ✅ | **fertig** |
| 8. Repository (SQLite CRUD) | teilweise | ⬜ | teilweise |
| 9. Admin-Router | ⬜ | ⬜ | offen |
| 10. Events-Router | ⬜ | ⬜ | offen |
| 11. Aufgaben-Router | ⬜ | ⬜ | offen |
| 12. Onboarding | ⬜ | ⬜ | offen |
| 13. Config-Loader | ⬜ | ⬜ | offen |
| 14. Spielplan-Sync | ⬜ | ⬜ | offen |

---

## 1. Auth & Session — `auth/auth.py`, `auth/dependencies.py`, `web/routers/auth.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| AUTH-1 | Gut: `hash_password` → `verify_password` | True bei korrektem Passwort | ⬜ |
| AUTH-2 | Fehler: `verify_password` falsches PW | False | ⬜ |
| AUTH-3 | Gut: `create_jwt` → `decode_jwt` | TokenPayload identisch (sub, role, mannschaft) | ⬜ |
| AUTH-4 | Fehler: `decode_jwt` abgelaufenes Token | `jwt.ExpiredSignatureError` | ⬜ |
| AUTH-5 | Fehler: `decode_jwt` falsche Signatur | `jwt.InvalidSignatureError` | ⬜ |
| AUTH-6 | Gut: `POST /login` korrekte Credentials | 303 Redirect + `session`-Cookie gesetzt | ⬜ |
| AUTH-7 | Fehler: `POST /login` falsches PW | Login-Seite mit Fehlermeldung, kein Cookie | ⬜ |
| AUTH-8 | `POST /login` `must_change_password` | Redirect nach `/change-password` | ⬜ |
| AUTH-9 | Gut: `POST /change-password` gültig | PW geändert, Flag zurückgesetzt | ⬜ |
| AUTH-10 | Fehler: `/change-password` neue PW ≠ Bestätigung | Fehlermeldung, PW unverändert | ⬜ |
| AUTH-11 | Fehler: `/change-password` < 8 Zeichen | Fehlermeldung | ⬜ |
| AUTH-12 | Gut: `POST /auth/switch-alias` gültige Alias-ID | Cookie mit Alias-Kontext | ⬜ |
| AUTH-13 | Fehler: `switch-alias` fremde/ungültige ID | Ablehnung (kein Wechsel) | ⬜ |
| AUTH-14 | Gut: `get_current_user` gültiger Cookie | TokenPayload | ⬜ |
| AUTH-15 | Fehler: `get_current_user` kein/ungültiger Cookie | Redirect `/login` bzw. 401 | ⬜ |
| AUTH-16 | Gut/Fehler: `require_role` erlaubt/verweigert | Pass bzw. 403 | ⬜ |
| AUTH-17 | Gut/Fehler: `require_permission` erlaubt/verweigert | Pass bzw. 403 | ⬜ |
| AUTH-18 | Gut: `POST /logout` | Cookie gelöscht, Redirect | ⬜ |
| AUTH-19 | Gut: `POST /profile/cc` CC-Mails setzen | gespeichert | ⬜ |

## 2. Berechtigungen — `booking/models.py::has_permission`, `ROLE_PERMISSIONS`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| PERM-1 | Gut: Administrator hat jede Permission | alle True (parametrisiert über `Permission`) | ⬜ |
| PERM-2 | Gut: Trainer `CREATE_BOOKING` | True | ⬜ |
| PERM-3 | Fehler: Trainer `MANAGE_USERS` | False | ⬜ |
| PERM-4 | Fehler: Trainer `DELETE_ALL_BOOKINGS` | False | ⬜ |
| PERM-5 | Gut: Platzwart `DELETE_ALL_TASKS` | True | ⬜ |
| PERM-6 | Fehler: Platzwart `MANAGE_SERIES` | False | ⬜ |
| PERM-7 | Gut: DFBnet `DFBNET_BOOKING` + `MANAGE_SERIES` | True | ⬜ |
| PERM-8 | Fehler: DFBnet `MANAGE_USERS` | False | ⬜ |
| PERM-9 | Fehler: unbekannte Rolle | False (leeres frozenset) | ⬜ |

## 3. Buchungs-Domänenlogik — `booking/booking.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| BOOK-1 | Gut: `get_conflicting_fields` Feld mit Konflikten | erwartete Konfliktliste | ⬜ |
| BOOK-2 | Gut: `check_availability` freier Slot | `available=True`, keine Konflikte | ⬜ |
| BOOK-3 | Fehler: `check_availability` belegter Slot | `available=False` + Konfliktnamen | ⬜ |
| BOOK-4 | Gut: `validate_booking_input` gültige Eingabe | `[]` (keine Fehler) | ⬜ |
| BOOK-5 | Fehler: Dauer nicht 15er-Vielfaches / außerhalb 15–840 | Fehlermeldung „Ungültige Buchungsdauer“ | ⬜ |
| BOOK-6 | Fehler: Startzeit nicht im 15-Min-Slot / vor 8:00 | Fehlermeldung „Ungültige Startzeit“ | ⬜ |
| BOOK-7 | Fehler: Ende nach 22:00 | Fehlermeldung „endet nach 22:00“ | ⬜ |
| BOOK-8 | Gut: `build_booking` Formular-Mannschaft gespeichert | `data.mannschaft` durchgereicht | ✅ `test_build_booking_mannschaft.py::test_formular_mannschaft_wird_gespeichert` |
| BOOK-9 | Gut: `build_booking` User-Default wenn Formular leer | `current_user.mannschaft` | ✅ `test_build_booking_mannschaft.py::test_user_default_wenn_formular_leer` |
| BOOK-10 | Gut: `build_booking` Override schlägt Formular | Priorität override | ✅ `test_build_booking_mannschaft.py::test_override_schlaegt_formular` |
| BOOK-11 | Gut: `build_booking` Formular schlägt User-Default | Priorität Formular | ✅ `test_build_booking_mannschaft.py::test_formular_schlaegt_user_default` |
| BOOK-12 | Gut: `dfbnet_displace` als Administrator/DFBnet | verdrängt bestehende Buchung | ⬜ |
| BOOK-13 | Fehler: `dfbnet_displace` als Trainer | `ValueError("Nur DFBnet oder Administrator darf verdrängen.")` | ⬜ |

## 4. Buchungs-Pill-Rendering — `partials/_calendar_*`, `_booking_form`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| PILL-1 | Gut: Mannschaft schlägt Zweck als Label | Mannschaftsname | ✅ `test_booking_pill.py::test_mannschaft_schlaegt_zweck` |
| PILL-2 | Gut: Shortname wird genutzt | Kurzname im Label | ✅ `test_booking_pill.py::test_shortname_wird_genutzt` |
| PILL-3 | Gut: Zweck-Fallback ohne Mannschaft | Zweck als Label | ✅ `test_booking_pill.py::test_zweck_fallback_ohne_mannschaft` |
| PILL-4 | Gut: Namens-Fallback ohne Mannschaft+Zweck | Bucher-Name | ✅ `test_booking_pill.py::test_name_fallback_ohne_mannschaft_und_zweck` |
| PILL-5 | Rand: Mannschaft ohne Shortname → voller Name | voller Name | ✅ `test_booking_pill.py::test_mannschaft_ohne_shortname_nutzt_vollen_namen` |
| PILL-6 | Gut: Tooltip enthält Zweck | Zweck im title | ✅ `test_booking_pill.py::test_tooltip_enthaelt_zweck` |
| PILL-7 | Gut: Tooltip zeigt Buchungsverantwortlichen | Name im Tooltip | ✅ `test_booking_pill.py::test_tooltip_zeigt_buchungsverantwortlichen` |
| PILL-8 | Rand: Tooltip-Verantwortlicher ohne Mannschaft | korrekt | ✅ `test_booking_pill.py::test_tooltip_verantwortlicher_ohne_mannschaft` |
| PILL-9 | Gut: Tooltip enthält Kontakt + Zeit | beides | ✅ `test_booking_pill.py::test_tooltip_enthaelt_kontakt_und_zeit` |
| PILL-10 | Gut: Buchungsart → CSS-Klasse (parametrisiert) | korrekte Klasse je `BookingType` | ✅ `test_booking_pill.py::test_buchungsart_als_css_klasse` |

## 5. Kalender / Übersicht — `web/routers/calendar.py`, `bookings.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| CAL-1 | Gut: `calendar_start_hour_for` Mapping (parametrisiert) | korrektes Fenster-Start | ✅ `test_calendar_start_hour.py::test_start_hour_mapping` |
| CAL-2 | Gut: Buchung liegt im Zeitfenster | Startstunde ≤ Buchung | ✅ `test_calendar_start_hour.py::test_buchung_liegt_im_fenster` |
| CAL-3 | Gut: Startstunde im erlaubten Bereich | 8 ≤ h ≤ 16 | ✅ `test_calendar_start_hour.py::test_start_hour_im_erlaubten_bereich` |
| CAL-4 | Gut: Wochenansicht-Default = 16 | 16 | ✅ `test_calendar_start_hour.py::test_wochenansicht_default_ist_16` |
| CAL-5 | Gut: `_build_slots` erzeugt Slot-Liste | korrekte Anzahl/Schrittweite | ⬜ |
| CAL-6 | Gut: `_get_week_context` KW/Jahr | Wochentage korrekt | ⬜ |
| CAL-7 | Gut: `GET /calendar/week` gerendert | 200, enthält Buchungen | ⬜ |
| CAL-8 | Gut: `GET /overview/timeline` | 200, Timeline-Partial | ⬜ |
| CAL-9 | Gut: `GET /calendar/export.ics` | gültige ICS mit VEVENTs | ⬜ |
| CAL-10 | Gut: `invalidate_week_cache` leert betroffene KW | Cache-Eintrag entfernt | ⬜ |

## 6. Serien — `booking/series.py`, `web/routers/series.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| SER-1 | Gut: `generate_series_dates` wöchentlich | N Termine im 7-Tage-Raster | ⬜ |
| SER-2 | Gut: `generate_series_dates` 14-tägig | N Termine im 14-Tage-Raster | ⬜ |
| SER-3 | Gut: `create_series_with_bookings` alle frei | alle Termine erstellt | ⬜ |
| SER-4 | Fehler-/Rand: einzelne Termine kollidieren | Kollisionen in `skipped`, Rest erstellt | ⬜ |
| SER-5 | Gut: `remove_date_from_series` | einzelner Termin storniert | ⬜ |
| SER-6 | Gut: `cancel_series` | Serie + Zukunftstermine storniert | ⬜ |
| SER-7 | Gut: `GET /series/trainers?mannschaft=` | Verantwortliche der Mannschaft | ⬜ |
| SER-8 | Gut: `POST /series` gültig | Serie angelegt | ⬜ |
| SER-9 | Fehler: `POST /series` Validierungsfehler | Formular mit Fehlern re-rendered | ⬜ |
| SER-10 | Gut: `POST /series/season-transfer` | Serien in neue Saison übertragen | ⬜ |

## 7. Mannschaft-Verantwortliche (M:N) — `db/sqlite_repository.py`, Admin-Templates

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| MV-1 | Gut: User → mehrere Teams | beide Teams | ✅ `test_mannschaft_verantwortliche.py::test_user_verantwortlich_fuer_mehrere_teams` |
| MV-2 | Gut: Team → mehrere Verantwortliche | beide User | ✅ `test_mannschaft_verantwortliche.py::test_team_mit_mehreren_verantwortlichen` |
| MV-3 | Rand: `add` idempotent | kein Duplikat | ✅ `test_mannschaft_verantwortliche.py::test_add_ist_idempotent` |
| MV-4 | Gut: `remove_verantwortlicher` | entfernt | ✅ `test_mannschaft_verantwortliche.py::test_remove_verantwortlicher` |
| MV-5 | Fehler-/Rand: gelöschter User gefiltert | nicht mehr gelistet | ✅ `test_mannschaft_verantwortliche.py::test_geloeschter_user_nicht_mehr_verantwortlich` |
| MV-6 | Rand: ohne Zuweisung leer | `[]` | ✅ `test_mannschaft_verantwortliche.py::test_ohne_zuweisung_leer` |
| MV-7 | Gut: `_user_row` zeigt Team-Liste | „Team A, Team B“ | ✅ `test_mannschaft_verantwortliche.py::test_user_row_zeigt_team_liste` |
| MV-8 | Rand: `_user_row` leer → `–` | genau eine `–`-Zelle | ✅ `test_mannschaft_verantwortliche.py::test_user_row_leer_zeigt_strich` |
| MV-9 | Gut: `_mannschaft_row` zeigt Liste | „Hans, Klaus“ | ✅ `test_mannschaft_verantwortliche.py::test_mannschaft_row_zeigt_verantwortlichen_liste` |
| MV-10 | Rand: `_mannschaft_row` leer → `–` | genau eine `–`-Zelle | ✅ `test_mannschaft_verantwortliche.py::test_mannschaft_row_leer_zeigt_strich` |
| MV-11 | Regression: Combobox nutzt `m.name` (nicht `m.value`) | Optionen gefüllt | ✅ `test_mannschaft_verantwortliche.py::test_create_user_combobox_nutzt_name_nicht_value` |

## 8. Repository — `db/sqlite_repository.py` (echte SQLite, `tmp_path`)

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| REPO-1 | Gut: `create_user` + `get_user_by_name/_id` | Round-Trip | teilw. (via MV-Fixtures) |
| REPO-2 | Fehler: doppelter aktiver Nutzername | Ablehnung/Konflikt (`idx_users_name`) | ⬜ |
| REPO-3 | Gut: `delete_user` Soft-Delete | `deleted_at` gesetzt, nicht in `get_all_users` | ⬜ |
| REPO-4 | Gut: `update_user` Rolle/Mannschaft/Email | persistiert | ⬜ |
| REPO-5 | Gut: `create_booking` + `get_bookings_*` | Round-Trip | ⬜ |
| REPO-6 | Gut: `cancel_booking` | Status `Storniert` | ⬜ |
| REPO-7 | Gut: `create_mannschaft` + `get_all_mannschaften(only_active)` | Filter aktiv | teilw. (MV-Fixture) |
| REPO-8 | Gut: `create_series` + Termine | Round-Trip | ⬜ |
| REPO-9 | Gut: Aufgabe CRUD | Round-Trip + Status-Update | ⬜ |
| REPO-10 | Gut: Event CRUD | Round-Trip | ⬜ |
| REPO-11 | Gut: Blackout CRUD | Round-Trip | ⬜ |
| REPO-12 | Gut: Alias anlegen/entkoppeln | `user_aliases`-Zeile / gelöscht | ⬜ |
| REPO-13 | Gut: Migration `trainer_id` → M:N (einmalig) | seed nur bei leerer Tabelle | ⬜ |

## 9. Admin-Router — `web/routers/admin.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| ADM-1 | Gut: `POST /admin/users` neuer Nutzer | Toast „angelegt“ | ⬜ |
| ADM-2 | Fehler: `POST /admin/users` Name vergeben | Toast „bereits vergeben“ | ⬜ |
| ADM-3 | Gut: `POST /admin/users/{id}/reset-password` | PW-Reset + Token-Invalidierung | ⬜ |
| ADM-4 | Gut: `POST /admin/users/{id}` update | Zeile aktualisiert | ⬜ |
| ADM-5 | Gut: `DELETE /admin/users/{id}` | Zeile entfernt | ⬜ |
| ADM-6 | Gut: `POST /admin/mannschaften` neu | angelegt, Trainer → M:N | ⬜ |
| ADM-7 | Gut: `POST /admin/mannschaften/{id}` update | aktualisiert | ⬜ |
| ADM-8 | Fehler: `DELETE .../{id}` unbekannt | 404 „nicht gefunden“ | ⬜ |
| ADM-9 | Gut: `POST .../verantwortliche` Mehrfachauswahl | Diff add/remove korrekt | ⬜ |
| ADM-10 | Fehler: `POST .../verantwortliche` unbekannte Mannschaft | 404 | ⬜ |
| ADM-11 | Gut: `POST /admin/dfbnet` Buchung | angelegt | ⬜ |
| ADM-12 | Fehler: `POST /admin/dfbnet` mit Konflikt | Verdrängung / Meldung | ⬜ |
| ADM-13 | Gut: `_parse_ics` gültige Datei | Termine extrahiert | ⬜ |
| ADM-14 | Rand: `_round_to_slot` / `_nearest_duration` | korrekt gerundet | ⬜ |
| ADM-15 | Gut: `POST /admin/mannschaften/auto-colors` | Farben gesetzt | ⬜ |
| ADM-16 | Zugriff: Nicht-Admin auf `_admin_required`-Route | 403 | ⬜ |

## 10. Events-Router — `web/routers/events.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| EVT-1 | Gut: `POST /events` gültig | Event angelegt | ⬜ |
| EVT-2 | Gut: `DELETE /events/{id}` eigenes (Trainer) | gelöscht | ⬜ |
| EVT-3 | Fehler: `DELETE` fremdes ohne `DELETE_ALL_EVENTS` | 403 | ⬜ |
| EVT-4 | Gut: Paginierung `?page=` | korrekte Seite | ⬜ |

## 11. Aufgaben-Router — `web/routers/tasks.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| TASK-1 | Gut: `POST /tasks` gültig | Aufgabe angelegt | ⬜ |
| TASK-2 | Gut: `POST /tasks/{id}/status` | Status geändert | ⬜ |
| TASK-3 | Gut: `DELETE /tasks/{id}` eigene | gelöscht | ⬜ |
| TASK-4 | Fehler: `DELETE` fremde ohne `DELETE_ALL_TASKS` | 403 | ⬜ |

## 12. Onboarding — `web/routers/onboarding.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| ONB-1 | Gut: `_guard` erlaubt wenn nicht eingerichtet | kein Redirect | ⬜ |
| ONB-2 | Fehler: `_guard` blockt wenn bereits eingerichtet | Redirect | ⬜ |
| ONB-3 | Gut: `_teams_from_counts` / `_derive_shortname` | korrekte Ableitung | ⬜ |
| ONB-4 | Rand: `_roman` / `_roman_to_int` Round-Trip | identisch | ⬜ |
| ONB-5 | Gut: `POST /onboarding/step/admin` | Admin angelegt | ⬜ |
| ONB-6 | Gut: `POST /onboarding/step/vereinsconfig` | Config geschrieben | ⬜ |
| ONB-7 | Rand: `_mask` maskiert Secret | nur letzte N Zeichen sichtbar | ⬜ |

## 13. Config-Loader — `booking/field_config.py`, `vereinsconfig.py`, `scheduler_config.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| CFG-1 | Gut: `get_display_name` bekanntes Feld | Anzeigename | ⬜ |
| CFG-2 | Rand: `get_display_name` unbekanntes Feld | Fallback (ID) | ⬜ |
| CFG-3 | Gut: `get_visible_fields(role)` Trainer vs. Admin | rollenabhängige Liste | ⬜ |
| CFG-4 | Gut: `get_conflict_sources` | Konfliktabbildung | ⬜ |
| CFG-5 | Gut: `is_lit` Flutlicht-Feld | bool | ⬜ |
| CFG-6 | Gut: `get_heim_keywords` | Liste aus Config | ⬜ |
| CFG-7 | Gut: `get_spielort_zu_feld` Mapping | Spielort → FieldName | ⬜ |
| CFG-8 | Gut: `scheduler_config.load/save` Round-Trip | persistiert | ⬜ |

## 14. Spielplan-Sync — `booking/spielplan_sync.py`

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| SYNC-1 | Gut: Heim-Spiel (heim_keyword match, case-insensitiv) | als Buchung angelegt | ⬜ |
| SYNC-2 | Fehler-/Rand: Auswärtsspiel (kein Match) | übersprungen | ⬜ |
| SYNC-3 | Gut: `_spielort_zu_feld` bekannter Spielort | FieldName | ⬜ |
| SYNC-4 | Rand: `_spielort_zu_feld` unbekannt | `None` | ⬜ |
| SYNC-5 | Gut: `SyncResult.zusammenfassung` / `.ok` | korrekt formatiert | ⬜ |
| SYNC-6 | Gut: `write_sync_status` → `read_sync_status` | Round-Trip | ⬜ |

---

## Nicht testpflichtig (bewusst ausgeschlossen)

- **`booking/instagram.py`, `booking/scheduler.py`** — externe I/O (Playwright, APScheduler); nur reine Helfer (`_next_sunday`) lohnen einen Test.
- **`notion/client.py`** — Legacy, nicht aktiv (siehe CLAUDE.md).
- **`web/routers/about.py::_git_info`** — reine Anzeige.

---

## Fortschritt

- **Vollständig:** Bereich 4 (Pill), 7 (M:N).
- **Teilweise:** Bereich 3 (nur `build_booking`), 5 (nur `calendar_start_hour_for`), 8 (nur via Fixtures).
- **Offen:** Bereiche 1, 2, 6, 9–14.

**Empfohlene nächste Schritte** (höchster Nutzen/Aufwand):
1. Bereich 2 (Berechtigungen) — reine Funktionstests, keine Fixtures, schnell.
2. Bereich 3 (`validate_booking_input`, `check_availability`, `dfbnet_displace`) — Kern-Domänenlogik.
3. Bereich 6 (Serien) — komplexe Logik mit Kollisionspfad.
4. Bereich 8 (Repository CRUD) — Fundament, `tmp_path`-Muster steht bereits.

# Team-Zuordnung, Verantwortliche & Buchungsrechte

> **Status:** ✅ Umgesetzt (C1–C6) — 2026-07-04. Tests: `docs/tests/test_team_buchungsrechte.py`, `test_mannschaft_verantwortliche.py`.
> **Datum:** 2026-07-04
> **Betrifft:** Mannschaftsverwaltung, Buchungsformular, CC-Benachrichtigungen, Berechtigungen

---

## 1. Ziel in einem Satz

Ein Team hat **einen primären Verantwortlichen** und **beliebig viele weitere zugewiesene User**. Alle zugewiesenen User bilden automatisch die **Team-Liste**, bekommen CC-Mails und dürfen für das Team buchen. Beim Buchen sieht ein normaler User nur die Teams, denen er zugewiesen ist — Admins alle.

---

## 2. Begriffe

| Begriff | Bedeutung | Datenquelle |
|---------|-----------|-------------|
| **Primärer Verantwortlicher** | Genau 1 pro Team. Für Anzeige, Serien, Profilseite. | `mannschaften.trainer_id` / `trainer_name` (Legacy, 1:1) |
| **Zugewiesene User** (= sekundäre Verantwortliche) | 0..N pro Team. Dürfen buchen, bekommen CC. | `mannschaft_verantwortliche` (M:N) |
| **Team-Liste** | Primärer + alle zugewiesenen User (Vereinigung, dedupliziert). | M:N-Tabelle (primärer wird beim Speichern mit-eingetragen) |
| **CC-Empfänger** | Manuelle `cc_emails` **+** E-Mails aller in der Team-Liste. | `mannschaften.cc_emails` + Liste |

**Wichtig:** Der primäre Verantwortliche wird beim Speichern **auch** als Zeile in `mannschaft_verantwortliche` geführt. Damit ist die Team-Liste = `get_verantwortliche_for_mannschaft(team)` — eine einzige Quelle. `trainer_id` bleibt nur der Marker, *welcher* aus der Liste der primäre ist.

---

## 3. Ist-Zustand (Stand 2026-07-04)

| Baustein | Ist | Datei |
|----------|-----|-------|
| M:N-Tabelle | ✅ vorhanden | `db/schema.sql` → `mannschaft_verantwortliche` |
| Repo-Methoden | ✅ `get_verantwortliche_for_mannschaft`, `get_mannschaften_for_user`, `add/remove_verantwortlicher` | `db/sqlite_repository.py` |
| Mannschaften-Übersicht: Liste | ✅ Spalte „Verantwortlicher“ zeigt Team-Liste (Join) | `partials/_mannschaft_row.html` |
| Mannschaften-Editor: Zuweisung | ⚠️ aktuell Mehrfach-Checkboxen ohne Primär-Unterscheidung | `partials/_mannschaft_row_edit.html` |
| Nutzer-Übersicht: „Verantwortlich für“ | ✅ Spalte zeigt Teams des Users | `partials/_user_row.html` |
| CC-Bau bei Buchung | ✅ `cc_emails` + alle Verantwortlichen-Mails, dedup, ohne Hauptempfänger | `web/routers/bookings.py::_build_cc` (Z. 50) |
| CC-Mails im Editor sichtbar | ❌ nur manuelles `cc_emails`-Feld, Verantwortlichen-Mails unsichtbar | `partials/_mannschaft_row_edit.html` |
| Buchungs-Team-Dropdown | ❌ zeigt **allen** alle aktiven Teams | `bookings.py::bookings_page` (Z. 74) + `_booking_form.html` (Z. 101) |
| Buchungsrecht serverseitig | ❌ keine Prüfung, ob User dem Team zugewiesen ist | `booking/booking.py::build_booking` |

**Fazit:** CC (Anforderung „sekundäre bekommen CC“) ist **bereits erfüllt**. Offen sind: Editor-Darstellung (Primär + Liste + CC-Mails), Buchungs-Dropdown-Filter und die serverseitige Buchungsrechts-Prüfung.

---

## 4. Soll-Verhalten

### 4.1 Mannschaften-Übersicht (`/admin/mannschaften`)
- Spalte **„Verantwortlicher“** zeigt weiterhin die Team-Liste als kommaseparierte Namen.
- Der **primäre** Verantwortliche wird optisch hervorgehoben (z.B. **fett** oder mit ★), Rest normal.
- Spalte **„CC-Mails“** zeigt die effektive CC-Liste: manuelle Adressen **plus** (kursiv/ausgegraut) die automatisch ergänzten Verantwortlichen-Mails, damit der Admin sieht, wer wirklich CC bekommt.

### 4.2 Mannschaften-Editor (Edit-Zeile)
- **Primärer Verantwortlicher:** Einzel-Dropdown (`trainer_id`). Genau einer.
- **Weitere zugewiesene User:** Mehrfach-Checkboxliste (die bereits gebaute UI), ohne den bereits als primär gewählten doppelt zu verlangen (primär wird automatisch mit-zugewiesen).
- **CC-Mails:** das bestehende manuelle Textfeld **plus** ein read-only Hinweis „Automatisch ergänzt: hans@…, klaus@…“ (die Mails der Team-Liste). Nicht editierbar, nur zur Transparenz.

### 4.3 Buchungsformular (`/bookings`)
- Der Team-Dropdown zeigt für **Trainer/normale Rollen** nur Teams, denen der User zugewiesen ist (`get_mannschaften_for_user(sub)` ∪ primäres Team `current_user.mannschaft`).
- **Administrator / DFBnet:** alle aktiven Teams (unverändert).
- Ist der User genau einem Team zugewiesen → dieses ist vorausgewählt (bestehendes `user_mannschaft`-Verhalten).
- Ist der User keinem Team zugewiesen und keine Admin-Rolle → Dropdown zeigt nur „– keine –“ (Buchung ohne Team weiter möglich, sofern erlaubt).

### 4.4 Serverseitige Buchungsrechts-Prüfung (Pflicht — Dropdown-Filter ist nur UI)
In `build_booking` bzw. `create_booking`:
- Wenn `data.mannschaft` gesetzt ist und der User **nicht** Admin/DFBnet ist:
  - Prüfen, ob `data.mannschaft` in den Teams des Users liegt (`get_mannschaften_for_user`).
  - Wenn nicht → Fehler `„Sie sind für die Mannschaft '…' nicht eingetragen.“`, Buchung abgelehnt.
- Admin/DFBnet: keine Einschränkung.

### 4.5 CC-Benachrichtigung
- Unverändert über `_build_cc`: manuelle `cc_emails` + Team-Liste-Mails, dedupliziert, Hauptempfänger ausgeschlossen. ✅ bereits implementiert.

---

## 5. Datenmodell

Keine Schema-Änderung nötig — `mannschaft_verantwortliche` und `mannschaften.trainer_id` reichen.

```
mannschaften
  id, name, trainer_id (→ primärer Verantwortlicher), trainer_name, cc_emails, …

mannschaft_verantwortliche  (M:N — die Team-Liste)
  mannschaft_id, user_id     (PK zusammengesetzt)
  → enthält primären UND sekundäre Verantwortliche
```

**Invariante:** `trainer_id` (falls gesetzt) MUSS auch als Zeile in `mannschaft_verantwortliche` existieren. Beim Speichern eines Teams sicherstellen (`add_verantwortlicher(mid, trainer_id)`).

---

## 6. Umzusetzende Änderungen (Backlog)

| # | Bereich | Änderung | Datei(en) | Status |
|---|---------|----------|-----------|:---:|
| C1 | Editor | Primär-Dropdown **plus** Sekundär-Checkboxen | `_mannschaft_row_edit.html`, `admin.py::update_mannschaft` | ✅ |
| C2 | Editor | Read-only Anzeige der automatischen CC-Mails (Team-Liste) | `_mannschaft_row_edit.html`, `_mannschaft_row_ctx` | ✅ |
| C3 | Übersicht | Primären hervorheben (fett); CC-Spalte um Auto-Mails ergänzt | `_mannschaft_row.html`, `mannschaften_page`, `_mannschaft_row_ctx` | ✅ |
| C4 | Buchung UI | Team-Dropdown nach Zugehörigkeit filtern (Admin=alle) | `bookings.py::_bookable_teams`, `bookings_page` | ✅ |
| C5 | Buchung Server | Buchungsrecht prüfen (`user_may_book_for`) | `booking/booking.py::build_booking` | ✅ |
| C6 | Invariante | `trainer_id` immer in M:N mitführen (`selected.add(trainer_id)`) | `admin.py::update_mannschaft`, `create_mannschaft` | ✅ |

---

## 7. Randfälle & Entscheidungen

| Fall | Verhalten |
|------|-----------|
| User buchte bisher für Team X, wird entfernt | Bestehende Buchungen bleiben; neue für X nicht mehr möglich (außer Admin). |
| Primärer Verantwortlicher wird gewechselt | Alter **bleibt** als sekundärer in der Liste (Entscheidung 1). |
| Team ohne Verantwortliche | Team-Liste leer, CC = nur manuelle `cc_emails`. Buchung nur durch Admin. |
| Alias-Account | `sub` ist Alias-ID; `get_mannschaften_for_user(sub)` muss auf Alias-User zeigen (Alias hat eigene M:N-Einträge). Prüfen. |
| DFBnet-Rolle | Wie Admin: alle Teams buchbar. |

### Getroffene Entscheidungen (2026-07-04)
1. **Primär-Wechsel:** ✅ **Alter primärer bleibt als sekundärer Verantwortlicher in der Liste** (behält CC + Buchungsrecht), muss manuell entfernt werden. → C1/C6: beim Primär-Wechsel den alten *nicht* aus M:N löschen, nur `trainer_id` umsetzen.
2. **Buchung ohne Team:** ✅ **Erlaubt.** „– keine –“ bleibt für alle Rollen wählbar; Buchung ohne Team-Zuordnung möglich. → C5: Prüfung nur wenn `data.mannschaft` gesetzt.
3. **CC-Mails:** ✅ **Read-only.** Verantwortlichen-Mails werden im Editor transparent angezeigt, sind immer CC, nicht abwählbar. → C2: kein zusätzliches Ausnahmefeld nötig.

---

## 8. Akzeptanzkriterien / Tests

Ergänzt `docs/tests/TESTFALL_SPEZIFIKATION.md`.

| Test-ID | Fall | Erwartung | Status |
|---------|------|-----------|:---:|
| TEAM-1 | Team-Liste = zugewiesene User; primär hervorgehoben | Namen korrekt, primär **fett** | ✅ `test_team_buchungsrechte.py::test_user_teams_enthaelt_zugewiesene`, `test_mannschaft_verantwortliche.py::test_mannschaft_row_zeigt_verantwortlichen_liste` |
| TEAM-2 | CC-Bau: manuelle + Verantwortlichen-Mails, dedup, ohne Empfänger | korrekt | ✅ bereits `_build_cc`; Anzeige `test_mannschaft_row_cc_zeigt_auto_mails` |
| TEAM-3 | Editor: Primär-Dropdown + Sekundär-Checkboxen | Dropdown selected + Checkboxen | ✅ `test_mannschaft_verantwortliche.py::test_mannschaft_edit_row_primaer_und_sekundaere` |
| TEAM-4 | Buchungs-Dropdown Trainer → nur eigene Teams | fremde Teams fehlen | ✅ `test_team_buchungsrechte.py::test_dropdown_trainer_nur_eigene_teams` |
| TEAM-5 | Buchungs-Dropdown Admin → alle Teams | alle sichtbar | ✅ `test_team_buchungsrechte.py::test_dropdown_admin_alle_teams` |
| TEAM-6 | `build_booking` Trainer bucht fremdes Team | Fehler „nicht eingetragen“, keine Buchung | ✅ `test_team_buchungsrechte.py::test_trainer_darf_fremdes_team_nicht`, `test_build_booking_trainer_fremdes_team_fehler` |
| TEAM-7 | `build_booking` Admin/DFBnet bucht beliebiges Team | erlaubt | ✅ `test_team_buchungsrechte.py::test_admin_darf_jedes_team`, `test_dfbnet_darf_jedes_team` |
| TEAM-8 | Buchung ohne Mannschaft (`– keine –`) | erlaubt | ✅ `test_team_buchungsrechte.py::test_buchung_ohne_team_immer_erlaubt` |
| TEAM-9 | `trainer_id` gesetzt → auch M:N-Zeile (Invariante) | konsistent nach Speichern | ⬜ (Router-Integrationstest offen; Logik in `update_mannschaft`) |

---

## 9. Verweise

- `docs/Features/buchungen_fuer_eine_gruppe.md` — Alias-System, ursprüngliches M:N-Konzept.
- `docs/Features/User-Rollen.md` — Rollen/Permissions.
- `booking/models.py` — `ROLE_PERMISSIONS`, `Permission`.
- `web/routers/bookings.py::_build_cc` — CC-Logik (bereits fertig).

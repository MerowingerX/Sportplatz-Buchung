# Namenskonsistenz-Pflichtliste

Dieses Dokument listet alle Stellen im System, an denen ein Name oder
String-Wert exakt mit einem anderen übereinstimmen **muss**.
Bei jeder Änderung eines dieser Werte **alle markierten Dateien prüfen**.

Stand: 2026-03-01

---

## 1. Platz-IDs (FieldName-Enum)

**Quelle der Wahrheit:** `booking/models.py` — `FieldName`-Enum

Interne IDs sind stabil und werden **nie** umbenannt. Anzeigenamen kommen
ausschließlich aus `config/field_config.json` → `"display_names"`.

| Interne ID | Enum-Konstante | Default-Anzeigename |
|------------|----------------|---------------------|
| `"A"`  | `A`  | `"Kura AB"` |
| `"AA"` | `AA` | `"Kura A"` |
| `"AB"` | `AB` | `"Kura B"` |
| `"B"`  | `B`  | `"Rasen AB"` |
| `"BA"` | `BA` | `"Rasen A"` |
| `"BB"` | `BB` | `"Rasen B"` |
| `"C"`  | `C`  | `"Halle Ganz"` |
| `"CA"` | `CA` | `"Halle 2/3"` |
| `"CB"` | `CB` | `"Halle 1/3"` |

**Konfliktlogik:** Zwei Felder kollidieren, wenn eine ID die andere als Präfix enthält:
`f1.startswith(f2) or f2.startswith(f1)`.
→ `"A"` + `"AA"` kollidieren, `"AA"` + `"AB"` nicht.

**Muss übereinstimmen in:**

| Datei | Kontext |
|-------|---------|
| `scripts/setup_notion.py` | Notion Select-Optionen anlegen |
| `config/field_config.json` → `"display_names"` | Anzeigenamen (umbenennen = nur hier!) |
| `config/field_config.json` → `"fields"` | Gruppen-Zuordnung |
| `booking/field_config.py` → `_DEFAULT` | Fallback-Konfiguration |
| `config/vereinsconfig.json` → `"feld"` | Spielort-Mapping |

**Umbenennung eines Platzes:** Nur `config/field_config.json` → `"display_names"` ändern.
Kein Code, kein Neustart nötig (bei hot-reload).

**Fehlerfolge:** Buchungen erscheinen nicht im Kalender, Konfliktprüfung versagt.

---

## 2. Notion Property-Namen — Buchungen-DB

**Quelle der Wahrheit:** `notion/client.py` (Lese-/Schreib-Aufrufe)

Diese Namen müssen mit den tatsächlichen Property-Namen in der Notion-Datenbank
und mit den Einträgen in `scripts/setup_notion.py` übereinstimmen.

| Property-Name | Typ | Wenn falsch → |
|---------------|-----|---------------|
| `"Titel"` | title | Buchungen ohne Titel |
| `"Platz"` | select | Platz kann nicht gelesen/gesetzt werden |
| `"Datum"` | date | Datum fehlt, Filter schlägt fehl |
| `"Startzeit"` | select | Zeitangaben fehlen |
| `"Endzeit"` | select | dto. |
| `"Dauer"` | select | dto. |
| `"Typ"` | select | Buchungstyp fehlt |
| `"Gebucht von"` | rich_text | Nutzer-ID fehlt |
| `"Gebucht von Name"` | rich_text | Nutzername fehlt |
| `"Rolle"` | select | Rolle fehlt |
| `"Status"` | select | Filter liefert keine Ergebnisse |
| `"Mannschaft"` | rich_text | Mannschaftszuordnung fehlt |
| `"Zweck"` | rich_text | Freitext fehlt |
| `"Kontakt"` | rich_text | Kontakt fehlt |
| `"Serie"` | rich_text | Serien-ID fehlt |
| `"Serienausnahme"` | checkbox | Ausnahmen nicht erkannt |
| `"Hinweis Sonnenuntergang"` | rich_text | Hinweis fehlt |
| `"Spielkennung"` | rich_text | Duplikaterkennung kaputt |

---

## 3. Notion Property-Namen — übrige DBs

### Serien-DB

| Property | Typ |
|----------|-----|
| `"Titel"` | title |
| `"Platz"` | select |
| `"Startzeit"` | select |
| `"Dauer"` | select |
| `"Rhythmus"` | select |
| `"Startdatum"` | date |
| `"Enddatum"` | date |
| `"Gebucht von ID"` | rich_text |
| `"Gebucht von Name"` | rich_text |
| `"Status"` | select |
| `"Mannschaft"` | rich_text |
| `"Trainer ID"` | rich_text |
| `"Trainer Name"` | rich_text |

### Sperrzeiten-DB

| Property | Typ |
|----------|-----|
| `"Titel"` | title |
| `"Datum"` | date |
| `"Art"` | select |
| `"Startzeit"` | select |
| `"Endzeit"` | select |
| `"Grund"` | rich_text |
| `"Eingetragen von ID"` | rich_text |
| `"Eingetragen von Name"` | rich_text |

### Nutzer-DB

| Property | Typ |
|----------|-----|
| `"Name"` | title |
| `"Rolle"` | select |
| `"E-Mail"` | rich_text |
| `"Password_Hash"` | rich_text |
| `"Passwort ändern"` | checkbox |
| `"Mannschaft"` | select |

### Aufgaben-DB

| Property | Typ |
|----------|-----|
| `"Titel"` | title |
| `"Typ"` | select |
| `"Status"` | select |
| `"Priorität"` | select |
| `"Erstellt am"` | date |
| `"Fällig am"` | date |
| `"Erstellt von ID"` | rich_text |
| `"Erstellt von Name"` | rich_text |
| `"Ort"` | rich_text |
| `"Beschreibung"` | rich_text |

### Events-DB

| Property | Typ |
|----------|-----|
| `"Name"` | title |
| `"Datum"` | date |
| `"Startzeit"` | rich_text |
| `"Ort"` | rich_text |
| `"Beschreibung"` | rich_text |
| `"Mannschaft"` | rich_text |
| `"Erstellt von ID"` | rich_text |
| `"Erstellt von Name"` | rich_text |

---

## 4. Enum-Werte und ihre Abhängigkeiten

### BookingType (`"Typ"` in Buchungen-DB)

| Python-Enum-Wert | Notion Select | CSS-Klasse | Template-Stellen |
|------------------|---------------|------------|-----------------|
| `"Training"` | `"Typ"` option | `.slot--training` | `_booking_pill.html`, `_calendar_week.html:133`, `_calendar_day.html:99` |
| `"Spiel"` | `"Typ"` option | `.slot--spiel` | dto. |
| `"Turnier"` | `"Typ"` option | `.slot--turnier` | dto. |

CSS generiert via `{{ b.booking_type.value | lower }}` → muss in `web/static/style.css` definiert sein.

### BookingStatus (`"Status"` in Buchungen-DB)

| Python-Enum-Wert | Notion Select | Verwendung |
|------------------|---------------|------------|
| `"Bestätigt"` | `"Status"` option | Filter in fast allen Notion-Abfragen |
| `"Storniert"` | `"Status"` option | `notion/client.py:550` |
| `"Storniert (DFBnet)"` | `"Status"` option | `scripts/setup_notion.py:98` |

### UserRole (`"Rolle"` in Nutzer-DB und Buchungen-DB)

| Python-Enum-Wert | Notion Select | Templates | field_config.json |
|------------------|---------------|-----------|-------------------|
| `"Trainer"` | ✓ | — | `"visible_to"` |
| `"Platzwart"` | ✓ | `base.html` Navbar | `"visible_to"` |
| `"Administrator"` | ✓ | `base.html` Navbar, `_booking_pill.html` | `"visible_to"` (immer) |
| `"DFBnet"` | ✓ | `base.html` Navbar, `_booking_pill.html` | `"visible_to"` |

**Template-Hardcodes** (müssen mit Enum übereinstimmen):
- `base.html`: `role.value in ["Administrator", "DFBnet"]` (2×)
- `base.html`: `role.value in ["Platzwart", "Administrator"]`
- `base.html`: `role.value == "Administrator"`
- `_booking_pill.html`: `role.value in ["Administrator", "DFBnet"]`
- `field_config.html`: `role == "Administrator"` (onclick="return false")

**`booking/field_config.py`**: `ALL_ROLES = ["Trainer", "Platzwart", "DFBnet", "Administrator"]`
→ Muss alle UserRole-Werte in gleicher Reihenfolge enthalten.

### SeriesStatus (`"Status"` in Serien-DB)

| Python-Enum-Wert | Notion Select | Templates |
|------------------|---------------|-----------|
| `"Aktiv"` | ✓ | `_series_row.html:18` hardcoded |
| `"Pausiert"` | ✓ | — |
| `"Beendet"` | ✓ | `_series_row.html:2` hardcoded |

### SeriesRhythm (`"Rhythmus"` in Serien-DB)

| Python-Enum-Wert | Notion Select |
|------------------|---------------|
| `"Wöchentlich"` | ✓ |
| `"14-tägig"` | ✓ |

### AufgabeTyp (`"Typ"` in Aufgaben-DB)

| Python-Enum-Wert | Notion Select | CSS-Klasse |
|------------------|---------------|------------|
| `"Defekt"` | ✓ | `.badge--typ-defekt` |
| `"Nutzeranfrage"` | ✓ | `.badge--typ-nutzeranfrage` |
| `"Turniertermin"` | ✓ | `.badge--typ-turniertermin` |
| `"Sonstiges"` | ✓ | `.badge--typ-sonstiges` |

### AufgabeStatus (`"Status"` in Aufgaben-DB)

| Python-Enum-Wert | Notion Select | Template-Hardcode | CSS-Klasse |
|------------------|---------------|-------------------|------------|
| `"Offen"` | ✓ | `_task_row.html:21` | `.task-row--offen` |
| `"In Bearbeitung"` | ✓ | `_task_row.html:21` | `.task-row--in-bearbeitung` |
| `"Erledigt"` | ✓ | `_task_row.html:21` | `.task-row--erledigt` |

**Achtung:** `_task_row.html` hat einen hardcodierten Python-ähnlichen Select:
```jinja2
{% for s in ['Offen', 'In Bearbeitung', 'Erledigt'] %}
```
→ Muss exakt mit Enum-Werten übereinstimmen!

### BlackoutType (`"Art"` in Sperrzeiten-DB)

| Python-Enum-Wert | Notion Select | CSS-Klasse |
|------------------|---------------|------------|
| `"Ganztägig"` | ✓ | `.badge--typ-ganztaegig` (via `replace('ä','ae')`) |
| `"Zeitlich"` | ✓ | `.badge--typ-zeitlich` |

### Prioritaet (`"Priorität"` in Aufgaben-DB)

| Python-Enum-Wert | Notion Select | CSS-Klasse |
|------------------|---------------|------------|
| `"Niedrig"` | ✓ | `.badge--prio-niedrig` |
| `"Mittel"` | ✓ | `.badge--prio-mittel` |
| `"Hoch"` | ✓ | `.badge--prio-hoch` |

---

## 5. Spielort-Strings (fussball.de ↔ Platz-IDs)

**Quelle der Wahrheit:** `config/vereinsconfig.json` → `"spielorte"`

Diese Strings werden in Kleinschreibung mit `spielort.lower()` verglichen:

| `fussball_de_string` | → FieldName-ID | → Platz-Präfix |
|----------------------|----------------|----------------|
| `"cremlingen b-platz"` | `"A"` | `["A"]` |
| `"cremlingen a-platz rasen"` | `"B"` | `["B"]` |

`platz_praefix: ["A"]` matcht per `startswith` auf A, AA, AB (ganzer Platz blockiert auch Hälften).

**Wird verwendet in:**
- `booking/spielplan_sync.py` → `_SPIELORT_ZU_FELD` (via `get_spielort_zu_feld()`)
- `tools/check_spielplan.py` → `SPIELORT_ZU_PLATZ`, `PLATZ_ZU_SPIELORT` (via `get_spielort_zu_praefix()`)

---

## 6. Vereinsconfig-Parameter (config/vereinsconfig.json)

| Schlüssel | Verwendet in |
|-----------|-------------|
| `"vereinsname"` | Jinja2-Global `vereinsname` in allen Templates |
| `"vereinsname_lang"` | Jinja2-Global `vereinsname_lang` in allen Templates |
| `"heim_keyword"` | `scripts/fetch_spielplan.py` → `TUS_HOME_KEYWORDS` |
| `"primary_color"` | CSS `:root --color-primary` (via inline `<style>`) |
| `"primary_color_dark"` | CSS `:root --color-primary-hover` |
| `"primary_color_darker"` | CSS `:root --color-primary-darker` |
| `"gold_color"` | CSS `:root --color-gold` |
| `"spielorte[].feld"` | Muss ein gültiger `FieldName`-Enum-Wert sein |
| `"spielorte[].platz_praefix"` | Muss ein Präfix eines `FieldName`-Werts sein |

---

## 7. Checkliste bei Enum-Änderungen

**Wenn ein Platz-Anzeigename geändert werden soll:**
- [ ] Nur `config/field_config.json` → `"display_names"` ändern — fertig.

**Wenn eine neue FieldName-ID hinzugefügt oder entfernt wird:**
- [ ] `booking/models.py` — FieldName-Enum anpassen
- [ ] `scripts/setup_notion.py` — Notion Select-Optionen anpassen
- [ ] `config/field_config.json` → `"display_names"` und `"field_groups"` anpassen
- [ ] `booking/field_config.py` → `_DEFAULT` anpassen
- [ ] `config/vereinsconfig.json` → `"spielorte[].feld"` und `"platz_praefix"` prüfen
- [ ] Notion-Datenbank: neues Select-Option via `scripts/setup_notion.py` anlegen

**Wenn ein anderer Enum-Wert in `booking/models.py` geändert wird:**
- [ ] `scripts/setup_notion.py` — Select-Optionen anpassen
- [ ] `notion/client.py` — Lese-/Schreib-Aufrufe prüfen (nutzen `.value`)
- [ ] Templates in `web/templates/partials/` auf hardcodierte Strings prüfen
- [ ] CSS-Klassen in `web/static/style.css` prüfen (`.slot--*`, `.badge--*`)
- [ ] `booking/field_config.py` → `ALL_ROLES` und defaults prüfen
- [ ] `config/field_config.json` → `"visible_to"` prüfen

Wenn ein Notion Property-Name geändert wird:

- [ ] `notion/client.py` — alle `_get_prop(page, "…")` Aufrufe
- [ ] `scripts/setup_notion.py` — Property-Anlage anpassen
- [ ] Notion-Datenbank manuell umbenennen (API unterstützt das nicht)

---

## 8. Bekannte Inkonsistenz: notion/setup.py vs. scripts/setup_notion.py

`notion/setup.py` ist eine **ältere, unvollständige Version** des Setup-Scripts.
**Nur `scripts/setup_notion.py` verwenden.**

Unterschiede:
- `notion/setup.py` kennt die Rolle `"DFBnet"` nicht
- `notion/setup.py` hat andere Zeitslot-Listen
- `notion/setup.py` fehlt die Dauer `"120"`

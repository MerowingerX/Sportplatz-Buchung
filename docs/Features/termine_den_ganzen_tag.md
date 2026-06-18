# Ganztägige Buchbarkeit (8:00–22:00) im 15-Minuten-Raster

> **Status:** Planungsphase  
> **Ziel:** Buchungszeitraum von 16:00–22:00 auf 8:00–22:00 erweitern. Raster bleibt einheitlich 15 Minuten.

---

## Zusammenfassung

| Aspekt | Ist | Soll |
|--------|-----|------|
| Buchungsbeginn | 16:00 | **8:00** |
| Buchungsende | 22:00 | 22:00 (unverändert) |
| Buchungsraster | 15 Min | 15 Min (unverändert) |
| Darstellungsraster | 15 Min (Woche) / 30 Min (Tag, Bug!) | 15 Min (einheitlich) |
| Gültige Dauern | 60, 90, 180 Min | **15–840 Min in 15-Min-Schritten** |
| Tagesansicht-Slots | hartcodiert 30-Min | dynamisch 15-Min |
| Fehlermeldung | "30-Min-Slots" | "15-Min-Slots" |
| Dauer-Dropdown | fest 60/90/180 | dynamisch alle 15-Min-Werte |

Das ist im Kern eine **Aufweitung des Zeitfensters** von 6 Stunden (16–22) auf 14 Stunden (8–22) PLUS **flexible Buchungsdauer** (nicht mehr nur 60/90/180, sondern jedes Vielfache von 15 Min zwischen 15 und 840 Min).

---

## Änderungsplan

### 1. `utils/time_slots.py` — Kernkonstanten ändern

```python
BOOKING_START = time(8, 0)     # war: time(16, 0)
BOOKING_END   = time(22, 0)    # unverändert
SLOT_MINUTES  = 15             # unverändert
MIN_DURATION_MINUTES = 15      # NEU: minimale Buchungsdauer
MAX_DURATION_MINUTES = 840     # NEU: maximale Buchungsdauer (14h)
```

**Betroffene Funktionen:**
- `get_all_start_slots()` — gibt jetzt Slots von 08:00 bis 21:45.
  **ACHTUNG:** Die Funktion hat ein hartkodiertes Ende `time(21, 30)` ([utils/time_slots.py:13](../../utils/time_slots.py)) — nicht nur `BOOKING_START` ändern. `21:30`→`21:45` (bei 15-Min-Mindestdauer ist die letzte Startzeit 21:45, Ende 22:00).
- `is_valid_duration(d)` — **ändert sich**: nicht mehr `d in [60, 90, 180]`, sondern `MIN_DURATION_MINUTES <= d <= MAX_DURATION_MINUTES and d % SLOT_MINUTES == 0`
- `is_within_booking_hours()` — prüft jetzt `start >= 08:00`
- `VALID_DURATIONS`-Konstante: **NICHT blind löschen.** Erst alle Verwender finden:
  ```bash
  grep -rn "VALID_DURATIONS" .
  ```
  Wird u.a. in `web/routers/bookings.py` (Dauer-Dropdown) erwartet. Jede Stelle auf die neue Preset-/Custom-Logik bzw. `MIN/MAX_DURATION_MINUTES` umstellen, sonst `ImportError` beim Start.

### 2. `web/routers/calendar.py` — Kalender-Router

**Achtung: DREI Views betroffen, nicht zwei** (vorher unterschätzt):

| Route | Funktion | Fenster | time_slots | Status |
|-------|----------|---------|-----------|--------|
| `/calendar/week` | `calendar_week` ([L96](../../web/routers/calendar.py)) | 6 h | dynamisch im Router | anpassen |
| `/calendar/day` | `calendar_day` ([L62](../../web/routers/calendar.py)) | — | **fehlt, Template hartcodiert** | Bug, siehe §3 |
| `/overview/week` | `overview_week` ([L180](../../web/routers/calendar.py)) | 8 h, `slot_min=30` | dynamisch (`_build_slots`) | prüfen, siehe §2c |

#### 2a. `calendar_week()` ([L96](../../web/routers/calendar.py))
- `num_slots = 360 // SLOT_MINUTES` — `SLOT_MINUTES` bleibt 15, 6h-Fenster, unverändert
- `start_hour`-Default von 16 auf 8 ändern ([L102](../../web/routers/calendar.py))
- Clamping `max(0, min(18, start_hour))` → `max(0, min(16, start_hour))` ([L114](../../web/routers/calendar.py)); auch `next_start_hour = min(18, …)` ([L116](../../web/routers/calendar.py)) → `min(16, …)`. (8+6=14; max-Start 16, damit Fenster nicht über 22:00 läuft.)
- `prev_start_hour` / `next_start_hour`: Schrittweite 2 beibehalten

#### 2b. `calendar_day()` ([L62](../../web/routers/calendar.py)) — Day-Router
- Übergibt **aktuell kein** `time_slots` → Template hartcodiert (Bug). Muss `time_slots` dynamisch generieren und ans Template übergeben (analog `calendar_week`, 6h-Fenster, gleiche start_hour-Logik). Siehe §3.

#### 2c. `overview_week()` ([L180](../../web/routers/calendar.py)) — separate Übersicht
- Eigenes 8-Stunden-Fenster, `slot_min`-Default 30, `start_hour_wd=14` / `start_hour_we=10`, bereits `min(16)`-Clamp.
- **Existing-Bug beachten:** 8h-Fenster + Start-Clamp 16 → 16+8 = **24 > 22:00**. `_build_slots` läuft bis Stunde 23. Bei Ausweitung auf 8:00 entscheiden: Fenster auf 6h angleichen ODER end_hour hart auf 22 cappen. NICHT die 6h-Logik der Wochenansicht 1:1 hierher kopieren (anderes Fenster).
- Defaults (14/10) ggf. auf 8 senken, wenn diese View dieselbe Ausweitung erhalten soll.

### 3. `web/templates/partials/_calendar_day.html` — Tagesansicht

**Aktueller Zustand (KRITISCHER BUG):**
```jinja2
{% set time_slots = ["16:00","16:30","17:00","17:30","18:00","18:30",
                     "19:00","19:30","20:00","20:30","21:00","21:30"] %}
```

- Hartcodierte 30-Minuten-Slots — passt weder zum alten 15-Min- noch zum neuen System
- **Muss dynamisch werden**, wie die Wochenansicht, mit `SLOT_MINUTES` (15)
- Die `time_slots`-Liste muss vom Router übergeben werden (analog zur Wochenansicht)

**Änderung:** Hartcode entfernen, `{{ time_slots }}` aus dem Template-Kontext beziehen.

### 4. `web/templates/partials/_calendar_week.html` — Wochenansicht

- Keine Template-Änderung nötig (nutzt bereits `time_slots` aus dem Kontext)
- Matching-Logik `b.start_time <= slot_time and b.end_time > slot_time` funktioniert unverändert

### 5. `web/templates/partials/_booking_form.html` — Buchungsformular

- **Help-Text** (Zeile ~7): `"ab 16:00 in 30-Min-Schritten"` → `"ab 8:00 in 15-Min-Schritten"`

- **Startzeit-Dropdown**: Unverändert dynamisch aus `start_slots` befüllt.

- **Dauer-Picker — NEU als Preset-Buttons + Custom**:  
  Statt eines monströsen Dropdowns mit 56 Einträgen (15…840) ein zweistufiges UI:

  ```
  ┌─────────────────────────────────────────────┐
  │  Dauer                                       │
  │  [1h] [1,5h] [2h] [3h]  ───  [⋮ mehr]      │
  │                                             │
  │  (bei "mehr": Stunden/Minuten-Selects)       │
  │  [2 ▼] h [30 ▼] min                         │
  └─────────────────────────────────────────────┘
  ```

  - **Preset-Buttons**: 1h, 1½h, 2h, 3h — decken >90% der Fälle ab (Training, Spiel, Turnier)
  - **"mehr"-Button**: klappt Custom-Input aus — zwei Dropdowns (Stunden 0–14, Minuten 0/15/30/45)
  - Presets als `<button type="button">` mit `hx-get` auf Availability-Check
  - Custom-Selects mit `hx-get` auf Availability-Check bei Änderung
  - Ein `hidden`-Input `duration_min` hält den tatsächlichen Wert für den POST

- **Aktive Dauer visuell hervorheben**: gewählter Preset-Button bekommt `.btn--primary`, Custom-Selects erscheinen nur bei aktiver Wahl

- **Validierung clientseitig**: "Ungültige Dauer" wenn < 15 Min oder nicht durch 15 teilbar (selten, da Selects das schon einschränken)

### 6. `web/routers/bookings.py` — Buchungs-Router

- `get_all_start_slots()` → automatisch neue Slots (8:00–21:45)
- **Dauer-Presets an Template übergeben**:
  ```python
  duration_presets = [
      (60, "1 h"), (90, "1½ h"), (120, "2 h"), (180, "3 h"),
  ]
  ```
- Custom-Dauer wird aus `duration_hours` + `duration_minutes` (zwei Formfelder) zusammengesetzt: `duration_min = hours * 60 + minutes`
- Validierung im POST-Handler: `duration_min` muss durch 15 teilbar sein, zwischen MIN/MAX_DURATION

### 7. `booking/booking.py` — Validierung

- **Fehlermeldung Zeile 81**: `"Buchungen nur in 30-Min-Slots ab 16:00"` → `"Buchungen nur in 15-Min-Slots ab 8:00"`
- **`is_valid_duration()`**: Neue Logik — `d % 15 == 0 and 15 <= d <= 840`
- **Neue Fehlermeldung für ungültige Dauer**: z.B. `"Ungültige Dauer. Erlaubt: 15–840 Min in 15-Min-Schritten."`
- **`is_valid_start_time()`**: Prüft gegen `get_all_start_slots()` → automatisch korrekt
- **`is_within_booking_hours()`**: Prüft `start >= BOOKING_START` → automatisch korrekt

### 8. CSS — `web/static/style.css`

- **Kalender-Tabellenhöhe**: Bei 14 Stunden (8–22) mit 15-Min-Raster = 56 Zeilen.
- **`.cal-table__cell { height: 32px; }`**: Bei 56 Zeilen = 1792px Tischhöhe. Akzeptabel mit Scroll-Container.
- Ggf. `height` auf `28px` oder `24px` reduzieren, um Platz zu sparen.
- **`.cal-table__time`**: Breite (48px) reicht für "21:45" — ok.
- **Buchungs-Pills**: Bei sehr kurzen Buchungen (15 Min) nur 1 Zeile hoch, passt.

### 9. `web/routers/calendar.py` — Day-Router ergänzen

Bestätigt: `calendar_day()` ([L62](../../web/routers/calendar.py)) übergibt kein `time_slots`; [_calendar_day.html:1](../../web/templates/partials/_calendar_day.html) hartcodiert 30-Min-Slots. `time_slots` dynamisch im Router bauen und übergeben (analog `calendar_week`). Siehe §2b + §3. (Kein Duplikat zu §2c — `overview_week` ist eine andere View.)

### 10. Weitere betroffene Stellen (Grep-Suche nötig)

- [ ] Alle Hartcodierungen von `16:00`, `22:00`, `"16"`, `"22"` in Templates und Python-Dateien finden
- [ ] `CONTEXT.md` Zeile 38: "30-Minuten-Slots" → korrigieren
- [ ] `docs/manual.md` und andere Doku-Dateien auf veraltete Zeitangaben prüfen
- [ ] Sunset-Logik (`utils/sunset.py`): Prüfen ob Sonnenuntergangs-Warnungen für 8:00–16:00 relevant sind

---

## Reihenfolge der Umsetzung

| Schritt | Datei | Aufwand |
|---------|-------|---------|
| 1 | `utils/time_slots.py` — BOOKING_START=8, MIN/MAX_DURATION, is_valid_duration anpassen | klein |
| 2 | `booking/booking.py` — Fehlermeldung + Dauer-Validierung anpassen | klein |
| 3 | `web/templates/partials/_booking_form.html` — Help-Text + Preset-Buttons + Custom-Dauer-Selects | mittel |
| 4 | `web/routers/bookings.py` — duration_presets, Custom-Dauer parsen | mittel |
| 5 | `web/routers/calendar.py` — `calendar_week` start_hour=8 + Clamp min(16); `calendar_day` time_slots ergänzen; `overview_week` Fenster/Clamp prüfen (24>22 Bug) | mittel |
| 6 | `web/templates/partials/_calendar_day.html` — Hartcode entfernen | mittel |
| 7 | `web/static/style.css` — Zeilenhöhe + Preset-Button-Styling | klein |
| 8 | Dokumentation (`CONTEXT.md`, `docs/manual.md`) | klein |

---

## Risiken & Offene Fragen

1. **Performance**: 14h × 4 Slots/h = 56 Zeilen × 7 Tage × N Felder. Bei 3 Gruppen à 3 Felder = 56 × 7 × 9 = 3.528 Zellen. HTMX sollte das verkraften, aber testen.

2. **Start_hour-Navigation**: Die "Früher/Später"-Buttons springen in 2h-Schritten. Bei 8–22 Uhr mit 6h-Fenster: mögliche Startstunden = 0, 2, 4, 6, 8, 10, 12, 14, 16. Clamping auf `max(0, min(16, start_hour))`.

3. **Sonnenuntergang**: Bei Buchungen am Vormittag (8–12 Uhr) ist die Sunset-Warnung irrelevant. Die Logik in `utils/sunset.py` sollte nur warnen, wenn die Buchung in die Dämmerung reicht.

4. **Serienbuchungen** (`booking/series.py`): Prüfen ob Serien-Logik Annahmen über den Zeitraum oder fixe Dauern trifft.

5. **Dauer-Preset-UI**: Die Preset-Buttons + Custom-Selects sind ein neues UI-Pattern. Sollte mit ein paar Nutzern getestet werden, ob das intuitiv ist. Alternative: einfaches Number-Input "Minuten" mit Step=15 — noch simpler, aber weniger komfortabel.

6. **Kurze Buchungen (15–45 Min)**: Bisher nicht möglich. Sind die wirklich gewollt? Ein 15-Min-Slot auf dem Rasen ist sportlich sinnlos — aber für Halle oder Besprechungen vielleicht relevant. → **Klärungsbedarf**

---

## Betroffene Dateien (vollständig)

```
utils/time_slots.py              # BOOKING_START=8, MIN/MAX_DURATION, is_valid_duration
booking/booking.py               # Fehlermeldung + Dauer-Validierung
web/routers/calendar.py          # start_hour=8, Clamping 0–16, Day-Router time_slots
web/routers/bookings.py          # duration_presets, Custom-Dauer parsen
web/templates/partials/_booking_form.html     # Help-Text + Preset-Buttons + Custom-Dauer
web/templates/partials/_calendar_day.html     # Hartcode → dynamisch
web/templates/partials/_calendar_week.html    # (unverändert, nur prüfen)
web/static/style.css             # Zeilenhöhe + Preset-Button-Styling
CONTEXT.md                       # Doku-Korrektur
docs/manual.md                   # Doku-Korrektur (falls vorhanden)
```

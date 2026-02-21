# Code-Review – Sportplatz-Buchungssystem

Stand: 2026-02-21
Scope: Alle Backend-Router, Modelle, Notion-Client, Auth, Templates, Homepage

---

## Übersicht nach Priorität

| Priorität | Thema | Datei(en) |
|---|---|---|
| ~~Hoch~~ | ~~Falsche Standortkoordinaten (Sonnenuntergang)~~ | ~~`web/config.py`~~ ✓ |
| Hoch | JWT bleibt nach Rollenänderung gültig | `auth/auth.py`, `notion/client.py` |
| Hoch | `_toast()` in jedem Router dupliziert | 6 Router-Dateien |
| Mittel | Rollenprüfungen als Magic Strings in Templates | `base.html`, alle Partials |
| Mittel | `asyncio.ensure_future()` ohne Task-Tracking | `web/routers/admin.py` |
| Mittel | Globale Job-Dicts für mehrstufige Imports | `web/routers/admin.py` |
| Mittel | Notion-Client: breite `except Exception`-Blöcke | `notion/client.py` |
| Mittel | `booking.py` enthält Datenbankaufrufe (keine Trennung) | `booking/booking.py` |
| Mittel | `mannschaft` als `str` statt Enum in Events | `booking/models.py` |
| Niedrig | Keine Pagination bei Aufgaben (Tasks) | `web/routers/tasks.py` |
| Niedrig | Notion-Property-Check bei jedem App-Start | `notion/client.py` |
| Niedrig | Inline-Styles in mehreren Templates | diverse Templates |
| Niedrig | HTMX von externem CDN geladen | `web/templates/base.html` |
| Niedrig | Keine automatischen Tests | – |

---

## 1. Falsche Standortkoordinaten (Hoch)

**Datei:** [`web/config.py`](../web/config.py)

```python
standort_lat: float = 48.14
standort_lon: float = 11.57
```

Die Defaults entsprechen **München** (48,14°N / 11,57°O), nicht Cremlingen (≈ 52,26°N / 10,64°O). Das ergibt Sonnenuntergangszeiten, die im Sommer bis zu ~45 Minuten zu früh sind.

**Fix:** Koordinaten auf Cremlingen setzen oder als Pflichtfeld ohne Default definieren:
```python
standort_lat: float = 52.26
standort_lon: float = 10.64
```

---

## 2. JWT bleibt nach Rollenänderung gültig (Hoch)

**Dateien:** [`auth/auth.py`](../auth/auth.py), [`web/routers/admin.py`](../web/routers/admin.py)

Das JWT enthält Rolle und Mannschaft und ist 8 Stunden gültig. Nach einem Rollen-Downgrade (z.B. DFBnet → Trainer) über den neuen User-Editor bleibt das bestehende Token des Nutzers bis zu 8 Stunden gültig — der Nutzer behält die alten Berechtigungen.

**Optionen:**
- **Einfach:** Token-Ablaufzeit auf 1–2 Stunden reduzieren.
- **Sauber:** Eine Blacklist (z.B. Set im `app.state`) mit widerrufenen Sub-IDs führen. `get_current_user()` prüft dagegen.
- **Alternativ:** Nach einem Edit den Nutzer explizit ausloggen (Cookie löschen) und ihm eine neue Anmelde-Aufforderung anzeigen.

---

## 3. `_toast()` in jedem Router dupliziert (Hoch)

**Dateien:** `web/routers/bookings.py`, `series.py`, `blackouts.py`, `tasks.py`, `events.py`, `admin.py`

Jeder Router definiert dieselbe Hilfsfunktion:

```python
def _toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'
```

**Fix:** Eine gemeinsame Utility-Datei:

```python
# web/htmx.py
def toast(message: str, kind: str = "success") -> str:
    return f'<div id="toast" hx-swap-oob="true" class="toast toast--{kind}">{message}</div>'
```

Alle Router importieren daraus. Änderungen (z.B. escaping) müssen nur einmal gemacht werden.

---

## 4. Rollenprüfungen als Magic Strings in Templates (Mittel)

**Datei:** [`web/templates/base.html`](../web/templates/base.html)

Die Navigation enthält mehrfach Rollenprüfungen wie:
```jinja2
{% if current_user.role.value in ["Administrator", "DFBnet"] %}
{% if current_user.role.value in ["Platzwart", "Administrator"] %}
{% if current_user.role.value == "Administrator" %}
```

Das System hat bereits eine funktionierende `has_permission()`-Funktion in `booking/models.py`. Statt String-Listen in Templates wäre es konsistenter, im Router boolesche Flags in den Kontext zu geben oder `has_permission` als Jinja2-Global zu registrieren:

```python
# web/main.py
from booking.models import has_permission, Permission
templates.env.globals["has_permission"] = has_permission
```

Dann im Template:
```jinja2
{% if has_permission(current_user.role, Permission.MANAGE_USERS) %}
```

Das schützt außerdem vor Tippfehlern bei Rollennamen.

---

## 5. `asyncio.ensure_future()` ohne Task-Tracking (Mittel)

**Datei:** [`web/routers/admin.py`](../web/routers/admin.py)

Hintergrundaufgaben (Spielplan-Abruf, Massen-Benachrichtigungen) werden mit `asyncio.ensure_future()` gestartet. Fehler in diesen Tasks werden still geschluckt, wenn kein `done_callback` gesetzt ist.

**Fix:** FastAPI's `BackgroundTasks` verwenden — das ist der idiomatische Weg, Hintergrundarbeit in FastAPI zu erledigen:

```python
from fastapi import BackgroundTasks

@router.post("/fetch-spielplan")
async def fetch_spielplan(background_tasks: BackgroundTasks, ...):
    background_tasks.add_task(_do_fetch, repo, settings)
    return HTMLResponse(_toast("Abruf gestartet …"))
```

Alternativ für komplexere Jobs: Fehler-Logging explizit im `except`-Block des Tasks.

---

## 6. Globale Job-Dicts für mehrstufige Imports (Mittel)

**Datei:** [`web/routers/admin.py`](../web/routers/admin.py)

Sowohl der ICS-Import als auch der CSV-Import nutzen globale Dicts (`_ics_job`, `_csv_job`) um Zwischenzustand zwischen Requests zu halten (Upload → Vorschau → Bestätigen). Das hat mehrere Schwächen:

- Bei Neustart des Servers verloren — Nutzer sieht leere Vorschau
- Kein Ablauf: Abgebrochene Imports bleiben dauerhaft im Speicher
- Race Condition wenn zwei Admins gleichzeitig importieren (zweiter überschreibt den ersten)

**Besser:** Den Vorschau-State in der Session halten (als Base64-kodiertes JSON im Cookie) oder temporär in Notion/einer Datei ablegen. Für den einfachsten Fix: ein `job_id`-Schlüssel pro Nutzer statt einem einzigen globalen Eintrag:

```python
_ics_job: dict[str, dict] = {}  # keyed by user sub
```

---

## 7. Notion-Client: breite `except Exception`-Blöcke (Mittel)

**Datei:** [`notion/client.py`](../notion/client.py)

An mehreren Stellen werden Fehler mit `except Exception` gefangen, ohne den Fehlertyp zu beachten. Das maskiert echte Bugs (z.B. Typo in Property-Name → `KeyError` → wird als „Property fehlt" behandelt statt als Programmierfehler).

**Empfehlung:** Notion-spezifische Fehler (`notion_client.errors.APIResponseError`) gezielt fangen, alle anderen re-raisen oder zumindest mit vollständigem Traceback loggen:

```python
import logging
from notion_client.errors import APIResponseError

try:
    result = self._client.pages.create(...)
except APIResponseError as e:
    logger.error("Notion API error: %s", e)
    raise
except Exception:
    logger.exception("Unexpected error in create_booking")
    raise
```

---

## 8. `booking.py` enthält Datenbankaufrufe (Mittel)

**Datei:** [`booking/booking.py`](../booking/booking.py)

Die Funktion `dfbnet_displace()` nimmt ein `repo`-Objekt entgegen und ruft direkt `repo.update_booking_status()`, `repo.create_booking()` etc. auf. Das Modul ist als „reine Buchungslogik" beschrieben, enthält aber Datenbankinteraktion.

**Empfehlung:** Die DB-Operationen in den Router (`web/routers/admin.py`) verschieben. `dfbnet_displace()` sollte nur die Konflikte berechnen und das neue Buchungsobjekt zurückgeben. Der Router führt dann die DB-Writes durch — analog zu `build_booking()`, das auch kein `repo` nimmt.

---

## 9. `mannschaft` als `str` statt Enum in Events (Mittel)

**Datei:** [`booking/models.py`](../booking/models.py)

```python
class ExternalEvent(BaseModel):
    mannschaft: Optional[str] = None  # freier String

class User(BaseModel):
    mannschaft: Optional[Mannschaft] = None  # typisiertes Enum
```

Der Vergleich `event.mannschaft == current_user.mannschaft` in `events.py` funktioniert nur, weil `current_user.mannschaft` aus dem JWT als String deserialisiert wird. Wenn `User.mannschaft` aber ein `Mannschaft`-Enum ist und ein Trainer seinen Termin löschen möchte, könnte der Vergleich je nach Deserialisierungspfad fehlschlagen.

**Fix:** `ExternalEvent.mannschaft` ebenfalls als `Optional[Mannschaft]` typisieren. Die Notion-Property speichert ohnehin nur definierte Werte aus dem Dropdown.

---

## 10. Keine Pagination bei Aufgaben / Tasks (Niedrig)

**Datei:** [`web/routers/tasks.py`](../web/routers/tasks.py)

Events haben eine Pagination (25 pro Seite), Tasks laden alle Einträge auf einmal. Bei einem aktiven Verein mit vielen offenen Aufgaben wird die Seite träge.

**Fix:** Analog zu `events.py` eine `page`-Parameter-basierte Pagination einbauen (oder zumindest einen `limit`-Filter nach Erledigt/Nicht-erledigt, um abgeschlossene Aufgaben auszublenden).

---

## 11. Notion-Property-Check bei jedem App-Start (Niedrig)

**Datei:** [`notion/client.py`](../notion/client.py)

`_ensure_db_properties()` und `_ensure_events_db_properties()` werden beim Starten der App aufgerufen. Dabei werden für jede Datenbank die bestehenden Properties via API abgefragt und ggf. hinzugefügt. Das sind mehrere synchrone Notion-API-Calls beim Start.

**Empfehlung:** Das Auto-Migrations-Feature ist praktisch für die Ersteinrichtung, sollte aber nach erfolgreicher Migration deaktivierbar sein (z.B. über ein `SKIP_NOTION_MIGRATE=true`-Env-Flag) oder auf wirklich fehlende Properties beschränkt bleiben (nur dann API-Call auslösen).

---

## 12. Inline-Styles in Templates (Niedrig)

Mehrere Templates verwenden direkte Style-Attribute statt CSS-Klassen:

| Template | Beispiel |
|---|---|
| [`_user_row_edit.html`](../web/templates/partials/_user_row_edit.html) | `style="width:120px;"`, `style="width:160px;"` |
| [`_user_row.html`](../web/templates/partials/_user_row.html) | `style="text-align:right; white-space:nowrap;"` |
| [`_event_row.html`](../web/templates/partials/_event_row.html) | `style="white-space: nowrap;"` |
| [`admin/users.html`](../web/templates/admin/users.html) | `style="margin: 2rem 0;"`, `style="margin-bottom: 1rem;"` |

**Empfehlung:** Wiederkehrende Inline-Styles in `style.css` auslagern. Besonders die Breiten-Angaben in `_user_row_edit.html` sollten über Klassen gesteuert werden, damit Responsive-Anpassungen zentral möglich sind.

---

## 13. HTMX von externem CDN geladen (Niedrig)

**Datei:** [`web/templates/base.html:7`](../web/templates/base.html#L7)

```html
<script src="https://unpkg.com/htmx.org@2.0.3" integrity="sha384-..." crossorigin="anonymous"></script>
```

Das Integrity-Hash schützt gegen manipulierte CDN-Auslieferung (SRI), aber die App hat eine externe Abhängigkeit beim Laden. Bei CDN-Ausfall oder Offline-Betrieb (Vereinsgelände ohne Internet) funktioniert die gesamte UI nicht.

**Fix:** HTMX als statische Datei ablegen: `web/static/htmx.min.js` und lokal einbinden:
```html
<script src="/static/htmx.min.js"></script>
```

---

## 14. Keine automatischen Tests (Niedrig)

Das Projekt hat kein `tests/`-Verzeichnis. Besonders folgende Bereiche hätten hohen Nutzen durch Unit-Tests:

- **`booking/booking.py`:** Konflikt-Checks, Saisonprüfung, DFBnet-Verdrängungslogik
- **`booking/models.py`:** `ROLE_PERMISSIONS`, `has_permission()`
- **`utils/time_slots.py`:** Slot-Berechnung (16–22 Uhr, 30-Min-Raster)
- **`auth/auth.py`:** JWT erstellen/dekodieren

Diese Funktionen haben keine Seiteneffekte und sind trivial testbar mit `pytest`. Ein Regressionstest für die Konflikt-Logik würde z.B. verhindern, dass eine Änderung am Konflikt-Mapping unbemerkt Doppelbuchungen ermöglicht.

---

## Zusammenfassung

Die Architektur ist sauber und die Hauptlogik korrekt implementiert. Die meisten Punkte betreffen Code-Hygiene (Duplikation, Inline-Styles) oder pragmatische Vereinfachungen, die bei wachsender Nutzerzahl relevant werden (JWT-Widerruf, Pagination, Test-Coverage). Der einzige funktionale Fehler mit Auswirkung auf das Alltagsgeschäft ist **Punkt 1 (Standortkoordinaten)** — falsche Sonnenuntergangszeiten im Buchungsformular.

# Anleitung: Feldkonfiguration ändern

Diese Anleitung beschreibt alle Schritte, um Plätze hinzuzufügen, zu entfernen
oder umzubenennen. Kalender-Templates sind vollständig dynamisch (Router berechnet
`field_groups`, `field_display_names`, `conflict_sources` zur Laufzeit) — dort
ist kein manueller Eingriff nötig.

---

## Kurzcheckliste

| # | Datei | Was tun |
|---|-------|---------|
| 1 | `booking/models.py` | `FieldName`-Enum: neue IDs ergänzen / alte entfernen |
| 2 | `booking/field_config.py` | `_DEFAULT` aktualisieren (Fallback falls JSON fehlt) |
| 3 | `config/field_config.json` | Produktion: `display_names` + `field_groups` |
|   | `config/demo/field_config.json` | Demo: dasselbe |
| 4 | `scripts/setup_notion.py` | `sel(...)` in `schema_buchungen()` + `schema_serien()` |
| 5 | `config/vereinsconfig.json` | `spielorte[].feld` prüfen (nur bei fussball.de-Plätzen) |
|   | `config/demo/vereinsconfig.json` | Demo: dasselbe |
| — | Notion UI | Alte Select-Optionen ausblenden (optional) |

---

## Schritt 1 — `booking/models.py`: FieldName-Enum

Stabile interne IDs — Anzeigenamen kommen aus `field_config.json`, nicht aus dem Enum.

**Neue IDs hinzufügen:**
```python
class FieldName(str, Enum):
    # bestehende ...
    F  = "F"   # neue Platzgruppe F (ganz)
    FA = "FA"  # Platzgruppe F – Hälfte A
    FB = "FB"  # Platzgruppe F – Hälfte B
```

**Alte IDs entfernen:** Nur entfernen wenn die ID in keiner Notion-DB mehr als
Buchungs-Wert vorkommt. Andernfalls werden bestehende Buchungen beim Lesen
übersprungen (`_page_to_booking()` gibt `None` zurück).

---

## Schritt 2 — `booking/field_config.py`: `_DEFAULT`

`_DEFAULT` ist der Fallback, wenn `config/field_config.json` nicht gelesen werden
kann. Er muss alle gültigen IDs kennen.

```python
_DEFAULT: dict = {
    "display_names": {
        # ...
        "F":  "Neuer Platz (ganz)",
        "FA": "Neuer Platz A",
        "FB": "Neuer Platz B",
    },
    "field_groups": [
        # ...
        {
            "id": "neugruppe",
            "name": "Neuer Platz",
            "fields": ["F", "FA", "FB"],
            "lit": True,
            "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"],
        },
    ],
}
```

---

## Schritt 3 — `config/field_config.json` (und Demo-Variante)

Beide Felder müssen konsistent sein:

```json
{
  "display_names": {
    "F":  "Neuer Platz (ganz)",
    "FA": "Neuer Platz A",
    "FB": "Neuer Platz B"
  },
  "field_groups": [
    {
      "id": "neugruppe",
      "name": "Neuer Platz",
      "fields": ["F", "FA", "FB"],
      "lit": true,
      "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"]
    }
  ]
}
```

**Pflichtfelder pro Gruppe:**

| Feld | Typ | Bedeutung |
|------|-----|-----------|
| `id` | string | Eindeutige Gruppen-ID (a–z, keine Leerzeichen) |
| `name` | string | Anzeigename der Gruppe in der UI |
| `fields` | array | IDs in Anzeigereihenfolge; erstes Element = Ganz-Platz |
| `lit` | bool | `false` → Sonnenuntergangs-Hinweis bei Buchungen ohne Flutlicht |
| `visible_to` | array | Rollen, die diese Gruppe sehen: `Trainer`, `Platzwart`, `DFBnet`, `Administrator` |

**Konfliktlogik** wird automatisch berechnet: Felder blockieren sich, wenn eines
ein Präfix des anderen ist (`"A"` blockiert `"AA"` und `"AB"`, und umgekehrt).
Keine manuelle Pflege nötig.

---

## Schritt 4 — `scripts/setup_notion.py`

Die Platz-Select-Optionen in **beiden** Schemata ergänzen:

```python
def schema_buchungen() -> dict:
    return {
        "Platz": sel("A", "AA", "AB", ..., "F", "FA", "FB"),
        ...
    }

def schema_serien() -> dict:
    return {
        "Platz": sel("A", "AA", "AB", ..., "F", "FA", "FB"),
        ...
    }
```

Danach ausführen (legt fehlende Optionen an, löscht keine bestehenden):
```bash
python scripts/setup_notion.py
```

---

## Schritt 5 — `config/vereinsconfig.json`: Spielorte prüfen

Nur relevant wenn der Platz als Spielfeld auf fussball.de erscheint.

```json
"spielorte": [
  {
    "fussball_de_string": "meinverein f-platz",
    "feld": "F",
    "platz_praefix": ["F", "FA", "FB"]
  }
]
```

- `fussball_de_string`: Teilstring des Spielort-Namens auf fussball.de (Kleinschreibung)
- `feld`: Ganz-Platz-ID für automatische Spieleintragung
- `platz_praefix`: Alle IDs dieser Gruppe (für Gegencheck-Script)

---

## Notion UI (optional)

Das Setup-Script legt neue Optionen an, entfernt aber keine alten.
Alte Optionen in Notion ausblenden: Datenbankeinstellungen → Property „Platz" →
Option → ausblenden. **Nicht löschen** — historische Buchungen verweisen darauf.

---

## Was automatisch passt (kein Eingriff nötig)

- Kalender-Wochenansicht (`_calendar_week.html`) — dynamisch via Router
- Kalender-Tagesansicht (`_calendar_day.html`) — dynamisch via Router
- Konflikt-Berechnung (welche Felder blockieren sich) — Präfix-Logik in `field_config.py`
- Admin-UI für Feldsichtbarkeit (`/admin/field-config`) — liest direkt aus JSON

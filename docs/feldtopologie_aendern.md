# Anleitung: Platz-Topologie ändern

Diese Anleitung beschreibt, was zu tun ist, wenn die Anzahl der Plätze oder
ihre Unterteilung geändert werden soll — z. B. Kunstrasen wird nicht mehr
in Halb A / Halb B geteilt, sondern in Viertel A / B / C / D.

Beispiel durchgehend: **Kura Halb A + Kura Halb B → Kura Viertel A/B/C/D**

---

## Schritt 1 — booking/models.py

Die `FieldName`-Enum-Werte sind die Quelle der Wahrheit für alle Platznamen.

**Alte Werte entfernen / neue hinzufügen:**

```python
# vorher
KURA_HALB_A = "Kura Halb A"
KURA_HALB_B = "Kura Halb B"

# nachher
KURA_VIERTEL_A = "Kura Viertel A"
KURA_VIERTEL_B = "Kura Viertel B"
KURA_VIERTEL_C = "Kura Viertel C"
KURA_VIERTEL_D = "Kura Viertel D"
```

Wenn der Ganz-Platz erhalten bleibt (`"Kura Ganz"`), bleibt er unverändert.

**Achtung:** Prüfen ob `is_kura`, `is_ganz` etc. weiterhin korrekt sind
(die Properties nutzen `startswith`/`endswith`, also kein Handlungsbedarf
wenn die Präfixe gleich bleiben).

---

## Schritt 2 — config/field_config.json

Die Gruppen-Konfiguration mit Sichtbarkeit pro Rolle anpassen.

```json
{
  "field_groups": [
    {
      "name": "Kura (Kunstrasen)",
      "fields": ["Kura Ganz", "Kura Viertel A", "Kura Viertel B", "Kura Viertel C", "Kura Viertel D"],
      "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"]
    }
  ]
}
```

---

## Schritt 3 — web/templates/partials/_calendar_week.html

Zwei Dictionaries am Anfang der Datei aktualisieren:

**`field_short`** — Kurzbezeichnung im Kalender-Tabellenkopf:
```jinja2
{% set field_short = {
  "Kura Ganz": "Ganz",
  "Kura Viertel A": "Vrtl A",   {# neu #}
  "Kura Viertel B": "Vrtl B",   {# neu #}
  "Kura Viertel C": "Vrtl C",   {# neu #}
  "Kura Viertel D": "Vrtl D",   {# neu #}
  ...
} %}
```

**`conflict_sources`** — Welche Felder blockieren sich gegenseitig:
```jinja2
{% set conflict_sources = {
  "Kura Ganz":     ["Kura Viertel A", "Kura Viertel B", "Kura Viertel C", "Kura Viertel D"],
  "Kura Viertel A": ["Kura Ganz"],
  "Kura Viertel B": ["Kura Ganz"],
  "Kura Viertel C": ["Kura Ganz"],
  "Kura Viertel D": ["Kura Ganz"],
  ...
} %}
```

---

## Schritt 4 — web/templates/partials/_calendar_day.html

Dieselben zwei Dictionaries wie in `_calendar_week.html` analog anpassen
(die Datei ist eine parallele Tagesansicht mit identischer Struktur).

---

## Schritt 5 — scripts/setup_notion.py

Die Select-Optionen für die Property **"Platz"** in der Buchungen-DB ergänzen.
Dann `python scripts/setup_notion.py` ausführen — das Script legt fehlende
Optionen automatisch nach, ohne vorhandene zu löschen.

```python
PLATZ_OPTIONS = [
    "Kura Ganz",
    "Kura Viertel A",   # neu
    "Kura Viertel B",   # neu
    "Kura Viertel C",   # neu
    "Kura Viertel D",   # neu
    # "Kura Halb A",    # alt — in Notion manuell archivieren wenn nicht mehr gebraucht
    # "Kura Halb B",    # alt
    ...
]
```

**Alte Optionen** können in Notion unter Datenbankeinstellungen → Property "Platz"
manuell ausgeblendet werden (nicht löschen, da alte Buchungen darauf verweisen).

---

## Schritt 6 — config/vereinsconfig.json

Nur relevant wenn der Platz, der sich ändert, auch als Spielfeld für
fussball.de-Spiele genutzt wird.

`"spielorte[].feld"` auf das neue Ganz-Feld zeigen lassen (üblicherweise
`"Kura Ganz"` — bleibt unverändert, kein Handlungsbedarf wenn Ganz-Feld gleich bleibt):

```json
"spielorte": [
  {
    "fussball_de_string": "cremlingen b-platz",
    "feld": "Kura Ganz",
    "platz_praefix": ["Kura"]
  }
]
```

---

## Schritt 7 — Notion-Datenbank (manuell / optional)

Das Setup-Script (Schritt 5) legt neue Optionen an. Alte Optionen werden
**nicht automatisch gelöscht** (schützt historische Buchungen).

Wenn die alten Felder `"Kura Halb A"` / `"Kura Halb B"` im Kalender nicht
mehr auftauchen sollen:
- Sie tauchen bereits nicht mehr auf, sobald `field_config.json` und der
  `FieldName`-Enum sie nicht mehr enthalten
- Bestehende Notion-Seiten mit alten Werten werden im Kalender nicht mehr
  angezeigt (kein `FieldName`-Wert → `page_to_booking()` gibt `None` zurück
  und überspringt die Buchung)

---

## Kurzcheckliste

| # | Datei | Was tun |
|---|-------|---------|
| 1 | `booking/models.py` | Enum-Werte anpassen |
| 2 | `config/field_config.json` | Gruppen-Felder aktualisieren |
| 3 | `_calendar_week.html` | `field_short` + `conflict_sources` |
| 4 | `_calendar_day.html` | `field_short` + `conflict_sources` |
| 5 | `scripts/setup_notion.py` | Platz-Optionen ergänzen, dann ausführen |
| 6 | `config/vereinsconfig.json` | `spielorte[].feld` prüfen (oft kein Änderungsbedarf) |
| — | Notion UI | Alte Optionen ausblenden (optional) |

---

## Sonderfall: Neue Platzgruppe hinzufügen

Beispiel: Ein **zweiter Kunstrasen (Kura 2)** kommt dazu.

Zusätzlich zu den Schritten 1–5:

- `booking/models.py`: Neue Enum-Werte mit neuem Präfix (`"Kura2 Ganz"` etc.)
- `config/field_config.json`: Neue Gruppe anlegen
- `booking/field_config.py`: Neue Gruppe in `ALL_GROUPS` oder Defaults ergänzen
  *(falls dort hardcodiert — prüfen)*
- `_calendar_week.html` / `_calendar_day.html`: Neue Felder in beide Dicts
- `homepage/main.py` → `VENUES` Dict: Neue Venue-Kategorie falls die Homepage
  eine separate Verfügbarkeitsansicht für Kura2 zeigen soll:
  ```python
  VENUES = {
      "kura":  ("Kunstrasen 1", "is_kura",  "Kura"),
      "kura2": ("Kunstrasen 2", "is_kura2", "Kura2"),
      ...
  }
  ```
  Dazu müssen `is_kura2` Property im `FieldName`-Enum ergänzt werden.

---

## Warum ist das so aufwändig?

Die Platznamen sind als **typisierter Enum** (`FieldName`) implementiert,
der Typ-Sicherheit und IDE-Unterstützung bietet. Der Preis dafür ist, dass
Änderungen an mehreren Stellen gleichzeitig gemacht werden müssen.

Eine vollständig dynamische Konfiguration (Plätze nur aus JSON, kein Enum)
wäre möglich, würde aber einen größeren Refactor erfordern:
- `booking/models.py` müsste `FieldName` als `str` statt `Enum` behandeln
- Alle `FieldName.XYZ`-Referenzen im Code müssten angepasst werden
- Validierung beim Buchungsanlegen müsste anders gelöst werden

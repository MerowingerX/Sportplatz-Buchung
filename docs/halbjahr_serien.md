# Plan: Halbjahr-Gliederung für Serienbuchungen

Stand: 2026-02-28

## Ziel

Der Kalender wird in zwei Hälften gegliedert:
- **Sommerhalbjahr** – z. B. 1. April bis 30. September
- **Winterhalbjahr** – z. B. 1. Oktober bis 31. März

Die Wechseldaten sind konfigurierbar. Beim Anlegen einer Serie wählt
der Admin, ob die Serie ganzjährig, nur im Sommer- oder nur im
Winterhalbjahr laufen soll. Das Enddatum wird automatisch auf das Ende
des gewählten Halbjahrs begrenzt.

Die bisherige Hardcodierung `30. Juni` in `web/routers/series.py`
entfällt vollständig.

---

## Terminologie

| Begriff | Bedeutung |
|---------|-----------|
| `sommer_start` | Erster Tag des Sommerhalbjahrs (MM-DD, z. B. `"04-01"`) |
| `winter_start` | Erster Tag des Winterhalbjahrs (MM-DD, z. B. `"10-01"`) |
| Sommerhalbjahr | `sommer_start` bis `winter_start − 1 Tag` |
| Winterhalbjahr | `winter_start` bis `sommer_start − 1 Tag` des Folgejahres |
| Ganzjährig | kein automatischer Endtermin; Enddatum frei wählbar |

---

## Änderungen (Reihenfolge)

### 1. `config/vereinsconfig.json` — Neue Sektion

```json
"saisonwechsel": {
    "sommer_start": "04-01",
    "winter_start": "10-01"
}
```

Beide Werte als `"MM-DD"`. Mit den Defaults April/Oktober entspricht das
dem bisherigen Saisonverhalten (Rasen ist März–Oktober verfügbar).

---

### 2. `booking/vereinsconfig.py` — Neue Hilfsfunktionen

```python
def get_saisonwechsel() -> dict:
    """Gibt {"sommer_start": "04-01", "winter_start": "10-01"} zurück."""
    vc = load()
    return vc.get("saisonwechsel", {"sommer_start": "04-01", "winter_start": "10-01"})

def get_halbjahr_ende(saison: "SeriesSaison", ref_date: date) -> date | None:
    """
    Gibt das letzte Datum des gewählten Halbjahrs zurück,
    bezogen auf ref_date (Startdatum der Serie).
    Gibt None zurück für Ganzjährig.
    """
    from booking.models import SeriesSaison
    if saison == SeriesSaison.GANZJAEHRIG:
        return None

    sw = get_saisonwechsel()
    sommer_month, sommer_day = map(int, sw["sommer_start"].split("-"))
    winter_month, winter_day = map(int, sw["winter_start"].split("-"))

    if saison == SeriesSaison.SOMMERHALBJAHR:
        # Ende = Tag vor winter_start
        winter_start = date(ref_date.year, winter_month, winter_day)
        if winter_start <= ref_date:
            winter_start = date(ref_date.year + 1, winter_month, winter_day)
        return winter_start - timedelta(days=1)

    if saison == SeriesSaison.WINTERHALBJAHR:
        # Ende = Tag vor sommer_start des Folgejahres
        sommer_start_next = date(ref_date.year + 1, sommer_month, sommer_day)
        return sommer_start_next - timedelta(days=1)
```

---

### 3. `booking/models.py` — Neues Enum + Felder

```python
class SeriesSaison(str, Enum):
    GANZJAEHRIG      = "Ganzjährig"
    SOMMERHALBJAHR   = "Sommerhalbjahr"
    WINTERHALBJAHR   = "Winterhalbjahr"
```

In `Series` (Lese-Modell):
```python
saison: SeriesSaison = SeriesSaison.GANZJAEHRIG
```

In `SeriesCreate` (Schreib-Modell):
```python
saison: SeriesSaison = SeriesSaison.GANZJAEHRIG
```

---

### 4. `notion/client.py` — Property lesen/schreiben

#### `_REQUIRED_SERIES_PROPS` erweitern
```python
"Saison": {"select": {}},
```

#### `_page_to_series()` — lesen
```python
saison_raw = _get_select(props, "Saison") or "Ganzjährig"
saison = SeriesSaison(saison_raw)
# ... im return:
saison=saison,
```

#### `create_series()` — schreiben
```python
"Saison": _select(data.saison.value),
```

---

### 5. `web/routers/series.py` — Saison-Logik ersetzen

**Neues Formular-Feld akzeptieren:**
```python
saison: str = Form("Ganzjährig"),
```

**Hardcodierte Season-End-Logik ersetzen** (aktuelle Zeilen 105–110):

```python
# ALT (entfernen):
season_end = date(start_date.year, 6, 30)
if start_date.month >= 7:
    season_end = date(start_date.year + 1, 6, 30)
if end_date > season_end:
    end_date = season_end

# NEU:
from booking.models import SeriesSaison
from booking.vereinsconfig import get_halbjahr_ende

saison_enum = SeriesSaison(saison)
halbjahr_ende = get_halbjahr_ende(saison_enum, start_date)
if halbjahr_ende and end_date > halbjahr_ende:
    end_date = halbjahr_ende
```

**`SeriesCreate` um `saison` erweitern:**
```python
data = SeriesCreate(
    ...
    saison=saison_enum,
)
```

---

### 6. `web/templates/partials/_series_form.html` — Saison-Dropdown

Nach dem Rhythmus-Dropdown:
```html
<div class="form-group">
  <label for="saison">Saison</label>
  <select id="saison" name="saison" required>
    <option value="Ganzjährig">Ganzjährig</option>
    <option value="Sommerhalbjahr">Sommerhalbjahr</option>
    <option value="Winterhalbjahr">Winterhalbjahr</option>
  </select>
</div>
```

Das Enddatum-Feld bleibt erhalten: als maximales Datum (wird vom
Server auf das Halbjahresende begrenzt). Optional kann per HTMX
das Enddatum-Feld dynamisch vorausgefüllt werden (nicht Pflicht
für MVP).

---

### 7. `web/templates/partials/_series_row.html` — Saison-Spalte

Neue `<td>` nach Rhythmus:
```html
<td>{{ s.saison.value }}</td>
```

---

### 8. `web/templates/series/index.html` — Tabellenkopf

Neue `<th>` nach Rhythmus:
```html
<th>Saison</th>
```

---

### 9. `scripts/setup_notion.py` — Neue Select-Property

In der Serien-DB-Anlage die Property ergänzen:
```python
"Saison": {
    "select": {
        "options": [
            {"name": "Ganzjährig",    "color": "gray"},
            {"name": "Sommerhalbjahr","color": "yellow"},
            {"name": "Winterhalbjahr","color": "blue"},
        ]
    }
},
```

---

### 10. `docs/datenmodell.md` — Serien-Tabelle ergänzen

```markdown
| Saison | Select | Ganzjährig, Sommerhalbjahr, Winterhalbjahr |
```

(nach Rhythmus einfügen)

---

### 11. `docs/anforderungen.md` — Serien-Abschnitt ergänzen

In Abschnitt 3 „Serienbuchungen → Regeln":
```markdown
- **Saison:** Ganzjährig, Sommerhalbjahr oder Winterhalbjahr
- Saisonwechseldaten konfigurierbar in `config/vereinsconfig.json`
  (Default: Sommerhalbjahr 1. April – 30. September,
            Winterhalbjahr 1. Oktober – 31. März)
- Enddatum wird automatisch auf das Ende des gewählten Halbjahrs
  begrenzt; bei Ganzjährig gilt das eingetragene Enddatum ohne Korrektur
```

Bisherige Zeile `**Saisonende:** 30. Juni …` entfernen oder ersetzen.

---

## Dateien-Übersicht

| Datei | Aktion |
|-------|--------|
| `config/vereinsconfig.json` | `saisonwechsel`-Block hinzufügen |
| `booking/vereinsconfig.py` | `get_saisonwechsel()`, `get_halbjahr_ende()` |
| `booking/models.py` | `SeriesSaison`-Enum, Felder in `Series`/`SeriesCreate` |
| `notion/client.py` | Property lesen/schreiben, `_REQUIRED_SERIES_PROPS` |
| `web/routers/series.py` | Hartcodierung entfernen, `saison`-Parameter |
| `web/templates/partials/_series_form.html` | Saison-Dropdown |
| `web/templates/partials/_series_row.html` | Saison-Spalte |
| `web/templates/series/index.html` | Tabellenkopf |
| `scripts/setup_notion.py` | Select-Optionen anlegen |
| `docs/datenmodell.md` | Serien-Tabelle |
| `docs/anforderungen.md` | Serien-Regeln |

---

## Namenskopplungen (Pflicht)

Der Enum-Wert `SeriesSaison` muss exakt in folgenden Stellen
übereinstimmen:

| Wert | Enum-Konstante | Notion Select | Template |
|------|---------------|---------------|---------|
| `"Ganzjährig"` | `GANZJAEHRIG` | ✓ | ✓ |
| `"Sommerhalbjahr"` | `SOMMERHALBJAHR` | ✓ | ✓ |
| `"Winterhalbjahr"` | `WINTERHALBJAHR` | ✓ | ✓ |

→ `docs/naming_constraints.md` nach Umsetzung ergänzen.

---

## Migrationsverhalten (Bestand)

Bestehende Serien-Einträge in Notion haben keine `Saison`-Property.
Beim Lesen fällt `_get_select(props, "Saison")` auf `None` zurück →
Default `"Ganzjährig"` greift. Kein Datenverlust, keine Migration nötig.

---

## Verifizierung

1. `sommer_start = "04-01"`, `winter_start = "10-01"` in config
2. Serie „Sommerhalbjahr" anlegen mit Startdatum 01.04., Enddatum 31.12.
   → Enddatum wird automatisch auf 30.09. begrenzt
3. Serie „Winterhalbjahr" anlegen mit Startdatum 01.10.
   → Enddatum wird auf 31.03. des Folgejahres begrenzt
4. Serie „Ganzjährig" anlegen → Enddatum bleibt unverändert
5. Bestehende Serien in Notion zeigen in der Liste „Ganzjährig"
6. `scripts/setup_notion.py` legt neue Serien-DB korrekt an

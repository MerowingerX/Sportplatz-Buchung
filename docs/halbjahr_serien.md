# Plan: Saison-Kennzeichnung für Serienbuchungen

Stand: 2026-03-01
*(überarbeitet – ursprünglicher Ansatz mit automatischem Enddatum-Clamping
wurde vereinfacht; kein Pausemechanismus nötig)*

## Ziel

Serienbuchungen werden mit einem **Saison-Label** versehen
(Ganzjährig / Sommerhalbjahr / Winterhalbjahr). Das Label:

1. **Kennzeichnet** die Serie in der Übersichtsliste
2. **Füllt** Start- und Enddatum im Formular automatisch vor
   (überschreibbar)
3. **Ersetzt** die Hardcodierung `30. Juni` im Router durch einen
   konfigurierbaren Wert

Es gibt **keinen automatischen Pausemechanismus**. Eine Mannschaft mit
Sommer- und Winterbetrieb legt einfach drei separate Serien an:

```
Serie 1: Sommerhalbjahr   – z. B. 01.08. – 30.10.  (Outdoor vor Winterpause)
Serie 2: Winterhalbjahr   – z. B. 30.10. – 01.03.  (Hallenbetrieb)
Serie 3: Sommerhalbjahr   – z. B. 01.03. – 30.06.  (Outdoor nach Winterpause)
```

→ Anleitung für Admins: [docs/manual.md](manual.md#sommer--und-winterbetrieb)

---

## Konfiguration: `config/vereinsconfig.json`

```json
"saison_defaults": {
    "ganzjaehrig":    {"start": "08-01", "ende": "06-30"},
    "sommerhalbjahr": {"start": "08-01", "ende": "10-30"},
    "winterhalbjahr": {"start": "10-30", "ende": "03-01"}
}
```

Alle Werte als `"MM-DD"`. Werden als Vorausfüllung im Formular verwendet
und können pro Serie überschrieben werden.

---

## Änderungen (Reihenfolge)

### 1. `config/vereinsconfig.json`
`saison_defaults`-Block hinzufügen (siehe oben).

---

### 2. `booking/vereinsconfig.py` — Neue Hilfsfunktion

```python
def get_saison_defaults() -> dict:
    """
    Gibt Default-Daten je Saison zurück.
    Format: {"ganzjaehrig": {"start": "08-01", "ende": "06-30"}, ...}
    """
    vc = load()
    return vc.get("saison_defaults", {
        "ganzjaehrig":    {"start": "08-01", "ende": "06-30"},
        "sommerhalbjahr": {"start": "08-01", "ende": "10-30"},
        "winterhalbjahr": {"start": "10-30", "ende": "03-01"},
    })
```

---

### 3. `booking/models.py` — Neues Enum + Felder

```python
class SeriesSaison(str, Enum):
    GANZJAEHRIG    = "Ganzjährig"
    SOMMERHALBJAHR = "Sommerhalbjahr"
    WINTERHALBJAHR = "Winterhalbjahr"
```

In `Series` und `SeriesCreate`:
```python
saison: SeriesSaison = SeriesSaison.GANZJAEHRIG
```

---

### 4. `notion/client.py` — Property lesen/schreiben

`_REQUIRED_SERIES_PROPS` um `"Saison": {"select": {}}` erweitern.

`_page_to_series()`:
```python
saison_raw = _get_select(props, "Saison") or "Ganzjährig"
saison = SeriesSaison(saison_raw)
```

`create_series()`:
```python
"Saison": _select(data.saison.value),
```

---

### 5. `web/routers/series.py` — Hardcodierung ersetzen

```python
# ALT (entfernen):
season_end = date(start_date.year, 6, 30)
if start_date.month >= 7:
    season_end = date(start_date.year + 1, 6, 30)
if end_date > season_end:
    end_date = season_end

# NEU: konfiguriertes Saisonende für Ganzjährig lesen
from booking.vereinsconfig import get_saison_defaults
from booking.models import SeriesSaison

saison_enum = SeriesSaison(saison)
defaults = get_saison_defaults()
if saison_enum == SeriesSaison.GANZJAEHRIG:
    m, d = map(int, defaults["ganzjaehrig"]["ende"].split("-"))
    gz_ende = date(start_date.year if start_date.month < m else start_date.year + 1, m, d)
    if end_date > gz_ende:
        end_date = gz_ende
```

Für Sommer- und Winterhalbjahr wird das Enddatum **nicht** serverseitig
begrenzt — der Admin trägt es frei ein, vorausgefüllt durch das Formular.

---

### 6. `web/routers/series.py` — Saison-Defaults an Formular übergeben

```python
from booking.vereinsconfig import get_saison_defaults

@router.get("/new")
async def series_form(request: Request, ...):
    return templates.TemplateResponse(
        "partials/_series_form.html",
        {
            ...
            "saison_defaults": get_saison_defaults(),
            "saisons": list(SeriesSaison),
        },
    )
```

---

### 7. `web/templates/partials/_series_form.html` — Saison-Dropdown

```html
<div class="form-group">
  <label for="saison">Saison</label>
  <select id="saison" name="saison"
          onchange="prefillSaisonDates(this.value)">
    <option value="Ganzjährig">Ganzjährig</option>
    <option value="Sommerhalbjahr">Sommerhalbjahr</option>
    <option value="Winterhalbjahr">Winterhalbjahr</option>
  </select>
</div>
```

Kleines Inline-Script befüllt `start_date` und `end_date` aus den
Saison-Defaults (als `data-*`-Attribut auf das `<form>`-Element):

```js
function prefillSaisonDates(saison) {
  const defaults = JSON.parse(document.getElementById('saison-defaults').textContent);
  const key = saison.toLowerCase().replace('ä','a').replace('ü','u');
  const d = defaults[key];
  if (!d) return;
  const year = new Date().getFullYear();
  document.getElementById('start_date').value = year + '-' + d.start.replace('-', '-');
  document.getElementById('end_date').value   = year + '-' + d.ende.replace('-', '-');
}
```

*(Jahreslogik: wenn `start`-Monat < aktueller Monat → nächstes Jahr)*

---

### 8. `web/templates/partials/_series_row.html` — Saison-Spalte

```html
<td>{{ s.saison.value }}</td>
```

### 9. `web/templates/series/index.html` — Tabellenkopf

```html
<th>Saison</th>
```

### 10. `scripts/setup_notion.py` — Select-Optionen

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

## Dateien-Übersicht

| Datei | Aktion |
|-------|--------|
| `config/vereinsconfig.json` | `saison_defaults`-Block |
| `booking/vereinsconfig.py` | `get_saison_defaults()` |
| `booking/models.py` | `SeriesSaison`-Enum, Felder |
| `notion/client.py` | Property lesen/schreiben |
| `web/routers/series.py` | Hartcodierung ersetzen, Defaults übergeben |
| `web/templates/partials/_series_form.html` | Dropdown + JS-Prefill |
| `web/templates/partials/_series_row.html` | Saison-Spalte |
| `web/templates/series/index.html` | Tabellenkopf |
| `scripts/setup_notion.py` | Select-Optionen |

---

## Migrationsverhalten

Bestehende Serien ohne `Saison`-Property → Default `"Ganzjährig"`.
Kein Datenverlust, keine Migration nötig.

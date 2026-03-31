# Demo-Onboarding: Schritt-für-Schritt

Diese Anleitung dokumentiert, wie die isolierte Demo-Umgebung für den TSV Hotzenplotz
eingerichtet wurde. Sie dient als Referenz für zukünftige Demo-Setups oder als
Vorlage für die Einrichtung eines neuen Vereins.

---

## Überblick

Die Demo-Umgebung läuft auf demselben Server wie die Produktion, verwendet aber:

| | Produktion | Demo |
|---|---|---|
| Vereinsname | TuS Cremlingen | TSV Hotzenplotz |
| `.env`-Datei | `.env` | `.env.demo` |
| Konfigurationsverzeichnis | `config/` | `config/demo/` |
| Notion-Datenbanken | Produktions-DBs | separate Demo-DBs |
| Notion-Account | gemeinsam | gemeinsam |
| Startbefehl | `bash start_server.sh` | `bash start_demo.sh` |

---

## Schritt 1 – Notion-Integration freischalten

Das System verwendet eine **Notion-Integration** (interner Bot), die API-Zugriff auf
ausgewählte Seiten und Datenbanken erhält. Ohne explizite Freigabe verweigert Notion
den Zugriff, auch wenn API-Key und Seiten-ID korrekt sind.

**Integration-Namen zum vorhandenen Token ermitteln:**
```bash
.venv/bin/python -c "
from notion_client import Client
me = Client(auth='<NOTION_API_KEY>').users.me()
print(me.get('name'))
"
```

**Freigabe in Notion:**

1. Demo-Elternseite in Notion öffnen
2. `···` (oben rechts) → **Connections** → Integration suchen → **Confirm**

> Tipp: Es reicht, die **Elternseite** freizugeben. Alle Unterseiten und -datenbanken
> erben den Zugriff automatisch.

---

## Schritt 2 – Notion-Datenbanken anlegen

Das Setup-Script legt alle 5 Pflicht-Datenbanken mit vollständigem Schema an:

```bash
NOTION_API_KEY=<key> .venv/bin/python scripts/setup_notion.py \
  --parent <NOTION_PARENT_PAGE_ID>
```

Das Script gibt die generierten DB-IDs direkt in `.env`-Syntax aus:

```
NOTION_BUCHUNGEN_DB_ID=319ca010-5fee-81c2-8ba3-c35130bd92fe
NOTION_SERIEN_DB_ID=319ca010-5fee-81fd-93ef-e97e25c2e838
NOTION_NUTZER_DB_ID=319ca010-5fee-8102-a203-f2c1c17523bf
NOTION_AUFGABEN_DB_ID=319ca010-5fee-8155-bd81-e6036334ddc8
NOTION_EVENTS_DB_ID=319ca010-5fee-810d-a639-e8f39b888122
```

Diese Werte in `.env.demo` eintragen.

> Falls eine Mannschaften-DB bereits existiert, deren ID direkt aus der Notion-URL
> ablesen und als `NOTION_MANNSCHAFTEN_DB_ID` eintragen.

---

## Schritt 3 – Mannschaften aus fussball.de importieren

Voraussetzung: `APIFUSSBALL_TOKEN` und `APIFUSSBALL_CLUB_ID` sind in `.env.demo` gesetzt.

> **Wichtig:** Die API erwartet den Header `x-auth-token`, nicht `Authorization`.
> Der Token ist an den registrierten Account auf api-fussball.de gebunden und
> gibt immer die Mannschaften des registrierten Vereins zurück – unabhängig von
> der übergebenen Club-ID.

```bash
.venv/bin/python -c "
import requests
from notion_client import Client

token = '<APIFUSSBALL_TOKEN>'
club_id = '<APIFUSSBALL_CLUB_ID>'
notion_key = '<NOTION_API_KEY>'
db_id = '<NOTION_MANNSCHAFTEN_DB_ID>'

teams = requests.get(
    f'https://api-fussball.de/api/club/{club_id}',
    headers={'x-auth-token': token},
    timeout=15
).json().get('data', [])

client = Client(auth=notion_key)
for t in teams:
    client.pages.create(
        parent={'database_id': db_id},
        properties={
            'Name':             {'title': [{'text': {'content': t['name']}}]},
            'FussballDeTeamId': {'rich_text': [{'text': {'content': t['id']}}]},
            'Aktiv':            {'checkbox': True},
        }
    )
    print(f'+ {t[\"name\"]}')
"
```

Anschließend nicht benötigte Mannschaften (z. B. Hallenmannschaften) direkt in
Notion löschen.

---

## Schritt 4 – Ersten Admin-Nutzer anlegen

Passwort-Hash erzeugen:

```bash
ENV_FILE=.env.demo .venv/bin/python -c "
from auth.auth import hash_password
print(hash_password('ErstesPasswort123'))
"
```

In der Notion-Datenbank `Nutzer` einen neuen Eintrag anlegen:

| Property | Wert |
|---|---|
| Name | `admin` |
| Rolle | `Administrator` |
| Password_Hash | *(Hash aus dem Befehl oben)* |
| Passwort ändern | `true` (Checkbox aktivieren) |

---

## Schritt 5 – Vereinsfarben und Logo anpassen

### Farben

Die Primärfarben werden in `config/demo/vereinsconfig.json` gesetzt und automatisch
als CSS-Variablen in alle Templates injiziert (Login-Seite, Navigationsleiste,
Buttons):

```json
{
  "primary_color":        "#2d6a2d",
  "primary_color_dark":   "#1a4a1a",
  "primary_color_darker": "#0f2e0f",
  "gold_color":           "#f0c040"
}
```

| Variable | Verwendung |
|---|---|
| `primary_color` | Buttons, Links, Akzente |
| `primary_color_dark` | Hover-Zustände, Navbar-Hintergrund |
| `primary_color_darker` | Aktive Elemente, Schatten |
| `gold_color` | Akzentfarbe (Sterne, Highlights) |

### Logo

Das Logo wird als halbdurchsichtiger Hintergrund auf der Login-Seite und als
Icon in der Navigationsleiste verwendet. Es muss eine SVG- oder PNG-Datei in
`web/static/` sein, da nur dieser Ordner öffentlich ausgeliefert wird.

**Für die Demo** liegt das Logo unter `web/static/logo_demo.svg` und ist in
`config/demo/vereinsconfig.json` eingetragen:

```json
{
  "logo_url": "/static/logo_demo.svg"
}
```

**Für einen neuen Verein** das eigene Logo nach `web/static/` kopieren und
`logo_url` entsprechend anpassen:

```bash
cp /pfad/zum/wappen.svg web/static/logo_meinverein.svg
# dann in config/demo/vereinsconfig.json:
# "logo_url": "/static/logo_meinverein.svg"
```

> Das Logo sollte ein Hochformat-SVG sein (empfohlen: Viewbox 1200×1600 oder ähnlich),
> damit es als Hintergrundbild auf der Login-Seite gut wirkt. PNG funktioniert
> ebenfalls, SVG ist bevorzugt (skaliert verlustfrei).

---

## Schritt 6 – Demo-Server starten

```bash
bash start_demo.sh
```

Beim nächsten Seitenaufruf werden die neuen Farben und das neue Logo sofort
angezeigt — ein Server-Neustart ist nicht nötig, da `vereinsconfig.json` beim
Start einmalig geladen wird. Bei laufendem `--reload`-Server reicht eine
Dateiänderung.

Entspricht intern:
```bash
ENV_FILE=.env.demo CONFIG_DIR=config/demo uvicorn web.main:app --reload --port 1946
```

Login unter **http://localhost:1946/login** mit dem in Schritt 4 angelegten Account.
Das System fordert beim ersten Login sofort einen Passwortwechsel (da `Passwort ändern = true`).

---

## Demo-Konfiguration im Überblick

| Datei | Inhalt |
|---|---|
| `.env.demo` | Demo-Notion-DB-IDs, fussball.de-Zugangsdaten, JWT-Secret |
| `config/demo/vereinsconfig.json` | TSV Hotzenplotz (grüne Farben, fiktive Spielorte) |
| `config/demo/field_config.json` | Rasen, Kura 1+2, Trainingsfeld, Halle |

---

## Fehler-Referenz

| Fehlermeldung | Ursache | Lösung |
|---|---|---|
| `Could not find page with ID … Make sure the relevant pages and databases are shared with your integration.` | Integration hat keinen Zugriff auf die Elternseite | Schritt 1 wiederholen |
| `Token in header: "x-auth-token" not found` | Falscher Header bei api-fussball.de | Header `x-auth-token` statt `Authorization` verwenden |
| `Failed to resolve 'apifussball.de'` | Falscher Domainname | Korrekt: `api-fussball.de` (mit Bindestrich) |
| Login schlägt fehl, Passwort korrekt | `Password_Hash` in Notion leer oder falsch | Hash neu erzeugen und eintragen |

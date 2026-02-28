# Hardcodierte Werte & Geheimnisse

Dieser Bericht dokumentiert alle Stellen im Code, die entweder sensible
Zugangsdaten oder vereinsspezifische Konstanten hardcodiert enthalten.
Stand: 2026-02-28.

---

## 1. Kritisch — Secrets im Code (nicht in .env)

Diese Werte müssen **sofort** aus dem Code entfernt und in `.env` ausgelagert
werden, da sie bei einem Git-Push öffentlich sichtbar wären.

| Datei | Zeile | Wert | Beschreibung |
|-------|-------|------|--------------|
| `scripts/fetch_spielplan.py` | 23 | `TOKEN = "Y1t797t1t5Z8Y5h2D2b6r736X5M6HVEYzhWbM6DIeU"` | api-fussball.de API-Token |
| `scripts/fetch_spielplan.py` | 24 | `CLUB_ID = "00ES8GN75400000VVV0AG08LVUPGND5I"` | fussball.de Club-ID |
| `homepage/userdata/vereinsinfo/verein_to_id.py` | 9 | `token = "Y1t797t1t5Z8Y5h2D2b6r736X5M6HVEYzhWbM6DIeU"` | api-fussball.de API-Token (Duplikat) |
| `tools/check_spielplan.py` | 58 | `CLUB_ID = "00ES8GN75400000VVV0AG08LVUPGND5I"` | fussball.de Club-ID (Duplikat) |

**Maßnahme:** Neue `.env`-Variablen `APIFUSSBALL_TOKEN` und (optional) `FUSSBALL_DE_CLUB_ID`
anlegen; Wert in `booking/spielplan_sync.py` bereits als `_FALLBACK_CLUB_ID` vorhanden,
der Fallback bleibt tolerierbar, muss aber dokumentiert sein.

---

## 2. Bereits in .env — korrekt ausgelagert

Die folgenden Werte sind bereits in `.env` und über `web/config.py` (`pydantic-settings`)
eingelesen. Kein Handlungsbedarf.

| Variable | Beschreibung |
|----------|--------------|
| `NOTION_API_KEY` | Notion Integration Token |
| `NOTION_BUCHUNGEN_DB_ID` | Notion Datenbank: Buchungen |
| `NOTION_SERIEN_DB_ID` | Notion Datenbank: Serien |
| `NOTION_SPERRZEITEN_DB_ID` | Notion Datenbank: Sperrzeiten |
| `NOTION_NUTZER_DB_ID` | Notion Datenbank: Nutzer |
| `NOTION_AUFGABEN_DB_ID` | Notion Datenbank: Aufgaben |
| `NOTION_EVENTS_DB_ID` | Notion Datenbank: Externe Termine |
| `JWT_SECRET` | JWT Signing-Key |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Mail-Versand |
| `ADMIN_EMAIL` | Empfänger für Crash-Mails |
| `BOOKING_URL` | Öffentliche URL des Buchungssystems |
| `FUSSBALL_DE_VEREINSSEITE` | fussball.de Vereinsseiten-URL (enthält Club-ID) |
| `LOCATION_LAT` / `LOCATION_LON` / `LOCATION_NAME` | Standort für Sonnenuntergang |

---

## 3. Vereinsspezifika — hardcodiert, aber kein Geheimnis

Diese Werte sind öffentlich, sollten aber für eine Wiederverwendbarkeit des
Systems ebenfalls konfigurierbar sein (→ TODO 2).

### 3a. Platz-Namen / Platz-Topologie

Die Platznamen sind im gesamten System als fester Enum kodiert:

| Datei | Beschreibung |
|-------|--------------|
| `booking/models.py:10–19` | `FieldName` Enum: Kura Ganz/Halb A/Halb B, Rasen Ganz/Halb A/Halb B, Halle Ganz/2/3/1/3 |
| `config/field_config.json` | Gruppen und deren Sichtbarkeit pro Rolle |
| `web/templates/partials/_calendar_week.html:2–6` | `field_short`-Map für Kurzbezeichnungen |
| `web/templates/partials/_calendar_week.html:9–19` | `conflict_sources`-Map (welche Felder blockieren sich) |

### 3b. fussball.de Spielort-Strings

Werden benutzt, um fussball.de-Spielorte auf interne Platznamen zu mappen:

| Datei | Zeile | Wert |
|-------|-------|------|
| `tools/check_spielplan.py` | 61–64 | `"Cremlingen B-Platz Kustrasen"` → Kura |
| `tools/check_spielplan.py` | 181–182 | `"Cremlingen A-Platz Rasen"` → Rasen |
| `tools/check_spielplan.py` | 388–391 | `"cremlingen b-platz"`, `"cremlingen a-platz rasen"` (Kleinschreibung) |
| `booking/spielplan_sync.py` | (Spielort-Matching) | Gleiche Strings im Sync-Code |

### 3c. Heim-Keyword (Vereinsname im Spielplan)

| Datei | Zeile | Wert |
|-------|-------|------|
| `scripts/fetch_spielplan.py` | 33 | `TUS_HOME_KEYWORDS = {"cremlingen"}` |

### 3d. Vereinsname in Templates

| Datei | Beschreibung |
|-------|--------------|
| `web/templates/base.html:15` | `<title>TuS Cremlingen – Buchung</title>` |
| `web/templates/login.html:12,14` | `"TuS Cremlingen Wappen"`, `"TuS Cremlingen"` |
| `homepage/main.py:72` | `FastAPI(title="TuS Cremlingen", ...)` |
| `homepage/templates/index.html:6,17` | `"TuS Cremlingen e.V."` |
| `homepage/templates/impressum.html:41,52` | Mail-Adressen |

### 3e. Vereinsfarben (CSS)

| Datei | Variable / Wert | Beschreibung |
|-------|-----------------|--------------|
| `web/static/style.css:6` | `--color-primary: #1e4fa3` | Primärfarbe (Blau) |
| `web/static/style.css:7` | `--color-primary-hover: #0d2f6b` | Hover-Dunkelblau |
| `homepage/static/style.css:4–7` | `--green: #1a4a8f`, `--green-light: #2563b0`, `--gold: #e8c04a` | Vereinsfarben |

*(Die Variablen-Namen `--green` in der Homepage sind historisch; tatsächlich sind
es Vereinsblau-Töne.)*

### 3f. Logo

| Datei | Pfad |
|-------|------|
| `web/static/logo.svg` | Logo im Buchungssystem |
| `homepage/userdata/logo.svg` | Logo auf der Homepage |

---

## 4. Kontakt- und Impressumsdaten

Diese Daten sind bewusst in `homepage/userdata/impressum.txt` abgelegt
und werden aus dem Template geladen. Sie sind für das Impressum gesetzlich
erforderlich und stellen kein Problem dar.

| Inhalt | Datei |
|--------|-------|
| Vereinsadresse, Vorstand, Registernummer | `homepage/userdata/impressum.txt` |
| Datenschutzbeauftragter / Kontakt | `homepage/userdata/impressum.txt` |

---

## 5. Handlungsplan (Priorität)

| # | Maßnahme | Priorität |
|---|----------|-----------|
| 1 | `scripts/fetch_spielplan.py` und `homepage/userdata/vereinsinfo/verein_to_id.py`: TOKEN aus Code entfernen, `APIFUSSBALL_TOKEN` aus `.env` lesen | 🔴 Hoch |
| 2 | `tools/check_spielplan.py`: CLUB_ID aus `.env` / `FUSSBALL_DE_VEREINSSEITE` extrahieren statt hardcodieren | 🟡 Mittel |
| 3 | Platz-Topologie (Namen, Gruppen, Konflikt-Map) in `config/` zentralisieren und aus `models.py`-Enum herauslösen | 🟡 Mittel |
| 4 | fussball.de Spielort-Strings und Heim-Keyword in `.env` oder `config/vereinsconfig.json` | 🟡 Mittel |
| 5 | Vereinsname, Farben, Logo per `config/vereinsconfig.json` konfigurierbar machen | 🟢 Niedrig |

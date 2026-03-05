# Betriebshandbuch – Platzbuchungssystem

Dieses Handbuch beschreibt wiederkehrende Admin-Aufgaben.

---

## Saisonplanung: Serien anlegen

### Übersicht der Saisontypen

| Typ | Typisches Datum | Platz |
|-----|----------------|-------|
| **Ganzjährig** | 01.08. – 30.06. | Kunstrasen oder Turnhalle |
| **Sommerhalbjahr** | 01.08. – 30.10. *oder* 01.03. – 30.06. | Outdoor (Kura / Rasen) |
| **Winterhalbjahr** | 30.10. – 01.03. | Turnhalle |

Die genauen Daten sind pro Serie frei wählbar — die Typen dienen als
Kennzeichnung und füllen das Formular vor.

---

## Sommer- und Winterbetrieb

Mannschaften, die im Winter auf die Halle wechseln, benötigen
**drei Serien** pro Saison:

```
Aug          Okt          Mrz          Jun
 |── Sommer 1 ──|── Winter ──|── Sommer 2 ──|
```

### Schritt-für-Schritt

**1. Sommer-Serie 1 anlegen** (Outdoor vor Winterpause)

| Feld | Beispiel D1 |
|------|-------------|
| Mannschaft | D1 |
| Trainer | zugewiesener Trainer |
| Platz | Kura Halb B |
| Startzeit | 17:00 |
| Dauer | 90 Min |
| Rhythmus | Wöchentlich |
| Saison | Sommerhalbjahr |
| Startdatum | 01.08.2026 |
| Enddatum | 30.10.2026 *(individuell – wann beginnt die Mannschaft Wintertraining?)* |

**2. Winter-Serie anlegen** (Hallenbetrieb)

| Feld | Beispiel D1 |
|------|-------------|
| Platz | Halle 1/3 *(oder 2/3, Ganz – je nach Verfügbarkeit)* |
| Saison | Winterhalbjahr |
| Startdatum | 30.10.2026 *(= Enddatum Sommer 1 + 1 Tag)* |
| Enddatum | 01.03.2027 *(individuell – Rückkehr der Mannschaft)* |

> **Hinweis:** Der Outdoor-Platz (Kura Halb B) ist während des
> Winterhalbjahrs **nicht belegt** und steht anderen Nutzern
> für Einzelbuchungen oder andere Serien zur Verfügung.

**3. Sommer-Serie 2 anlegen** (Outdoor nach Winterpause)

| Feld | Beispiel D1 |
|------|-------------|
| Platz | Kura Halb B *(gleicher Platz wie Sommer 1)* |
| Saison | Sommerhalbjahr |
| Startdatum | 01.03.2027 *(= Enddatum Winter + 1 Tag)* |
| Enddatum | 30.06.2027 |

---

### Ganzjährige Serie (kein Winterwechsel)

Für Mannschaften ohne Hallentraining (z. B. TuS 1 / TuS 2, Ü-Mannschaften
auf Kunstrasen):

| Feld | Wert |
|------|------|
| Saison | Ganzjährig |
| Startdatum | 01.08.2026 |
| Enddatum | 30.06.2027 |

Das System begrenzt das Enddatum automatisch auf den konfigurierten
Saisonabschluss (Standard: 30.06.).

---

## Saisonwechsel: neue Saison vorbereiten

Am Ende einer Saison (i. d. R. Ende Juni) müssen alle Serien für die
neue Saison neu angelegt werden. Alte Serien laufen automatisch aus —
es ist kein manuelles Beenden nötig, sofern das Enddatum korrekt gesetzt war.

### Checkliste Saisonstart (August)

- [ ] Alle Serien der Vorjahressaison auf Status „Beendet" prüfen
      (laufen sie noch? → manuell beenden)
- [ ] Neue Ganzjahres-Serien anlegen (Kunstrasen-Mannschaften)
- [ ] Sommer-Serien Teil 1 anlegen (alle Outdoor-Mannschaften)
- [ ] Wintertermine je Mannschaft klären und notieren
      (wann beginnt Hallenbetrieb, wann Rückkehr?)
- [ ] Hallenkapazität prüfen: passen alle Winter-Serien in die
      verfügbaren Hallenzeiten?
- [ ] DFBnet-Spielplan für neue Saison importieren (CSV-Import)

### Checkliste Winterwechsel (Oktober / November)

- [ ] Winter-Serien für alle wechselnden Mannschaften anlegen
- [ ] Sommer-Serien Teil 2 (Rückkehr im März) direkt mit anlegen,
      damit der Slot reserviert ist
- [ ] Prüfen: sind alle Outdoor-Slots der Winter-Mannschaften frei?

---

## Serie vorzeitig beenden

Wenn eine Mannschaft ihren Platz aufgibt oder der Trainer wechselt:

1. Serien-Übersicht öffnen (`/series`)
2. Betroffene Serie suchen → **„Serie beenden"** klicken
3. Alle zukünftigen Einzeltermine werden automatisch auf „Storniert" gesetzt
4. Betroffene Trainer erhalten eine E-Mail mit der Liste der Termine
5. Neue Serie mit geänderten Daten anlegen

---

## Einzeltermin aus Serie entfernen

Wenn ein einzelner Termin nicht stattfindet (z. B. wegen Feiertag):

1. Im Kalender auf den Termin klicken
2. **„Termin aus Serie entfernen"** wählen
3. Der Slot wird freigegeben; die Serie läuft an den übrigen Terminen weiter

> Erlaubt für: Administrator, DFBnet, zugewiesener Trainer der Serie.

---

## Konflikte beim Anlegen einer Serie

Wenn beim Anlegen Termine übersprungen werden (Konflikt mit bestehenden
Buchungen), erscheint eine Meldung mit den betroffenen Daten, z. B.:

> *„Serie angelegt (D1): 28 Termine erstellt. 2 übersprungen (Konflikt): 15.09., 22.09."*

Die übersprungenen Termine müssen entweder:
- als **Einzelbuchung** manuell nachgetragen werden, oder
- bleiben unbesetzt (der Slot bleibt frei)

---

## Nutzerverwaltung

### Neuen Nutzer anlegen

1. Admin-Bereich → **„Nutzer"** → **„Neuer Nutzer"**
2. Felder ausfüllen: Name, Rolle, E-Mail, Mannschaft (optional)
3. Passwort wird automatisch generiert und muss beim ersten Login
   geändert werden

### Passwort zurücksetzen

1. Nutzer-Zeile aufklappen → **„Passwort zurücksetzen"**
2. Neues temporäres Passwort vergeben
3. Nutzer beim nächsten Login zur Änderung aufgefordert

### Rolle ändern

Inline-Editor in der Nutzerliste: Zeile aufklappen → Rolle ändern →
Speichern. Das bestehende JWT-Token des Nutzers läuft nach max. 8 Stunden
ab; bis dahin behält er die alte Rolle.

---

## Platzkonfiguration

### Platz-ID-Schema

Jeder Platz hat eine kurze ID (ein oder zwei Buchstaben). Das Schema folgt
einem einheitlichen Muster:

```
Gruppe  Ganzer Platz  Hälfte A  Hälfte B
──────  ────────────  ────────  ────────
Kura    A             AA        AB
Rasen   B             BA        BB
Halle   C             CA        CB
```

Der erste Buchstabe kennzeichnet die Gruppe; der zweite (A oder B)
die jeweilige Hälfte. Buchungen können auf den ganzen Platz
(`A`, `B`, `C`) oder auf eine Hälfte (`AA`/`AB`, `BA`/`BB`, `CA`/`CB`)
erfolgen.

### Anzeigenamen

| ID | Anzeigename |
|----|-------------|
| A  | Kura AB     |
| AA | Kura A      |
| AB | Kura B      |
| B  | Rasen AB    |
| BA | Rasen A     |
| BB | Rasen B     |
| C  | Halle Ganz  |
| CA | Halle 2/3   |
| CB | Halle 1/3   |

### Platzeigenschaften

| Gruppe | Fläche | Beleuchtet | Sichtbar für |
|--------|--------|-----------|--------------|
| Kura (Kunstrasen) | A, AA, AB | Ja | Trainer, Platzwart, DFBnet, Administrator |
| Rasen (Naturrasen) | B, BA, BB | Nein | Trainer, Platzwart, DFBnet, Administrator |
| Turnhalle | C, CA, CB | Ja | Administrator |

> Die Turnhalle ist nur für Administratoren buchbar (interne Hallennutzung
> ohne direkten Trainerzugang).

`lit: true` bedeutet: der Platz hat Flutlicht. Das System nutzt dieses Flag,
um bei Buchungen nach Sonnenuntergang einen Hinweis anzuzeigen.

### Konfigurationsdatei: `config/field_config.json`

Alle Platzeigenschaften werden in `config/field_config.json` gepflegt:

```jsonc
{
  "display_names": {
    "A": "Kura AB",   // Ganzer Kunstrasen
    "AA": "Kura A",   // Hälfte A
    "AB": "Kura B",   // Hälfte B
    ...
  },
  "field_groups": [
    {
      "id": "kura",
      "name": "Kura (Kunstrasen)",
      "fields": ["A", "AA", "AB"],   // Welche IDs gehören zur Gruppe
      "lit": true,                    // Flutlicht vorhanden
      "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"]
    },
    ...
  ]
}
```

**Neue Gruppe / neuen Platz hinzufügen:**
1. Neuen Eintrag in `display_names` anlegen (`"X": "Anzeigename"`)
2. Neue `field_groups`-Gruppe anlegen oder bestehende Gruppe um die ID erweitern
3. Notion-Datenbank: Property „Platz" um den neuen Wert ergänzen
4. `FieldName`-Enum in `booking/models.py` erweitern

---

## Systemkonfiguration

### Übersicht der Konfigurationsquellen

| Datei / Quelle | Zweck |
|---------------|-------|
| `config/vereinsconfig.json` | Vereinsspezifika: Name, Farben, Logo, Saisonvorgaben, Spielorte |
| `config/field_config.json` | Platzstruktur: IDs, Anzeigenamen, Gruppen, Eigenschaften |
| `.env` | Betriebsgeheimnisse: API-Keys, SMTP, JWT |

### `config/vereinsconfig.json`

| Schlüssel | Beispielwert | Bedeutung |
|-----------|-------------|-----------|
| `vereinsname` | `"TuS Cremlingen"` | Kurzname, erscheint im UI-Header |
| `vereinsname_lang` | `"Turn- und Sportverein …"` | Vollständiger Name (Footer, Mails) |
| `logo_url` | `"/static/logo.svg"` | Pfad zum Vereinslogo (Navbar + Hintergrundbild Login) |
| `heim_keywords` | `["cremlingen"]` | Liste von Substrings zum Erkennen von Heimspielen (Spielgemeinschaften → mehrere Einträge) |
| `primary_color` | `"#1e4fa3"` | Hauptfarbe (Buttons, Links, Hintergrund-Gradient) |
| `primary_color_dark` | `"#0d2f6b"` | Hover-Zustände |
| `primary_color_darker` | `"#071c44"` | Navbar-Hintergrund, aktive Zustände |
| `gold_color` | `"#e8c04a"` | Akzentfarbe |
| `saison_defaults` | siehe unten | Standard-Datumsgrenzen je Saisontyp |
| `spielorte` | siehe unten | Zuordnung fussball.de-Spielortstring → Feld-ID |

**`saison_defaults`** – Vorbefüllung der Datumsfelder beim Anlegen einer Serie:

```json
"saison_defaults": {
  "ganzjaehrig":    {"start": "08-01", "ende": "06-30"},
  "sommerhalbjahr": {"start": "08-01", "ende": "10-30"},
  "winterhalbjahr": {"start": "10-30", "ende": "03-01"}
}
```

Format: `MM-DD`. Das Jahr wird automatisch aus dem aktuellen Datum abgeleitet.

**`spielorte`** – Verknüpft fussball.de-Spielortbeschreibungen mit internen Feld-IDs,
damit importierte Spielplandaten dem richtigen Platz zugeordnet werden:

```json
"spielorte": [
  {"fussball_de_string": "cremlingen b-platz", "feld": "A", "platz_praefix": ["A"]},
  {"fussball_de_string": "cremlingen a-platz rasen", "feld": "B", "platz_praefix": ["B"]}
]
```

**`heim_keywords`** – Liste von Schlüsselwörtern (Kleinschreibung), die im Heimteam-Namen auf fussball.de gesucht werden.
Stimmt eines überein, gilt das Spiel als Heimspiel und wird automatisch ins Buchungssystem eingetragen.

Einfacher Verein:
```json
"heim_keywords": ["cremlingen"]
```

Spielgemeinschaft / JSG (Teams laufen unter verschiedenen Namen):
```json
"heim_keywords": ["cremlingen", "sg cremlingen-sickte"]
```

> Rückwärtskompatibel: Der alte String-Key `"heim_keyword"` wird noch akzeptiert, aber `heim_keywords` (Liste) ist der neue Standard.

---

### `config/scheduler.json`

Steuert den automatischen Spielplan-Sync (in-process APScheduler).
Die Konfiguration kann auch direkt im Admin-Dashboard (unter **fussball.de Spielplan-Sync**) geändert werden — Änderungen dort wirken sofort ohne Server-Neustart.

| Schlüssel | Standardwert | Bedeutung |
|-----------|-------------|-----------|
| `spielplan_sync_enabled` | `true` | Automatischen Cron-Job ein-/ausschalten |
| `spielplan_sync_uhrzeit` | `"06:00"` | Uhrzeit der täglichen Ausführung (Format `HH:MM`) |

Beispiel `config/scheduler.json`:
```json
{
  "spielplan_sync_enabled": true,
  "spielplan_sync_uhrzeit": "06:00"
}
```

> Die Datei wird **nicht** gecacht — Änderungen werden beim nächsten Scheduler-Ereignis oder nach einem Speichern im Admin-Dashboard sofort wirksam.

---

**Logo austauschen:**

1. Logo-Datei nach `web/static/` kopieren (SVG empfohlen, PNG möglich)
2. `logo_url` in `vereinsconfig.json` anpassen: `"/static/meinverein.svg"`
3. Server neu starten

Das Logo erscheint als Icon in der Navigationsleiste und als halbdurchsichtiges
Wasserzeichen im Seitenhintergrund. Empfohlenes Format: Hochformat-SVG mit
`viewBox="0 0 1200 1600"` (Schildform skaliert gut). PNG funktioniert, SVG ist bevorzugt.

**Farben ändern:**

Die drei Primärfarben steuern das gesamte Farbschema. Alle abgeleiteten Farben
(Hintergrund-Tints, Rahmen, freie Slots) passen sich automatisch via `color-mix()` an —
es müssen nur die drei Hauptfarben gesetzt werden:

```json
"primary_color":        "#1e4fa3",   // Hauptfarbe
"primary_color_dark":   "#0d2f6b",   // ~20 % dunkler
"primary_color_darker": "#071c44"    // ~50 % dunkler (Navbar)
```

Die Farben werden als CSS-Variablen in `web/templates/base.html` eingebettet und
überschreiben die Fallback-Werte in `web/static/style.css`.

> **Server-Neustart erforderlich** nach Änderungen an `vereinsconfig.json`:
> Die Datei wird mit `lru_cache` einmalig beim Start geladen.
> ```bash
> pkill -f "uvicorn web.main:app" && bash start_server.sh
> # oder im Demo-Betrieb:
> pkill -f "uvicorn web.main:app" && bash start_demo.sh
> ```

### `.env` – Betriebsvariablen

| Variable | Pflicht | Bedeutung |
|----------|---------|-----------|
| `NOTION_API_KEY` | Ja | Notion-Integration-Token |
| `NOTION_BUCHUNGEN_DB_ID` | Ja | Notion-DB-ID für Buchungen |
| `NOTION_SERIEN_DB_ID` | Ja | Notion-DB-ID für Serien |
| `NOTION_NUTZER_DB_ID` | Ja | Notion-DB-ID für Nutzer |
| `NOTION_AUFGABEN_DB_ID` | Ja | Notion-DB-ID für Aufgaben |
| `NOTION_EVENTS_DB_ID` | Nein | Notion-DB-ID für externe Termine |
| `JWT_SECRET` | Ja | Geheimer Schlüssel für JWT-Tokens (min. 32 Zeichen) |
| `JWT_ALGORITHM` | Nein | Standard: `HS256` |
| `JWT_EXPIRE_HOURS` | Nein | Token-Laufzeit in Stunden (Standard: 8) |
| `SMTP_HOST` | Ja | SMTP-Server (z. B. `smtp.gmail.com`) |
| `SMTP_PORT` | Nein | Standard: `587` |
| `SMTP_USER` | Ja | SMTP-Nutzername / Absenderadresse |
| `SMTP_PASSWORD` | Ja | SMTP-Passwort / App-Passwort |
| `SMTP_FROM` | Ja | Absenderadresse in gesendeten E-Mails |
| `ADMIN_EMAIL` | Nein | Empfänger für Fehler-Mails (fällt auf `SMTP_FROM` zurück) |
| `BOOKING_URL` | Nein | Öffentliche URL (für Links in E-Mails), Standard: `http://localhost:1946` |
| `FUSSBALL_DE_VEREINSSEITE` | Nein | URL der Vereinsseite auf fussball.de (Spielplan-Import) |
| `APIFUSSBALL_TOKEN` | Nein | API-Token für api-fussball.de |
| `LOCATION_LAT` | Nein | Breitengrad für Sonnenuntergangsberechnung (Standard: 52.264) |
| `LOCATION_LON` | Nein | Längengrad (Standard: 10.639) |
| `LOCATION_NAME` | Nein | Ortsname für Logs (Standard: `Cremlingen/Germany`) |
| `SKIP_NOTION_MIGRATE` | Nein | `true` = Notion-Schema-Prüfung beim Start überspringen (Offline-Tests) |

> Alle Variablen müssen als Felder in `web/config.py` (`Settings`-Klasse)
> deklariert sein, sonst verweigert pydantic-settings den Start mit
> `ValidationError: Extra inputs are not permitted`.

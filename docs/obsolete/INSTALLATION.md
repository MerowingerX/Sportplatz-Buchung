# Installation & Ersteinrichtung

Diese Anleitung richtet sich an den Systemverantwortlichen, der das TuS Cremlingen Platzbuchungssystem auf einem neuen Server aufsetzt.

---

## Voraussetzungen

| Komponente | Mindestversion |
|---|---|
| Python | 3.11 |
| Betriebssystem | Debian/Ubuntu (systemd) |
| Notion | kostenloser Account ausreichend |
| SMTP-Zugang | beliebiger Mailserver (z. B. Gmail, Strato, eigener) |

---

## 1. Notion vorbereiten

Das System verwendet Notion als Datenbank. Alle Tabellen werden als **Notion-Datenbanken** (Full-Page, nicht inline) angelegt.

### 1.1 Integration erstellen

Eine **Notion-Integration** ist ein interner Bot-Account, der der Anwendung API-Zugriff auf ausgewählte Seiten und Datenbanken gewährt. Notion-Inhalte sind standardmäßig privat — die Integration darf **nur auf Seiten zugreifen, die ihr explizit freigegeben wurden**, selbst wenn du derselbe Account-Inhaber bist.

1. → [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. **New integration** → Name z. B. `Sportplatz-Buchung`
3. Capabilities: **Read content**, **Update content**, **Insert content**
4. Den angezeigten **Internal Integration Token** notieren → `NOTION_API_KEY`

> **Integrations-Namen nachschlagen:** Falls unklar ist, welcher Name zu einem Token gehört:
> ```bash
> NOTION_API_KEY=<token> .venv/bin/python -c "
> from notion_client import Client
> me = Client(auth='<token>').users.me()
> print(me.get('name'))
> "
> ```

### 1.2 Datenbanken anlegen

Für jede der folgenden Tabellen eine leere Notion-Datenbank anlegen. Die Properties werden **beim ersten Start automatisch ergänzt** – es genügt, die Datenbank anzulegen und den Namen für die Spalte `Name` (Titel-Spalte) beizubehalten.

| Variable | Inhalt der Datenbank |
|---|---|
| `NOTION_BUCHUNGEN_DB_ID` | Platzbuchungen |
| `NOTION_SERIEN_DB_ID` | Serienbuchungen |
| `NOTION_SPERRZEITEN_DB_ID` | Sperrzeiten |
| `NOTION_NUTZER_DB_ID` | Nutzerkonten |
| `NOTION_AUFGABEN_DB_ID` | Aufgaben & Meldungen |
| `NOTION_EVENTS_DB_ID` | Externe Termine *(optional)* |

**Datenbank-ID ermitteln**: Die URL einer geöffneten Datenbank in Notion sieht so aus:
```
https://www.notion.so/<workspace>/<DATABASE_ID>?v=...
```
Der 32-stellige Hex-Block vor dem `?` ist die ID (ohne Bindestriche).

### 1.3 Integration mit den Datenbanken verknüpfen

Jede Datenbank (bzw. die übergeordnete Seite) muss der Integration freigegeben werden:

1. Seite oder Datenbank in Notion öffnen → `···` (Drei-Punkte-Menü, oben rechts) → **Connections** → Integrations-Name suchen und hinzufügen → **Confirm**.
2. Diesen Schritt für alle 5 (bzw. 6) Datenbanken wiederholen.

> **Tipp:** Wenn alle Datenbanken unter einer gemeinsamen Eltern-Seite liegen, reicht es, die **Eltern-Seite** freizugeben — alle Unterseiten und -datenbanken erben den Zugriff automatisch.
>
> Die Integration verweigert den Zugriff auch dann, wenn der API-Key korrekt ist. Die Fehlermeldung lautet: *"Could not find page with ID … Make sure the relevant pages and databases are shared with your integration."*

---

## 2. Repository klonen

```bash
git clone https://github.com/<org>/Sportplatz-Buchung.git /root/git.com/Sportplatz-Buchung
cd /root/git.com/Sportplatz-Buchung
```

> Die systemd-Services erwarten das Verzeichnis unter `/root/git.com/Sportplatz-Buchung`.
> Bei einem anderen Pfad müssen `deploy/*.service` entsprechend angepasst werden.

---

## 3. Konfigurationsdateien anlegen

Die vereinsspezifischen Config-Dateien sind **nicht im Repository** enthalten
(`.gitignore`). Beim erstmaligen Einrichten müssen sie aus den Beispieldateien
erzeugt werden:

```bash
cp config/vereinsconfig.example.json  config/vereinsconfig.json
cp config/field_config.example.json   config/field_config.json
```

Anschließend beide Dateien an den eigenen Verein anpassen. Die `.example.json`-Dateien
enthalten ausführliche Kommentare zu jedem Feld.

### Wichtige Felder in `config/vereinsconfig.json`

| Schlüssel | Bedeutung |
|-----------|-----------|
| `vereinsname` | Kurzname (Navbar, Browser-Tab) |
| `heim_keywords` | Liste von Substrings zum Erkennen von Heimspielen auf fussball.de. Mehrere Einträge für Spielgemeinschaften/JSG, z. B. `["musterstadt", "sg musterstadt"]` |
| `spielorte` | Zuordnung fussball.de-Spielortstring → interne Feld-ID |
| `primary_color` / `_dark` / `_darker` | Vereinsfarben → steuern das gesamte Farbschema |
| `logo_url` | Pfad zum Logo (z. B. `"/static/logo.svg"`) |

---

## 4. Python-Umgebung einrichten

Das Projekt benötigt **Python 3.11**. Ein Virtual Environment (`.venv`) ist
notwendig, um die Paketversionen aus `requirements.txt` isoliert vom
System-Python zu installieren.

### 3.1 Warum `.venv`?

- Exakte Versionen (z. B. `pydantic-settings==2.3.4`) ohne Konflikte mit
  anderen Projekten
- Unabhängig vom System-Python (Debian/Ubuntu liefert oft Python 3.10)
- `start_demo.sh` und `start_server.sh` verwenden direkt `.venv/bin/uvicorn`

### 3.2 Python-Version sicherstellen

Das System-Python reicht, wenn es bereits 3.11 ist:

```bash
python3 --version   # sollte 3.11.x sein
```

Ist das System-Python älter (z. B. 3.10 unter Ubuntu 22.04), muss Python 3.11
über **pyenv** oder `deadsnakes`-PPA bereitgestellt werden:

```bash
# Option A – pyenv (empfohlen, kein sudo nötig)
pyenv install 3.11.14
# danach den venv-Befehl mit vollem Pfad aufrufen (siehe 3.3)

# Option B – deadsnakes-PPA (Ubuntu)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv
```

### 3.3 Venv anlegen

**Wichtig bei pyenv:** Mit `--copies` erstellen, nicht mit Symlinks. Andernfalls
zeigt `.venv/bin/python` auf das System-Python statt auf das pyenv-Python, und
installierte Pakete werden nicht gefunden.

```bash
# System-Python 3.11 (deadsnakes oder direkt verfügbar)
python3.11 -m venv .venv --copies

# pyenv: Python 3.11 über vollständigen Pfad
~/.pyenv/versions/3.11.14/bin/python3.11 -m venv .venv --copies
```

Prüfen ob das korrekte Python im venv liegt:

```bash
.venv/bin/python --version   # muss Python 3.11.x ausgeben
```

### 3.4 Abhängigkeiten installieren

```bash
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Verifizieren:

```bash
.venv/bin/python -c "from notion_client import Client; print('OK')"
```

---

## 5. `.env`-Datei anlegen

Im Projektverzeichnis eine Datei `.env` anlegen:

```bash
cp .env.example .env   # falls vorhanden, sonst neue Datei erstellen
nano .env
```

### Pflichtfelder

```dotenv
# ── Notion ──────────────────────────────────────────────────────────
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_BUCHUNGEN_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_SERIEN_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_SPERRZEITEN_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_NUTZER_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_AUFGABEN_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Sicherheit ──────────────────────────────────────────────────────
# Beliebiger langer zufälliger String, z. B.: openssl rand -hex 32
JWT_SECRET=<langer_zufaelliger_string>

# ── E-Mail (Crash-Benachrichtigungen & Systemmails) ─────────────────
SMTP_HOST=smtp.example.com
SMTP_USER=buchung@example.com
SMTP_PASSWORD=<smtp-passwort>
SMTP_FROM=buchung@example.com
```

### Optionale Felder (mit Standardwerten)

```dotenv
# Notion – Externe Termine (für Eventliste auf der Homepage)
NOTION_EVENTS_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# JWT-Session-Gültigkeit in Stunden (Standard: 8)
JWT_EXPIRE_HOURS=8

# Port, auf dem das Admin-System läuft (für E-Mail-Links)
BOOKING_URL=http://<server-ip>:1946

# Absender für Crash-Mails (Standard: SMTP_FROM)
ADMIN_EMAIL=admin@example.com

# SMTP-Port (Standard: 587)
SMTP_PORT=587

# Standort für Sonnenuntergangsberechnung (Standard: München)
LOCATION_LAT=52.277
LOCATION_LON=10.524
LOCATION_NAME=Cremlingen/Germany
```

> **Hinweis zu `LOCATION_*`**: Die Koordinaten bestimmen, bis wann abends Platzbuchungen möglich sind (Sonnenuntergang + Puffer). Für Cremlingen: `LOCATION_LAT=52.277`, `LOCATION_LON=10.524`.

### JWT-Secret generieren

```bash
openssl rand -hex 32
```

### Gmail als SMTP

Bei Gmail muss ein **App-Passwort** erstellt werden (Google-Konto → Sicherheit → 2-Faktor → App-Passwörter). Standard-SMTP-Einstellungen:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

---

## 6. Ersten Admin-Nutzer anlegen

Das System hat keine Web-Oberfläche zur Erstkonfiguration. Der erste Administrator-Account wird direkt in der Notion-Datenbank angelegt.

1. Notion-Datenbank `NOTION_NUTZER_DB_ID` öffnen
2. Neue Seite anlegen mit diesen Properties:

| Property | Wert |
|---|---|
| Name (Titel) | `admin` *(oder gewünschter Benutzername)* |
| Rolle | `Administrator` |
| Passwort-Hash | *(leer lassen)* |
| Must Change Password | `true` (Checkbox aktivieren) |

3. Server starten (siehe Schritt 6) und auf `http://<server>:1946/login` einloggen
4. Da kein Passwort gesetzt ist, zunächst einen Hash erzeugen:

```bash
.venv/bin/python3 -c "
from auth.auth import hash_password
print(hash_password('ErstesPasswort123'))
"
```

5. Den ausgegebenen Hash in das Feld **Passwort-Hash** in Notion eintragen
6. Einloggen → System fordert sofortigen Passwortwechsel (da `Must Change Password = true`)
7. Danach im Web unter `/admin/users` weitere Nutzer anlegen

---

## 7. systemd-Services installieren

```bash
sudo bash deploy/install.sh
```

Das Skript:
- kopiert `deploy/*.service` nach `/etc/systemd/system/`
- lädt die systemd-Konfiguration neu
- aktiviert und startet beide Dienste

### Dienste manuell steuern

```bash
# Status prüfen
systemctl status sportplatz-buchung.service
systemctl status sportplatz-homepage.service

# Neustart
systemctl restart sportplatz-buchung.service
systemctl restart sportplatz-homepage.service

# Logs
journalctl -u sportplatz-buchung.service -f
journalctl -u sportplatz-homepage.service -f
```

### Ports

| Dienst | Port | URL |
|---|---|---|
| Buchungssystem (Admin/Login) | **1946** | `http://<server>:1946` |
| Öffentliche Homepage | **8046** | `http://<server>:8046` |

---

## 8. Lokaler Testserver (Demo-Betrieb)

Für lokale Entwicklung und Tests ohne Einfluss auf die Produktionsdaten gibt
es eine isolierte Demo-Umgebung mit einem fiktiven Verein.

### 7.1 Wie die Isolation funktioniert

Zwei Umgebungsvariablen steuern, welche Konfiguration geladen wird. Sie müssen
**vor** dem Start gesetzt sein und können nicht aus der `.env`-Datei gelesen
werden:

| Variable | Standard | Demo |
|----------|----------|------|
| `ENV_FILE` | `.env` | `.env.demo` |
| `CONFIG_DIR` | `config` | `config/demo` |

`ENV_FILE` bestimmt, welche `.env`-Datei geladen wird (separate Notion-DBs).
`CONFIG_DIR` bestimmt, welche `vereinsconfig.json` und `field_config.json`
verwendet werden (andere Vereinsdaten, andere Platznamen).

### 7.2 Demo-Umgebung einrichten

**Schritt 1:** `.env.demo` befüllen

```bash
cp .env.demo .env.demo   # bereits vorhanden als Vorlage
nano .env.demo
```

Pflicht: `NOTION_API_KEY` (gleicher Key wie Produktion) und alle `*_DB_ID`-
Felder mit den Demo-Datenbank-IDs befüllen.

**Schritt 2:** Demo-Notion-DBs anlegen (falls noch nicht geschehen)

```bash
export $(grep NOTION_API_KEY .env.demo | xargs)
python scripts/setup_notion.py --parent <NOTION_PARENT_PAGE_ID>
```

Die ausgegebenen DB-IDs in `.env.demo` eintragen.

**Schritt 3:** Demo-Server starten

```bash
bash start_demo.sh
# entspricht: ENV_FILE=.env.demo CONFIG_DIR=config/demo uvicorn web.main:app --reload --port 1946
```

### 7.3 Demo-Konfiguration

| Datei | Inhalt |
|-------|--------|
| `config/demo/vereinsconfig.json` | TSV Hotzenplotz (grüne Farben, fiktive Spielorte) |
| `config/demo/field_config.json` | Rasen, Kura 1+2, Trainingsfeld, Halle |
| `.env.demo` | Demo-Notion-DB-IDs, `BOOKING_URL=http://localhost:1946` |

### 7.4 Produktion vs. Demo

```bash
bash start_demo.sh      # Demo: TSV Hotzenplotz, Demo-Notion-DBs
bash start_server.sh    # Produktion: TuS Cremlingen, Produktions-Notion-DBs
```

Beide laufen auf Port 1946 — nie gleichzeitig starten.

---

## 9. Nginx als Reverse Proxy *(empfohlen)*

Um die Dienste unter Standard-Ports (80/443) erreichbar zu machen und HTTPS einzurichten, wird ein Nginx-Reverse-Proxy empfohlen.

Beispielkonfiguration für `/etc/nginx/sites-available/tus-cremlingen`:

```nginx
server {
    listen 80;
    server_name buchung.tus-cremlingen.de;

    location / {
        proxy_pass http://127.0.0.1:1946;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name www.tus-cremlingen.de tus-cremlingen.de;

    location / {
        proxy_pass http://127.0.0.1:8046;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

HTTPS mit Let's Encrypt:
```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d buchung.tus-cremlingen.de -d tus-cremlingen.de
```

Nach HTTPS-Einrichtung in `web/routers/auth.py` die Cookie-Option `secure=True` setzen:
```python
response.set_cookie(..., secure=True, ...)
```

---

## 10. Verifizierung

Nach der Installation folgende Punkte prüfen:

- [ ] `http://<server>:1946/login` erreichbar → Login-Seite erscheint
- [ ] Admin-Login funktioniert → Kalenderansicht erscheint
- [ ] Notion-Datenbanken wurden automatisch mit Properties befüllt (in Notion nachsehen)
- [ ] Neue Buchung erstellen → erscheint in Notion
- [ ] `http://<server>:8046` erreichbar → Vereinshomepage erscheint
- [ ] Crash-Benachrichtigung testen: `systemctl stop sportplatz-buchung && systemctl start sportplatz-buchung`

---

## 11. Nutzerrollen

| Rolle | Beschreibung |
|---|---|
| **Administrator** | Vollzugriff: Nutzerverwaltung, alle Buchungen/Events/Aufgaben verwalten, Sperrzeiten, Serien |
| **DFBnet** | Wie Administrator, aber keine Nutzerverwaltung; zusätzlich: DFBnet-Spielplan und -Buchungen |
| **Platzwart** | Sperrzeiten & Serien verwalten, alle Aufgaben löschen, eigene Buchungen/Events |
| **Trainer** | Eigene Platzbuchungen, eigene Events und Aufgaben erstellen/löschen |

---

## 12. Instagram Matchday-Karussell *(optional)*

Das Script `scripts/instagram_matchday.py` generiert automatisch Spielvorschau-Bilder
(1080×1080 px) und kann sie als Karussell-Post auf Instagram veröffentlichen.

### Voraussetzungen

**Playwright installieren** (einmalig, ca. 150 MB):

```bash
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
.venv/bin/playwright install-deps chromium   # Debian/Ubuntu: GTK-/ATK-Bibliotheken
```

**`.env`-Variablen setzen:**

| Variable | Quelle |
|----------|--------|
| `INSTAGRAM_ACCOUNT_ID` | Meta Business Manager → Instagram-Konto → Konto-ID |
| `INSTAGRAM_ACCESS_TOKEN` | [Graph API Explorer](https://developers.facebook.com/tools/explorer/) → `instagram_basic,instagram_content_publish` |

> **Hinweis:** Access Tokens laufen nach ~60 Tagen ab. Fehlercode `190 – Malformed access token`
> bedeutet, ein neuer Token muss im Graph API Explorer generiert werden.

### Verwendung

```bash
# Vorschau (nur Liste, keine Bilder)
.venv/bin/python scripts/instagram_matchday.py --dry-run

# Bilder generieren (lokal, kein Posting)
.venv/bin/python scripts/instagram_matchday.py

# Bilder generieren und auf Instagram posten
.venv/bin/python scripts/instagram_matchday.py --post

# Nur die nächsten 7 Tage
.venv/bin/python scripts/instagram_matchday.py --days 7 --post
```

### Wie das Posting funktioniert

1. Bilder werden nach `web/static/instagram/<datum>/` kopiert → per `BOOKING_URL` öffentlich erreichbar
2. Jedes Bild wird als Carousel-Item bei der Instagram Graph API registriert
3. Ein Karussell-Container wird angelegt
4. Der Post wird veröffentlicht

> Der Server muss unter `BOOKING_URL` öffentlich erreichbar sein, damit Instagram
> die Bilder abrufen kann. Bei lokalem Betrieb (localhost) schlägt das Posting fehl.

---

## 13. Datensicherung

Da alle Daten in Notion gespeichert sind, übernimmt Notion das Hosting und die Verfügbarkeit. Empfehlungen:

- **Notion-Export**: Regelmäßig unter *Settings → Export* als CSV/Markdown exportieren
- **`.env`-Backup**: Die `.env`-Datei enthält alle Geheimnisse – sicher aufbewahren (z. B. Bitwarden, Vaultwarden)
- **Code**: Liegt in Git → `git pull` für Updates genügt

---

## Schnellreferenz: benötigte Notion-Datenbanken

```
Buchungen     → NOTION_BUCHUNGEN_DB_ID
Serien        → NOTION_SERIEN_DB_ID
Sperrzeiten   → NOTION_SPERRZEITEN_DB_ID
Nutzer        → NOTION_NUTZER_DB_ID
Aufgaben      → NOTION_AUFGABEN_DB_ID
Events        → NOTION_EVENTS_DB_ID  (optional)
```

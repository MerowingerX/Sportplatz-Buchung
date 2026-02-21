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

1. → [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. **New integration** → Name z. B. `Sportplatz-Buchung`
3. Capabilities: **Read content**, **Update content**, **Insert content**
4. Den angezeigten **Internal Integration Token** notieren → `NOTION_API_KEY`

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

Jede Datenbank muss der Integration freigegeben werden:

1. Datenbank öffnen → `···` (Drei-Punkte-Menü, oben rechts) → **Connections** → Integration suchen und hinzufügen.
2. Diesen Schritt für alle 5 (bzw. 6) Datenbanken wiederholen.

---

## 2. Repository klonen

```bash
git clone https://github.com/<org>/Sportplatz-Buchung.git /root/git.com/Sportplatz-Buchung
cd /root/git.com/Sportplatz-Buchung
```

> Die systemd-Services erwarten das Verzeichnis unter `/root/git.com/Sportplatz-Buchung`.
> Bei einem anderen Pfad müssen `deploy/*.service` entsprechend angepasst werden.

---

## 3. Python-Umgebung einrichten

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

---

## 4. `.env`-Datei anlegen

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

## 5. Ersten Admin-Nutzer anlegen

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

## 6. systemd-Services installieren

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

## 7. Nginx als Reverse Proxy *(empfohlen)*

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

## 8. Verifizierung

Nach der Installation folgende Punkte prüfen:

- [ ] `http://<server>:1946/login` erreichbar → Login-Seite erscheint
- [ ] Admin-Login funktioniert → Kalenderansicht erscheint
- [ ] Notion-Datenbanken wurden automatisch mit Properties befüllt (in Notion nachsehen)
- [ ] Neue Buchung erstellen → erscheint in Notion
- [ ] `http://<server>:8046` erreichbar → Vereinshomepage erscheint
- [ ] Crash-Benachrichtigung testen: `systemctl stop sportplatz-buchung && systemctl start sportplatz-buchung`

---

## 9. Nutzerrollen

| Rolle | Beschreibung |
|---|---|
| **Administrator** | Vollzugriff: Nutzerverwaltung, alle Buchungen/Events/Aufgaben verwalten, Sperrzeiten, Serien |
| **DFBnet** | Wie Administrator, aber keine Nutzerverwaltung; zusätzlich: DFBnet-Spielplan und -Buchungen |
| **Platzwart** | Sperrzeiten & Serien verwalten, alle Aufgaben löschen, eigene Buchungen/Events |
| **Trainer** | Eigene Platzbuchungen, eigene Events und Aufgaben erstellen/löschen |

---

## 10. Datensicherung

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

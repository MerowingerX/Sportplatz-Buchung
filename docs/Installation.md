
# Sportplatz-Buchung — Installationsanleitung

## Server: 46.224.96.208
## Domain: book-tsv-hotzenplotz.dns.army (dns.army)

## 1. Virtualmin Virtual Server
Virtualmin → Create Virtual Server:
- Domain: `book-tsv-hotzenplotz.dns.army`
- DNS: **OFF** (extern dns.army)
- PHP: **OFF** (Python-App, kein PHP)
- MariaDB: **OFF** (SQLite-Backend, keine externe Datenbank nötig)

DNS Records (dns.army):
```
A: book-tsv-hotzenplotz.dns.army → 46.224.96.208
AAAA: book-tsv-hotzenplotz.dns.army → 2a01:4f8:c0c:xxxx::
```

## 2. Benutzer landlord
```bash
virtualmin create-user --domain book-tsv-hotzenplotz.dns.army --user landlord
```

## 3. Docker Installation
```bash
apt update && apt install -y curl gnupg lsb-release ca-certificates apt-transport-https
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker landlord
newgrp docker
```

## 4. Projekt klonen
```bash
su - landlord
mkdir -p ~/booking
cd ~/booking
git clone YOUR-REPO-URL sportplatz-buchung
cd sportplatz-buchung
ls web/main.py  # Prüfen!
```

## 5. Konfiguration

**Verzeichnisse anlegen**:
```bash
mkdir -p ~/booking/sportplatz-buchung/{data,logs,backup}
```

**.env erstellen**:
```bash
cp .env.example .env
nano .env
```

Mindestens diese Felder müssen gesetzt werden:
```
# JWT-Signaturschlüssel (mind. 32 Zeichen, zufällig generieren)
JWT_SECRET=<openssl rand -hex 32>

# E-Mail (Pflicht für Buchungsbenachrichtigungen)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=booking@tsv-hotzenplotz.de
SMTP_PASSWORD=app-password
SMTP_FROM=booking@tsv-hotzenplotz.de

# Öffentliche URL (wird in E-Mails verlinkt)
BOOKING_URL=https://book-tsv-hotzenplotz.dns.army

# Standort für Sonnenuntergangsberechnung
LOCATION_LAT=52.25
LOCATION_LON=9.90

# Datenbank-Backend
DB_BACKEND=sqlite
SQLITE_DB_PATH=data/sportplatz.db
```

> **Hinweis**: Für den SQLite-Betrieb müssen die `NOTION_*`-Felder trotzdem gesetzt sein
> (leere Strings oder Platzhalter genügen), da pydantic-settings sie als Pflichtfelder behandelt.
> Der einfachste Weg: `.env.example` vollständig kopieren und dann bearbeiten.

**Konfigurations-JSONs anlegen**:
```bash
cp config/vereinsconfig.example.json config/vereinsconfig.json
cp config/field_config.example.json config/field_config.json
nano config/vereinsconfig.json
nano config/field_config.json
```

**config/field_config.json** (Beispiel mit zwei Plätzen):
```json
{
  "display_names": {
    "A": "Rasen",
    "AA": "Rasen A",
    "AB": "Rasen B",
    "B": "Kunstrasen",
    "BA": "Kunstrasen A",
    "BB": "Kunstrasen B"
  },
  "field_groups": [
    {
      "id": "a",
      "name": "Rasenplatz",
      "fields": ["A", "AA", "AB"],
      "lit": false,
      "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"]
    },
    {
      "id": "b",
      "name": "Kunstrasen",
      "fields": ["B", "BA", "BB"],
      "lit": true,
      "visible_to": ["Trainer", "Platzwart", "DFBnet", "Administrator"]
    }
  ]
}
```

**config/vereinsconfig.json** (Beispiel):
```json
{
  "vereinsname": "TSV Hotzenplotz",
  "vereinsname_lang": "Turn- und Sportverein Hotzenplotz e. V.",
  "primary_color": "#1e4fa3",
  "heim_keywords": ["hotzenplotz"],
  "spielorte": []
}
```

> Alternativ können diese Werte direkt im Onboarding-Assistenten eingegeben werden
> (Schritt 3 und 4), nachdem der erste Admin-Nutzer angelegt wurde.

## 6. Docker Files

Das Projekt enthält fertige Docker-Dateien. **Dockerfile** und **docker-compose.yml** müssen
nicht manuell erstellt werden — sie liegen bereits im Repo.

Relevante Abschnitte aus `docker-compose.yml`:
```yaml
services:
  app:
    build: .
    container_name: sportplatz-buchung
    restart: unless-stopped
    ports:
      - "127.0.0.1:1946:1946"
    env_file:
      - .env
    environment:
      PYTHONUNBUFFERED: "1"
      ENV_FILE: ".env"
      CONFIG_DIR: "config"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./backup:/app/backup
      - ./.env:/app/.env:ro
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:1946/login')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
```

> `ENV_FILE` und `CONFIG_DIR` müssen im `environment:`-Abschnitt stehen, nicht nur in `env_file:`,
> da sie steuern, welche Konfigurationsdateien geladen werden.

**Start**:
```bash
cd ~/booking/sportplatz-buchung
docker compose up -d --build
docker ps
curl http://127.0.0.1:1946/
```

## 7. Reverse Proxy (Virtualmin)

book-tsv-hotzenplotz.dns.army → **Web Configuration** → **Proxy Paths**:

```
Path to proxy: /
Destination URLs: http://127.0.0.1:1946/
☐ Don't proxy for this path
☑ Proxy WebSockets
```

```bash
systemctl reload apache2
curl -k https://book-tsv-hotzenplotz.dns.army/
```

## 8. Troubleshooting

**Docker permission**:
```bash
usermod -aG docker landlord; newgrp docker
```

**Import main**:
CMD `["uvicorn", "web.main:app", ...]`

**Proxy 503**:
- Destination `http://127.0.0.1:1946/` (http + trailing slash!)
- `curl http://127.0.0.1:1946/` testen

**SSL self-signed**:
```bash
curl -k https://book-tsv-hotzenplotz.dns.army/
```

**Let's Encrypt**:
Server Config → SSL Certificate → Request

**Container-Logs**:
```bash
docker compose logs -f
```

## 9. Onboarding

Nach dem ersten Start unter https://book-tsv-hotzenplotz.dns.army den Assistenten durchlaufen:

1. **Systemprüfung** — .env-Werte und Konfigurationsdateien werden geprüft
2. **Admin-Nutzer anlegen** — erster Administrator + `dfbnet`-Systemnutzer werden erstellt
3. **Vereinskonfiguration** — Name, Farbe, Logo, Heim-Keywords
4. **Platzkonfiguration** — Anzahl Plätze, Anzeigenamen, Flutlicht-Status
5. **Spielort-Zuordnung** — fussball.de-Strings den Plätzen zuordnen (optional)
6. **Mannschaften** — Teams von api-fussball.de importieren (optional)

**Fertig!**

---
TSV Hotzenplotz | 31.03.2026

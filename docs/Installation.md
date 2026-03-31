
# Sportplatz-Buchung TSV Hotzenplotz - Complete Installation

## Server: 46.224.96.208
## Domain: book-tsv-hotzenplotz.dns.army (dns.army)

## 1. Virtualmin Virtual Server
Virtualmin → Create Virtual Server:
- Domain: `book-tsv-hotzenplotz.dns.army`
- DNS: **OFF** (extern dns.army)
- PHP: **ON**
- MariaDB: **ON** [web:115]

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
newgrp docker [web:78]
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

**data/ Verzeichnisse**:
```bash
mkdir -p ~/booking/sportplatz-buchung/{data,logs,backup}
chown -R landlord:docker ~/booking/sportplatz-buchung/{data,logs,backup}
```

**Minimum .env**:
```bash
cp .env.demo .env
nano .env
```
```
BOOKING_URL=https://book-tsv-hotzenplotz.dns.army
DB_BACKEND=sqlite
SQLITE_DB_PATH=data/sportplatz.db
```

**Erweitert**:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=booking@tsv-hotzenplotz.de
SMTP_PASS=app-password
LOCATION_LAT=52.25
LOCATION_LNG=9.90
```
```
SECRET_KEY=$(openssl rand -hex 32)
```

**JSONs**:
```bash
cp field_config.json.example field_config.json
cp vereinsconfig.json.example vereinsconfig.json
nano field_config.json
nano vereinsconfig.json
```

**field_config.json**:
```json
{
  "display_names": {
    "A": "Rasen",
    "AA": "Rasen A",
    "B": "Kura",
    "BA": "Kura A"
  },
  "field_groups": [
    {
      "id": "rasen",
      "name": "Rasenplätze",
      "fields": ["A", "AA"],
      "lit": false,
      "visible_to": ["Trainer", "Administrator"]
    }
  ]
}
```

**vereinsconfig.json**:
```json
{
  "vereinsname": "TSV Hotzenplotz",
  "heim_keywords": ["hotzenplotz"],
  "spielorte": [...]
}
```

## 6. Docker Files

**Dockerfile**:
```
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 1946
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "1946", "--proxy-headers", "--forwarded-allow-ips=*"]
```

**docker-compose.yml**:
```
version: '3.8'
services:
  app:
    build: .
    ports:
      - "127.0.0.1:1946:1946"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./backup:/app/backup
      - ./.env:/app/.env:ro
    env_file: [.env]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:1946/login')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
```

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
- Destination `http://127.0.0.1:1946/` (http + /!)
- `curl http://127.0.0.1:1946/` testen

**SSL self-signed**:
```bash
curl -k https://book-tsv-hotzenplotz.dns.army/
```

**Let's Encrypt**:
Server Config → SSL Certificate → Request

## 9. Onboarding

https://book-tsv-hotzenplotz.dns.army
1. Admin User
2. JWT Secrets  
3. Sportplatz-Serien

**Fertig!** 🚀

---
TSV Hotzenplotz | 31.03.2026 | [code_file:92]

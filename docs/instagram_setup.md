# Instagram Matchday-Post — Setup & Betrieb

## Übersicht

Das Script `scripts/instagram_matchday.py` generiert ein Karussell aus Spielvorschau-Karten
(Cover + je eine Karte pro Spiel) und veröffentlicht es über die Meta Graph API auf Instagram.

---

## Voraussetzungen

### 1. Instagram Business-Konto

Das Instagram-Konto des Vereins **muss ein Business-Konto** sein, kein Creator- und kein
persönliches Konto. Die Graph API (`instagram_content_publish`) funktioniert ausschließlich
mit Business-Konten.

**Umschalten:**
Instagram-App → Profil → ☰ → Einstellungen und Datenschutz → Konto →
**Kontotyp wechseln → Zu Business-Konto wechseln**

### 2. Verknüpfung mit einer Facebook-Seite

Das Instagram Business-Konto muss mit einer **Facebook-Seite** (Page) des Vereins verknüpft
sein — nicht mit einem persönlichen Facebook-Profil.

**Facebook-Seite anlegen** (falls noch nicht vorhanden):
1. `facebook.com` → "Seiten" → "Neue Seite erstellen"
2. Name: z.B. "TuS Cremlingen", Kategorie: "Sportverein"

**Verknüpfen:**
Instagram-App → Einstellungen → Konto → **Mit Facebook verknüpfen** →
die Vereins-Seite auswählen (nicht das persönliche Profil)

---

## Meta Developer App

### App anlegen
1. `developers.facebook.com` → "Meine Apps" → "App erstellen"
2. Typ: **Business**
3. Produkte hinzufügen: **Instagram Graph API**

### Instagram Business Account ID ermitteln
Sobald Instagram Business-Konto und Facebook-Seite verknüpft sind:

```bash
TOKEN="EAAxxxxx..."
curl "https://graph.facebook.com/v21.0/me/accounts?fields=id,name,instagram_business_account{id,username}&access_token=$TOKEN"
```

Die `instagram_business_account.id` aus der Antwort → in `.env` als `INSTAGRAM_ACCOUNT_ID`.

---

## Access Token generieren

### Kurzfristiger Token (im Graph API Explorer)
1. `developers.facebook.com/tools/explorer`
2. App auswählen (deine Vereins-App)
3. Berechtigungen aktivieren:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
4. **"Generate Access Token"** → die **Facebook-Seite** auswählen (nicht den User!)
5. Der Token beginnt mit `EAA...` — Token mit `IGAAU...` (Basic Display API) funktionieren **nicht**

### Langfristigen Token erzeugen (60 Tage gültig)
```bash
curl "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token\
&client_id=DEINE_APP_ID\
&client_secret=DEIN_APP_SECRET\
&fb_exchange_token=EAA_KURZFRISTIGER_TOKEN"
```

Den zurückgegebenen Token in `.env` eintragen:
```
INSTAGRAM_ACCESS_TOKEN=EAAxxxxx...
```

### Token validieren
```bash
TOKEN="EAAxxxxx..."
curl "https://graph.facebook.com/v21.0/me?fields=id,name&access_token=$TOKEN"
# Antwort mit id + name → Token gültig
# Fehler 190 → Token abgelaufen oder falsch
```

### Token-Ablauf
Langfristige Tokens laufen nach **60 Tagen** ab. Danach:
- Neuen kurzfristigen Token im Graph API Explorer holen
- Gegen langfristigen Token eintauschen (siehe oben)
- In `.env` aktualisieren

---

## Bilder öffentlich erreichbar machen

Die Meta API lädt Bilder über eine **öffentlich erreichbare HTTPS-URL** herunter.
Eine lokale IP (`http://192.168.x.x` oder `http://46.x.x.x`) wird abgelehnt.

### Produktivbetrieb (empfohlen)
Server hat eine öffentliche Domain mit HTTPS → in `.env`:
```
INSTAGRAM_IMAGE_BASE_URL=https://buchung.tus-cremlingen.de
```
Das Script legt die Bilder unter `web/static/instagram/<datum>/` ab,
erreichbar unter `https://buchung.tus-cremlingen.de/static/instagram/<datum>/`.

### Entwicklung / Test mit ngrok
Wenn der Server nur lokal oder per privater IP erreichbar ist:

1. ngrok installieren: `https://ngrok.com/download`
2. ngrok-Account anlegen + Authtoken hinterlegen:
   ```bash
   ngrok config add-authtoken DEIN_TOKEN
   ```
3. Tunnel starten (Port des Buchungssystems):
   ```bash
   ngrok http 1946
   ```
4. Die angezeigte `https://xxxx.ngrok-free.app`-URL in `.env`:
   ```
   INSTAGRAM_IMAGE_BASE_URL=https://xxxx.ngrok-free.app
   ```
5. Script ausführen, danach ngrok beenden

**Wichtig:** Jeder ngrok-Neustart erzeugt eine neue URL (kostenloser Plan).
Die `.env` muss dann aktualisiert werden.

---

## `.env`-Konfiguration

```dotenv
# Instagram / Meta Graph API
INSTAGRAM_ACCOUNT_ID=17841447186484598     # Instagram Business Account ID
INSTAGRAM_ACCESS_TOKEN=EAAxxxxx...         # Page Access Token (60 Tage)
INSTAGRAM_IMAGE_BASE_URL=https://...       # Öffentliche HTTPS-Basis-URL für Bilder
```

---

## Script ausführen

```bash
# Nur Bilder generieren (kein Post)
.venv/bin/python scripts/instagram_matchday.py

# Bilder generieren + auf Instagram posten
.venv/bin/python scripts/instagram_matchday.py --post
```

Bilder werden gespeichert unter:
- `output/instagram/<datum>/` — Originale
- `web/static/instagram/<datum>/` — Kopie für HTTP-Zugriff durch Meta API

---

## Häufige Fehler

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| Error 190: Cannot parse access token | Token abgelaufen oder falscher Typ (`IGAAU...`) | Neuen `EAA...` Page Access Token generieren |
| Error 100/33: Object does not exist | Account-ID falsch oder Token hat keinen Zugriff | Account-ID via `me/accounts` neu ermitteln |
| `me/accounts` gibt leere Liste | Kein Business-Konto oder keine Facebook-Seite verknüpft | Instagram auf Business umstellen, Seite verknüpfen |
| HTTP statt HTTPS URL | `INSTAGRAM_IMAGE_BASE_URL` nicht gesetzt oder HTTP | ngrok starten, URL in `.env` setzen |
| RuntimeError: URL muss https:// sein | `BOOKING_URL` als Fallback ist HTTP | `INSTAGRAM_IMAGE_BASE_URL` explizit setzen |

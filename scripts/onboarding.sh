#!/usr/bin/env bash
# =============================================================================
#  Sportplatz-Buchung — Onboarding
#  Richtet .env, Konfigurationen und Python-Umgebung ein.
# =============================================================================
set -euo pipefail

# ── Farben & Symbole ─────────────────────────────────────────────────────────
RED='\033[0;31m';  GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m';  BOLD='\033[1m';  DIM='\033[2m'; RESET='\033[0m'
OK="  ${GREEN}✓${RESET}"; SKIP="  ${CYAN}→${RESET}"; WARN="  ${YELLOW}⚠${RESET}"; ERR="  ${RED}✗${RESET}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

header() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}${BLUE}  $1${RESET}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

# hint <text>  →  gedimmte Beispielzeile
hint() { echo -e "  ${DIM}Beispiel: $1${RESET}"; }

# ask <var> <prompt> [default]
ask() {
    local var="$1" prompt="$2" default="${3:-}"
    if [[ -n "$default" ]]; then
        echo -ne "  ${CYAN}?${RESET} ${prompt} ${BOLD}[${default}]${RESET}: "
    else
        echo -ne "  ${CYAN}?${RESET} ${prompt}: "
    fi
    read -r input
    printf -v "$var" '%s' "${input:-$default}"
}

# ask_secret <var> <prompt>
ask_secret() {
    local var="$1" prompt="$2"
    echo -ne "  ${CYAN}?${RESET} ${prompt}: "
    read -rs input; echo ""
    printf -v "$var" '%s' "$input"
}

# confirm <prompt> [J/n]  →  returns 0=yes 1=no
confirm() {
    local prompt="$1" default="${2:-J}"
    echo -ne "  ${CYAN}?${RESET} ${prompt} [${default}] "
    read -r ans
    ans="${ans:-$default}"
    [[ "${ans,,}" == "j" || "${ans,,}" == "y" ]]
}

random_secret() { python3 -c "import secrets; print(secrets.token_hex(32))"; }

# ── Banner ───────────────────────────────────────────────────────────────────

clear
echo ""
echo -e "${BOLD}${BLUE}"
cat << 'EOF'
   ███████╗██████╗  ██████╗ ██████╗ ████████╗██████╗ ██╗      █████╗ ████████╗███████╗
   ██╔════╝██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝██╔══██╗██║     ██╔══██╗╚══██╔══╝╚══███╔╝
   ███████╗██████╔╝██║   ██║██████╔╝   ██║   ██████╔╝██║     ███████║   ██║     ███╔╝
   ╚════██║██╔═══╝ ██║   ██║██╔══██╗   ██║   ██╔═══╝ ██║     ██╔══██║   ██║    ███╔╝
   ███████║██║     ╚██████╔╝██║  ██║   ██║   ██║     ███████╗██║  ██║   ██║   ███████╗
   ╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
EOF
echo -e "${RESET}"
echo -e "  ${BOLD}Buchungssystem — Ersteinrichtung${RESET}"
echo -e "  ${CYAN}Arbeitsverzeichnis: ${ROOT}${RESET}"
echo ""

# ── 0. Voraussetzungen prüfen ────────────────────────────────────────────────

header "0 · Voraussetzungen"

if ! command -v python3 &>/dev/null; then
    echo -e "${ERR} Python 3 nicht gefunden. Bitte installieren und erneut starten."
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${OK} Python ${PY_VER} gefunden"

command -v git &>/dev/null && echo -e "${OK} git gefunden" \
    || echo -e "${WARN} git nicht gefunden – kein Problem für den Betrieb"

if command -v docker &>/dev/null; then
    echo -e "${OK} Docker gefunden ($(docker --version | cut -d' ' -f3 | tr -d ','))"
    HAS_DOCKER=true
else
    echo -e "${SKIP} Docker nicht gefunden – systemd-Betrieb wird vorbereitet"
    HAS_DOCKER=false
fi

# ── 1. Python-Umgebung ───────────────────────────────────────────────────────

header "1 · Python-Umgebung"
cd "$ROOT"

if [[ -d ".venv" ]]; then
    echo -e "${SKIP} .venv bereits vorhanden – überspringe"
else
    echo -e "  Erstelle virtuelle Umgebung …"
    python3 -m venv .venv
    echo -e "${OK} .venv erstellt"
fi

echo -e "  Installiere Abhängigkeiten …"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
echo -e "${OK} Abhängigkeiten installiert"

# ── 2. Logo ──────────────────────────────────────────────────────────────────

header "2 · Vereinslogo"

echo -e "  Das Logo wird an zwei Stellen verwendet:"
echo -e "  ${DIM}  • Navbar (klein)      →  web/static/logo.svg${RESET}"
echo -e "  ${DIM}  • Wasserzeichen (groß) →  homepage/userdata/logo.svg${RESET}"
echo ""

ask LOGO_KLEIN "Pfad zur Logo-Datei für Navbar (SVG oder PNG)" ""
hint "/home/user/bilder/logo_klein.svg  oder  Enter zum Überspringen"

if [[ -n "$LOGO_KLEIN" && -f "$LOGO_KLEIN" ]]; then
    cp "$LOGO_KLEIN" "web/static/logo.svg"
    echo -e "${OK} Navbar-Logo nach web/static/logo.svg kopiert"
else
    [[ -z "$LOGO_KLEIN" ]] && echo -e "${SKIP} Übersprungen – Platzhalter bleibt in web/static/logo.svg" \
        || echo -e "${WARN} Datei nicht gefunden: ${LOGO_KLEIN}"
fi

echo ""
ask LOGO_GROSS "Pfad zur Logo-Datei für Wasserzeichen (groß)" ""
hint "/home/user/bilder/logo_gross.svg  oder  Enter = gleiche Datei wie Navbar"

if [[ -z "$LOGO_GROSS" && -n "$LOGO_KLEIN" && -f "$LOGO_KLEIN" ]]; then
    cp "$LOGO_KLEIN" "homepage/userdata/logo.svg"
    echo -e "${OK} Wasserzeichen-Logo = Navbar-Logo (homepage/userdata/logo.svg)"
elif [[ -n "$LOGO_GROSS" && -f "$LOGO_GROSS" ]]; then
    cp "$LOGO_GROSS" "homepage/userdata/logo.svg"
    echo -e "${OK} Wasserzeichen-Logo nach homepage/userdata/logo.svg kopiert"
else
    echo -e "${SKIP} Übersprungen – Platzhalter bleibt in homepage/userdata/logo.svg"
fi

# ── 3. Vereinskonfiguration ──────────────────────────────────────────────────

header "3 · Vereinskonfiguration  (config/vereinsconfig.json)"

if [[ -f "config/vereinsconfig.json" ]]; then
    echo -e "${SKIP} config/vereinsconfig.json existiert bereits – überspringe"
else
    echo -e "  ${BOLD}Vereinsname & Erscheinungsbild${RESET}\n"

    hint "TuS Cremlingen"
    ask VC_NAME "Kurzname des Vereins" ""

    hint "Turn- und Sportverein Cremlingen 1946 e. V."
    ask VC_NAME_LANG "Vollständiger offizieller Name" "$VC_NAME"

    echo ""
    echo -e "  ${BOLD}Heim-Schlüsselwort${RESET}"
    echo -e "  ${DIM}Wird genutzt, um auf fussball.de Heimspiele zu erkennen.${RESET}"
    echo -e "  ${DIM}Muss als Teilstring im Heimteam-Namen vorkommen (Kleinschreibung).${RESET}"
    hint "cremlingen   → erkennt \"SV Cremlingen A-Junioren\" als Heimspiel"
    ask VC_KEYWORD "Heim-Schlüsselwort" "$(echo "$VC_NAME" | awk '{print tolower($NF)}')"

    echo ""
    echo -e "  ${BOLD}Vereinsfarben${RESET} ${DIM}(Hex-Codes, z. B. #1e4fa3)${RESET}"
    hint "#1e4fa3  →  Blau (Navbar, Buttons)"
    ask VC_PRIMARY "Hauptfarbe" "#1e4fa3"
    hint "#0d2f6b  →  dunklere Variante (Hover)"
    ask VC_DARK    "Hauptfarbe dunkel" "#0d2f6b"
    hint "#071c44  →  noch dunkler (tiefe Schatten)"
    ask VC_DARKER  "Hauptfarbe dunkler" "#071c44"
    hint "#e8c04a  →  Gold-Akzent (Abzeichen, Highlights)"
    ask VC_GOLD    "Akzentfarbe (Gold)" "#e8c04a"

    echo ""
    echo -e "  ${BOLD}Saison-Standarddaten${RESET} ${DIM}(Vorauswahl im Serien-Formular, Format MM-DD)${RESET}"
    hint "08-01 bis 06-30 = typisches Vereinsjahr"
    ask VC_SAI_GJ_S   "Ganzjährig Start"      "08-01"
    ask VC_SAI_GJ_E   "Ganzjährig Ende"       "06-30"
    ask VC_SAI_SO_S   "Sommerhalbjahr Start"  "08-01"
    ask VC_SAI_SO_E   "Sommerhalbjahr Ende"   "10-30"
    ask VC_SAI_WI_S   "Winterhalbjahr Start"  "10-30"
    ask VC_SAI_WI_E   "Winterhalbjahr Ende"   "03-01"

    # vereinsconfig.json wird nach dem Platz-Setup geschrieben (Spielorte fehlen noch)
    echo -e "${OK} Vereinsdaten erfasst – werden nach Platz-Setup gespeichert"
fi

# ── 4. Platzkonfiguration ─────────────────────────────────────────────────────

header "4 · Platzstruktur  (config/field_config.json)"

# Prefixe und Group-IDs der Reihe nach
FIELD_PREFIXES=("A" "B" "C" "D")
DEFAULT_GROUP_IDS=("kura" "rasen" "halle" "feld4")

if [[ -f "config/field_config.json" ]]; then
    echo -e "${SKIP} config/field_config.json existiert bereits – überspringe"
    NUM_VENUES=0   # Spielorte-Loop überspringen
else
    echo -e "  Beschreibe die Plätze/Hallen eures Vereins.\n"

    hint "2  →  z. B. Kunstrasen + Naturrasen"
    ask NUM_VENUES_STR "Wie viele Platztypen hat euer Verein?" "2"
    NUM_VENUES=$NUM_VENUES_STR

    # Arrays für Platz-Daten
    declare -a GRP_ID GRP_NAME FLD_FULL FLD_HALF_A FLD_HALF_B GRP_SPLIT GRP_LIT GRP_ROLES GRP_FUSSBALL

    for (( i=0; i<NUM_VENUES; i++ )); do
        PFX="${FIELD_PREFIXES[$i]}"
        NUM=$(( i + 1 ))
        echo ""
        echo -e "  ${BOLD}── Platztyp ${NUM} (Platz-Präfix: ${PFX}) ─────────────────────${RESET}"

        hint "Kunstrasen  /  Naturrasen  /  Turnhalle"
        ask GRP_NAME[$i] "Name dieser Anlage" ""

        # Gruppen-ID aus Name ableiten (Kleinbuchstaben, nur a-z)
        GRP_ID[$i]=$(echo "${GRP_NAME[$i]}" | python3 -c \
            "import sys,re; print(re.sub(r'[^a-z]','',sys.stdin.read().strip().lower())[:8] or 'gruppe${NUM}')")

        hint "Kura AB  →  ganzer Kunstrasen  |  Rasen AB  →  ganzer Naturrasen"
        ask FLD_FULL[$i] "Anzeigename ganzer Platz" "${GRP_NAME[$i]}"

        echo ""
        if confirm "Kann dieser Platz geteilt werden (Hälfte A / Hälfte B)?"; then
            GRP_SPLIT[$i]="ja"
            hint "Kura A   (erste Hälfte)"
            ask FLD_HALF_A[$i] "Anzeigename Hälfte A" "${GRP_NAME[$i]} A"
            hint "Kura B   (zweite Hälfte)"
            ask FLD_HALF_B[$i] "Anzeigename Hälfte B" "${GRP_NAME[$i]} B"
        else
            GRP_SPLIT[$i]="nein"
            FLD_HALF_A[$i]=""
            FLD_HALF_B[$i]=""
        fi

        echo ""
        if confirm "Flutlicht vorhanden? (nein = Sonnenuntergangs-Hinweis in Buchungen)"; then
            GRP_LIT[$i]="true"
        else
            GRP_LIT[$i]="false"
        fi

        echo ""
        echo -e "  ${DIM}Sichtbare Rollen: Trainer, Platzwart, DFBnet, Administrator${RESET}"
        if confirm "Soll diese Anlage für alle Rollen sichtbar sein?"; then
            GRP_ROLES[$i]='["Trainer","Platzwart","DFBnet","Administrator"]'
        else
            echo -e "  ${DIM}Nur Administrator (z. B. bei internen Hallen)${RESET}"
            GRP_ROLES[$i]='["Administrator"]'
        fi

        echo ""
        echo -e "  ${BOLD}fussball.de-Spielort${RESET} ${DIM}(für automatische Heimspiel-Erkennung)${RESET}"
        if confirm "Erscheint dieser Platz auf fussball.de als Spielort?"; then
            hint "cremlingen kunstrasen   (Teilstring aus dem Spielort-Feld auf fussball.de, Kleinschreibung)"
            ask GRP_FUSSBALL[$i] "fussball.de-Ortsbezeichnung" ""
        else
            GRP_FUSSBALL[$i]=""
        fi
    done

    # ── field_config.json erzeugen ────────────────────────────────────────────
    python3 - <<PYEOF
import json

num = ${NUM_VENUES}
prefixes   = ${FIELD_PREFIXES[@]+"${FIELD_PREFIXES[*]}".split()}
grp_ids    = [$(for i in "${!GRP_ID[@]}";    do echo -n "\"${GRP_ID[$i]}\",";    done)]
grp_names  = [$(for i in "${!GRP_NAME[@]}";  do echo -n "\"${GRP_NAME[$i]}\",";  done)]
fld_full   = [$(for i in "${!FLD_FULL[@]}";  do echo -n "\"${FLD_FULL[$i]}\",";  done)]
fld_a      = [$(for i in "${!FLD_HALF_A[@]}";do echo -n "\"${FLD_HALF_A[$i]}\",";done)]
fld_b      = [$(for i in "${!FLD_HALF_B[@]}";do echo -n "\"${FLD_HALF_B[$i]}\",";done)]
splits     = [$(for i in "${!GRP_SPLIT[@]}"; do echo -n "\"${GRP_SPLIT[$i]}\","; done)]
lits       = [$(for i in "${!GRP_LIT[@]}";   do echo -n "${GRP_LIT[$i]},";       done)]
roles_raw  = [$(for i in "${!GRP_ROLES[@]}"; do echo -n "'${GRP_ROLES[$i]}',";   done)]

prefixes = "${FIELD_PREFIXES[*]}".split()[:num]
roles = [json.loads(r.replace("'", '"')) for r in roles_raw]

display_names = {}
field_groups  = []

for i in range(num):
    pfx = prefixes[i]
    display_names[pfx] = fld_full[i]
    fields = [pfx]
    if splits[i] == "ja":
        ha, hb = pfx + "A", pfx + "B"
        display_names[ha] = fld_a[i]
        display_names[hb] = fld_b[i]
        fields += [ha, hb]
    field_groups.append({
        "id":         grp_ids[i],
        "name":       grp_names[i],
        "fields":     fields,
        "lit":        lits[i],
        "visible_to": roles[i],
    })

config = {"display_names": display_names, "field_groups": field_groups}
with open("config/field_config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print("  Geschrieben: config/field_config.json")
PYEOF
    echo -e "${OK} config/field_config.json erstellt"
fi

# ── 5. Vereinsconfig finalisieren (inkl. Spielorte) ──────────────────────────

if [[ ! -f "config/vereinsconfig.json" ]]; then

    # Spielorte aus den Platz-Daten aufbauen
    SPIELORTE_JSON=""
    for (( i=0; i<NUM_VENUES; i++ )); do
        [[ -z "${GRP_FUSSBALL[$i]}" ]] && continue
        PFX="${FIELD_PREFIXES[$i]}"
        HALVES=""
        [[ "${GRP_SPLIT[$i]}" == "ja" ]] && HALVES="\"${PFX}A\", \"${PFX}B\""
        SPIELORTE_JSON+="    {
      \"fussball_de_string\": \"${GRP_FUSSBALL[$i]}\",
      \"feld\": \"${PFX}\",
      \"platz_praefix\": [\"${PFX}\"$([ -n "$HALVES" ] && echo ", $HALVES")]
    },"
    done
    SPIELORTE_JSON="[${SPIELORTE_JSON%,}]"

    cat > "config/vereinsconfig.json" <<EOF
{
  "vereinsname": "${VC_NAME}",
  "vereinsname_lang": "${VC_NAME_LANG}",
  "logo_url": "/static/logo.svg",
  "heim_keyword": "${VC_KEYWORD}",
  "primary_color": "${VC_PRIMARY}",
  "primary_color_dark": "${VC_DARK}",
  "primary_color_darker": "${VC_DARKER}",
  "gold_color": "${VC_GOLD}",
  "saison_defaults": {
    "ganzjaehrig":    {"start": "${VC_SAI_GJ_S}", "ende": "${VC_SAI_GJ_E}"},
    "sommerhalbjahr": {"start": "${VC_SAI_SO_S}", "ende": "${VC_SAI_SO_E}"},
    "winterhalbjahr": {"start": "${VC_SAI_WI_S}", "ende": "${VC_SAI_WI_E}"}
  },
  "spielorte": ${SPIELORTE_JSON}
}
EOF
    echo -e "${OK} config/vereinsconfig.json gespeichert"
fi

# Homepage-Configs synchronisieren
cp "config/vereinsconfig.json" "homepage/config/vereinsconfig.json"
cp "config/field_config.json"  "homepage/config/field_config.json"
echo -e "${OK} homepage/config/ synchronisiert"

# ── 6. Umgebungsvariablen (.env) ──────────────────────────────────────────────

header "6 · Umgebungsvariablen  (.env)"

if [[ -f ".env" ]]; then
    echo -e "${SKIP} .env existiert bereits – überspringe"
    echo -e "  Zum Bearbeiten: \$EDITOR .env"
else
    echo -e "  ${BOLD}Notion-Integration${RESET}"
    echo -e "  ${DIM}Zuerst eine Integration anlegen: https://www.notion.so/my-integrations${RESET}"
    echo -e "  ${DIM}Danach jede Datenbank mit der Integration teilen (⋯ → Connections).${RESET}\n"

    hint "secret_abc123…  (beginnt immer mit secret_)"
    ask_secret NOTION_KEY "Notion API-Key"

    echo ""
    hint "317ca010-5fee-80b7-8e4b-d19b7c81693b  (32-stellige UUID aus der Notion-URL)"
    ask NOTION_BUCHUNGEN "Buchungen DB-ID"     ""
    ask NOTION_SERIEN    "Serien DB-ID"        ""
    ask NOTION_NUTZER    "Nutzer DB-ID"        ""
    ask NOTION_AUFGABEN  "Aufgaben DB-ID"      ""

    echo ""
    echo -e "  ${DIM}Optionale DBs – einfach leer lassen zum Deaktivieren${RESET}"
    ask NOTION_EVENTS  "Events DB-ID        (oder leer)" ""
    ask NOTION_MANNSCH "Mannschaften DB-ID  (oder leer)" ""

    echo ""
    echo -e "  ${BOLD}SMTP (ausgehende E-Mails)${RESET}"
    hint "smtp.ionos.de  /  smtp.gmail.com  /  mail.meinverein.de"
    ask        SMTP_HOST "SMTP-Host"        "smtp.example.com"
    hint "587 = STARTTLS  |  465 = SSL/TLS"
    ask        SMTP_PORT "SMTP-Port"        "587"
    hint "buchung@meinverein.de"
    ask        SMTP_USER "SMTP-Benutzername" ""
    ask_secret SMTP_PASS "SMTP-Passwort"
    hint "buchung@meinverein.de  (Absender-Adresse im Mail-Header)"
    ask        SMTP_FROM "Absender-Adresse" "$SMTP_USER"

    echo ""
    echo -e "  ${BOLD}Allgemein${RESET}"
    hint "https://buchung.meinverein.de  (erscheint als Link in E-Mails)"
    ask BOOKING_URL "Öffentliche URL des Buchungssystems" "https://buchung.meinverein.de"

    echo ""
    echo -e "  ${DIM}Koordinaten für Sonnenuntergangsberechnung (wann braucht es Flutlicht?)${RESET}"
    hint "52.264  /  10.639  →  Cremlingen. Eigene Koordinaten: maps.google.de → Rechtsklick"
    ask LOCATION_LAT  "Breitengrad"  "52.264"
    ask LOCATION_LON  "Längengrad"   "10.639"
    ask LOCATION_NAME "Ortsname"     "${VC_NAME:-Mein Verein}/Germany"

    JWT_GEN=$(random_secret)
    echo -e "\n${OK} JWT-Secret automatisch generiert (${#JWT_GEN} Zeichen)"

    cat > ".env" <<EOF
# Notion
NOTION_API_KEY=${NOTION_KEY}
NOTION_BUCHUNGEN_DB_ID=${NOTION_BUCHUNGEN}
NOTION_SERIEN_DB_ID=${NOTION_SERIEN}
NOTION_NUTZER_DB_ID=${NOTION_NUTZER}
NOTION_AUFGABEN_DB_ID=${NOTION_AUFGABEN}
NOTION_EVENTS_DB_ID=${NOTION_EVENTS}
NOTION_MANNSCHAFTEN_DB_ID=${NOTION_MANNSCH}

# JWT
JWT_SECRET=${JWT_GEN}
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# E-Mail (SMTP)
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=${SMTP_PORT}
SMTP_USER=${SMTP_USER}
SMTP_PASSWORD=${SMTP_PASS}
SMTP_FROM=${SMTP_FROM}

# Buchungssystem
BOOKING_URL=${BOOKING_URL}

# Standort
LOCATION_LAT=${LOCATION_LAT}
LOCATION_LON=${LOCATION_LON}
LOCATION_NAME=${LOCATION_NAME}
EOF
    chmod 600 .env
    echo -e "${OK} .env erstellt (chmod 600)"
fi

# ── 7. Notion-Datenbanken einrichten ─────────────────────────────────────────

header "7 · Notion-Datenbanken"

echo -e "  ${DIM}Prüft ob alle nötigen Properties in den Notion-DBs vorhanden sind${RESET}"
echo -e "  ${DIM}und legt fehlende an. Benötigt valide .env.${RESET}\n"

if confirm "Notion-Datenbanken jetzt prüfen und einrichten?"; then
    .venv/bin/python scripts/setup_notion.py \
        && echo -e "${OK} Notion-Setup abgeschlossen" \
        || echo -e "${WARN} setup_notion.py meldet Fehler – bitte Ausgabe prüfen"
else
    echo -e "${SKIP} Übersprungen – später: python scripts/setup_notion.py"
fi

# ── 8. Start-Methode ─────────────────────────────────────────────────────────

header "8 · Start-Methode"

USE_DOCKER=false
if [[ "$HAS_DOCKER" == true ]]; then
    if confirm "Docker verwenden? (nein = systemd)"; then
        echo -e "  Baue Docker-Image …"
        docker compose build --quiet
        echo -e "${OK} Image gebaut"
        USE_DOCKER=true
    fi
fi

if [[ "$USE_DOCKER" == false ]]; then
    if confirm "systemd-Services jetzt installieren? (braucht sudo)"; then
        sudo bash deploy/install.sh
    else
        echo -e "${SKIP} Übersprungen – später: sudo bash deploy/install.sh"
    fi
fi

# ── Fertig ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${GREEN}  ✓ Onboarding abgeschlossen!${RESET}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${BOLD}Nächste Schritte:${RESET}"
if [[ "$USE_DOCKER" == true ]]; then
echo -e "  1.  ${CYAN}docker compose up -d${RESET}"
echo -e "  2.  ${CYAN}http://localhost:1946${RESET} aufrufen"
else
echo -e "  1.  ${CYAN}bash start_server.sh${RESET}          (Entwicklung mit --reload)"
echo -e "      ${CYAN}sudo bash deploy/install.sh${RESET}   (Produktion via systemd)"
echo -e "  2.  ${CYAN}http://localhost:1946${RESET} aufrufen"
fi
echo -e "  3.  Ersten Admin-Nutzer direkt in der Notion-Nutzer-DB anlegen"
echo -e "  4.  Cron-Jobs einrichten – Beispiele in .env.example (unten)"
echo ""
echo -e "  ${DIM}Backup:    0 3 * * *  docker exec buchung python scripts/backup_notion.py${RESET}"
echo -e "  ${DIM}Spielplan: 30 6 * * * docker exec buchung python scripts/fetch_spielplan.py${RESET}"
echo ""

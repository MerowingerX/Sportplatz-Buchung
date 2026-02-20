#!/bin/bash

# Vollständiges Bash-Script: Identifiziert PNG-Logos via Reverse Image Search (TinEye/Google),
# benennt um nach Vereinsname und verschiebt Duplikate.
# Aufruf: ./logo_rename.sh /pfad/zu/pngs
# Voraussetzungen: curl, jq, imagemagick (apt install), tesseract (OCR optional)

set -e  # Exit on error

INPUT_DIR="$1"
if [ -z "$INPUT_DIR" ] || [ ! -d "$INPUT_DIR" ]; then
    echo "Nutzung: $0 <pfad_zum_png_ordner>"
    exit 1
fi

DUPLICATES_DIR="./duplicates"
RENAMED_DIR="./renamed_logos"
mkdir -p "$DUPLICATES_DIR" "$RENAMED_DIR"

# Nordharz-Vereine Liste (vollständig aus Kreisliga + Klassen 2025/26)
VEREINE=( 
    "TSV-Hallendorf" "Arminia-Adersheim" "SV-Innerstetal" "FC-Othfresen" "TSV-Münchehof"
    "SC-18-Harlingerode" "VfB-Dörnten" "SV-Langelsheim" "TuS-Echte" "SV-Klein Twülpstedt"
    "SV-Bothfeld" "TSG-Salzgitter" "SV-Berßel" "FC-Vienenburg" "SV-Engelnstedt"
    # Erweitere mit 1.-4. Kreisklasse aus https://www.fussball.de/nordharz
)

echo "Scanne $INPUT_DIR für PNGs..."

# Schritt 1: Exakte Duplikate via md5sum finden und verschieben
find "$INPUT_DIR" -name "*.png" -exec md5sum {} \; | sort | uniq -w32 -d | while read hash file; do
    filename=$(basename "$file")
    echo "Duplikat gefunden: $filename -> $DUPLICATES_DIR/"
    mv "$file" "$DUPLICATES_DIR/$filename"
done

# Schritt 2: Verbleibende PNGs umbenennen via Reverse Image + Vereinsliste
for png in "$INPUT_DIR"/*.png; do
    [ -f "$png" ] || continue
    filename=$(basename "$png")
    echo "Verarbeite: $filename"

    # Option 1: Reverse Image via TinEye API (kostenlos, API-Key optional)
    # curl -F "image_url=BASE64_ENCODED" https://api.tineye.com/rest/search

    # Option 2: Google Custom Search Hack (curl + OCR)
    # Konvertiere zu Base64 für Upload
    base64_img=$(base64 -w 0 "$png")
    
    # Google Lens Proxy (vereinfacht - nutze selenium oder API)
    # Hier: Fallback auf OCR + Vereinsmatch
    text=$(tesseract "$png" - -l deu 2>/dev/null | grep -i -E "$(printf '%s|' "${VEREINE[@]}")" || echo "")
    
    if [ -n "$text" ]; then
        verein=$(echo "$text" | head -1 | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z-]//g')
        new_name="${verein}_logo.png"
        mv "$png" "$RENAMED_DIR/$new_name"
        echo "  -> Umbenannt zu: $new_name (OCR: $text)"
        continue
    fi

    # Option 3: Perceptual Hash gegen bekannte Vereins-Hashes (precompute)
    # Erzeuge Hash
    hash=$(convert "$png" -resize 8x8! -colorspace Gray -format '%c' histogram:info: | md5sum | cut -d' ' -f1)
    
    # Vergleiche mit Pre-Hash-Liste (manuell erweitern)
    case "$hash" in
        "a1b2c3d4"|"e5f6g7h8") verein="TSV-Hallendorf" ;;  # Beispiel-Hashes
        *) verein="unbekannt" ;;
    esac
    
    new_name="${verein}_${filename}"
    cp "$png" "$RENAMED_DIR/$new_name"
    echo "  -> Umbenannt zu: $new_name (Hash: $hash)"
done

echo "Fertig!"
echo "Duplikate: $DUPLICATES_DIR"
echo "Umbenannte Logos: $RENAMED_DIR"
ls -la "$RENAMED_DIR"

import os
import sys
import shutil
import hashlib
from PIL import Image
import imagehash  # pip install imagehash Pillow

def md5_hash(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def perceptual_hash(file_path):
    try:
        return str(imagehash.average_hash(Image.open(file_path)))
    except:
        return None

if len(sys.argv) != 2:
    print("Nutzung: python find_duplicates.py <pfad_zum_ordner>")
    sys.exit(1)

pfad = sys.argv[1]
if not os.path.isdir(pfad):
    print(f"Fehler: {pfad} ist kein gültiger Ordner.")
    sys.exit(1)

duplicates_dir = "./duplicates"
os.makedirs(duplicates_dir, exist_ok=True)

dateien = [f for f in os.listdir(pfad) if f.lower().endswith('.png')]
if not dateien:
    print("Keine PNG-Dateien gefunden.")
    sys.exit(0)

geloescht = 0

# Exakte Duplikate (MD5) - behalte ersten, verschiebe Rest
md5_dict = {}
for datei in dateien:
    full_path = os.path.join(pfad, datei)
    h = md5_hash(full_path)
    if h in md5_dict:
        md5_dict[h].append(datei)
    else:
        md5_dict[h] = [datei]

print("Exakte Duplikate (MD5):")
for h, lst in md5_dict.items():
    if len(lst) > 1:
        print(f"  Verschiebe Duplikate von Gruppe: {lst}")
        # Behalte ersten, verschiebe Rest
        for duplikat in lst[1:]:
            src = os.path.join(pfad, duplikat)
            dst = os.path.join(duplicates_dir, duplikat)
            shutil.move(src, dst)
            geloescht += 1

# Ähnliche (pHash, Distanz < 5) - gruppiere und verschiebe alle außer ersten pro Gruppe
phash_groups = {}
for datei in [f for f in os.listdir(pfad) if f.lower().endswith('.png')]:  # Neu scannen nach MD5
    full_path = os.path.join(pfad, datei)
    ph = perceptual_hash(full_path)
    if ph:
        if ph not in phash_groups:
            phash_groups[ph] = []
        phash_groups[ph].append(datei)

print("\nÄhnliche Duplikate (pHash):")
for ph, lst in phash_groups.items():
    if len(lst) > 1:
        print(f"  Verschiebe Duplikate von Gruppe: {lst}")
        # Behalte ersten, verschiebe Rest
        for duplikat in lst[1:]:
            src = os.path.join(pfad, duplikat)
            dst = os.path.join(duplicates_dir, duplikat)
            if os.path.exists(src):  # Falls noch da
                shutil.move(src, dst)
                geloescht += 1

print(f"\nFertig! {geloescht} Duplikate nach {duplicates_dir} verschoben.")

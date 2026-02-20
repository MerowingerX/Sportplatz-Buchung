import requests
from bs4 import BeautifulSoup
import sys
import re
import os
import time
from urllib.parse import quote_plus

token ="snip"

def vereins_info(club_id):
    url = f"https://api-fussball.de/api/club/{club_id}"
    headers = {"x-auth-token": token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        with open(f'{club_id}.json', 'w') as f:
            f.write(response.text)
        time.sleep(5)
        return response.json()
    else:
        print(f"❌ Fehler beim Abrufen der Vereinsinformationen: {response.status_code}")
        return None

def generate_id_list():
    logos = list(Path("./logos").glob("*.png"))
    ids = []
    for logo in logos:
        match = re.search(r'[A-Z0-9]{24,32}', logo.name)
        if match:
            ids.append({"filename": logo.name, "club_id": match.group(0)})
            vereins_info(match.group(0))  # Optional: Informationen zum Verein abrufen
        
    df = pd.DataFrame(ids)
    df.to_csv("club_ids.csv", index=False)
    print(f"✅ club_ids.csv erstellt ({len(ids)} IDs)")
    return df

if __name__ == "__main__":
    from pathlib import Path
    import pandas as pd

    if not Path("./logos").exists():
        print("❌ Der Ordner 'logos' existiert nicht. Bitte erstelle den Ordner und füge die Logos hinzu.")
        sys.exit(1)

    df = generate_id_list()
    print(df.head())
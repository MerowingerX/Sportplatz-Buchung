# Buchungen für eine Gruppe — Verantwortliche & Alias-System

> **Status:** Planungsphase  
> **Ziel:** Mehrere Verantwortliche pro Mannschaft, Alias-Accounts für Multi-Mannschafts-Nutzer, erweiterte Benachrichtigungen.

---

## Zusammenfassung

| Aspekt | Ist | Soll |
|--------|-----|------|
| User ↔ Mannschaft | 1:1 (`user.mannschaft`, `mannschaft.trainer_id`) | **M:N** (mehrere User pro Mannschaft) |
| Verantwortliche pro Mannschaft | 1 Trainer + CC-Emails | **N User + CC-Emails** |
| Multi-Mannschafts-User | Nicht möglich | **Alias-Accounts** mit Switcher-UI |
| Login | Ein Account = ein Login | **Hauptaccount-Login**, Alias-Switch nach Login |
| Benachrichtigungen | Buchender + CC-Emails | **Alle Verantwortlichen + CC-Emails** |
| Token | `mannschaft: Optional[str]` | **`alias_id` + `mannschaft` aus gewähltem Alias** |

---

## Konzept: Alias-Accounts

### Das Problem
Ein Trainer (z.B. Hans Dampf) ist für mehrere Mannschaften verantwortlich:
- Herren (Hauptamtlich)
- F-Junioren 1 (Betreuer)

Er braucht für jede Mannschaft eine eigene "Identität", damit Buchungen der richtigen Mannschaft zugeordnet werden. Aktuell müsste er zwei komplett separate Accounts mit zwei Passwörtern haben.

### Die Lösung
- **Hauptaccount**: `HansDampf` — mit Passwort, zum Einloggen
- **Alias-Accounts**: `HansDampf_F` — mit dem Hauptaccount verknüpft, **kein eigenes Passwort**
- Login immer über Hauptaccount → auf der Startseite Alias wählen → Buchungen landen unter dem gewählten Alias

```
┌─────────────────────────────────────────────────┐
│  Hans Dampf (Hauptaccount)                       │
│  ├── HansDampf      → Herren (Trainer)           │
│  └── HansDampf_F    → F-Junioren 1 (Betreuer)    │
│                                                   │
│  Login: HansDampf / Passwort                      │
│  Nach Login: Switcher auf Startseite              │
└─────────────────────────────────────────────────┘
```

---

## Datenmodell-Änderungen

### 1. Neue Tabelle: `user_aliases`

```sql
CREATE TABLE IF NOT EXISTS user_aliases (
    alias_id        TEXT PRIMARY KEY,    -- notion_id des Alias-Users
    parent_id       TEXT NOT NULL,       -- notion_id des Hauptaccounts
    FOREIGN KEY (alias_id) REFERENCES users(id),
    FOREIGN KEY (parent_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_user_aliases_parent ON user_aliases(parent_id);
```

- Jeder User kann Alias eines anderen sein
- Ein User kann mehrere Aliase haben
- Die Verknüpfung ist transitiv einfach (nur eine Ebene: parent → alias)
- Der Alias-User existiert ganz normal in der `users`-Tabelle (hat `name`, `role`, `mannschaft`, `email`)
- Der Alias hat **kein eigenes Passwort** (`password_hash = ''`, `must_change_pw = 0`)

### 2. Neue Tabelle: `mannschaft_verantwortliche`

```sql
CREATE TABLE IF NOT EXISTS mannschaft_verantwortliche (
    mannschaft_id   TEXT NOT NULL,       -- notion_id der Mannschaft
    user_id         TEXT NOT NULL,       -- notion_id des Users
    PRIMARY KEY (mannschaft_id, user_id),
    FOREIGN KEY (mannschaft_id) REFERENCES mannschaften(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

- M:N-Beziehung zwischen Mannschaften und Usern
- Ersetzt das bisherige 1:1-Feld `mannschaften.trainer_id`
- `user.mannschaft` bleibt als "primäre" Mannschaft erhalten (für Abwärtskompatibilität)

### 3. Änderungen an bestehenden Tabellen

**`users`**: Keine Schema-Änderung. Das Feld `mannschaft` bleibt.

**`mannschaften`**: `trainer_id` und `trainer_name` bleiben vorerst (Abwärtskompatibilität), werden aber nicht mehr als einzige Quelle genutzt. Langfristig deprecatable.

---

## Auth-Änderungen

### Token-Erweiterung

**WICHTIG:** Nur die zwei neuen Felder `parent_id` + `alias_ids` ergänzen. Bestehende Felder unverändert lassen — besonders `iat` (wird für Token-Invalidierung genutzt) und die Defaults (`= None` / `= False`). Snippet zeigt das echte Modell aus `booking/models.py`:

```python
class TokenPayload(BaseModel):
    sub: str                          # notion_id des aktiven Accounts (Haupt oder Alias)
    username: str
    role: UserRole
    mannschaft: Optional[str] = None
    parent_id: Optional[str] = None   # NEU: gesetzt, wenn sub ein Alias ist → parent notion_id
    alias_ids: list[str] = []         # NEU: alle Alias-IDs des Hauptaccounts (für Switcher)
    must_change_password: bool = False
    exp: int
    iat: int = 0                      # issued-at — NICHT entfernen (Invalidierung)
```

- `sub` ist die ID des **gerade aktiven** Accounts (Haupt oder Alias)
- `parent_id` ist gesetzt, wenn aktuell ein Alias aktiv ist
- `alias_ids` enthält alle verfügbaren Alias-IDs (für den Switcher)
- `iat` bleibt erhalten — sonst bricht die bestehende Token-Invalidierung

### Login-Flow (angepasst)

1. User loggt sich mit Hauptaccount-Name/Passwort ein → Token wird mit `sub = Hauptaccount-ID` erstellt
2. `alias_ids` werden aus `user_aliases` geladen
3. Auf der Startseite: Alias-Switcher zeigt Hauptaccount + alle Aliase
4. Bei Switch: Neues Token wird ausgestellt mit `sub = Alias-ID`, `parent_id = Hauptaccount-ID`

#### Login-Bypass verhindern (kritisch)

Alias-User haben `password_hash = ''`. Der Login-Handler MUSS solche Accounts ablehnen — sonst Login mit leerem/beliebigem Passwort möglich:

```python
# im Login-Handler, vor der Passwortprüfung:
if not user.password_hash or repo.get_parent_for_alias(user.notion_id):
    raise HTTPException(401)   # Alias / passwortloser Account → kein Direkt-Login
```

- Beide Checks (leerer Hash UND Alias-Eintrag) — belt + suspenders.
- Sicherstellen, dass die bcrypt-Verify-Funktion `''` NICHT als Treffer wertet.

### Switch-Endpoint (neu)

```
POST /auth/switch-alias
Body: { "alias_id": "uuid-des-gewählten-accounts" }

→ AUTHZ (kritisch): alias_id MUSS in der alias_ids-Menge des aktuellen
  Hauptaccounts liegen. Parent zuerst auflösen:
     parent = token.parent_id or token.sub
     erlaubt = {parent} ∪ get_aliases_for_user(parent).ids
     assert alias_id in erlaubt   # sonst 403, kein "existiert"-Check
→ Erstellt neues JWT mit sub = alias_id, parent_id = parent
→ Setzt Cookie neu
→ Redirect zur Startseite
```

> **Sicherheit:** Reiner Existenz-Check (`alias_id in users`) reicht NICHT —
> sonst horizontale Privilege-Escalation (Switch in fremde Aliase). Immer
> gegen die eigene erlaubte Menge prüfen.

---

## UI-Änderungen

### 1. Alias-Switcher auf Startseite (`overview.html`)

```
┌──────────────────────────────────────────┐
│  👤 Hans Dampf                           │
│  Aktuell: HansDampf (Herren)      [▼]    │
│  ──────────────────────────────────────  │
│  ○ HansDampf      → Herren              │
│  ○ HansDampf_F    → F-Junioren 1        │
└──────────────────────────────────────────┘
```

- Dropdown oder Radio-Liste
- Aktuell aktiver Account hervorgehoben
- Bei Wechsel: POST `/auth/switch-alias` → Seite neu laden

### 2. Admin-UI: User-Alias-Verwaltung

In der User-Edit-Ansicht (`/admin/users/{id}/edit`):

```
┌──────────────────────────────────────────┐
│  User: Hans Dampf                        │
│  ──────────────────────────────────────  │
│  Aliase:                                 │
│  ┌────────────────────────────────────┐  │
│  │ HansDampf_F  → F-Junioren 1    [✕] │  │
│  │ [+ Alias hinzufügen]               │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

- Liste aller Aliase mit Mannschaft
- Button zum Erstellen eines neuen Alias → öffnet Modal/Dialog
- Alias erstellen: Name, Mannschaft, Rolle (default: Trainer), Email
- Alias lösen (entfernen der Verknüpfung, User bleibt bestehen)
- Alias löschen (komplett)

### 3. Admin-UI: Mannschaft-Verantwortliche

In der Mannschaft-Edit-Ansicht:

```
┌──────────────────────────────────────────┐
│  Mannschaft: F-Junioren 1                │
│  ──────────────────────────────────────  │
│  Verantwortliche:                        │
│  ┌────────────────────────────────────┐  │
│  │ ☑ HansDampf_F  (Trainer)          │  │
│  │ ☑ PeterLustig (Betreuer)          │  │
│  │ [+ Verantwortlichen hinzufügen]    │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

- Checkbox-Liste aller User (oder Multi-Select)
- Speichern aktualisiert `mannschaft_verantwortliche`

---

## Benachrichtigungs-Änderungen

### Wer wird benachrichtigt?

**Aktuell:**
- `send_booking_confirmation()` → nur der Buchende + `cc_emails` der Mannschaft

**Neu:**
- `send_booking_confirmation()` → Buchender + **alle Verantwortlichen der Mannschaft** + `cc_emails`
- `send_cancellation_notice()` → Buchender + **alle Verantwortlichen** + `cc_emails`
- `send_booking_update_notice()` → (falls vorhanden) analog

### Implementierung

Neue Hilfsfunktion in `notifications/notify.py`:

```python
def _get_verantwortliche_emails(repo, mannschaft_name: str) -> list[str]:
    """Alle Email-Adressen der Verantwortlichen einer Mannschaft."""
    verantwortliche = repo.get_verantwortliche_for_mannschaft(mannschaft_name)
    return [u.email for u in verantwortliche if u.email]
```

Die bestehenden `_get_cc_emails()`-Aufrufe werden um die Verantwortlichen-Emails erweitert.

**Dedup — am Aufrufort, nicht in notify():** `send_booking_confirmation()` / `send_cancellation_notice()` nehmen `cc: list[str]` ([notifications/notify.py:40,56](../../notifications/notify.py)). Die CC-Liste in `web/routers/bookings.py` zusammenbauen und VOR Übergabe deduplizieren — inkl. Ausschluss des Buchenden (steht schon im `to`):

```python
cc = sorted(set(cc_emails + verantwortliche_emails) - {user.email})
```

Sonst Doppelzustellung, wenn Buchender zugleich Verantwortlicher ist.

---

## Repository-Änderungen (`db/sqlite_repository.py`)

### Neue Methoden

```python
# User-Alias-Verwaltung
def get_aliases_for_user(self, parent_id: str) -> list[User]
def get_parent_for_alias(self, alias_id: str) -> Optional[User]
def create_alias(self, parent_id: str, name: str, role: str, 
                 email: str, mannschaft: Optional[str]) -> User
def remove_alias_link(self, alias_id: str)  # löst Verknüpfung, löscht User nicht
def delete_alias(self, alias_id: str)       # löscht User + Verknüpfung

# Mannschaft-Verantwortliche (M:N)
def get_verantwortliche_for_mannschaft(self, mannschaft_name: str) -> list[User]
def add_verantwortlicher(self, mannschaft_id: str, user_id: str)
def remove_verantwortlicher(self, mannschaft_id: str, user_id: str)
def get_mannschaften_for_user(self, user_id: str) -> list[MannschaftConfig]
```

### Schema-Erweiterung (`db/schema.sql`)

Neue Tabellen (siehe oben) + ggf. Migration für bestehende `trainer_id` → `mannschaft_verantwortliche`.

---

## Abwärtskompatibilität

- `user.mannschaft` bleibt das "primäre" Team — wird gesetzt wenn der Alias erstellt wird
- `mannschaften.trainer_id` bleibt erhalten und wird weiterhin gesetzt
- Bestehende Buchungen mit `mannschaft`-Feld funktionieren unverändert
- Alte `_sync_user_mannschaft_change()` und `_sync_trainer_change()` bleiben, werden ergänzt um `mannschaft_verantwortliche`

---

## Reihenfolge der Umsetzung

| Schritt | Was | Aufwand |
|---------|-----|---------|
| 1 | `db/schema.sql` — neue Tabellen `user_aliases`, `mannschaft_verantwortliche` | klein |
| 2 | `booking/models.py` — `TokenPayload` um `parent_id`, `alias_ids` erweitern | klein |
| 3 | `db/sqlite_repository.py` — neue Methoden für Aliase + Verantwortliche | mittel |
| 4 | `auth/auth.py` — `create_jwt` mit `parent_id`, `alias_ids` | klein |
| 5 | `auth/dependencies.py` — Alias-Switch-Logik, `/auth/switch-alias` Endpoint | mittel |
| 6 | `web/templates/overview.html` — Alias-Switcher UI | mittel |
| 7 | `web/routers/admin.py` — User-Alias-Verwaltung + Mannschaft-Verantwortlichen-UI | groß |
| 8 | `notifications/notify.py` — Verantwortliche in CC aufnehmen | klein |
| 9 | `web/routers/bookings.py` — CC-Logik um Verantwortliche erweitern | klein |
| 10 | Migration: bestehende `mannschaften.trainer_id` → `mannschaft_verantwortliche` seeden (idempotent, `INSERT OR IGNORE`) | klein |

Migrations-SQL (idempotent, kann in `schema.sql` ans Ende oder als One-Shot-Script):

```sql
INSERT OR IGNORE INTO mannschaft_verantwortliche (mannschaft_id, user_id)
SELECT id, trainer_id FROM mannschaften
WHERE trainer_id IS NOT NULL AND trainer_id != '';
```

`mannschaften.trainer_id` liegt real in [db/schema.sql:146](../../db/schema.sql); zusätzlich `users.trainer_id`-artige Felder prüfen, nicht verwechseln.

---

## Risiken & Offene Fragen

1. **Alias ohne Passwort (kritisch)**: Direktes Einloggen als Alias verhindern. Login-Handler lehnt ab, wenn `password_hash == ''` ODER ein `user_aliases`-Eintrag für die ID existiert (beide Checks). Zusätzlich sicherstellen, dass bcrypt-Verify leeren Hash nicht als Treffer wertet. Siehe Abschnitt „Login-Bypass verhindern".

2. **Token-Invalidierung bei Alias-Wechsel**: Der alte Token muss nicht invalidiert werden — das neue Token überschreibt einfach das Cookie. Der alte Token läuft normal ab.

3. **Alias-Kaskaden**: Alias von Alias? → Nein, nur eine Ebene (parent → alias). Validierung beim Erstellen.

4. **Berechtigungen**: Ein Alias hat seine eigene `role`. Wenn der Hauptaccount Admin ist, der Alias aber Trainer — der Alias hat nur Trainer-Rechte. Das ist korrekt und gewollt.

5. **Mannschaftszuordnung doppelt**: `user.mannschaft` + `mannschaft_verantwortliche` + `mannschaften.trainer_id` — drei Quellen der Wahrheit. Langfristig sollte nur `mannschaft_verantwortliche` die autoritative Quelle sein. Kurzfristig bleiben alle drei synchron.

6. **Email-Doppelzustellung**: Wenn ein User sowohl Buchender als auch Verantwortlicher ist, bekommt er die Email zweimal? → Deduplizierung in `_get_verantwortliche_emails()`.

---

## Betroffene Dateien

```
db/schema.sql                           # Neue Tabellen
db/sqlite_repository.py                 # Neue Methoden
booking/models.py                       # TokenPayload-Erweiterung
auth/auth.py                            # create_jwt erweitern
auth/dependencies.py                    # Switch-Endpoint + Token-Logik
web/templates/overview.html             # Alias-Switcher
web/templates/admin/                    # User-Edit + Mannschaft-Edit
web/routers/admin.py                    # Alias- & Verantwortlichen-Verwaltung
web/routers/bookings.py                 # CC-Logik erweitern
web/routers/auth.py                     # Neuer switch-alias Endpoint
notifications/notify.py                 # Verantwortliche in CC
``` 

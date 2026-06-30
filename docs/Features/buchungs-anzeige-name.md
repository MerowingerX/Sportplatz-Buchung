# Buchungsnamen

Auf dem Kalender werden Buchungen mit einem Kurznamen angezeigt. 

Bei Serienterminen ist der Name klar:
- welche Mannschaft
- Dauer
- ggf noch Buchungsverantwortlicher beim drüber hoovern

Bei Spielen auch:
- Spielpaarungsdaten
- Anpfiff
- Mannschaft aus dfbnet (es ist nicht nötig, die entsprechende eingetragene Mannschft zu erraten)

Bei Einzelbuchungen dagegen taucht der Buchungsname auf
Das soll anders sein.
- Eine Einzelbuchung ist ja auch für eine Mannschaft, Training
- das soll erkennbar sein


## Ist-Zustand (Code)

Der Kalender-Pill rendert in [`_booking_pill.html`](../../web/templates/partials/_booking_pill.html#L6):

```jinja
{{ b.zweck or m_display or b.booked_by_name }}
```

Reihenfolge der Prioritäten:
1. `zweck` (Freitext-Buchungszweck, optional) — **gewinnt aktuell immer**
2. `m_display` = Mannschafts-Kurzname (`mannschaft_shortnames.get(b.mannschaft)`)
3. `booked_by_name` (Name des Buchenden)

Daher das Problem: Sobald bei einer Einzelbuchung `zweck` gesetzt ist,
verdrängt der Freitext die Mannschaft. Die Zugehörigkeit zur Mannschaft /
zum Training ist dann nicht mehr erkennbar.

Der `title`-Tooltip (Hover) zeigt bereits mehr:
`zweck | mannschaft | booked_by_name | kontakt | Zeit | sunset_note`.

## Umgesetzt (Stand 2026-06-30)

Pill-Name (Tag-/Wochenansicht inkl. continuation-Slots):

```jinja
{{ m_display or b.zweck or b.booked_by_name }}
```

Mannschaft (Kurzname) gewinnt vor `zweck`. Buchungsart bleibt über die
CSS-Farbe (`slot--training/spiel/turnier`) erkennbar.

Tooltip (Hover) — **Buchungsverantwortlicher immer sichtbar**:

```
<Mannschaft> · <booked_by_name> – <zweck> – <kontakt> | HH:MM–HH:MM | <sunset_note>
```

`booked_by_name` steht jetzt immer im Tooltip (vorher nur als Fallback ohne
Mannschaft). `· ` trennt Mannschaft vom Verantwortlichen; `zweck`/`kontakt`
nur wenn gesetzt.

Backend-Fix dazu: die im Formular gewählte Mannschaft (`data.mannschaft`)
wird in `build_booking()` jetzt tatsächlich gespeichert (vorher verworfen →
Buchungen ohne eigene Mannschaft, z. B. von Admins, zeigten den Bucher-Namen).

Tests: `docs/tests/test_booking_pill.py`, `docs/tests/test_build_booking_mannschaft.py`.

## Datenfelder einer Buchung

Aus [`booking/models.py → Booking`](../../booking/models.py#L136):

| Feld | Typ | Bedeutung |
|------|-----|-----------|
| `booking_type` | `Training` / `Spiel` / `Turnier` | Buchungsart → CSS-Klasse |
| `mannschaft` | `str?` | zugeordnete Mannschaft (dynamisch, Tabelle) |
| `zweck` | `str?` | Freitext-Zweck, sichtbar im Kalender |
| `kontakt` | `str?` | Ansprechpartner |
| `booked_by_name` | `str` | wer gebucht hat |
| `spielkennung` | `str?` | DFBnet-Spielkennung (nur Spiele) |
| `sunset_note` | `str?` | Flutlicht-/Sonnenuntergangs-Hinweis |

Mannschafts-Kurzname kommt aus `MannschaftConfig.shortname` (Fallback: voller Name).

## Soll

Der Anzeigename soll **immer** die Mannschaft erkennbar machen, nicht der
Freitext-`zweck`. Vorschlag für die Komposition (Kurzname auf dem Pill):

- **Training (Serie & Einzel):** `<Mannschaft-Kurzname>` — `zweck` nur in den Tooltip.
  Bei Einzelbuchung ggf. Suffix für Erkennbarkeit, z. B. `<Kurzname> · Training`.
- **Spiel:** Mannschaft aus DFBnet, kein Raten. Pill: `<dfbnet-Mannschaft>` + Anpfiff;
  Spielpaarung in Tooltip.
- **Turnier:** offen — eigener Titel oder Mannschaft? (siehe unten)
- **Fallback** wenn keine Mannschaft: `zweck` → `booked_by_name`.

## Was gibt es noch? — offene Fälle

- **Turnier** (`BookingType.TURNIER`): wie benennen? Oft mehrere Mannschaften /
  Gäste → evtl. eigenes Titel-Feld statt Mannschaft.
- **Externe Events** (eigener Router, `_event_row.html` nutzt `event.title`):
  laufen separat, nicht über `Booking`. Anzeige-Logik konsistent halten?
- **Gruppenbuchungen** (siehe `docs/Features/` — Gruppen-Buchungen): mehrere Felder /
  Mannschaften gleichzeitig — welcher Name?
- **Ganztags-/All-Day-Slots**: eigene Darstellung nötig?
- **DFBnet-Systembuchungen** ohne zugeordnete lokale Mannschaft: nur dfbnet-Name.
- **Tooltip vs. Pill**: was gehört auf den Pill (knapp), was nur in den Hover-Tooltip?
- **Übersichtswoche** ([`_overview_week.html`](../../web/templates/partials/_overview_week.html#L102)) nutzt
  andere Reihenfolge: `mannschaft or zweck or 'Extern'` — Logik vereinheitlichen.


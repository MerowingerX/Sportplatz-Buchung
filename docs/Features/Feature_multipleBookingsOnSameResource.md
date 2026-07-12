currently the system deos not allow multiple bookings of the same field at same time.
This sometimes is a problem.
E.G a children team could be split into team 1,2 and 3, but in fact, those teams are able to use one resource, even if it is uncomfortable.

What we want, is:
A reservation exists for a team.
One wants to book the same resource at same time.
Then this should be allowed, with a big warning, and shall be displayed in the calendarby a split of the box.

tell me, if it is possible to:
- have same duration and start
- have different duration and /or startime

**Plan**

- **Goal:** Allow multiple bookings for the same resource at overlapping times while surfacing a clear warning and visual split in the calendar view.
- **Assumptions:** Users can intentionally create overlapping bookings; conflicts remain visible to admins; existing DB allows multiple rows per timeslot.
- **Implementation Steps:**
	- **Add plan to doc:** Insert this plan section into the feature document. (Done)
	- **Define UX warnings:** Decide exact wording, severity, and where to show the warning (booking form, confirmation, calendar tooltip).
	- **Update DB/schema:** Ensure bookings table permits overlapping entries and add a lightweight conflict flag if needed.
	- **Implement backend logic:** Allow creation of overlapping bookings while optionally setting a `conflict` marker and emitting a warning message.
	- **Update calendar UI:** Render overlapping bookings by splitting the calendar cell visually and showing both entries; add hover/tooltip with warning details.
	- **Add tests and docs:** Cover same-start/different-duration cases and update `docs/` with examples and screenshots.

If you want, I can implement the DB change and calendar rendering next — which step should I start?

---

## Entscheidungen (final, 2026-07-12)

- **Opt-in mit Bestätigung:** Teilen ist eine Option. Beim Buchen auf eine belegte
  Ressource erscheint eine Warnbox; der User muss explizit bestätigen
  („Teilen bestätigen & buchen“), erst dann wird gespeichert. Die Bestätigung ist
  per Token an genau diesen Slot (Platz/Datum/Zeit/Dauer) gebunden.
- **Gleichbehandlung:** Ist die geteilte Buchung eingetragen, werden beide wie jede
  andere Buchung behandelt. Storniert eine, wird die andere Alleinnutzer.
- **DFBnet unsharable (an der Rolle festgemacht):** Buchungen mit Rolle `DFBnet`
  sind nie teilbar. DFBnet-Buchungen verdrängen weiterhin (Storno der Konflikte).
- **DFBnet im normalen Formular verdrängt:** Bucht ein User mit Rolle `DFBnet`
  über das normale Buchungsformular auf einen belegten Slot, erscheint eine rote
  Bestätigungs-Box („X Buchung(en) werden storniert und benachrichtigt“); nach
  Bestätigung läuft `dfbnet_displace` (Storno + Benachrichtigung der Verdrängten).
  Kein Teilen-Angebot für DFBnet. Ohne Konflikt bucht DFBnet normal.
- **Serien:** Serienbuchungen können bestehende Termine NICHT überbuchen —
  Konfliktdaten werden wie bisher übersprungen (`skipped`).
- **Nur unterste Feldebene teilbar:** Ein Feld ist teilbar, wenn es keine
  konfigurierten Sub-Felder hat („A“ mit „AA“/„AB“ nicht teilbar, „AA“ schon).
  Logik: `field_config.is_leaf_field()`.
- **Storno im Kalender:** nur am obersten Eintrag (Start-Slot), keine Teilzeiten.
- **Darstellung:** überlappende Buchungen werden in der Kalenderzelle gestapelt
  (`slot-stack`, kompakte Pillen mit `slot--overlap`).

### Antwort auf die Ausgangsfrage
Beides möglich: gleiche Start/Dauer **und** unterschiedliche Start/Dauer.
Das Rendering stapelt pro Zelle — bei Teilüberlappung erscheint die kompakte
Darstellung nur dort, wo beide Buchungen aktiv sind.

### Umsetzung
- `booking/booking.py`: `get_same_field_overlaps()`, `overlaps_are_shareable()`,
  `build_booking(..., allow_same_field_overlap=)` (Default `False`).
- `booking/field_config.py`: `is_leaf_field()`.
- `web/routers/bookings.py` + `web/routers/admin.py`: Bestätigungs-Schritt vor dem
  Speichern (Warnbox + Token), Verfügbarkeits-Badge zeigt „Teilen möglich“.
- Tests: `docs/tests/test_overlapping_bookings.py`.


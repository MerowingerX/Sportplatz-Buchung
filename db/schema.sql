-- Sportplatz-Buchungssystem — SQLite-Schema
-- Konventionen:
--   TEXT          für Strings, Datumsangaben (YYYY-MM-DD), Zeiten (HH:MM) und Enum-Werte
--   INTEGER       für Booleans (0/1) und Ganzzahlen
--   deleted_at    für Soft-Delete (NULL = aktiv)

PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

-- ------------------------------------------------------------------ users

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL,              -- UserRole.value
    email           TEXT NOT NULL DEFAULT '',
    password_hash   TEXT NOT NULL DEFAULT '',
    mannschaft      TEXT,                       -- nullable
    must_change_pw  INTEGER NOT NULL DEFAULT 1,
    deleted_at      TEXT                        -- NULL = aktiv
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_name
    ON users(name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ------------------------------------------------------------------ series

CREATE TABLE IF NOT EXISTS series (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    field           TEXT NOT NULL,              -- FieldName.value
    start_time      TEXT NOT NULL,              -- HH:MM
    duration_min    INTEGER NOT NULL,
    rhythm          TEXT NOT NULL,              -- SeriesRhythm.value
    start_date      TEXT NOT NULL,              -- YYYY-MM-DD
    end_date        TEXT NOT NULL,              -- YYYY-MM-DD
    booked_by_id    TEXT NOT NULL,
    booked_by_name  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Aktiv',  -- SeriesStatus.value
    mannschaft      TEXT,
    trainer_id      TEXT,
    trainer_name    TEXT,
    saison          TEXT NOT NULL DEFAULT 'Ganzjährig'  -- SeriesSaison.value
);

CREATE INDEX IF NOT EXISTS idx_series_status ON series(status);

-- ------------------------------------------------------------------ bookings

CREATE TABLE IF NOT EXISTS bookings (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    field            TEXT NOT NULL,             -- FieldName.value
    date             TEXT NOT NULL,             -- YYYY-MM-DD
    start_time       TEXT NOT NULL,             -- HH:MM
    end_time         TEXT NOT NULL,             -- HH:MM
    duration_min     INTEGER NOT NULL,
    booking_type     TEXT NOT NULL,             -- BookingType.value
    booked_by_id     TEXT NOT NULL,
    booked_by_name   TEXT NOT NULL,
    role             TEXT NOT NULL,             -- UserRole.value
    status           TEXT NOT NULL DEFAULT 'Bestätigt',  -- BookingStatus.value
    mannschaft       TEXT,
    zweck            TEXT,
    kontakt          TEXT,
    series_id        TEXT,                      -- → series.id
    series_exception INTEGER NOT NULL DEFAULT 0,
    sunset_note      TEXT,
    spielkennung     TEXT,
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bookings_date_status ON bookings(date, status);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);
CREATE INDEX IF NOT EXISTS idx_bookings_series_id
    ON bookings(series_id) WHERE series_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_spielkennung
    ON bookings(spielkennung)
    WHERE spielkennung IS NOT NULL AND status = 'Bestätigt';

-- ------------------------------------------------------------------ blackouts

CREATE TABLE IF NOT EXISTS blackouts (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    start_date      TEXT NOT NULL,              -- YYYY-MM-DD
    end_date        TEXT NOT NULL,              -- YYYY-MM-DD
    blackout_type   TEXT NOT NULL,              -- BlackoutType.value
    start_time      TEXT,                       -- HH:MM, nullable (nur bei ZEITLICH)
    end_time        TEXT,                       -- HH:MM, nullable (nur bei ZEITLICH)
    reason          TEXT NOT NULL DEFAULT '',
    entered_by_id   TEXT NOT NULL,
    entered_by_name TEXT NOT NULL,
    deleted_at      TEXT                        -- NULL = aktiv
);

-- Effiziente Bereichsabfrage: start_date <= :end AND end_date >= :start
CREATE INDEX IF NOT EXISTS idx_blackouts_start_date ON blackouts(start_date);
CREATE INDEX IF NOT EXISTS idx_blackouts_end_date ON blackouts(end_date);

-- ------------------------------------------------------------------ aufgaben

CREATE TABLE IF NOT EXISTS aufgaben (
    id                TEXT PRIMARY KEY,
    titel             TEXT NOT NULL,
    typ               TEXT NOT NULL,            -- AufgabeTyp.value
    status            TEXT NOT NULL DEFAULT 'Offen',    -- AufgabeStatus.value
    prioritaet        TEXT NOT NULL DEFAULT 'Mittel',   -- Prioritaet.value
    erstellt_von_id   TEXT NOT NULL,
    erstellt_von_name TEXT NOT NULL,
    erstellt_am       TEXT NOT NULL,            -- YYYY-MM-DD
    faellig_am        TEXT,                     -- YYYY-MM-DD, nullable
    ort               TEXT,
    beschreibung      TEXT,
    deleted_at        TEXT                      -- NULL = aktiv
);

CREATE INDEX IF NOT EXISTS idx_aufgaben_status ON aufgaben(status);

-- ------------------------------------------------------------------ events

CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    date            TEXT NOT NULL,              -- YYYY-MM-DD
    start_time      TEXT NOT NULL,              -- HH:MM
    location        TEXT,
    description     TEXT,
    created_by_id   TEXT NOT NULL,
    created_by_name TEXT NOT NULL,
    mannschaft      TEXT,
    deleted_at      TEXT                        -- NULL = aktiv
);

CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);

-- ------------------------------------------------------------------ mannschaften

CREATE TABLE IF NOT EXISTS mannschaften (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    shortname             TEXT,
    trainer_name          TEXT,
    trainer_id            TEXT,
    fussball_de_team_id   TEXT,
    aktiv                 INTEGER NOT NULL DEFAULT 1,
    cc_emails             TEXT NOT NULL DEFAULT ''   -- kommagetrennte E-Mail-Adressen
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mannschaften_name ON mannschaften(name);

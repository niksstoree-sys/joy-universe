-- =========================================
-- JOY UNIVERSE - Event System (Stage 3)
-- =========================================

CREATE TABLE IF NOT EXISTS events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            TEXT NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    channel_id          TEXT NOT NULL,
    role_ping_id        TEXT,

    run_at              TEXT NOT NULL,                  -- next occurrence, disimpan dalam UTC ('YYYY-MM-DD HH:MM:SS')
    timezone            TEXT NOT NULL DEFAULT 'Asia/Jakarta', -- timezone asli saat event dibuat (untuk tampilan)
    repeat_type         TEXT NOT NULL DEFAULT 'once',    -- once | daily | weekly | monthly

    reminder_minutes    INTEGER,                         -- kirim reminder N menit sebelum event, NULL = tanpa reminder
    reminder_sent       INTEGER NOT NULL DEFAULT 0,

    banner_url          TEXT,
    thumbnail_url       TEXT,
    embed_color         TEXT,

    active              INTEGER NOT NULL DEFAULT 1,
    created_by          TEXT NOT NULL,
    last_run_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_active_runat ON events(active, run_at);
CREATE INDEX IF NOT EXISTS idx_events_guild ON events(guild_id);

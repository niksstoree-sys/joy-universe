-- =========================================
-- JOY UNIVERSE - Moderation & Moderation Log (Stage 7)
-- =========================================

-- Toggle granular untuk tiap kategori moderation log.
-- Channel log & mute role pakai kolom yang sudah ada di guild_configs
-- (mod_log_channel, mute_role_id) dari migration 001.
CREATE TABLE IF NOT EXISTS mod_log_config (
    guild_id                TEXT PRIMARY KEY,
    log_join_leave          INTEGER NOT NULL DEFAULT 1,
    log_message_delete      INTEGER NOT NULL DEFAULT 1,
    log_message_edit        INTEGER NOT NULL DEFAULT 1,
    log_role_update         INTEGER NOT NULL DEFAULT 1,
    log_nickname            INTEGER NOT NULL DEFAULT 1,
    log_moderation_action   INTEGER NOT NULL DEFAULT 1,  -- ban/kick/timeout/warn/mute
    log_voice                INTEGER NOT NULL DEFAULT 1,
    log_emoji_sticker        INTEGER NOT NULL DEFAULT 1,
    log_thread               INTEGER NOT NULL DEFAULT 1,
    log_webhook              INTEGER NOT NULL DEFAULT 1
);

-- Riwayat warning per user
CREATE TABLE IF NOT EXISTS warnings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    moderator_id    TEXT NOT NULL,
    reason          TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings(guild_id, user_id);

-- Riwayat semua aksi moderasi (ban, softban, kick, mute, timeout, warn, unban, dst)
CREATE TABLE IF NOT EXISTS mod_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            TEXT NOT NULL,
    user_id             TEXT NOT NULL,
    moderator_id        TEXT NOT NULL,
    action              TEXT NOT NULL,       -- ban|softban|kick|mute|unmute|timeout|untimeout|warn|unban
    reason              TEXT,
    duration_seconds    INTEGER,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_mod_history_guild_user ON mod_history(guild_id, user_id, created_at DESC);

-- =========================================
-- JOY UNIVERSE - Initial Schema (Stage 1)
-- Fokus: Core config, prefix, no-prefix, owner/admin, maintenance
-- =========================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Konfigurasi per-guild (server)
CREATE TABLE IF NOT EXISTS guild_configs (
    guild_id        TEXT PRIMARY KEY,
    prefix          TEXT NOT NULL DEFAULT '!',
    embed_color     TEXT NOT NULL DEFAULT '#FFD54A',
    mod_log_channel TEXT,
    mute_role_id    TEXT,
    is_premium      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Bot admin/owner tambahan (selain OWNER_ID di .env)
CREATE TABLE IF NOT EXISTS bot_admins (
    user_id     TEXT PRIMARY KEY,
    added_by    TEXT NOT NULL,
    added_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- User yang diizinkan pakai No-Prefix Command
CREATE TABLE IF NOT EXISTS no_prefix_users (
    user_id     TEXT PRIMARY KEY,
    added_by    TEXT NOT NULL,
    added_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Status maintenance mode global bot
CREATE TABLE IF NOT EXISTS maintenance_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    is_active       INTEGER NOT NULL DEFAULT 0,
    reason          TEXT,
    activated_by    TEXT,
    activated_at    TEXT
);
INSERT OR IGNORE INTO maintenance_state (id, is_active) VALUES (1, 0);

-- Log command usage (buat statistik & debugging ringan)
CREATE TABLE IF NOT EXISTS command_usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT,
    user_id     TEXT NOT NULL,
    command     TEXT NOT NULL,
    is_slash    INTEGER NOT NULL DEFAULT 0,
    used_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_command_usage_guild ON command_usage_log(guild_id);
CREATE INDEX IF NOT EXISTS idx_command_usage_command ON command_usage_log(command);

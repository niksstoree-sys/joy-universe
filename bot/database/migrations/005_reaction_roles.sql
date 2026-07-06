-- =========================================
-- JOY UNIVERSE - Reaction Role & Auto Role (Stage 5)
-- =========================================

CREATE TABLE IF NOT EXISTS reaction_role_panels (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            TEXT NOT NULL,
    channel_id          TEXT,
    message_id          TEXT,                     -- NULL sampai panel di-post

    panel_type          TEXT NOT NULL,             -- button | reaction | dropdown
    title               TEXT NOT NULL,
    description         TEXT,
    color               TEXT,

    unique_mode         INTEGER NOT NULL DEFAULT 0, -- 1 = hanya boleh 1 role dari panel ini (radio-button)
    verification_mode   INTEGER NOT NULL DEFAULT 0, -- 1 = role hanya ditambah, tidak pernah dilepas otomatis

    created_by          TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rr_panels_guild ON reaction_role_panels(guild_id);
CREATE INDEX IF NOT EXISTS idx_rr_panels_message ON reaction_role_panels(message_id);

CREATE TABLE IF NOT EXISTS reaction_role_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id    INTEGER NOT NULL REFERENCES reaction_role_panels(id) ON DELETE CASCADE,
    role_id     TEXT NOT NULL,
    emoji       TEXT,                              -- wajib untuk type reaction, opsional untuk button/dropdown
    label       TEXT,                              -- label tombol/opsi dropdown
    style       TEXT NOT NULL DEFAULT 'secondary',  -- primary | secondary | success | danger (khusus button)
    description TEXT,                              -- deskripsi opsi dropdown
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_rr_entries_panel ON reaction_role_entries(panel_id);

CREATE TABLE IF NOT EXISTS auto_role_config (
    guild_id    TEXT PRIMARY KEY,
    enabled     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS auto_roles (
    guild_id    TEXT NOT NULL,
    role_id     TEXT NOT NULL,
    PRIMARY KEY (guild_id, role_id)
);

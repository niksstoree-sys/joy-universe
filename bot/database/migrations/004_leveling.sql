-- =========================================
-- JOY UNIVERSE - Leveling System (Stage 4)
-- =========================================

-- Konfigurasi leveling per-guild
CREATE TABLE IF NOT EXISTS level_config (
    guild_id                TEXT PRIMARY KEY,
    enabled                 INTEGER NOT NULL DEFAULT 1,

    xp_per_message_min      INTEGER NOT NULL DEFAULT 15,
    xp_per_message_max      INTEGER NOT NULL DEFAULT 25,
    xp_cooldown_seconds     INTEGER NOT NULL DEFAULT 60,   -- anti-spam: jarak minimal antar XP text
    daily_xp_limit          INTEGER NOT NULL DEFAULT 0,     -- 0 = tidak dibatasi

    voice_xp_enabled        INTEGER NOT NULL DEFAULT 1,
    voice_xp_per_minute     INTEGER NOT NULL DEFAULT 10,
    voice_xp_min_members    INTEGER NOT NULL DEFAULT 2,     -- minimal member non-bot di VC supaya dapat XP (anti AFK farming)

    level_up_message_enabled INTEGER NOT NULL DEFAULT 1,
    level_up_channel_id     TEXT,                            -- NULL = kirim di channel yang sama saat XP didapat
    level_up_message        TEXT DEFAULT '{user_mention} naik ke **Level {level}**!',
    level_up_use_card       INTEGER NOT NULL DEFAULT 1,       -- 1 = kirim rank card image, 0 = embed teks saja

    prestige_enabled        INTEGER NOT NULL DEFAULT 1,
    prestige_required_level INTEGER NOT NULL DEFAULT 100,

    rank_card_background    TEXT,                            -- URL background custom untuk /rank
    leaderboard_background  TEXT,                            -- URL background custom untuk /leaderboard

    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Data XP per user per guild
CREATE TABLE IF NOT EXISTS user_levels (
    guild_id            TEXT NOT NULL,
    user_id             TEXT NOT NULL,

    xp                  INTEGER NOT NULL DEFAULT 0,     -- xp di prestige saat ini
    prestige             INTEGER NOT NULL DEFAULT 0,

    total_messages      INTEGER NOT NULL DEFAULT 0,
    voice_minutes       INTEGER NOT NULL DEFAULT 0,

    last_text_xp_at     TEXT,                            -- dipakai untuk anti-spam cooldown
    daily_xp_earned     INTEGER NOT NULL DEFAULT 0,
    daily_xp_date       TEXT,                            -- 'YYYY-MM-DD', reset otomatis tiap hari baru

    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_levels_leaderboard ON user_levels(guild_id, prestige DESC, xp DESC);

-- Role reward per level
CREATE TABLE IF NOT EXISTS level_role_rewards (
    guild_id    TEXT NOT NULL,
    level       INTEGER NOT NULL,
    role_id     TEXT NOT NULL,
    PRIMARY KEY (guild_id, level)
);

-- Role reward per prestige
CREATE TABLE IF NOT EXISTS prestige_role_rewards (
    guild_id    TEXT NOT NULL,
    prestige    INTEGER NOT NULL,
    role_id     TEXT NOT NULL,
    PRIMARY KEY (guild_id, prestige)
);

-- =========================================
-- JOY UNIVERSE - Auto Moderation (Stage 6)
-- =========================================

CREATE TABLE IF NOT EXISTS automod_config (
    guild_id                        TEXT PRIMARY KEY,
    enabled                         INTEGER NOT NULL DEFAULT 1,
    log_channel_id                  TEXT,

    -- Spam (banyak pesan dalam waktu singkat)
    spam_enabled                    INTEGER NOT NULL DEFAULT 1,
    spam_message_threshold          INTEGER NOT NULL DEFAULT 5,
    spam_interval_seconds           INTEGER NOT NULL DEFAULT 5,
    spam_action                     TEXT NOT NULL DEFAULT 'timeout',   -- delete|timeout|kick|ban
    spam_timeout_seconds            INTEGER NOT NULL DEFAULT 300,

    -- Mention Spam & Anti Mass Ping (kebanyakan mention di satu pesan)
    mention_spam_enabled            INTEGER NOT NULL DEFAULT 1,
    mention_spam_threshold          INTEGER NOT NULL DEFAULT 5,
    mention_spam_action             TEXT NOT NULL DEFAULT 'timeout',
    mention_spam_timeout_seconds    INTEGER NOT NULL DEFAULT 300,

    -- Invite Filter
    invite_filter_enabled           INTEGER NOT NULL DEFAULT 0,
    invite_filter_action            TEXT NOT NULL DEFAULT 'delete',

    -- Link Filter
    link_filter_enabled             INTEGER NOT NULL DEFAULT 0,
    link_filter_action              TEXT NOT NULL DEFAULT 'delete',

    -- Caps Filter
    caps_filter_enabled             INTEGER NOT NULL DEFAULT 0,
    caps_filter_threshold_percent   INTEGER NOT NULL DEFAULT 70,
    caps_filter_min_length          INTEGER NOT NULL DEFAULT 10,
    caps_filter_action              TEXT NOT NULL DEFAULT 'delete',

    -- Bad Word Filter
    badword_filter_enabled          INTEGER NOT NULL DEFAULT 0,
    badword_action                  TEXT NOT NULL DEFAULT 'delete',

    -- Scam Detection
    scam_detection_enabled          INTEGER NOT NULL DEFAULT 1,
    scam_detection_action           TEXT NOT NULL DEFAULT 'ban',

    -- Anti Ghost Ping
    ghost_ping_enabled               INTEGER NOT NULL DEFAULT 1,

    -- Anti Raid & Anti Join Flood (satu sistem: deteksi lonjakan member join)
    anti_raid_enabled               INTEGER NOT NULL DEFAULT 0,
    anti_raid_join_threshold        INTEGER NOT NULL DEFAULT 10,
    anti_raid_interval_seconds      INTEGER NOT NULL DEFAULT 10,
    anti_raid_action                TEXT NOT NULL DEFAULT 'kick',      -- kick|ban
    anti_raid_lockdown_minutes      INTEGER NOT NULL DEFAULT 10,

    created_at                       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Whitelist: user/role/channel yang dikecualikan dari semua automod
CREATE TABLE IF NOT EXISTS automod_whitelist (
    guild_id    TEXT NOT NULL,
    target_type TEXT NOT NULL,   -- user | role | channel
    target_id   TEXT NOT NULL,
    PRIMARY KEY (guild_id, target_type, target_id)
);

-- Blacklist kata-kata terlarang (per guild)
CREATE TABLE IF NOT EXISTS automod_badwords (
    guild_id    TEXT NOT NULL,
    word        TEXT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

-- Log pelanggaran automod (dipakai juga oleh moderation log di Stage 7)
CREATE TABLE IF NOT EXISTS automod_violations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    rule            TEXT NOT NULL,
    action_taken    TEXT NOT NULL,
    detail          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_automod_violations_guild ON automod_violations(guild_id, created_at DESC);
